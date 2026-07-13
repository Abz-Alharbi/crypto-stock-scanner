from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.domain import AssetClass, Instrument, Timeframe
from backend.market_config import CANONICAL_TIMEFRAMES
from backend.schemas.market import ScanRequest
from backend.services import scans
from backend.services.technical import TechnicalAnalysis
from backend.strategies import (
    DuplicateStrategyError,
    SignalDirection,
    StrategyContext,
    StrategyRegistry,
    StrategyStatus,
    registry,
)
from backend.strategies.capabilities import get_plan_capabilities
from backend.strategy_runtime import get_strategies, validate_strategy_selection
from backend.services.universe.providers import UniverseResolution

LEGACY_IDS = {
    "rsi_oversold",
    "rsi_overbought",
    "stoch_oversold",
    "stoch_overbought",
    "ema_golden_cross",
    "ema_death_cross",
    "price_above_sma200",
    "macd_bullish",
    "macd_bearish",
    "bb_squeeze",
    "bb_breakout",
    "bullish_pattern",
    "bearish_pattern",
    "chart_pattern_bullish",
    "near_fib_support",
    "near_fib_resistance",
    "fib_golden_zone",
    "fib_shallow_retrace",
    "fib_deep_retrace",
    "fib_uptrend",
    "fib_downtrend",
    "fib_confluence_zone",
}

BEARISH_LEGACY_IDS = {
    "rsi_overbought",
    "stoch_overbought",
    "ema_death_cross",
    "macd_bearish",
    "bearish_pattern",
    "near_fib_resistance",
    "fib_downtrend",
}


def _legacy_match(strategy_id, analysis):
    indicators = analysis["indicators"]
    fib = analysis["fibonacci"]
    checks = {
        "rsi_oversold": lambda: indicators["rsi"] is not None
        and indicators["rsi"] < 30,
        "rsi_overbought": lambda: indicators["rsi"] is not None
        and indicators["rsi"] > 70,
        "stoch_oversold": lambda: indicators["stochastic"]["k"] is not None
        and indicators["stochastic"]["k"] < 20,
        "stoch_overbought": lambda: indicators["stochastic"]["k"] is not None
        and indicators["stochastic"]["k"] > 80,
        "ema_golden_cross": lambda: indicators["ema"]["ema_50"] is not None
        and indicators["ema"]["ema_200"] is not None
        and indicators["ema"]["ema_50"] > indicators["ema"]["ema_200"],
        "ema_death_cross": lambda: indicators["ema"]["ema_50"] is not None
        and indicators["ema"]["ema_200"] is not None
        and indicators["ema"]["ema_50"] < indicators["ema"]["ema_200"],
        "price_above_sma200": lambda: indicators["sma"]["sma_200"] is not None
        and analysis["price"]["last"] > indicators["sma"]["sma_200"],
        "macd_bullish": lambda: indicators["macd"]["line"] is not None
        and indicators["macd"]["signal"] is not None
        and indicators["macd"]["line"] > indicators["macd"]["signal"],
        "macd_bearish": lambda: indicators["macd"]["line"] is not None
        and indicators["macd"]["signal"] is not None
        and indicators["macd"]["line"] < indicators["macd"]["signal"],
        "bb_squeeze": lambda: indicators["bollinger_bands"]["lower"] is not None
        and analysis["price"]["last"]
        <= indicators["bollinger_bands"]["lower"] * 1.02,
        "bb_breakout": lambda: indicators["bollinger_bands"]["upper"] is not None
        and analysis["price"]["last"]
        >= indicators["bollinger_bands"]["upper"] * 0.98,
        "bullish_pattern": lambda: any(
            p["type"] == "bullish" for p in analysis["patterns"]["candlestick"]
        ),
        "bearish_pattern": lambda: any(
            p["type"] == "bearish" for p in analysis["patterns"]["candlestick"]
        ),
        "chart_pattern_bullish": lambda: any(
            p["type"] == "bullish" for p in analysis["patterns"]["chart"]
        ),
        "near_fib_support": lambda: fib is not None
        and fib["nearest_support"] is not None
        and abs(analysis["price"]["last"] - fib["nearest_support"])
        / analysis["price"]["last"]
        < 0.02,
        "near_fib_resistance": lambda: fib is not None
        and fib["nearest_resistance"] is not None
        and abs(analysis["price"]["last"] - fib["nearest_resistance"])
        / analysis["price"]["last"]
        < 0.02,
        "fib_golden_zone": lambda: fib is not None
        and fib.get("price_zone") == "golden_zone",
        "fib_shallow_retrace": lambda: fib is not None
        and fib.get("price_zone") == "shallow_retrace",
        "fib_deep_retrace": lambda: fib is not None
        and fib.get("price_zone") in ("deep_retrace", "very_deep"),
        "fib_uptrend": lambda: fib is not None and fib.get("trend") == "uptrend",
        "fib_downtrend": lambda: fib is not None
        and fib.get("trend") == "downtrend",
        "fib_confluence_zone": lambda: fib is not None
        and any(
            zone["strength"] >= 2
            and abs(analysis["price"]["last"] - zone["mid"])
            / analysis["price"]["last"]
            < 0.025
            for zone in fib.get("zones", [])
        ),
    }
    return checks[strategy_id]()


def _analysis(*, bearish=False, empty=False):
    if empty:
        return {
            "price": {"last": 100, "volume": 0},
            "indicators": {
                "rsi": None,
                "stochastic": {"k": None},
                "ema": {"ema_50": None, "ema_200": None},
                "sma": {"sma_200": None},
                "macd": {"line": None, "signal": None},
                "bollinger_bands": {"lower": None, "upper": None},
            },
            "patterns": {"candlestick": [], "chart": []},
            "fibonacci": None,
        }
    return {
        "price": {"last": 100, "volume": 1_500_000},
        "indicators": {
            "rsi": 75 if bearish else 25,
            "stochastic": {"k": 85 if bearish else 15},
            "ema": {
                "ema_50": 90 if bearish else 110,
                "ema_200": 100,
            },
            "sma": {"sma_200": 110 if bearish else 90},
            "macd": {
                "line": 0.5 if bearish else 1.5,
                "signal": 0.8,
            },
            "bollinger_bands": {
                "lower": 50 if bearish else 99,
                "upper": 101 if bearish else 130,
            },
        },
        "patterns": {
            "candlestick": [
                {"pattern": "Test", "type": "bearish" if bearish else "bullish"}
            ],
            "chart": [
                {"pattern": "Test", "type": "bearish" if bearish else "bullish"}
            ],
        },
        "fibonacci": {
            "nearest_support": 80 if bearish else 99,
            "nearest_resistance": 101 if bearish else 120,
            "price_zone": "deep_retrace" if bearish else "golden_zone",
            "trend": "downtrend" if bearish else "uptrend",
            "zones": [{"mid": 100.5, "strength": 2}],
        },
    }


@pytest.mark.parametrize("analysis", [_analysis(), _analysis(bearish=True), _analysis(empty=True)])
@pytest.mark.parametrize(
    ("asset_class", "symbol", "timeframe"),
    [
        (AssetClass.EQUITY, "AAPL", Timeframe("1m")),
        (AssetClass.EQUITY, "MSFT", Timeframe("1D")),
        (AssetClass.CRYPTO, "X:BTCUSD", Timeframe("4H")),
        (AssetClass.CRYPTO, "X:ETHUSD", Timeframe("1Y")),
    ],
)
def test_all_22_legacy_filters_are_boolean_equivalent(
    analysis, asset_class, symbol, timeframe
):
    legacy_strategies = {
        strategy.identifier: strategy
        for strategy in registry.all()
        if strategy.is_legacy_filter
    }
    assert set(legacy_strategies) == LEGACY_IDS
    bars = [{"c": 100}] * 250
    context = StrategyContext(
        bars=bars,
        analysis=analysis,
        asset_class=asset_class,
        timeframe=timeframe,
        instrument=Instrument.from_wire(symbol, asset_class),
    )
    for strategy_id, strategy in legacy_strategies.items():
        expected = _legacy_match(strategy_id, analysis)
        result = strategy.evaluate(context)
        assert result.matched is expected, strategy_id
        assert strategy.legacy_match(analysis) is expected, strategy_id
        expected_direction = (
            SignalDirection.BEARISH
            if strategy_id in BEARISH_LEGACY_IDS
            else SignalDirection.BULLISH
        )
        assert result.direction is (
            expected_direction if expected else SignalDirection.NO_SIGNAL
        ), strategy_id


@pytest.mark.parametrize(
    ("rsi", "status", "direction"),
    [
        (29.99, StrategyStatus.MATCHED, SignalDirection.BULLISH),
        (30.0, StrategyStatus.NOT_MATCHED, SignalDirection.NEUTRAL),
        (70.0, StrategyStatus.NOT_MATCHED, SignalDirection.NEUTRAL),
        (70.01, StrategyStatus.MATCHED, SignalDirection.BEARISH),
    ],
)
def test_rsi_demo_is_discovered_and_uses_exact_boundaries(
    rsi, status, direction
):
    strategy = get_strategies(["rsi_overbought_oversold"])[0]
    result = strategy.evaluate(
        StrategyContext(
            bars=[{"c": 100}] * 30,
            analysis={"indicators": {"rsi": rsi}},
            asset_class=AssetClass.CRYPTO,
            timeframe=Timeframe("1Y"),
        )
    )
    assert result.status is status
    assert result.direction is direction
    assert result.evidence == {"rsi": rsi}


@pytest.mark.parametrize(
    ("closes", "expected_rsi", "direction"),
    [
        (list(range(130, 100, -1)), 0.0, SignalDirection.BULLISH),
        (list(range(100, 130)), 100.0, SignalDirection.BEARISH),
    ],
)
def test_rsi_demo_computes_evidence_from_candles(
    closes, expected_rsi, direction
):
    strategy = registry.get("rsi_overbought_oversold")
    bars = [
        {
            "t": index,
            "o": close,
            "h": close + 1,
            "l": close - 1,
            "c": close,
            "v": 1000,
        }
        for index, close in enumerate(closes)
    ]
    analysis = TechnicalAnalysis.full_analysis(bars, features={"rsi"})
    result = strategy.evaluate(
        StrategyContext(
            bars=bars,
            analysis=analysis,
            asset_class=AssetClass.EQUITY,
            timeframe=Timeframe("1D"),
        )
    )
    assert result.status is StrategyStatus.MATCHED
    assert result.direction is direction
    assert result.evidence == {"rsi": expected_rsi}


def test_rsi_demo_enforces_history_and_fixed_period_parameter():
    strategy = registry.get("rsi_overbought_oversold")
    context = StrategyContext(
        bars=[{"c": 100}] * 29,
        analysis={"indicators": {"rsi": 20}},
        asset_class=AssetClass.EQUITY,
        timeframe=Timeframe("1D"),
    )
    assert strategy.evaluate(context).status is StrategyStatus.INSUFFICIENT_DATA
    with pytest.raises(ValueError):
        strategy.validate_parameters({"period": 10})
    with pytest.raises(ValueError):
        strategy.validate_parameters({"unexpected": True})


def test_demo_registration_requires_no_strategy_specific_scan_branch(
    monkeypatch, app, fake_provider
):
    scan_source = Path("backend/services/scans.py").read_text(encoding="utf-8")
    runtime_source = Path("backend/strategy_runtime.py").read_text(encoding="utf-8")
    assert "rsi_overbought_oversold" not in scan_source
    assert "rsi_overbought_oversold" not in runtime_source
    assert "backend.strategies" not in scan_source
    assert registry.get("rsi_overbought_oversold").identifier in registry.ids()

    # A newly registered strategy is immediately executable by the generic
    # scan loop; no orchestration dispatch table or strategy-ID branch exists.
    probe = replace(
        registry.get("rsi_overbought_oversold"),
        identifier="registry_extension_probe",
        display_name="Registry Extension Probe",
    )
    fake_provider.default_bars = [
        {
            "t": index,
            "o": 130 - index,
            "h": 131 - index,
            "l": 128 - index,
            "c": 129 - index,
            "v": 1000,
        }
            for index in range(140)
    ]
    monkeypatch.setattr(
        scans,
        "resolve_scan_universe",
        lambda asset_class, universe_key=None: UniverseResolution(
            universe_key or "us_stocks_top",
            asset_class,
            ("AAPL",),
            "test",
        ),
    )
    registry.register(probe)
    try:
        with app.app_context():
            payload = scans.scan_market(
                "stocks",
                [probe.identifier],
                "1D",
                1,
                job_id="registry-extension-proof",
            )
        assert payload["results"][0]["matched_filters"] == [probe.identifier]
        assert payload["results"][0]["strategy_results"][probe.identifier][
            "direction"
        ] == "bullish"
    finally:
        registry._strategies.pop(probe.identifier, None)


def test_registry_rejects_duplicate_identifiers():
    local_registry = StrategyRegistry()
    strategy = registry.get("rsi_overbought_oversold")
    local_registry.register(strategy)
    with pytest.raises(DuplicateStrategyError):
        local_registry.register(strategy)


def test_full_analysis_can_select_features_and_preserves_numeric_zero():
    bars = [
        {
            "t": index,
            "o": 100 - index,
            "h": 101 - index,
            "l": 98 - index,
            "c": 99 - index,
            "v": 1000,
        }
        for index in range(60)
    ]
    analysis = TechnicalAnalysis.full_analysis(bars, features={"rsi"})
    assert analysis["indicators"]["rsi"] == 0.0
    assert analysis["indicators"]["macd"]["line"] is None
    assert analysis["fibonacci"] is None
    assert analysis["patterns"] == {"candlestick": [], "chart": []}
    assert analysis["trade_setup"] is None


def test_strict_request_validation_rejects_unknown_strategy():
    with pytest.raises(ValidationError, match="unknown_strategy"):
        ScanRequest.model_validate(
            {
                "market": "stocks",
                "timeframe": "1D",
                "filters": ["unknown_strategy"],
            }
        )


def test_unlimited_plan_enables_all_assets_timeframes_and_registered_strategies():
    capabilities = get_plan_capabilities("unlimited")
    assert capabilities["strategy_ids"] == "*"
    assert set(capabilities["asset_classes"]) == {"stocks", "crypto"}
    assert tuple(capabilities["timeframes"]) == tuple(CANONICAL_TIMEFRAMES)
    validate_strategy_selection(
        registry.ids(),
        asset_class=AssetClass.CRYPTO,
        timeframe=Timeframe("1Y"),
    )


def test_filters_endpoint_exposes_registry_capability_metadata(client):
    response = client.get("/api/filters")
    assert response.status_code == 200
    payload = response.get_json()
    demo = payload["filters"]["oscillators"]["rsi_overbought_oversold"]
    assert demo["required_history"] == 30
    assert demo["parameters"]["period"] == {
        "type": "integer",
        "default": 14,
        "const": 14,
    }
    assert set(demo["supported_asset_classes"]) == {"stocks", "crypto"}
    assert demo["supported_timeframes"] == list(CANONICAL_TIMEFRAMES)
    assert demo["available"] is True
    assert all(item["available"] for item in payload["timeframes"].values())
