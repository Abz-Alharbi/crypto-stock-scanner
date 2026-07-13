import pytest
from pydantic import ValidationError

from backend.market_config import CANONICAL_TIMEFRAMES, TIMEFRAME_MAP
from backend.schemas.market import ChartQuery, ScanRequest


EXPECTED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "45m", "1H", "4H", "1D", "1W", "1M", "1Y")


def test_filters_endpoint_returns_exact_canonical_timeframes(client):
    response = client.get("/api/filters")

    assert response.status_code == 200
    timeframes = response.get_json()["timeframes"]
    assert tuple(timeframes.keys()) == EXPECTED_TIMEFRAMES
    assert tuple(CANONICAL_TIMEFRAMES) == EXPECTED_TIMEFRAMES
    assert timeframes["1m"]["multiplier"] == 1
    assert timeframes["1m"]["timespan"] == "minute"
    assert timeframes["1M"]["multiplier"] == 1
    assert timeframes["1M"]["timespan"] == "month"
    assert timeframes["4H"]["multiplier"] == 4
    assert timeframes["4H"]["timespan"] == "hour"
    assert timeframes["1Y"]["timespan"] == "year"


def test_timeframe_validation_is_case_sensitive():
    assert ChartQuery.model_validate({"timeframe": "1m"}).timeframe == "1m"
    assert ChartQuery.model_validate({"timeframe": "1M"}).timeframe == "1M"
    assert ScanRequest.model_validate(
        {"market": "stocks", "timeframe": "4H", "filters": ["macd_bullish"], "limit": 5}
    ).timeframe == "4H"

    with pytest.raises(ValidationError):
        ChartQuery.model_validate({"timeframe": "1MIN"})

    with pytest.raises(ValidationError):
        ChartQuery.model_validate({"timeframe": "1h"})


def test_timeframe_map_contains_only_canonical_keys():
    assert tuple(TIMEFRAME_MAP.keys()) == EXPECTED_TIMEFRAMES


def test_scan_request_accepts_registered_universe_and_ignores_future_context():
    request = ScanRequest.model_validate(
        {
            "market": "crypto",
            "timeframe": "1D",
            "filters": ["rsi_oversold"],
            "limit": 5,
            "asset_class": "crypto",
            "venue": "GLOBAL_CRYPTO",
            "universe": "crypto_static",
        }
    )

    assert request.model_dump() == {
        "market": "crypto",
        "timeframe": "1D",
        "filters": ["rsi_oversold"],
        "limit": 5,
        "universe": "crypto_static",
    }


def test_scan_request_rejects_unknown_or_cross_asset_universe():
    with pytest.raises(ValidationError, match="Unknown universe"):
        ScanRequest.model_validate(
            {
                "market": "crypto",
                "timeframe": "1D",
                "filters": ["rsi_oversold"],
                "universe": "crypto_usd_top",
            }
        )

    with pytest.raises(ValidationError, match="does not support crypto"):
        ScanRequest.model_validate(
            {
                "market": "crypto",
                "timeframe": "1D",
                "filters": ["rsi_oversold"],
                "universe": "nasdaq_top",
            }
        )
