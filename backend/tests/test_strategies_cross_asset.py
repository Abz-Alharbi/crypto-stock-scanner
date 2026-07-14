"""Phase 9 cross-asset strategy and context validation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.domain import AssetClass, Instrument, Timeframe
from backend.market_config import CANONICAL_TIMEFRAMES
from backend.models.scan import ScanHistory, ScanResult
from backend.schemas.market import ScanRequest
from backend.services import scans
from backend.services import scan_jobs as scan_job_service
from backend.services.technical import TechnicalAnalysis
from backend.services.universe.providers import UniverseResolution
from backend.strategies import SignalDirection, StrategyContext, StrategyStatus, registry
from backend.strategy_runtime import validate_strategy_selection


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "phase9"
PRIMARY_SYMBOL = {
    AssetClass.EQUITY: "AAPL",
    AssetClass.CRYPTO: "X:BTCUSD",
}
ALL_COMBINATIONS = tuple(
    (strategy_id, asset_class, timeframe)
    for strategy_id in registry.ids()
    for asset_class in AssetClass
    for timeframe in CANONICAL_TIMEFRAMES
)


def _neutral_analysis():
    return {
        "price": {"last": 100.0, "volume": 1_000_000},
        "indicators": {
            "rsi": 50.0,
            "stochastic": {"k": 50.0, "d": 50.0},
            "ema": {"ema_50": 100.0, "ema_200": 100.0},
            "sma": {"sma_200": 100.0},
            "macd": {"line": 0.0, "signal": 0.0},
            "bollinger_bands": {"lower": 90.0, "upper": 110.0},
        },
        "patterns": {"candlestick": [], "chart": []},
        "fibonacci": {
            "nearest_support": 80.0,
            "nearest_resistance": 120.0,
            "price_zone": "near_high",
            "trend": "sideways",
            "zones": [],
        },
    }


def _controlled_analysis(strategy_id: str, *, matched: bool):
    analysis = deepcopy(_neutral_analysis())
    if not matched:
        return analysis

    if strategy_id == "near_fib_support":
        analysis["fibonacci"]["nearest_support"] = 99.0
    elif strategy_id == "near_fib_resistance":
        analysis["fibonacci"]["nearest_resistance"] = 101.0
    elif strategy_id == "fib_golden_zone":
        analysis["fibonacci"]["price_zone"] = "golden_zone"
    elif strategy_id == "fib_shallow_retrace":
        analysis["fibonacci"]["price_zone"] = "shallow_retrace"
    elif strategy_id == "fib_deep_retrace":
        analysis["fibonacci"]["price_zone"] = "deep_retrace"
    elif strategy_id == "fib_uptrend":
        analysis["fibonacci"]["trend"] = "uptrend"
    elif strategy_id == "fib_downtrend":
        analysis["fibonacci"]["trend"] = "downtrend"
    elif strategy_id == "fib_confluence_zone":
        analysis["fibonacci"]["zones"] = [{"mid": 100.5, "strength": 2}]
    elif strategy_id == "ema_golden_cross":
        analysis["indicators"]["ema"] = {"ema_50": 101.0, "ema_200": 100.0}
    elif strategy_id == "ema_death_cross":
        analysis["indicators"]["ema"] = {"ema_50": 99.0, "ema_200": 100.0}
    elif strategy_id == "price_above_sma200":
        analysis["indicators"]["sma"]["sma_200"] = 99.0
    elif strategy_id == "macd_bullish":
        analysis["indicators"]["macd"] = {"line": 0.1, "signal": 0.0}
    elif strategy_id == "macd_bearish":
        analysis["indicators"]["macd"] = {"line": -0.1, "signal": 0.0}
    elif strategy_id in {"rsi_oversold", "rsi_overbought_oversold"}:
        analysis["indicators"]["rsi"] = 29.0
    elif strategy_id == "rsi_overbought":
        analysis["indicators"]["rsi"] = 71.0
    elif strategy_id == "stoch_oversold":
        analysis["indicators"]["stochastic"]["k"] = 19.0
    elif strategy_id == "stoch_overbought":
        analysis["indicators"]["stochastic"]["k"] = 81.0
    elif strategy_id == "bullish_pattern":
        analysis["patterns"]["candlestick"] = [
            {"pattern": "Hammer", "type": "bullish"}
        ]
    elif strategy_id == "bearish_pattern":
        analysis["patterns"]["candlestick"] = [
            {"pattern": "Shooting Star", "type": "bearish"}
        ]
    elif strategy_id == "chart_pattern_bullish":
        analysis["patterns"]["chart"] = [
            {"pattern": "Double Bottom", "type": "bullish"}
        ]
    elif strategy_id == "bb_squeeze":
        analysis["indicators"]["bollinger_bands"]["lower"] = 99.0
    elif strategy_id == "bb_breakout":
        analysis["indicators"]["bollinger_bands"]["upper"] = 101.0
    else:  # pragma: no cover - registry additions must extend the golden matrix
        raise AssertionError(f"Missing controlled fixture for {strategy_id}")
    return analysis


def _controlled_bars(count: int, asset_class: AssetClass):
    scale = 400.0 if asset_class is AssetClass.CRYPTO else 1.0
    return [
        {
            "t": index,
            "o": 100.0 * scale,
            "h": 101.0 * scale,
            "l": 99.0 * scale,
            "c": 100.0 * scale,
            "v": 1_000_000,
        }
        for index in range(count)
    ]


def _snapshot_name(asset_class: AssetClass, symbol: str, timeframe: str) -> str:
    slug = {"1m": "1min", "1M": "1month"}.get(timeframe, timeframe)
    return f"{asset_class.value}_{symbol.replace(':', '_')}_{slug}.json"


@lru_cache(maxsize=None)
def _load_snapshot(asset_class: AssetClass, symbol: str, timeframe: str):
    path = FIXTURE_ROOT / _snapshot_name(asset_class, symbol, timeframe)
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _snapshot_analysis(asset_class: AssetClass, symbol: str, timeframe: str):
    payload = _load_snapshot(asset_class, symbol, timeframe)
    return TechnicalAnalysis.full_analysis(payload["bars"], timeframe=timeframe)


def test_snapshot_manifest_contains_44_verified_provider_snapshots():
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshot_count"] == 44
    assert len(manifest["snapshots"]) == 44
    assert len({entry["file"] for entry in manifest["snapshots"]}) == 44
    assert {
        (entry["asset_class"], entry["symbol"], entry["timeframe"])
        for entry in manifest["snapshots"]
    } == {
        (asset_class.value, symbol, timeframe)
        for asset_class, symbols in (
            (AssetClass.EQUITY, ("AAPL", "MSFT")),
            (AssetClass.CRYPTO, ("X:BTCUSD", "X:ETHUSD")),
        )
        for symbol in symbols
        for timeframe in CANONICAL_TIMEFRAMES
    }
    for entry in manifest["snapshots"]:
        data = (FIXTURE_ROOT / entry["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        payload = json.loads(data)
        assert payload["source"] == "Massive/Polygon aggregates"
        assert payload["asset_class"] == entry["asset_class"]
        assert payload["symbol"] == entry["symbol"]
        assert payload["timeframe"] == entry["timeframe"]
        assert len(payload["bars"]) == entry["closed_bars"]
        assert all(not bar.get("partial", False) for bar in payload["bars"])


@pytest.mark.parametrize(
    ("strategy_id", "asset_class", "timeframe"),
    ALL_COMBINATIONS,
    ids=lambda value: value.value if isinstance(value, AssetClass) else str(value),
)
def test_complete_506_combination_contract_matrix(
    strategy_id, asset_class, timeframe
):
    strategy = registry.get(strategy_id)
    parsed_timeframe = Timeframe(timeframe)
    assert asset_class in strategy.supported_asset_classes
    assert parsed_timeframe in strategy.supported_timeframes
    validate_strategy_selection(
        [strategy_id], asset_class=asset_class, timeframe=parsed_timeframe
    )

    bars = _controlled_bars(strategy.required_history, asset_class)
    context = StrategyContext(
        bars=bars,
        analysis=_controlled_analysis(strategy_id, matched=True),
        asset_class=asset_class,
        timeframe=parsed_timeframe,
        instrument=Instrument.from_wire(PRIMARY_SYMBOL[asset_class], asset_class),
    )
    matched = strategy.evaluate(context)
    assert matched.status is StrategyStatus.MATCHED
    assert matched.direction is not SignalDirection.NO_SIGNAL

    not_matched = strategy.evaluate(
        replace(context, analysis=_controlled_analysis(strategy_id, matched=False))
    )
    assert not_matched.status is StrategyStatus.NOT_MATCHED

    insufficient = strategy.evaluate(
        replace(context, bars=bars[: strategy.required_history - 1])
    )
    assert insufficient.status is StrategyStatus.INSUFFICIENT_DATA
    assert insufficient.evidence == {
        "required_history": strategy.required_history,
        "available_history": strategy.required_history - 1,
    }


@pytest.mark.parametrize(
    ("strategy_id", "asset_class", "timeframe"),
    ALL_COMBINATIONS,
    ids=lambda value: value.value if isinstance(value, AssetClass) else str(value),
)
def test_real_primary_snapshots_have_explicit_outcomes_for_all_506_combinations(
    strategy_id, asset_class, timeframe
):
    strategy = registry.get(strategy_id)
    symbol = PRIMARY_SYMBOL[asset_class]
    payload = _load_snapshot(asset_class, symbol, timeframe)
    result = strategy.evaluate(
        StrategyContext(
            bars=payload["bars"],
            analysis=_snapshot_analysis(asset_class, symbol, timeframe),
            asset_class=asset_class,
            timeframe=Timeframe(timeframe),
            instrument=Instrument.from_wire(symbol, asset_class),
        )
    )
    expected = (
        StrategyStatus.INSUFFICIENT_DATA
        if len(payload["bars"]) < strategy.required_history
        else {StrategyStatus.MATCHED, StrategyStatus.NOT_MATCHED}
    )
    if isinstance(expected, set):
        assert result.status in expected
    else:
        assert result.status is expected


def test_equity_only_strategy_is_rejected_for_crypto_request():
    probe = replace(
        registry.get("rsi_overbought_oversold"),
        identifier="phase9_equity_only_probe",
        supported_asset_classes=frozenset({AssetClass.EQUITY}),
    )
    registry.register(probe)
    try:
        with pytest.raises(
            ValidationError,
            match="does not support crypto",
        ):
            ScanRequest.model_validate(
                {
                    "market": "crypto",
                    "universe": "crypto_static",
                    "timeframe": "4H",
                    "filters": [probe.identifier],
                }
            )
    finally:
        registry._strategies.pop(probe.identifier, None)


def _bullish_engulfing_bars(count=140):
    bars = _controlled_bars(count - 2, AssetClass.CRYPTO)
    bars.extend(
        [
            {"t": count - 2, "o": 106, "h": 107, "l": 99, "c": 100, "v": 1000},
            {"t": count - 1, "o": 99, "h": 108, "l": 98, "c": 107, "v": 1000},
        ]
    )
    return bars


def test_crypto_asset_context_survives_request_job_persistence_and_response(
    app, client, admin_headers, fake_provider, monkeypatch
):
    monkeypatch.setenv("SCAN_QUEUE_SYNC", "true")
    job_state = {}

    def set_json(key, value, ttl=None):
        del ttl
        job_state[key] = value
        return True

    monkeypatch.setattr(scan_job_service, "redis_set_json", set_json)
    monkeypatch.setattr(scan_job_service, "redis_get_json", job_state.get)
    monkeypatch.setattr(scan_job_service, "redis_exists", lambda _key: False)
    fake_provider.default_bars = _bullish_engulfing_bars()
    monkeypatch.setattr(
        scans,
        "resolve_scan_universe",
        lambda asset_class, universe_key=None: UniverseResolution(
            universe_key or "crypto_static",
            asset_class,
            ("X:BTCUSD",),
            "phase9_fixture",
            symbol_venues=(("X:BTCUSD", "GLOBAL_CRYPTO"),),
        ),
    )

    submitted = client.post(
        "/api/scan",
        headers=admin_headers,
        json={
            "market": "crypto",
            "universe": "crypto_static",
            "timeframe": "4H",
            "filters": ["bullish_pattern"],
            "limit": 5,
        },
    )
    assert submitted.status_code == 202, submitted.get_json()
    job_id = submitted.get_json()["job_id"]
    response = client.get(f"/api/scan/status/{job_id}", headers=admin_headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "completed"
    assert payload["meta"]["market"] == "crypto"
    assert payload["meta"]["universe"] == "crypto_static"
    assert payload["meta"]["timeframe"] == "4H"
    assert payload["results"][0]["market"] == "crypto"

    with app.app_context():
        history = ScanHistory.query.filter_by(job_id=job_id).one()
        result = ScanResult.query.filter_by(job_id=job_id).one()
        assert history.market == "crypto"
        assert history.timeframe == "4H"
        assert result.market == "crypto"
        assert result.timeframe == "4H"
        assert result.provider_symbol == "X:BTCUSD"
