"""Moving-average and MACD strategies."""

from backend.strategies.base import SignalDirection
from backend.strategies.legacy import register_legacy

register_legacy(
    identifier="ema_golden_cross",
    display_name="EMA Golden Cross",
    description="EMA 50 above EMA 200",
    category="moving_averages",
    predicate=lambda a: a["indicators"]["ema"]["ema_50"] is not None
    and a["indicators"]["ema"]["ema_200"] is not None
    and a["indicators"]["ema"]["ema_50"]
    > a["indicators"]["ema"]["ema_200"],
    direction=SignalDirection.BULLISH,
    required_history=200,
    required_indicators=("ema_50", "ema_200"),
    required_features=frozenset({"ema"}),
)
register_legacy(
    identifier="ema_death_cross",
    display_name="EMA Death Cross",
    description="EMA 50 below EMA 200",
    category="moving_averages",
    predicate=lambda a: a["indicators"]["ema"]["ema_50"] is not None
    and a["indicators"]["ema"]["ema_200"] is not None
    and a["indicators"]["ema"]["ema_50"]
    < a["indicators"]["ema"]["ema_200"],
    direction=SignalDirection.BEARISH,
    required_history=200,
    required_indicators=("ema_50", "ema_200"),
    required_features=frozenset({"ema"}),
)
register_legacy(
    identifier="price_above_sma200",
    display_name="Price Above SMA 200",
    description="Current price above 200-day SMA",
    category="moving_averages",
    predicate=lambda a: a["indicators"]["sma"]["sma_200"] is not None
    and a["price"]["last"] > a["indicators"]["sma"]["sma_200"],
    direction=SignalDirection.BULLISH,
    required_history=200,
    required_indicators=("sma_200",),
    required_features=frozenset({"sma"}),
)
register_legacy(
    identifier="macd_bullish",
    display_name="MACD Bullish",
    description="MACD line above signal line",
    category="moving_averages",
    predicate=lambda a: a["indicators"]["macd"]["line"] is not None
    and a["indicators"]["macd"]["signal"] is not None
    and a["indicators"]["macd"]["line"] > a["indicators"]["macd"]["signal"],
    direction=SignalDirection.BULLISH,
    required_history=35,
    required_indicators=("macd",),
    required_features=frozenset({"macd"}),
)
register_legacy(
    identifier="macd_bearish",
    display_name="MACD Bearish",
    description="MACD line below signal line",
    category="moving_averages",
    predicate=lambda a: a["indicators"]["macd"]["line"] is not None
    and a["indicators"]["macd"]["signal"] is not None
    and a["indicators"]["macd"]["line"] < a["indicators"]["macd"]["signal"],
    direction=SignalDirection.BEARISH,
    required_history=35,
    required_indicators=("macd",),
    required_features=frozenset({"macd"}),
)
