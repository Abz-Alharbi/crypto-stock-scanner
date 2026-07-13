from dataclasses import dataclass

from backend.market_config import (
    CANONICAL_TIMEFRAMES,
    INTRADAY_TIMEFRAMES,
    TIMEFRAME_CHECK_SQL,
    TIMEFRAME_CONFIG,
    TIMEFRAME_MAP,
    data_limit_notice,
    is_intraday_timeframe,
    normalize_timeframe,
    public_timeframes,
    timeframe_config,
)


@dataclass(frozen=True)
class Timeframe:
    """Typed identity for one of the application's frozen timeframe keys."""

    value: str

    def __post_init__(self):
        normalized = normalize_timeframe(self.value)
        if normalized not in TIMEFRAME_CONFIG:
            raise ValueError(f"Unsupported timeframe: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    @classmethod
    def from_wire(cls, value: "Timeframe | str") -> "Timeframe":
        return value if isinstance(value, cls) else cls(value)

    @property
    def config(self):
        return timeframe_config(self.value)

    @property
    def is_intraday(self):
        return is_intraday_timeframe(self.value)

    def to_wire(self):
        return self.value

    def __str__(self):
        return self.value


def parse_timeframe(value):
    return Timeframe.from_wire(value)


__all__ = [
    "CANONICAL_TIMEFRAMES",
    "INTRADAY_TIMEFRAMES",
    "TIMEFRAME_CHECK_SQL",
    "TIMEFRAME_CONFIG",
    "TIMEFRAME_MAP",
    "Timeframe",
    "data_limit_notice",
    "is_intraday_timeframe",
    "normalize_timeframe",
    "parse_timeframe",
    "public_timeframes",
    "timeframe_config",
]
