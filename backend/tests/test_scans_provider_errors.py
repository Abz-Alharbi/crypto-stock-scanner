import pytest

from backend.errors import ApiError
from backend.services import scans


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
