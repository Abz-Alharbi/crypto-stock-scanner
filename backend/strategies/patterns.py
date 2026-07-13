"""Pattern strategies."""

from backend.strategies.base import SignalDirection
from backend.strategies.legacy import register_legacy

register_legacy(
    identifier="bullish_pattern",
    display_name="Bullish Pattern",
    description="Any bullish candlestick pattern detected",
    category="patterns",
    predicate=lambda a: any(
        p["type"] == "bullish" for p in a["patterns"]["candlestick"]
    ),
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"candlestick_patterns"}),
)
register_legacy(
    identifier="bearish_pattern",
    display_name="Bearish Pattern",
    description="Any bearish candlestick pattern detected",
    category="patterns",
    predicate=lambda a: any(
        p["type"] == "bearish" for p in a["patterns"]["candlestick"]
    ),
    direction=SignalDirection.BEARISH,
    required_features=frozenset({"candlestick_patterns"}),
)
register_legacy(
    identifier="chart_pattern_bullish",
    display_name="Bullish Chart Pattern",
    description="Bullish chart pattern (double bottom, flag, etc.)",
    category="patterns",
    predicate=lambda a: any(
        p["type"] == "bullish" for p in a["patterns"]["chart"]
    ),
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"chart_patterns"}),
)
