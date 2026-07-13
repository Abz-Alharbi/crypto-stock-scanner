"""Built-in strategy registration and public contract exports."""

from backend.strategies.base import (
    LegacyFilterStrategy,
    SignalDirection,
    Strategy,
    StrategyContext,
    StrategyParameterError,
    StrategyResult,
    StrategyStatus,
)
from backend.strategies.registry import (
    DuplicateStrategyError,
    StrategyRegistry,
    UnknownStrategyError,
    registry,
)

# Importing the package performs deterministic registration of built-ins.
from backend.strategies import fibonacci as _fibonacci  # noqa: F401, E402
from backend.strategies import moving_averages as _moving_averages  # noqa: F401, E402
from backend.strategies import oscillators as _oscillators  # noqa: F401, E402
from backend.strategies import patterns as _patterns  # noqa: F401, E402
from backend.strategies import rsi_overbought_oversold as _rsi_demo  # noqa: F401, E402
from backend.strategies import volatility as _volatility  # noqa: F401, E402

__all__ = [
    "DuplicateStrategyError",
    "LegacyFilterStrategy",
    "SignalDirection",
    "Strategy",
    "StrategyContext",
    "StrategyParameterError",
    "StrategyRegistry",
    "StrategyResult",
    "StrategyStatus",
    "UnknownStrategyError",
    "registry",
]
