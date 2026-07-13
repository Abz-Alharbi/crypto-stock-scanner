from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.domain.asset import AssetClass
from backend.domain.instrument import Instrument
from backend.domain.timeframes import Timeframe


@dataclass(frozen=True)
class MarketDataRequest:
    instrument: Instrument
    timeframe: Timeframe
    start: datetime | None = None
    end: datetime | None = None
    required_bars: int | None = None
    include_partial: bool = False

    def __post_init__(self):
        if not isinstance(self.instrument, Instrument):
            raise TypeError("instrument must be an Instrument")
        object.__setattr__(self, "timeframe", Timeframe.from_wire(self.timeframe))
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("Market-data start must be before end")
        if self.required_bars is not None and self.required_bars < 1:
            raise ValueError("required_bars must be positive")

    @property
    def asset_class(self):
        return self.instrument.asset_class

    @property
    def venue(self):
        return self.instrument.venue


class ScanScope(str, Enum):
    UNIVERSE = "universe"
    INSTRUMENT = "instrument"


@dataclass(frozen=True)
class ScanContext:
    asset_class: AssetClass
    venue: str
    timeframe: Timeframe
    scope: ScanScope
    universe: str | None = None
    instrument: Instrument | None = None

    def __post_init__(self):
        asset_class = AssetClass.from_wire(self.asset_class)
        timeframe = Timeframe.from_wire(self.timeframe)
        venue = str(self.venue or "").upper().strip()
        try:
            scope = self.scope if isinstance(self.scope, ScanScope) else ScanScope(self.scope)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported scan scope: {self.scope!r}") from exc

        if not venue:
            raise ValueError("venue is required")
        if scope is ScanScope.UNIVERSE:
            if not self.universe or self.instrument is not None:
                raise ValueError("Universe scope requires only a universe identifier")
        elif self.instrument is None or self.universe is not None:
            raise ValueError("Instrument scope requires only an instrument")

        if self.instrument is not None:
            if self.instrument.asset_class is not asset_class:
                raise ValueError("Instrument asset class does not match scan context")
            if self.instrument.venue != venue:
                raise ValueError("Instrument venue does not match scan context")

        object.__setattr__(self, "asset_class", asset_class)
        object.__setattr__(self, "venue", venue)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "scope", scope)
