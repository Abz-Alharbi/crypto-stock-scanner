"""Fibonacci strategies."""

from typing import Any, Mapping

from backend.strategies.base import SignalDirection
from backend.strategies.legacy import register_legacy


def fib_confluence(analysis: Mapping[str, Any]) -> bool:
    fib = analysis.get("fibonacci")
    if not fib:
        return False
    price = analysis["price"]["last"]
    for zone in fib.get("zones", []):
        if zone["strength"] >= 2 and abs(price - zone["mid"]) / price < 0.025:
            return True
    return False


register_legacy(
    identifier="near_fib_support",
    display_name="Near Fibonacci Support",
    description="Price within 2% of a Fibonacci support level",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("nearest_support") is not None
    and abs(a["price"]["last"] - a["fibonacci"]["nearest_support"])
    / a["price"]["last"]
    < 0.02,
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="near_fib_resistance",
    display_name="Near Fibonacci Resistance",
    description="Price within 2% of a Fibonacci resistance level",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("nearest_resistance") is not None
    and abs(a["price"]["last"] - a["fibonacci"]["nearest_resistance"])
    / a["price"]["last"]
    < 0.02,
    direction=SignalDirection.BEARISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="fib_golden_zone",
    display_name="In Golden Pocket (50-61.8%)",
    description="Price in the golden zone — highest probability reversal area",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("price_zone") == "golden_zone",
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="fib_shallow_retrace",
    display_name="Shallow Retracement (23.6-38.2%)",
    description="Price in shallow pullback — strong trend continuation signal",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("price_zone") == "shallow_retrace",
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="fib_deep_retrace",
    display_name="Deep Retracement (61.8-78.6%)",
    description="Price in deep retracement — potential bottom or trend change",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("price_zone") in ["deep_retrace", "very_deep"],
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="fib_uptrend",
    display_name="Fibonacci Uptrend",
    description="Fibonacci structure shows uptrend (swing low before swing high)",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("trend") == "uptrend",
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="fib_downtrend",
    display_name="Fibonacci Downtrend",
    description="Fibonacci structure shows downtrend (swing high before swing low)",
    category="fibonacci",
    predicate=lambda a: a.get("fibonacci") is not None
    and a["fibonacci"].get("trend") == "downtrend",
    direction=SignalDirection.BEARISH,
    required_features=frozenset({"fibonacci"}),
)
register_legacy(
    identifier="fib_confluence_zone",
    display_name="Fibonacci Confluence Zone",
    description="Price near a cluster of multiple Fibonacci levels (strong S/R)",
    category="fibonacci",
    predicate=fib_confluence,
    direction=SignalDirection.BULLISH,
    required_features=frozenset({"fibonacci"}),
)
