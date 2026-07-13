from dataclasses import dataclass

from backend.domain import AssetClass, Instrument, Timeframe


@dataclass(frozen=True)
class ProviderFailureContext:
    provider: str
    operation: str
    error_type: str
    status_code: int | None = None
    instrument: Instrument | None = None
    asset_class: AssetClass | None = None
    timeframe: Timeframe | None = None

    def to_dict(self):
        asset_class = self.asset_class or (self.instrument.asset_class if self.instrument else None)
        return {
            "provider": self.provider,
            "operation": self.operation,
            "error_type": self.error_type,
            "status_code": self.status_code,
            "instrument": self.instrument.provider_symbol if self.instrument else None,
            "asset_class": asset_class.value if asset_class else None,
            "timeframe": self.timeframe.value if self.timeframe else None,
        }


class ProviderError(Exception):
    """Typed provider failure that retains request and upstream context."""

    def __init__(
        self,
        message,
        *,
        provider,
        operation,
        error_type="provider_error",
        status_code=None,
        instrument=None,
        asset_class=None,
        timeframe=None,
        original_exception=None,
    ):
        super().__init__(message)
        self.message = str(message)
        self.context = ProviderFailureContext(
            provider=str(provider),
            operation=str(operation),
            error_type=str(error_type),
            status_code=status_code,
            instrument=instrument,
            asset_class=AssetClass.from_wire(asset_class) if asset_class is not None else None,
            timeframe=Timeframe.from_wire(timeframe) if timeframe is not None else None,
        )
        self.original_exception = original_exception

    def to_dict(self):
        return {"message": self.message, **self.context.to_dict()}
