import pytest

from backend.auth import service as auth_service
from backend.errors import ApiError
from backend.extensions import db
from backend.models.user import User
from backend.services import cache as cache_service
from backend.services.scans import get_flat_filters


def _analysis():
    return {
        "price": {"last": 100, "volume": 1_500_000},
        "indicators": {
            "rsi": 25,
            "stochastic": {"k": 15},
            "ema": {"ema_50": 110, "ema_200": 100},
            "sma": {"sma_200": 90},
            "macd": {"line": 1.5, "signal": 0.8},
            "bollinger_bands": {"lower": 99, "upper": 130},
        },
        "patterns": {
            "candlestick": [{"pattern": "Hammer", "type": "bullish"}],
            "chart": [{"pattern": "Double Bottom", "type": "bullish"}],
        },
        "fibonacci": {
            "nearest_support": 99,
            "nearest_resistance": 102,
            "price_zone": "golden_zone",
            "trend": "uptrend",
            "zones": [{"mid": 100.5, "strength": 2}],
        },
    }


def test_filter_logic_matches_expected_conditions():
    filters = get_flat_filters()
    analysis = _analysis()

    assert filters["rsi_oversold"]["check"](analysis)
    assert filters["stoch_oversold"]["check"](analysis)
    assert filters["ema_golden_cross"]["check"](analysis)
    assert filters["price_above_sma200"]["check"](analysis)
    assert filters["macd_bullish"]["check"](analysis)
    assert filters["bb_squeeze"]["check"](analysis)
    assert filters["bullish_pattern"]["check"](analysis)
    assert filters["chart_pattern_bullish"]["check"](analysis)
    assert filters["near_fib_support"]["check"](analysis)
    assert filters["fib_golden_zone"]["check"](analysis)
    assert filters["fib_confluence_zone"]["check"](analysis)

    assert not filters["rsi_overbought"]["check"](analysis)
    assert not filters["macd_bearish"]["check"](analysis)


def test_cache_get_honors_entry_ttl(monkeypatch):
    current_time = [1_000.0]

    monkeypatch.setattr(cache_service, "get_redis_client", lambda: None)
    monkeypatch.setattr(cache_service.time, "time", lambda: current_time[0])

    cache_service.cache_set("ttl-key", {"value": 1}, ttl=10)

    current_time[0] = 1_009.0
    assert cache_service.cache_get("ttl-key") == {"value": 1}

    current_time[0] = 1_011.0
    assert cache_service.cache_get("ttl-key") is None
    assert "ttl-key" not in cache_service._cache


def test_cache_get_honors_redis_entry_ttl(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.zadd_calls = []
            self.zrem_calls = []

        def zadd(self, key, payload):
            self.zadd_calls.append((key, payload))

        def zrem(self, key, *members):
            self.zrem_calls.append((key, members))

    current_time = [2_000.0]
    redis = FakeRedis()
    redis_key = cache_service._redis_cache_key("redis-ttl-key")
    entry = {"data": {"value": 2}, "time": 2_000.0, "ttl": 5}
    deleted = []

    monkeypatch.setattr(cache_service, "get_redis_client", lambda: redis)
    monkeypatch.setattr(cache_service, "redis_get_json", lambda key: entry)
    monkeypatch.setattr(cache_service, "redis_delete", lambda key: deleted.append(key))
    monkeypatch.setattr(cache_service.time, "time", lambda: current_time[0])

    assert cache_service.cache_get("redis-ttl-key") == {"value": 2}
    assert redis.zadd_calls

    current_time[0] = 2_006.0
    assert cache_service.cache_get("redis-ttl-key") is None
    assert deleted == [redis_key]
    assert redis.zrem_calls[-1] == (cache_service.CACHE_LRU_KEY, (redis_key,))


def test_cache_memory_lru_evicts_oldest_entry(monkeypatch):
    monkeypatch.setattr(cache_service, "get_redis_client", lambda: None)
    monkeypatch.setattr(cache_service, "CACHE_MAX_ENTRIES", 2)

    cache_service.cache_set("a", 1)
    cache_service.cache_set("b", 2)
    cache_service.cache_get("a")
    cache_service.cache_set("c", 3)

    assert list(cache_service._cache.keys()) == ["a", "c"]
    assert cache_service.cache_get("b") is None


def test_auth_token_service_lifecycle(app, monkeypatch):
    monkeypatch.setattr(auth_service.secrets, "token_urlsafe", lambda _length: "unit-token")

    with app.app_context():
        user = User(username="token_user", email="token@example.test")
        user.set_password("Password123")
        db.session.add(user)
        db.session.commit()

        token = auth_service.generate_token(user.id)
        assert token == "unit-token"
        assert auth_service.get_user_for_token(token).email == "token@example.test"
        assert not auth_service.is_token_revoked(token)

        auth_service.revoke_token(token)

        assert auth_service.is_token_revoked(token)
        assert auth_service.get_user_for_token(token) is None


def test_generate_token_requires_available_auth_store(monkeypatch):
    monkeypatch.setattr(auth_service, "redis_set_json", lambda *args, **kwargs: False)

    with pytest.raises(ApiError) as exc:
        auth_service.generate_token(1)

    assert exc.value.code == "auth_store_unavailable"
