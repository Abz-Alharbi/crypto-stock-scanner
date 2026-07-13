import pytest

from backend.errors import ApiError
from backend.extensions import db
from backend.models.scan import ScanHistory, ScanResult
from backend.models.universe import UniverseSymbol
from backend.services import scans
from backend.services.universe.providers import UniverseResolution


def _set_scan_symbols(monkeypatch, symbols):
    def resolve(asset_class, universe_key=None):
        return UniverseResolution(
            universe_key or "us_stocks_top",
            asset_class,
            tuple(symbols),
            "test",
        )

    monkeypatch.setattr(scans, "resolve_scan_universe", resolve)


def _bars_with_bullish_engulfing():
    bars = []
    for index in range(138):
        base = 100 + (index * 0.1)
        bars.append({"t": index, "o": base, "h": base + 0.2, "l": base - 0.2, "c": base + 0.05, "v": 1000})
    bars.append({"t": 138, "o": 106, "h": 107, "l": 99, "c": 100, "v": 1000})
    bars.append({"t": 139, "o": 99, "h": 108, "l": 98, "c": 107, "v": 1000})
    return bars


def _bars_without_bearish_patterns():
    bars = []
    for index in range(140):
        base = 100 + (index * 0.1)
        bars.append({"t": index, "o": base, "h": base + 0.2, "l": base - 0.2, "c": base + 0.05, "v": 1000})
    return bars


def _short_bars(count=20):
    return [
        {"t": index, "o": 100 + index, "h": 102 + index, "l": 99 + index, "c": 101 + index, "v": 1000}
        for index in range(count)
    ]


def test_scan_market_reports_provider_failure_when_no_symbols_have_data(monkeypatch, fake_provider):
    fake_provider.fail(
        "get_bars",
        message="Unauthorized",
        error_type="http_error",
        status_code=401,
    )
    _set_scan_symbols(monkeypatch, ["AAPL", "MSFT"])

    with pytest.raises(ApiError) as exc:
        scans.scan_market("stocks", ["rsi_oversold"], "1D", 10)

    assert exc.value.code == "provider_data_unavailable"
    assert exc.value.status_code == 502
    assert exc.value.details["total_symbols"] == 2
    assert exc.value.details["attempted"] == 2
    assert exc.value.details["no_data"] == 0
    assert exc.value.details["scan_counters"]["provider_failures"] == 2
    assert exc.value.details["provider_error"]["status_code"] == 401
    assert exc.value.details["symbol_failures"][0] == {
        "symbol": "AAPL",
        "message": "Unauthorized",
        "provider": "fake",
        "operation": "get_bars",
        "error_type": "http_error",
        "status_code": 401,
        "instrument": "AAPL",
        "asset_class": "stocks",
        "timeframe": "1D",
    }


def test_bulk_bullish_pattern_scan_uses_ohlcv_and_never_yolov8(monkeypatch, app, fake_provider):
    from backend.services.patternDetection import yoloService

    fake_provider.default_bars = _bars_with_bullish_engulfing()
    _set_scan_symbols(monkeypatch, ["AAPL"])
    monkeypatch.setattr(yoloService, "detect_patterns", lambda *_args, **_kwargs: pytest.fail("YOLOv8 should not run in bulk scans"))

    with app.app_context():
        payload = scans.scan_market("stocks", ["bullish_pattern"], "1D", 10)

    assert payload["meta"]["total_scanned"] == 1
    assert payload["meta"]["bars_fetched"] == 1
    assert payload["meta"]["bars_usable"] == 1
    assert payload["meta"]["pattern_computation_attempted"] == 1
    assert payload["meta"]["pattern_detected_symbols"] == 1
    assert payload["meta"]["pattern_matched_symbols"] == 1
    assert payload["results"][0]["provider_symbol"] == "AAPL"
    assert payload["results"][0]["matched_filters"] == ["bullish_pattern"]
    assert "Bullish Engulfing" in payload["results"][0]["patterns"]


def test_bulk_pattern_scan_can_complete_with_zero_matches(monkeypatch, app, fake_provider):
    fake_provider.default_bars = _bars_without_bearish_patterns()
    _set_scan_symbols(monkeypatch, ["AAPL"])

    with app.app_context():
        payload = scans.scan_market("stocks", ["bearish_pattern"], "1D", 10)

    assert payload["results"] == []
    assert payload["meta"]["total_scanned"] == 1
    assert payload["meta"]["total_matched"] == 0
    assert payload["meta"]["bars_fetched"] == 1
    assert payload["meta"]["bars_usable"] == 1
    assert payload["meta"]["pattern_computation_attempted"] == 1
    assert payload["meta"]["pattern_computation_errors"] == 0


@pytest.mark.parametrize(
    ("timeframe", "multiplier", "timespan"),
    [("1m", 1, "minute"), ("5m", 5, "minute")],
)
def test_intraday_pattern_scans_use_canonical_timeframes_without_crashing(
    monkeypatch,
    app,
    fake_provider,
    timeframe,
    multiplier,
    timespan,
):
    fake_provider.default_bars = _bars_with_bullish_engulfing()
    _set_scan_symbols(monkeypatch, ["AAPL"])

    with app.app_context():
        payload = scans.scan_market("stocks", ["bullish_pattern"], timeframe, 10)

    assert payload["meta"]["total_scanned"] == 1
    assert payload["meta"]["pattern_computation_errors"] == 0
    assert payload["results"][0]["matched_filters"] == ["bullish_pattern"]
    request = next(call["request"] for call in fake_provider.calls if call["operation"] == "get_bars")
    assert request.timeframe.config["multiplier"] == multiplier
    assert request.timeframe.config["timespan"] == timespan
    assert payload["meta"]["data_limit_notices"] == []


def test_scan_market_reports_analysis_failure_separately(monkeypatch, fake_provider):
    class BrokenAnalysis:
        def full_analysis(self, _bars, **_kwargs):
            raise RuntimeError("pattern engine exploded")

    fake_provider.default_bars = _bars_without_bearish_patterns()
    monkeypatch.setattr(scans, "ta", BrokenAnalysis())
    _set_scan_symbols(monkeypatch, ["AAPL"])

    with pytest.raises(ApiError) as exc:
        scans.scan_market("stocks", ["bearish_pattern"], "1D", 10)

    assert exc.value.code == "scan_analysis_failed"
    assert exc.value.details["analysis_failures"] == 1
    assert exc.value.details["symbol_failures"][0]["symbol"] == "AAPL"


def test_stock_scan_uses_database_universe_when_available(app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()
    with app.app_context():
        db.session.add_all(
            [
                UniverseSymbol(symbol="AAA", exchange="NASDAQ", avg_daily_volume=1000, rank=1),
                UniverseSymbol(symbol="CCC", exchange="NYSE", avg_daily_volume=900, rank=1),
            ]
        )
        db.session.commit()

        payload = scans.scan_market("stocks", ["bullish_pattern"], "1D", 10)

    assert payload["meta"]["total_symbols"] == 2
    assert payload["meta"]["total_scanned"] == 2
    assert {result["provider_symbol"] for result in payload["results"]} == {"AAA", "CCC"}


def test_insufficient_only_scan_returns_explicit_outcomes(monkeypatch, app, fake_provider):
    fake_provider.default_bars = _short_bars()
    _set_scan_symbols(monkeypatch, ["AAPL", "MSFT"])

    with app.app_context():
        payload = scans.scan_market("stocks", ["rsi_oversold"], "1D", 10)

    assert payload["meta"]["total_attempted"] == 2
    assert payload["meta"]["no_data"] == 0
    assert payload["meta"]["insufficient_data"] == 2
    assert {item["status"] for item in payload["meta"]["symbol_outcomes"]} == {
        "insufficient_data"
    }


def test_scan_rejects_unknown_filter_when_one_filter_is_valid(monkeypatch, app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()
    _set_scan_symbols(monkeypatch, ["AAPL"])

    with app.app_context(), pytest.raises(ApiError) as exc_info:
        scans.scan_market("stocks", ["unknown_filter", "bullish_pattern"], "1D", 10)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "validation_error"
    assert "unknown_filter" in exc_info.value.message


def test_result_limit_is_applied_after_later_exchange_candidates(monkeypatch, app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()
    _set_scan_symbols(monkeypatch, ["NASDAQ_FIRST", "NYSE_REACHED"])

    with app.app_context():
        payload = scans.scan_market("stocks", ["bullish_pattern"], "1D", 1)

    assert payload["meta"]["total_symbols"] == 2
    assert payload["meta"]["total_attempted"] == 2
    assert [
        call["request"].instrument.provider_symbol
        for call in fake_provider.calls
        if call["operation"] == "get_bars"
    ] == ["NASDAQ_FIRST", "NYSE_REACHED"]
    assert [result["provider_symbol"] for result in payload["results"]] == ["NASDAQ_FIRST"]


def test_scan_result_persistence_failure_is_an_explicit_error(monkeypatch, app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()
    _set_scan_symbols(monkeypatch, ["AAPL"])

    with app.app_context():
        original_add = db.session.add

        def fail_scan_result_add(instance):
            if isinstance(instance, ScanResult):
                raise RuntimeError("result persistence failed")
            return original_add(instance)

        monkeypatch.setattr(db.session, "add", fail_scan_result_add)
        payload = scans.scan_market("stocks", ["bullish_pattern"], "1D", 10)

        assert payload["results"] == []
        assert payload["meta"]["persistence_failures"][0]["stage"] == "add_scan_result"
        assert payload["meta"]["symbol_outcomes"][0]["status"] == "error"
        assert ScanResult.query.count() == 0
        assert ScanHistory.query.count() == 1


def test_scan_history_persistence_failure_raises_and_rolls_back(monkeypatch, app, fake_provider):
    fake_provider.default_bars = _bars_with_bullish_engulfing()
    _set_scan_symbols(monkeypatch, ["AAPL"])

    with app.app_context():
        original_add = db.session.add

        def fail_scan_history_add(instance):
            if isinstance(instance, ScanHistory):
                raise RuntimeError("history persistence failed")
            return original_add(instance)

        monkeypatch.setattr(db.session, "add", fail_scan_history_add)
        with pytest.raises(ApiError) as exc:
            scans.scan_market("stocks", ["bullish_pattern"], "1D", 10)

        assert exc.value.code == "persistence_error"
        assert ScanResult.query.count() == 0
        assert ScanHistory.query.count() == 0
