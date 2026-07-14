from backend.extensions import db
from backend.models.scan import ScanHistory, ScanResult
from backend.models.universe import UniverseSymbol
from backend.services import scans


def _bars_with_bullish_engulfing(count=140):
    bars = []
    for index in range(count - 2):
        base = 100 + (index * 0.1)
        bars.append({"t": index, "o": base, "h": base + 0.2, "l": base - 0.2, "c": base + 0.05, "v": 1000})
    bars.append({"t": count - 2, "o": 106, "h": 107, "l": 99, "c": 100, "v": 1000})
    bars.append({"t": count - 1, "o": 99, "h": 108, "l": 98, "c": 107, "v": 1000})
    return bars


def _short_trending_bars(count=40):
    return [
        {"t": index, "o": 100 + index, "h": 102 + index, "l": 99 + index, "c": 101 + index, "v": 1000}
        for index in range(count)
    ]


def test_current_crypto_scan_attempts_fixed_universe_and_persists_crypto_matches(app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()

    with app.app_context():
        payload = scans.scan_market("crypto", ["bullish_pattern"], "1D", 50, job_id="crypto-happy")
        persisted = ScanResult.query.order_by(ScanResult.id).all()
        history = ScanHistory.query.one()

    assert payload["meta"]["total_symbols"] == 15
    assert payload["meta"]["total_attempted"] == 15
    assert payload["meta"]["total_scanned"] == 15
    assert payload["meta"]["universe"] == "crypto_static"
    assert payload["meta"]["universe_source"] == "fallback"
    assert payload["meta"]["universe_degraded"] is True
    assert len(payload["results"]) == 15
    bar_calls = [call for call in fake_provider.calls if call["operation"] == "get_bars"]
    assert len(bar_calls) == 15
    assert all(call["request"].instrument.provider_symbol.startswith("X:") for call in bar_calls)
    assert all(result["market"] == "crypto" for result in payload["results"])
    assert all(result["provider_symbol"].startswith("X:") for result in payload["results"])
    assert len(persisted) == 15
    assert all(row.market == "crypto" and row.provider_symbol.startswith("X:") for row in persisted)
    assert history.market == "crypto"
    assert history.total_scanned == 15


def test_crypto_scan_uses_ranked_database_universe_and_keeps_context_labels(
    app, fake_provider
):
    fake_provider.default_bars = _bars_with_bullish_engulfing()

    with app.app_context():
        db.session.add_all(
            [
                UniverseSymbol(
                    symbol="X:BTCUSD",
                    asset_class="crypto",
                    venue="GLOBAL_CRYPTO",
                    quote_currency="USD",
                    universe_key="crypto_static",
                    avg_daily_volume=10_000_000,
                    rank=1,
                ),
                UniverseSymbol(
                    symbol="X:ETHUSD",
                    asset_class="crypto",
                    venue="GLOBAL_CRYPTO",
                    quote_currency="USD",
                    universe_key="crypto_static",
                    avg_daily_volume=5_000_000,
                    rank=2,
                ),
            ]
        )
        db.session.commit()

        payload = scans.scan_market(
            "crypto",
            ["bullish_pattern"],
            "1D",
            50,
            job_id="crypto-ranked",
        )

    assert payload["meta"]["universe"] == "crypto_static"
    assert payload["meta"]["universe_source"] == "database"
    assert payload["meta"]["universe_degraded"] is False
    assert payload["meta"]["market"] == "crypto"
    assert payload["meta"]["timeframe"] == "1D"
    assert payload["meta"]["total_attempted"] == 2
    assert {result["provider_symbol"] for result in payload["results"]} == {
        "X:BTCUSD",
        "X:ETHUSD",
    }


def test_current_crypto_intraday_scan_forwards_canonical_provider_mapping(app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()

    with app.app_context():
        payload = scans.scan_market("crypto", ["bullish_pattern"], "1m", 50, job_id="crypto-intraday")
        persisted_timeframes = {row.timeframe for row in ScanResult.query.all()}

    assert payload["meta"]["timeframe"] == "1m"
    assert payload["meta"]["total_attempted"] == 15
    bar_calls = [call for call in fake_provider.calls if call["operation"] == "get_bars"]
    assert len(bar_calls) == 15
    assert {call["request"].timeframe.config["multiplier"] for call in bar_calls} == {1}
    assert {call["request"].timeframe.config["timespan"] for call in bar_calls} == {"minute"}
    assert persisted_timeframes == {"1m"}


def test_crypto_long_history_filter_reports_explicit_insufficient_data(app, fake_provider):
    fake_provider.default_bars = _short_trending_bars()

    with app.app_context():
        payload = scans.scan_market("crypto", ["ema_golden_cross"], "1M", 50, job_id="crypto-short-history")

    assert payload["results"] == []
    assert payload["meta"]["total_attempted"] == 15
    assert payload["meta"]["total_scanned"] == 0
    assert payload["meta"]["insufficient_data"] == 15
    assert all(
        item["status"] == "insufficient_data"
        for item in payload["meta"]["symbol_outcomes"]
    )
    assert payload["meta"]["filters_applied"] == ["ema_golden_cross"]
