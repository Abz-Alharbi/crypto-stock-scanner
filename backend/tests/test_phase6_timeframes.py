from datetime import datetime, timezone

import pytest

from backend.domain import AssetClass
from backend.domain.market_calendar import lookback_for, normalize_bars
from backend.services import scans
from backend.services.universe.providers import UniverseResolution

UTC = timezone.utc


def _timestamp(value):
    return int(value.timestamp() * 1000)


def _bar(value):
    return {
        "t": _timestamp(value),
        "o": 100,
        "h": 102,
        "l": 99,
        "c": 101,
        "v": 1000,
    }


def _synthetic_bars(count):
    return [
        {"t": index, "o": 100, "h": 102, "l": 99, "c": 101, "v": 1000}
        for index in range(count)
    ]


def _one_symbol(monkeypatch, asset_class, symbol):
    monkeypatch.setattr(
        scans,
        "resolve_scan_universe",
        lambda _asset, universe_key=None: UniverseResolution(
            universe_key or ("crypto_static" if asset_class is AssetClass.CRYPTO else "nasdaq_top"),
            asset_class,
            (symbol,),
            "test",
            symbol_venues=((symbol, "GLOBAL_CRYPTO" if asset_class is AssetClass.CRYPTO else "XNAS"),),
        ),
    )


def test_daily_ema_200_computed_lookback_stays_within_safe_730_day_cap():
    now = datetime(2026, 7, 14, 16, tzinfo=UTC)
    result = lookback_for("1D", 200, AssetClass.EQUITY, venue="XNAS", now=now)

    assert result.cap_days == 730
    assert result.target_bars == 220
    assert result.capped is False
    assert 280 <= (result.end - result.start).days < 730


@pytest.mark.parametrize("timeframe", ["1M", "1Y"])
def test_1month_and_1year_ema_200_report_insufficient_data_for_five_year_depth(
    timeframe, app, fake_provider, monkeypatch
):
    symbol = "AAPL"
    fake_provider.default_bars = _synthetic_bars(61 if timeframe == "1M" else 5)
    _one_symbol(monkeypatch, AssetClass.EQUITY, symbol)

    with app.app_context():
        payload = scans.scan_market(
            "stocks", ["ema_golden_cross"], timeframe, 10
        )

    outcome = payload["meta"]["symbol_outcomes"][0]
    assert outcome["status"] == "insufficient_data"
    assert outcome["closed_bars"] < 200
    assert outcome["strategies"]["ema_golden_cross"]["status"] == "insufficient_data"
    assert payload["meta"]["provider_failures"] == 0


def test_1y_pattern_requiring_20_plus_bars_is_insufficient_not_false(
    app, fake_provider, monkeypatch
):
    symbol = "AAPL"
    fake_provider.default_bars = _synthetic_bars(5)
    _one_symbol(monkeypatch, AssetClass.EQUITY, symbol)

    with app.app_context():
        payload = scans.scan_market(
            "stocks", ["chart_pattern_bullish"], "1Y", 10
        )

    strategy = payload["meta"]["symbol_outcomes"][0]["strategies"][
        "chart_pattern_bullish"
    ]
    assert strategy["status"] == "insufficient_data"
    assert strategy["evidence"]["strategy_required_history"] >= 20
    assert payload["results"] == []


def test_equity_fixed_and_daily_partial_candles_respect_early_close():
    fixed = _bar(datetime(2026, 11, 27, 17, 30, tzinfo=UTC))
    premarket = _bar(datetime(2026, 11, 27, 13, 0, tzinfo=UTC))
    daily = _bar(datetime(2026, 11, 27, 5, 0, tzinfo=UTC))

    before_close = datetime(2026, 11, 27, 17, 45, tzinfo=UTC)
    at_close = datetime(2026, 11, 27, 18, 0, tzinfo=UTC)
    fixed_before = normalize_bars(
        [premarket, fixed], "1H", AssetClass.EQUITY, venue="XNYS", now=before_close
    )
    fixed_after = normalize_bars(
        [fixed], "1H", AssetClass.EQUITY, venue="XNYS", now=at_close
    )
    daily_before = normalize_bars(
        [daily], "1D", AssetClass.EQUITY, venue="XNYS", now=before_close
    )
    daily_after = normalize_bars(
        [daily], "1D", AssetClass.EQUITY, venue="XNYS", now=at_close
    )

    assert len(fixed_before) == 1  # pre-market was excluded
    assert fixed_before[0]["partial"] is True
    assert fixed_after[0]["partial"] is False
    assert daily_before[0]["partial"] is True
    assert daily_after[0]["partial"] is False


def test_crypto_fixed_and_monthly_partial_candles_use_utc_boundaries():
    fixed = _bar(datetime(2026, 7, 14, 12, 0, tzinfo=UTC))
    monthly = _bar(datetime(2026, 7, 1, 0, 0, tzinfo=UTC))

    fixed_before = normalize_bars(
        [fixed], "4H", AssetClass.CRYPTO, now=datetime(2026, 7, 14, 15, 59, tzinfo=UTC)
    )
    fixed_after = normalize_bars(
        [fixed], "4H", AssetClass.CRYPTO, now=datetime(2026, 7, 14, 16, 0, tzinfo=UTC)
    )
    month_before = normalize_bars(
        [monthly], "1M", AssetClass.CRYPTO, now=datetime(2026, 7, 31, 23, 59, tzinfo=UTC)
    )
    month_after = normalize_bars(
        [monthly], "1M", AssetClass.CRYPTO, now=datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
    )

    assert fixed_before[0]["partial"] is True
    assert fixed_after[0]["partial"] is False
    assert month_before[0]["partial"] is True
    assert month_after[0]["partial"] is False
