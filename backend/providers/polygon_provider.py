from datetime import date, datetime
import logging

from backend.clients.polygon import polygon
from backend.domain import AssetClass, Instrument, MarketDataRequest
from backend.providers.errors import ProviderError

logger = logging.getLogger(__name__)


class PolygonProvider:
    """Domain adapter around the existing, unchanged PolygonClient."""

    provider_id = "polygon"

    def __init__(self, client=None):
        self.client = client or polygon

    @property
    def configured(self):
        return bool(self.client.api_key)

    @property
    def last_error(self):
        return getattr(self.client, "last_error", None)

    @property
    def max_concurrent_requests(self):
        return max(1, int(getattr(self.client, "max_concurrent_requests", 1)))

    @staticmethod
    def _date_wire(value):
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _provider_error(self, operation, *, instrument=None, asset_class=None, timeframe=None):
        error = self.last_error or {}
        return ProviderError(
            error.get("message") or f"Polygon {operation} failed",
            provider=self.provider_id,
            operation=operation,
            error_type=error.get("type") or "provider_error",
            status_code=error.get("status_code"),
            instrument=instrument,
            asset_class=asset_class,
            timeframe=timeframe,
        )

    def _call(
        self,
        operation,
        callback,
        *,
        instrument=None,
        asset_class=None,
        timeframe=None,
    ):
        try:
            result = callback()
        except ProviderError:
            logger.exception(
                "provider_delegate_typed_failure",
                extra={
                    "provider": self.provider_id,
                    "operation": operation,
                    "instrument": instrument.provider_symbol if instrument else None,
                    "asset_class": asset_class.value if asset_class else None,
                    "timeframe": timeframe.value if timeframe else None,
                },
            )
            raise
        except Exception as exc:
            logger.exception(
                "provider_delegate_failed",
                extra={
                    "provider": self.provider_id,
                    "operation": operation,
                    "instrument": instrument.provider_symbol if instrument else None,
                    "asset_class": asset_class.value if asset_class else None,
                    "timeframe": timeframe.value if timeframe else None,
                    "exception_type": type(exc).__name__,
                },
            )
            raise ProviderError(
                str(exc),
                provider=self.provider_id,
                operation=operation,
                error_type=type(exc).__name__,
                instrument=instrument,
                asset_class=asset_class,
                timeframe=timeframe,
                original_exception=exc,
            ) from exc
        if not result and self.last_error:
            raise self._provider_error(
                operation,
                instrument=instrument,
                asset_class=asset_class,
                timeframe=timeframe,
            )
        return result

    def get_bars(self, request: MarketDataRequest, lookback=None):
        if not isinstance(request, MarketDataRequest):
            raise TypeError("request must be a MarketDataRequest")
        start = request.start
        end = request.end
        if lookback is not None:
            start, end = lookback
        config = request.timeframe.config
        return self._call(
            "get_bars",
            lambda: self.client.get_aggregates(
                request.instrument.provider_symbol,
                config["timespan"],
                config["multiplier"],
                self._date_wire(start),
                self._date_wire(end),
            ),
            instrument=request.instrument,
            timeframe=request.timeframe,
        )

    def search(self, query, asset_class, venue=None, limit=20):
        parsed_asset_class = AssetClass.from_wire(asset_class)
        return self._call(
            "search",
            lambda: self.client.search_tickers(query, parsed_asset_class.value, limit=limit),
            asset_class=parsed_asset_class,
        )

    def reference_universe(self, asset_class, venue, limit=1000):
        parsed_asset_class = AssetClass.from_wire(asset_class)
        if parsed_asset_class is AssetClass.CRYPTO:
            return self._call(
                "reference_universe",
                lambda: self.client.get_reference_crypto_tickers(limit=limit),
                asset_class=parsed_asset_class,
            )
        if parsed_asset_class is not AssetClass.EQUITY or not venue:
            raise ProviderError(
                "Polygon equity reference universe requires an exchange venue",
                provider=self.provider_id,
                operation="reference_universe",
                error_type="unsupported_asset_class",
                asset_class=parsed_asset_class,
            )
        return self._call(
            "reference_universe",
            lambda: self.client.get_reference_tickers(venue, limit=limit),
            asset_class=parsed_asset_class,
        )

    def crypto_snapshot(self):
        return self._call(
            "crypto_snapshot",
            self.client.get_snapshot_crypto,
            asset_class=AssetClass.CRYPTO,
        )

    def grouped_daily_stocks(self, day):
        day_value = self._date_wire(day)
        return self._call(
            "grouped_daily_stocks",
            lambda: self.client.get_grouped_daily_stocks(day_value),
            asset_class=AssetClass.EQUITY,
        )

    def grouped_daily_crypto(self, day):
        day_value = self._date_wire(day)
        return self._call(
            "grouped_daily_crypto",
            lambda: self.client.get_grouped_daily_crypto(day_value),
            asset_class=AssetClass.CRYPTO,
        )

    def ticker_details(self, instrument: Instrument):
        if not isinstance(instrument, Instrument):
            raise TypeError("instrument must be an Instrument")
        return self._call(
            "ticker_details",
            lambda: self.client.get_ticker_details(instrument.provider_symbol),
            instrument=instrument,
        )
