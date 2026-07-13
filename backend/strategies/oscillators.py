"""Oscillator strategies, preserving the legacy predicates."""

from backend.strategies.base import SignalDirection
from backend.strategies.legacy import register_legacy

register_legacy(
    identifier="rsi_oversold",
    display_name="RSI Oversold",
    description="RSI below 30",
    category="oscillators",
    predicate=lambda a: a["indicators"]["rsi"] is not None
    and a["indicators"]["rsi"] < 30,
    direction=SignalDirection.BULLISH,
    required_indicators=("rsi",),
    required_features=frozenset({"rsi"}),
)
register_legacy(
    identifier="rsi_overbought",
    display_name="RSI Overbought",
    description="RSI above 70",
    category="oscillators",
    predicate=lambda a: a["indicators"]["rsi"] is not None
    and a["indicators"]["rsi"] > 70,
    direction=SignalDirection.BEARISH,
    required_indicators=("rsi",),
    required_features=frozenset({"rsi"}),
)
register_legacy(
    identifier="stoch_oversold",
    display_name="Stochastic Oversold",
    description="Stochastic %K below 20",
    category="oscillators",
    predicate=lambda a: a["indicators"]["stochastic"]["k"] is not None
    and a["indicators"]["stochastic"]["k"] < 20,
    direction=SignalDirection.BULLISH,
    required_indicators=("stochastic",),
    required_features=frozenset({"stochastic"}),
)
register_legacy(
    identifier="stoch_overbought",
    display_name="Stochastic Overbought",
    description="Stochastic %K above 80",
    category="oscillators",
    predicate=lambda a: a["indicators"]["stochastic"]["k"] is not None
    and a["indicators"]["stochastic"]["k"] > 80,
    direction=SignalDirection.BEARISH,
    required_indicators=("stochastic",),
    required_features=frozenset({"stochastic"}),
)
