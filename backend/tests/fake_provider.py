from copy import deepcopy

from backend.domain import AssetClass, Instrument, MarketDataRequest
from backend.providers.errors import ProviderError


class FakeProvider:
    provider_id = "fake"
    configured = True
    max_concurrent_requests = 2

    def __init__(self, default_bars=None):
        self.default_bars = list(default_bars or [])
        self.bars_by_symbol = {}
        self.search_results = {AssetClass.EQUITY: [], AssetClass.CRYPTO: []}
        self.reference_results = {}
        self.crypto_snapshot_results = []
        self.grouped_daily_results = {}
        self.ticker_details_by_symbol = {}
        self.failure_specs = {}
        self.calls = []
        self._last_error = None

    @property
    def last_error(self):
        return self._last_error

    def fail(self, operation, *, message="Provider failure", error_type="provider_error", status_code=None):
        self.failure_specs[operation] = {
            "message": message,
            "error_type": error_type,
            "status_code": status_code,
        }

    def _record(self, operation, **payload):
        self.calls.append({"operation": operation, **payload})

    def _raise_if_configured(self, operation, *, instrument=None, asset_class=None, timeframe=None):
        spec = self.failure_specs.get(operation)
        if not spec:
            self._last_error = None
            return
        self._last_error = {
            "type": spec["error_type"],
            "message": spec["message"],
            "status_code": spec["status_code"],
        }
        raise ProviderError(
            spec["message"],
            provider=self.provider_id,
            operation=operation,
            error_type=spec["error_type"],
            status_code=spec["status_code"],
            instrument=instrument,
            asset_class=asset_class,
            timeframe=timeframe,
        )

    def get_bars(self, request: MarketDataRequest, lookback=None):
        if not isinstance(request, MarketDataRequest):
            raise TypeError("request must be a MarketDataRequest")
        self._record("get_bars", request=request, lookback=lookback)
        self._raise_if_configured(
            "get_bars",
            instrument=request.instrument,
            timeframe=request.timeframe,
        )
        return deepcopy(self.bars_by_symbol.get(request.instrument.provider_symbol, self.default_bars))

    def search(self, query, asset_class, venue=None, limit=20):
        parsed_asset_class = AssetClass.from_wire(asset_class)
        self._record("search", query=query, asset_class=parsed_asset_class, venue=venue, limit=limit)
        self._raise_if_configured("search", asset_class=parsed_asset_class)
        return deepcopy(self.search_results.get(parsed_asset_class, []))[:limit]

    def reference_universe(self, asset_class, venue, limit=1000):
        parsed_asset_class = AssetClass.from_wire(asset_class)
        self._record(
            "reference_universe",
            asset_class=parsed_asset_class,
            venue=venue,
            limit=limit,
        )
        self._raise_if_configured("reference_universe", asset_class=parsed_asset_class)
        return deepcopy(self.reference_results.get(venue, []))[:limit]

    def crypto_snapshot(self):
        self._record("crypto_snapshot")
        self._raise_if_configured("crypto_snapshot", asset_class=AssetClass.CRYPTO)
        return deepcopy(self.crypto_snapshot_results)

    def grouped_daily_stocks(self, day):
        day_value = day.isoformat() if hasattr(day, "isoformat") else str(day)
        self._record("grouped_daily_stocks", day=day_value)
        self._raise_if_configured("grouped_daily_stocks", asset_class=AssetClass.EQUITY)
        return deepcopy(self.grouped_daily_results.get(day_value, []))

    def ticker_details(self, instrument: Instrument):
        if not isinstance(instrument, Instrument):
            raise TypeError("instrument must be an Instrument")
        self._record("ticker_details", instrument=instrument)
        self._raise_if_configured("ticker_details", instrument=instrument)
        return deepcopy(self.ticker_details_by_symbol.get(instrument.provider_symbol))
