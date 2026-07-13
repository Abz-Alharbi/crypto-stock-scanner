"""Volatility strategies."""

from backend.strategies.base import SignalDirection
from backend.strategies.legacy import register_legacy

register_legacy(
    identifier="bb_squeeze",
    display_name="Bollinger Squeeze",
    description="Price near lower Bollinger Band",
    category="volatility",
    predicate=lambda a: a["indicators"]["bollinger_bands"]["lower"] is not None
    and a["price"]["last"]
    <= a["indicators"]["bollinger_bands"]["lower"] * 1.02,
    direction=SignalDirection.BULLISH,
    required_indicators=("bollinger_bands",),
    required_features=frozenset({"bollinger_bands"}),
)
register_legacy(
    identifier="bb_breakout",
    display_name="Bollinger Breakout",
    description="Price above upper Bollinger Band",
    category="volatility",
    predicate=lambda a: a["indicators"]["bollinger_bands"]["upper"] is not None
    and a["price"]["last"]
    >= a["indicators"]["bollinger_bands"]["upper"] * 0.98,
    direction=SignalDirection.BULLISH,
    required_indicators=("bollinger_bands",),
    required_features=frozenset({"bollinger_bands"}),
)
