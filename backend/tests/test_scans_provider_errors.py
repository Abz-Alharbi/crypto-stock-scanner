import pytest

from backend.errors import ApiError
from backend.extensions import db
from backend.models.universe import UniverseSymbol
from backend.services import scans


def _bars_with_bullish_engulfing():
    bars = []
    for index in range(58):
        base = 100 + (index * 0.1)
        bars.append({"t": index, "o": base, "h": base + 0.2, "l": base - 0.2, "c": base + 0.05, "v": 1000})
    bars.append({"t": 58, "o": 106, "h": 107, "l": 99, "c": 100, "v": 1000})
    bars.append({"t": 59, "o": 99, "h": 108, "l": 98, "c": 107, "v": 1000})
    return bars


def _bars_without_bearish_patterns():
    bars = []
    for index in range(60):
        base = 100 + (index * 0.1)
        bars.append({"t": index, "o": base, "h": base + 0.2, "l": base - 0.2, "c": base + 0.05, "v": 1000})
    return bars


class EmptyPolygonClient:
    api_key = "test-polygon-key"

    def __init__(self):
        self.last_error = None

    def get_aggregates(self, symbol, timespan="day", multiplier=1, from_date=None, to_date=None):
        self.last_error = {
            "type": "http_error",
            "message": "Unauthorized",
            "status_code": 401,
        }
        return []


class StaticBarsPolygonClient:
    api_key = "test-polygon-key"
    last_error = None

    def __init__(self, bars):
        self.bars = bars

    def get_aggregates(self, symbol, timespan="day", multiplier=1, from_date=None, to_date=None):
        return self.bars


class RecordingBarsPolygonClient(StaticBarsPolygonClient):
    def __init__(self, bars):
        super().__init__(bars)
        self.calls = []

    def get_aggregates(self, symbol, timespan="day", multiplier=1, from_date=None, to_date=None):
        self.calls.append(
            {
                "symbol": symbol,
                "timespan": timespan,
                "multiplier": multiplier,
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        return self.bars


def test_scan_market_reports_provider_failure_when_no_symbols_have_data(monkeypatch):
    polygon = EmptyPolygonClient()

    monkeypatch.setattr(scans, "polygon", polygon)
    monkeypatch.setattr(scans, "ALL_STOCK_SYMBOLS", ["AAPL", "MSFT"])

    with pytest.raises(ApiError) as exc:
        scans.scan_market("stocks", ["rsi_oversold"], "1D", 10)

    assert exc.value.code == "provider_data_unavailable"
    assert exc.value.status_code == 502
    assert exc.value.details["total_symbols"] == 2
    assert exc.value.details["attempted"] == 2
    assert exc.value.details["no_data"] == 2
    assert exc.value.details["provider_error"]["status_code"] == 401


def test_bulk_bullish_pattern_scan_uses_ohlcv_and_never_yolov8(monkeypatch, app):
    from backend.services.patternDetection import yoloService

    monkeypatch.setattr(scans, "polygon", StaticBarsPolygonClient(_bars_with_bullish_engulfing()))
    monkeypatch.setattr(scans, "ALL_STOCK_SYMBOLS", ["AAPL"])
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


def test_bulk_pattern_scan_can_complete_with_zero_matches(monkeypatch, app):
    monkeypatch.setattr(scans, "polygon", StaticBarsPolygonClient(_bars_without_bearish_patterns()))
    monkeypatch.setattr(scans, "ALL_STOCK_SYMBOLS", ["AAPL"])

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
def test_intraday_pattern_scans_use_canonical_timeframes_without_crashing(monkeypatch, app, timeframe, multiplier, timespan):
    polygon = RecordingBarsPolygonClient(_bars_with_bullish_engulfing())
    monkeypatch.setattr(scans, "polygon", polygon)
    monkeypatch.setattr(scans, "ALL_STOCK_SYMBOLS", ["AAPL"])

    with app.app_context():
        payload = scans.scan_market("stocks", ["bullish_pattern"], timeframe, 10)

    assert payload["meta"]["total_scanned"] == 1
    assert payload["meta"]["pattern_computation_errors"] == 0
    assert payload["results"][0]["matched_filters"] == ["bullish_pattern"]
    assert polygon.calls[0]["multiplier"] == multiplier
    assert polygon.calls[0]["timespan"] == timespan
    assert payload["meta"]["data_limit_notices"] == [
        "Historical data for this timeframe is limited to 60 bars"
    ]


def test_scan_market_reports_analysis_failure_separately(monkeypatch):
    class BrokenAnalysis:
        def full_analysis(self, _bars):
            raise RuntimeError("pattern engine exploded")

    monkeypatch.setattr(scans, "polygon", StaticBarsPolygonClient(_bars_without_bearish_patterns()))
    monkeypatch.setattr(scans, "ta", BrokenAnalysis())
    monkeypatch.setattr(scans, "ALL_STOCK_SYMBOLS", ["AAPL"])

    with pytest.raises(ApiError) as exc:
        scans.scan_market("stocks", ["bearish_pattern"], "1D", 10)

    assert exc.value.code == "scan_analysis_failed"
    assert exc.value.details["analysis_failures"] == 1
    assert exc.value.details["symbol_failures"][0]["symbol"] == "AAPL"


def test_stock_scan_uses_database_universe_when_available(monkeypatch, app):
    monkeypatch.setattr(scans, "polygon", StaticBarsPolygonClient(_bars_with_bullish_engulfing()))
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
