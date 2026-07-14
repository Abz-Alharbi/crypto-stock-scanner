"""Approved quantitative drift gates for deterministic pattern logic."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import pytest

from backend.domain import AssetClass
from backend.market_config import CANONICAL_TIMEFRAMES, timeframe_config
from backend.services.technical import TechnicalAnalysis


CANDLE_PATTERNS = (
    "Hammer",
    "Inverted Hammer",
    "Shooting Star",
    "Bullish Engulfing",
    "Bearish Engulfing",
    "Morning Star",
    "Evening Star",
)
CHART_PATTERNS = (
    "Double Bottom",
    "Double Top",
    "Ascending Triangle",
    "Descending Triangle",
    "Bullish Flag",
)
EXECUTABLE_CHART_TIMEFRAMES = tuple(
    timeframe for timeframe in CANONICAL_TIMEFRAMES if timeframe != "1Y"
)
VARIANTS_PER_PATTERN = 100


def _candle_case(pattern: str, asset_class: AssetClass, seed: int):
    rng = random.Random(seed)
    price_scale = 400.0 if asset_class is AssetClass.CRYPTO else 1.0
    volatility = 1.35 if asset_class is AssetClass.CRYPTO else 1.0
    center = 100.0

    def candle(open_, close, upper, lower):
        high = max(open_, close) + upper
        low = min(open_, close) - lower
        return open_, high, low, close

    body = rng.uniform(0.8, 1.2) * volatility
    neutral = [
        candle(center - 4, center - 3, 1.0, 1.0),
        candle(center - 2, center - 1, 1.0, 1.0),
        candle(center, center + 1, 1.0, 1.0),
    ]
    if pattern == "Hammer":
        neutral[-1] = candle(
            center,
            center + body,
            body * rng.uniform(0.1, 0.4),
            body * rng.uniform(2.2, 3.5),
        )
    elif pattern == "Inverted Hammer":
        neutral[-1] = candle(
            center,
            center + body,
            body * rng.uniform(2.2, 3.5),
            body * rng.uniform(0.1, 0.4),
        )
    elif pattern == "Shooting Star":
        neutral[-1] = candle(
            center + body,
            center,
            body * rng.uniform(2.2, 3.5),
            body * rng.uniform(0.1, 0.4),
        )
    elif pattern == "Bullish Engulfing":
        prior = rng.uniform(1.5, 2.5) * volatility
        neutral[-2] = candle(center + prior, center, 0.4, 0.4)
        neutral[-1] = candle(
            center - rng.uniform(0.1, 0.5),
            center + prior + rng.uniform(0.1, 0.5),
            0.4,
            0.4,
        )
    elif pattern == "Bearish Engulfing":
        prior = rng.uniform(1.5, 2.5) * volatility
        neutral[-2] = candle(center, center + prior, 0.4, 0.4)
        neutral[-1] = candle(
            center + prior + rng.uniform(0.1, 0.5),
            center - rng.uniform(0.1, 0.5),
            0.4,
            0.4,
        )
    elif pattern == "Morning Star":
        first_body = rng.uniform(2.5, 3.5) * volatility
        neutral[-3] = candle(center + first_body, center, 0.5, 0.5)
        neutral[-2] = candle(center, center + first_body * 0.15, 0.4, 0.4)
        neutral[-1] = candle(center, center + first_body * 0.75, 0.5, 0.5)
    elif pattern == "Evening Star":
        first_body = rng.uniform(2.5, 3.5) * volatility
        neutral[-3] = candle(center, center + first_body, 0.5, 0.5)
        neutral[-2] = candle(
            center + first_body,
            center + first_body * 0.85,
            0.4,
            0.4,
        )
        neutral[-1] = candle(
            center + first_body,
            center + first_body * 0.25,
            0.5,
            0.5,
        )
    else:  # pragma: no cover
        raise ValueError(pattern)

    opens, highs, lows, closes = zip(*neutral)
    return tuple(
        [value * price_scale for value in series]
        for series in (opens, highs, lows, closes)
    )


def _neutral_candles(asset_class: AssetClass, seed: int):
    rng = random.Random(seed)
    scale = 400.0 if asset_class is AssetClass.CRYPTO else 1.0
    candles = []
    for index in range(3):
        open_ = 100 + index * 2 + rng.uniform(-0.05, 0.05)
        close = open_ + 1
        candles.append((open_, close + 1, open_ - 1, close))
    return tuple([value * scale for value in series] for series in zip(*candles))


def _chart_case(
    pattern: str,
    timeframe: str,
    asset_class: AssetClass,
    seed: int,
):
    rng = random.Random(seed)
    window = int(timeframe_config(timeframe)["pattern_window"])
    volatility = 0.35 if asset_class is AssetClass.CRYPTO else 0.12
    scale = 400.0 if asset_class is AssetClass.CRYPTO else 1.0
    data = [100.0 + rng.uniform(-volatility, volatility) for _ in range(window)]
    mid = window // 2

    if pattern == "Double Bottom":
        data[max(1, mid // 2)] = 90.0 + rng.uniform(-0.3, 0.3)
        data[min(window - 1, mid + mid // 2)] = 90.5 + rng.uniform(-0.3, 0.3)
        for index in range(max(0, mid - 5), min(window, mid + 5)):
            data[index] = 100.0 + rng.uniform(0, 0.3)
    elif pattern == "Double Top":
        data[max(1, mid // 2)] = 110.0 + rng.uniform(-0.3, 0.3)
        data[min(window - 1, mid + mid // 2)] = 109.5 + rng.uniform(-0.3, 0.3)
        for index in range(max(0, mid - 5), min(window, mid + 5)):
            data[index] = 100.0 - rng.uniform(0, 0.3)
    elif pattern == "Ascending Triangle":
        for index in range(20):
            data[-20 + index] = 98.5 + (1.5 * index / 19) + rng.uniform(-0.05, 0.05)
    elif pattern == "Descending Triangle":
        for index in range(20):
            progress = index / 19
            if index % 2 == 0:
                data[-20 + index] = 100.0 + rng.uniform(-0.05, 0.05)
            else:
                data[-20 + index] = (
                    108.0 - (5.5 * progress) + rng.uniform(-0.08, 0.08)
                )
    elif pattern == "Bullish Flag":
        pole_start = window - 30
        for index in range(15):
            data[pole_start + index] = 100.0 + (8.0 * index / 14)
        for index in range(15):
            data[-15 + index] = 108.0 - (1.5 * index / 14) + rng.uniform(-0.1, 0.1)
    else:  # pragma: no cover
        raise ValueError(pattern)
    return [value * scale for value in data]


def _neutral_chart(timeframe: str, asset_class: AssetClass, seed: int):
    rng = random.Random(seed)
    window = int(timeframe_config(timeframe)["pattern_window"])
    scale = 400.0 if asset_class is AssetClass.CRYPTO else 1.0
    volatility = 0.05 if asset_class is AssetClass.CRYPTO else 0.02
    return [
        (120.0 - (40.0 * index / max(1, window - 1)) + rng.uniform(-volatility, volatility))
        * scale
        for index in range(window)
    ]


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _candlestick_metrics(asset_class: AssetClass):
    hits = 0
    total = 0
    false_positives = 0
    false_total = 0
    direction_inversions = 0
    expected_direction = {
        "Hammer": "bullish",
        "Inverted Hammer": "bullish",
        "Shooting Star": "bearish",
        "Bullish Engulfing": "bullish",
        "Bearish Engulfing": "bearish",
        "Morning Star": "bullish",
        "Evening Star": "bearish",
    }
    for timeframe_index, _timeframe in enumerate(CANONICAL_TIMEFRAMES):
        for pattern_index, pattern in enumerate(CANDLE_PATTERNS):
            for variant in range(VARIANTS_PER_PATTERN):
                seed = timeframe_index * 100_000 + pattern_index * 1_000 + variant
                detected = TechnicalAnalysis.detect_candlestick_patterns(
                    *_candle_case(pattern, asset_class, seed)
                )
                named = [item for item in detected if item["pattern"] == pattern]
                hits += bool(named)
                direction_inversions += any(
                    item["type"] != expected_direction[pattern] for item in named
                )
                total += 1
        for variant in range(VARIANTS_PER_PATTERN):
            detected = TechnicalAnalysis.detect_candlestick_patterns(
                *_neutral_candles(asset_class, timeframe_index * 1_000 + variant)
            )
            false_positives += bool(detected)
            false_total += 1
    return {
        "recall": _rate(hits, total),
        "false_positive_rate": _rate(false_positives, false_total),
        "direction_inversions": direction_inversions,
        "labeled_variants": total,
        "neutral_variants": false_total,
    }


def _chart_metrics(asset_class: AssetClass):
    hits = 0
    total = 0
    false_positives = 0
    false_total = 0
    direction_inversions = 0
    false_positive_patterns = Counter()
    false_positives_by_timeframe = Counter()
    expected_direction = {
        "Double Bottom": "bullish",
        "Double Top": "bearish",
        "Ascending Triangle": "bullish",
        "Descending Triangle": "bearish",
        "Bullish Flag": "bullish",
    }
    for timeframe_index, timeframe in enumerate(EXECUTABLE_CHART_TIMEFRAMES):
        window = int(timeframe_config(timeframe)["pattern_window"])
        for pattern_index, pattern in enumerate(CHART_PATTERNS):
            for variant in range(VARIANTS_PER_PATTERN):
                seed = timeframe_index * 100_000 + pattern_index * 1_000 + variant
                detected = TechnicalAnalysis.detect_chart_patterns(
                    _chart_case(pattern, timeframe, asset_class, seed),
                    window=window,
                )
                named = [item for item in detected if item["pattern"] == pattern]
                hits += bool(named)
                direction_inversions += any(
                    item["type"] != expected_direction[pattern] for item in named
                )
                total += 1
        for variant in range(VARIANTS_PER_PATTERN):
            detected = TechnicalAnalysis.detect_chart_patterns(
                _neutral_chart(
                    timeframe,
                    asset_class,
                    timeframe_index * 1_000 + variant,
                ),
                window=window,
            )
            false_positives += bool(detected)
            if detected:
                false_positives_by_timeframe[timeframe] += 1
                false_positive_patterns.update(item["pattern"] for item in detected)
            false_total += 1
    return {
        "recall": _rate(hits, total),
        "false_positive_rate": _rate(false_positives, false_total),
        "direction_inversions": direction_inversions,
        "labeled_variants": total,
        "neutral_variants": false_total,
        "false_positives_by_timeframe": dict(false_positives_by_timeframe),
        "false_positive_patterns": dict(false_positive_patterns),
    }


def test_candlestick_crypto_tolerance_drift_gate():
    equity = _candlestick_metrics(AssetClass.EQUITY)
    crypto = _candlestick_metrics(AssetClass.CRYPTO)
    print("PHASE9_CANDLE_METRICS", json.dumps({"stocks": equity, "crypto": crypto}))
    assert equity["recall"] >= 0.95
    assert crypto["recall"] >= 0.95
    assert equity["false_positive_rate"] <= 0.02
    assert crypto["false_positive_rate"] <= 0.02
    assert abs(crypto["recall"] - equity["recall"]) <= 0.02
    assert equity["direction_inversions"] == crypto["direction_inversions"] == 0


def test_chart_pattern_crypto_tolerance_drift_gate():
    equity = _chart_metrics(AssetClass.EQUITY)
    crypto = _chart_metrics(AssetClass.CRYPTO)
    print("PHASE9_CHART_METRICS", json.dumps({"stocks": equity, "crypto": crypto}))
    assert equity["recall"] >= 0.90
    assert crypto["recall"] >= 0.90
    assert equity["false_positive_rate"] <= 0.05, equity
    assert crypto["false_positive_rate"] <= 0.05, crypto
    assert abs(crypto["recall"] - equity["recall"]) <= 0.05
    assert equity["direction_inversions"] == crypto["direction_inversions"] == 0


@pytest.mark.parametrize("asset_class", tuple(AssetClass))
@pytest.mark.parametrize("timeframe", ("1m", "5m", "15m"))
def test_descending_triangle_short_timeframe_regression_gate(
    asset_class, timeframe
):
    window = int(timeframe_config(timeframe)["pattern_window"])
    false_positives = 0
    true_positives = 0
    for variant in range(VARIANTS_PER_PATTERN):
        neutral = TechnicalAnalysis.detect_chart_patterns(
            _neutral_chart(timeframe, asset_class, variant),
            window=window,
        )
        positive = TechnicalAnalysis.detect_chart_patterns(
            _chart_case("Descending Triangle", timeframe, asset_class, variant),
            window=window,
        )
        false_positives += any(
            item["pattern"] == "Descending Triangle" for item in neutral
        )
        true_positives += any(
            item["pattern"] == "Descending Triangle" for item in positive
        )

    assert false_positives / VARIANTS_PER_PATTERN <= 0.05
    assert true_positives / VARIANTS_PER_PATTERN >= 0.90


def test_real_aapl_1m_snapshot_no_longer_reports_descending_triangle():
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "phase9"
        / "stocks_AAPL_1min.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    detected = TechnicalAnalysis.detect_chart_patterns(
        [bar["c"] for bar in payload["bars"]],
        window=int(timeframe_config("1m")["pattern_window"]),
    )
    assert "Descending Triangle" not in {
        item["pattern"] for item in detected
    }


@pytest.mark.parametrize("timeframe", CANONICAL_TIMEFRAMES)
def test_candlestick_geometry_is_exactly_scale_invariant(timeframe):
    del timeframe  # detector is candle-local, but every declared timeframe is covered
    for pattern_index, pattern in enumerate(CANDLE_PATTERNS):
        equity = TechnicalAnalysis.detect_candlestick_patterns(
            *_candle_case(pattern, AssetClass.EQUITY, pattern_index)
        )
        crypto = TechnicalAnalysis.detect_candlestick_patterns(
            *_candle_case(pattern, AssetClass.CRYPTO, pattern_index)
        )
        assert {(item["pattern"], item["type"]) for item in equity} == {
            (item["pattern"], item["type"]) for item in crypto
        }


@pytest.mark.parametrize("timeframe", EXECUTABLE_CHART_TIMEFRAMES)
def test_chart_geometry_is_exactly_scale_invariant(timeframe):
    window = int(timeframe_config(timeframe)["pattern_window"])
    for pattern_index, pattern in enumerate(CHART_PATTERNS):
        equity = TechnicalAnalysis.detect_chart_patterns(
            _chart_case(pattern, timeframe, AssetClass.EQUITY, pattern_index),
            window=window,
        )
        crypto = TechnicalAnalysis.detect_chart_patterns(
            _chart_case(pattern, timeframe, AssetClass.CRYPTO, pattern_index),
            window=window,
        )
        assert {(item["pattern"], item["type"]) for item in equity} == {
            (item["pattern"], item["type"]) for item in crypto
        }


def test_numeric_features_and_boolean_boundaries_are_scale_invariant():
    equity_closes = [100 + index * 0.2 + ((index % 7) - 3) * 0.15 for index in range(240)]
    crypto_closes = [value * 400 for value in equity_closes]

    assert TechnicalAnalysis.calculate_rsi(crypto_closes) == pytest.approx(
        TechnicalAnalysis.calculate_rsi(equity_closes), rel=1e-10, abs=1e-8
    )
    for period in (20, 50, 200):
        assert TechnicalAnalysis.calculate_ema(crypto_closes, period) == pytest.approx(
            TechnicalAnalysis.calculate_ema(equity_closes, period) * 400,
            rel=1e-10,
            abs=1e-8,
        )
    equity_bands = TechnicalAnalysis.calculate_bollinger_bands(equity_closes)
    crypto_bands = TechnicalAnalysis.calculate_bollinger_bands(crypto_closes)
    assert crypto_bands == pytest.approx(
        tuple(value * 400 for value in equity_bands), rel=1e-10, abs=1e-8
    )
    equity_macd = TechnicalAnalysis.calculate_macd(equity_closes)
    crypto_macd = TechnicalAnalysis.calculate_macd(crypto_closes)
    assert crypto_macd == pytest.approx(
        tuple(value * 400 for value in equity_macd), rel=1e-10, abs=1e-8
    )
