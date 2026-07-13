import pytest

from backend.services.technical import TechnicalAnalysis


def test_sma_and_ema_calculations():
    prices = [1, 2, 3, 4, 5]

    assert TechnicalAnalysis.calculate_sma(prices, 3) == pytest.approx(4.0)
    assert TechnicalAnalysis.calculate_ema([1, 2, 3], 3) == pytest.approx(2.25)
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


def test_bollinger_bands_for_constant_prices():
    upper, middle, lower = TechnicalAnalysis.calculate_bollinger_bands([5] * 20)

    assert upper == pytest.approx(5.0)
    assert middle == pytest.approx(5.0)
    assert lower == pytest.approx(5.0)


def test_current_backend_ema_and_bollinger_goldens_use_pandas_conventions():
    assert TechnicalAnalysis.calculate_ema([1, 2, 3], 3) == pytest.approx(2.25)

    upper, middle, lower = TechnicalAnalysis.calculate_bollinger_bands(list(range(1, 21)), period=20, std_dev=2)
    assert middle == pytest.approx(10.5)
    assert upper == pytest.approx(22.33215956619923)
    assert lower == pytest.approx(-1.3321595661992323)


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
