"""Legacy filter presets, now owned by the strategy domain."""

FILTER_PRESETS = {
    "bullish_momentum": {
        "name": "Bullish Momentum",
        "description": "Stocks showing strong buying signals",
        "filters": [
            "rsi_oversold",
            "macd_bullish",
            "ema_golden_cross",
            "bullish_pattern",
        ],
    },
    "bearish_reversal": {
        "name": "Bearish Reversal",
        "description": "Stocks showing potential downturn",
        "filters": [
            "rsi_overbought",
            "macd_bearish",
            "ema_death_cross",
            "bearish_pattern",
        ],
    },
    "oversold_bounce": {
        "name": "Oversold Bounce",
        "description": "Deeply oversold with reversal potential",
        "filters": [
            "rsi_oversold",
            "stoch_oversold",
            "bb_squeeze",
            "near_fib_support",
        ],
    },
    "trend_following": {
        "name": "Trend Following",
        "description": "Strong uptrend with momentum",
        "filters": [
            "ema_golden_cross",
            "price_above_sma200",
            "macd_bullish",
        ],
    },
    "fib_golden_pocket": {
        "name": "Fibonacci Golden Pocket",
        "description": "Price in the 50-61.8% golden zone — highest probability reversal",
        "filters": ["fib_golden_zone", "fib_uptrend", "near_fib_support"],
    },
    "fib_confluence_play": {
        "name": "Fibonacci Confluence",
        "description": "Price near cluster of multiple Fibonacci levels (strong S/R)",
        "filters": ["fib_confluence_zone", "near_fib_support"],
    },
}
