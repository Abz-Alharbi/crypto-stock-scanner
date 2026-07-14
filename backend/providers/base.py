from datetime import date
from typing import Protocol, runtime_checkable

from backend.domain import AssetClass, Instrument, MarketDataRequest


@runtime_checkable
class MarketDataProvider(Protocol):
    """Provider-neutral market-data operations used by application services."""

    provider_id: str
    max_concurrent_requests: int

    @property
    def configured(self) -> bool: ...

    @property
    def last_error(self): ...

    def get_bars(self, request: MarketDataRequest, lookback=None) -> list[dict]: ...

    def search(
        self,
        query: str,
        asset_class: AssetClass,
        venue: str | None = None,
        limit: int = 20,
    ) -> list[dict]: ...

    def reference_universe(
        self,
        asset_class: AssetClass,
        venue: str | None,
        limit: int = 1000,
    ) -> list[dict]: ...

    def crypto_snapshot(self) -> list[dict]: ...

    def grouped_daily_stocks(self, day: date | str) -> list[dict]: ...

    def grouped_daily_crypto(self, day: date | str) -> list[dict]: ...

    def ticker_details(self, instrument: Instrument) -> dict | None: ...
