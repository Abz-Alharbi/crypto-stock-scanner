import pytest

from backend.services.technical import TechnicalAnalysis


def test_authoritative_indicator_series_aligns_with_latest_analysis_values():
    bars = [
        {
            "t": index * 60_000,
            "o": 100 + index,
            "h": 102 + index,
            "l": 99 + index,
            "c": 101 + index + ((index % 5) - 2) * 0.25,
            "v": 1_000 + index,
        }
        for index in range(240)
    ]

    analysis = TechnicalAnalysis.full_analysis(bars)
    series = TechnicalAnalysis.indicator_series(bars)

    assert series["version"] == "technical-analysis-v1"
    assert series["ema"]["ema_200"][-1]["value"] == pytest.approx(
        analysis["indicators"]["ema"]["ema_200"], abs=0.01
    )
    assert series["bollinger_bands"]["upper"][-1]["value"] == pytest.approx(
        analysis["indicators"]["bollinger_bands"]["upper"], abs=0.01
    )
    assert series["macd"]["line"][-1]["value"] == pytest.approx(
        analysis["indicators"]["macd"]["line"], abs=0.0001
    )
    assert series["rsi"][-1]["value"] == pytest.approx(
        analysis["indicators"]["rsi"], abs=0.01
    )


def test_authoritative_indicator_series_excludes_partial_candles():
    bars = [
        {"t": index, "o": 1, "h": 2, "l": 0.5, "c": index + 1, "v": 1}
        for index in range(40)
    ]
    bars.append({"t": 999, "o": 1, "h": 2, "l": 0.5, "c": 999, "v": 1, "partial": True})

    series = TechnicalAnalysis.indicator_series(bars)

    assert all(point["t"] != 999 for point in series["rsi"])
    assert all(point["t"] != 999 for point in series["ema"]["ema_9"])


def test_sma_and_ema_calculations():
    prices = [1, 2, 3, 4, 5]

    assert TechnicalAnalysis.calculate_sma(prices, 3) == pytest.approx(4.0)
    assert TechnicalAnalysis.calculate_ema([1, 2, 3], 3) == pytest.approx(2.0)
    assert TechnicalAnalysis.calculate_sma([1, 2], 3) is None


def test_rsi_calculation_for_all_gains_and_losses():
    assert TechnicalAnalysis.calculate_rsi(list(range(1, 17)), period=14) == pytest.approx(100.0)
    assert TechnicalAnalysis.calculate_rsi(list(range(17, 1, -1)), period=14) == pytest.approx(0.0)
    assert TechnicalAnalysis.calculate_rsi([1, 2, 3], period=14) is None


def test_macd_returns_numeric_components_for_sufficient_history():
    macd_line, signal_line, histogram = TechnicalAnalysis.calculate_macd(list(range(1, 60)))

    assert macd_line is not None
    assert signal_line is not None
    assert histogram is not None
    assert macd_line > 0
    assert signal_line > 0


def test_macd_uses_sma_seeded_component_emas_and_signal_line():
    macd_line, signal_line, histogram = TechnicalAnalysis.calculate_macd(
        list(range(1, 35))
    )

    assert macd_line == pytest.approx(7.0)
    assert signal_line == pytest.approx(7.0)
    assert histogram == pytest.approx(0.0)


def test_bollinger_bands_for_constant_prices():
    upper, middle, lower = TechnicalAnalysis.calculate_bollinger_bands([5] * 20)

    assert upper == pytest.approx(5.0)
    assert middle == pytest.approx(5.0)
    assert lower == pytest.approx(5.0)


def test_ema_and_bollinger_goldens_use_mainstream_chart_conventions():
    assert TechnicalAnalysis.calculate_ema([1, 2, 3], 3) == pytest.approx(2.0)
    assert TechnicalAnalysis.calculate_ema([1, 2, 3, 6], 3) == pytest.approx(4.0)

    upper, middle, lower = TechnicalAnalysis.calculate_bollinger_bands(list(range(1, 21)), period=20, std_dev=2)
    assert middle == pytest.approx(10.5)
    assert upper == pytest.approx(22.032562594670797)
    assert lower == pytest.approx(-1.0325625946707966)


def test_full_analysis_preserves_valid_zero_rsi():
    bars = [
        {"t": index, "o": 100 - index, "h": 101 - index, "l": 98 - index, "c": 99 - index, "v": 1000}
        for index in range(60)
    ]

    assert TechnicalAnalysis.calculate_rsi([bar["c"] for bar in bars]) == pytest.approx(0.0)
    assert TechnicalAnalysis.full_analysis(bars)["indicators"]["rsi"] == 0.0


def test_stochastic_calculation_stays_within_bounds():
    highs = list(range(10, 24))
    lows = list(range(1, 15))
    closes = list(range(5, 19))

    k_value, d_value = TechnicalAnalysis.calculate_stochastic(highs, lows, closes)

    assert k_value == pytest.approx((18 - 1) / (23 - 1) * 100)
    assert 0 <= d_value <= 100
