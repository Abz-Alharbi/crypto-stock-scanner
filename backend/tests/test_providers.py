from datetime import datetime, timezone

import pytest

from backend.domain import AssetClass, Instrument, MarketDataRequest, Timeframe
from backend.providers import MarketDataProvider, PolygonProvider, ProviderError, provider_override
from backend.providers import get_provider
from backend.tests.fake_provider import FakeProvider


class RecordingPolygonClient:
    api_key = "test-key"
    last_error = None
    max_concurrent_requests = 7

    def __init__(self, bars=None):
        self.bars = bars or [{"t": 1, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]
        self.calls = []

    def get_aggregates(self, ticker, timespan, multiplier, from_date, to_date):
        self.calls.append(
            {
                "operation": "get_aggregates",
                "ticker": ticker,
                "timespan": timespan,
                "multiplier": multiplier,
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        return self.bars

    def search_tickers(self, query, market, limit=20):
        self.calls.append(
            {"operation": "search_tickers", "query": query, "market": market, "limit": limit}
        )
        return [{"ticker": "AAPL", "market": "stocks"}]

    def get_reference_tickers(self, exchange, limit=1000):
        self.calls.append(
            {"operation": "get_reference_tickers", "exchange": exchange, "limit": limit}
        )
        return [{"ticker": "AAPL", "type": "CS"}]

    def get_reference_crypto_tickers(self, limit=1000):
        self.calls.append(
            {"operation": "get_reference_crypto_tickers", "limit": limit}
        )
        return [{"ticker": "X:BTCUSD", "base_currency_symbol": "USD"}]

    def get_snapshot_crypto(self):
        self.calls.append({"operation": "get_snapshot_crypto"})
        return [{"ticker": "X:BTCUSD"}]

    def get_grouped_daily_stocks(self, day):
        self.calls.append({"operation": "get_grouped_daily_stocks", "day": day})
        return [{"T": "AAPL", "v": 100}]

    def get_grouped_daily_crypto(self, day):
        self.calls.append({"operation": "get_grouped_daily_crypto", "day": day})
        return [{"T": "X:BTCUSD", "v": 2, "vw": 50_000}]

    def get_ticker_details(self, ticker):
        self.calls.append({"operation": "get_ticker_details", "ticker": ticker})
        return {"ticker": ticker, "market": "stocks"}


def _request():
    return MarketDataRequest(
        instrument=Instrument.for_equity("AAPL"),
        timeframe=Timeframe("4H"),
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        required_bars=60,
    )


def test_polygon_provider_and_fake_provider_are_contract_swappable():
    request = _request()
    bars = [{"t": 1, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]
    client = RecordingPolygonClient(bars)
    polygon_provider = PolygonProvider(client)
    fake_provider = FakeProvider(default_bars=bars)

    assert isinstance(polygon_provider, MarketDataProvider)
    assert isinstance(fake_provider, MarketDataProvider)
    assert polygon_provider.get_bars(request) == fake_provider.get_bars(request) == bars
    assert client.calls[0] == {
        "operation": "get_aggregates",
        "ticker": "AAPL",
        "timespan": "hour",
        "multiplier": 4,
        "from_date": "2026-01-01",
        "to_date": "2026-01-02",
    }
    fake_call = fake_provider.calls[0]
    assert fake_call["operation"] == "get_bars"
    assert fake_call["request"] == request


def test_polygon_provider_delegates_reference_search_snapshot_grouped_and_details():
    client = RecordingPolygonClient()
    provider = PolygonProvider(client)
    instrument = Instrument.for_equity("AAPL")

    assert provider.search("apple", AssetClass.EQUITY, limit=5)[0]["ticker"] == "AAPL"
    assert provider.reference_universe(AssetClass.EQUITY, "XNAS", limit=10)[0]["ticker"] == "AAPL"
    assert provider.reference_universe(AssetClass.CRYPTO, None, limit=10)[0]["ticker"] == "X:BTCUSD"
    assert provider.crypto_snapshot()[0]["ticker"] == "X:BTCUSD"
    assert provider.grouped_daily_stocks("2026-01-02")[0]["T"] == "AAPL"
    assert provider.grouped_daily_crypto("2026-01-02")[0]["T"] == "X:BTCUSD"
    assert provider.ticker_details(instrument)["ticker"] == "AAPL"


def test_provider_override_injects_and_restores_provider(fake_provider):
    original = get_provider()
    replacement = FakeProvider()

    with provider_override(replacement):
        assert get_provider() is replacement

    assert get_provider() is original
    assert original is fake_provider


def test_polygon_provider_preserves_original_exception_context():
    client = RecordingPolygonClient()
    original = RuntimeError("transport exploded")

    def fail(*_args, **_kwargs):
        raise original

    client.get_aggregates = fail
    provider = PolygonProvider(client)

    with pytest.raises(ProviderError) as exc:
        provider.get_bars(_request())

    assert exc.value.original_exception is original
    assert exc.value.to_dict() == {
        "message": "transport exploded",
        "provider": "polygon",
        "operation": "get_bars",
        "error_type": "RuntimeError",
        "status_code": None,
        "instrument": "AAPL",
        "asset_class": "stocks",
        "timeframe": "4H",
    }


def test_fake_provider_failure_retains_domain_request_context():
    provider = FakeProvider()
    provider.fail("get_bars", message="Unauthorized", error_type="http_error", status_code=401)

    with pytest.raises(ProviderError) as exc:
        provider.get_bars(_request())

    assert exc.value.to_dict()["instrument"] == "AAPL"
    assert exc.value.to_dict()["asset_class"] == "stocks"
    assert exc.value.to_dict()["timeframe"] == "4H"
    assert exc.value.to_dict()["status_code"] == 401
