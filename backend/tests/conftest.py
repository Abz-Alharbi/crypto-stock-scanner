import os
import time

import pytest

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SCAN_QUEUE_SYNC", "true")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from backend.auth import service as auth_service
from backend.domain import AssetClass
from backend.extensions import db
from backend.factory import create_app
from backend.providers import provider_override
from backend.tests.fake_provider import FakeProvider


class MockPolygonClient:
    api_key = "test-polygon-key"

    def search_tickers(self, query, market="stocks"):
        if market == "crypto":
            return [
                {
                    "ticker": "X:BTCUSD",
                    "name": "Bitcoin USD",
                    "market": "crypto",
                    "type": "crypto",
                    "currency_name": "USD",
                }
            ]
        return [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "market": "stocks",
                "type": "CS",
                "currency_name": "USD",
            }
        ]

    def get_aggregates(self, symbol, timespan="day", multiplier=1, from_date=None, to_date=None):
        return [
            {
                "t": index,
                "o": 100 + index,
                "h": 102 + index,
                "l": 99 + index,
                "c": 101 + index,
                "v": 1_000_000 + index,
            }
            for index in range(60)
        ]

    def get_ticker_details(self, symbol):
        market = "crypto" if str(symbol).startswith("X:") else "stocks"
        return {
            "ticker": symbol,
            "name": f"{symbol} Test Asset",
            "market": market,
            "locale": "us",
            "primary_exchange": "XNAS",
        }

    def get_previous_close(self, symbol):
        return {"c": 123.45}

    def get_financials(self, symbol, limit=4, timeframe="annual"):
        return []

    def get_dividends(self, symbol, limit=4):
        return []

    def get_news(self, symbol, limit=20):
        return []


@pytest.fixture(autouse=True)
def isolated_auth_store(monkeypatch):
    store = {}
    expires_at = {}

    def _expired(key):
        expiry = expires_at.get(key)
        if expiry is not None and expiry <= time.time():
            store.pop(key, None)
            expires_at.pop(key, None)
            return True
        return False

    def redis_set_json(key, value, ttl=None):
        store[key] = value
        expires_at[key] = time.time() + int(ttl) if ttl else None
        return True

    def redis_get_json(key):
        if _expired(key):
            return None
        return store.get(key)

    def redis_set_value(key, value, ttl=None):
        store[key] = value
        expires_at[key] = time.time() + int(ttl) if ttl else None
        return True

    def redis_delete(*keys):
        deleted = 0
        for key in keys:
            if key in store:
                deleted += 1
            store.pop(key, None)
            expires_at.pop(key, None)
        return deleted

    def redis_exists(key):
        return key in store and not _expired(key)

    def redis_ttl(key):
        if key not in store or _expired(key):
            return None
        expiry = expires_at.get(key)
        if expiry is None:
            return None
        return max(1, int(expiry - time.time()))

    monkeypatch.setattr(auth_service, "redis_set_json", redis_set_json)
    monkeypatch.setattr(auth_service, "redis_get_json", redis_get_json)
    monkeypatch.setattr(auth_service, "redis_set_value", redis_set_value)
    monkeypatch.setattr(auth_service, "redis_delete", redis_delete)
    monkeypatch.setattr(auth_service, "redis_exists", redis_exists)
    monkeypatch.setattr(auth_service, "redis_ttl", redis_ttl)

    return store


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    from backend.services import cache

    cache._cache.clear()
    monkeypatch.setattr(cache, "get_redis_client", lambda: None)
    yield
    cache._cache.clear()


@pytest.fixture(autouse=True)
def fake_provider():
    bars = [
        {
            "t": index,
            "o": 100 + index,
            "h": 102 + index,
            "l": 99 + index,
            "c": 101 + index,
            "v": 1_000_000 + index,
        }
        for index in range(60)
    ]
    provider = FakeProvider(default_bars=bars)
    provider.search_results.update(
        {
            AssetClass.EQUITY: [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "market": "stocks",
                    "type": "CS",
                    "currency_name": "USD",
                }
            ],
            AssetClass.CRYPTO: [
                {
                    "ticker": "X:BTCUSD",
                    "name": "Bitcoin USD",
                    "market": "crypto",
                    "type": "crypto",
                    "currency_name": "USD",
                }
            ],
        }
    )
    provider.ticker_details_by_symbol["AAPL"] = {
        "ticker": "AAPL",
        "name": "AAPL Test Asset",
        "market": "stocks",
        "locale": "us",
        "primary_exchange": "XNAS",
    }
    with provider_override(provider):
        yield provider


@pytest.fixture
def mock_polygon(monkeypatch):
    client = MockPolygonClient()

    from backend.services import fundamentals

    monkeypatch.setattr(fundamentals, "polygon", client)

    try:
        from backend.services import news

        monkeypatch.setattr(news, "polygon", client)
        monkeypatch.setattr(news.news_aggregator, "polygon", client)
    except Exception:
        pass

    return client


@pytest.fixture
def app(mock_polygon):
    app = create_app(
        {
            "ALLOWED_ORIGINS": "http://localhost:5173",
            "AUTO_CREATE_SCHEMA": False,
            "DEBUG": False,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_headers(app):
    with app.app_context():
        admin, _created = auth_service.create_admin("admin@example.test", "AdminPass123")
        token = auth_service.generate_token(admin.id)
    return {"Authorization": f"Bearer {token}"}
