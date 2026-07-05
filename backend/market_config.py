TIMEFRAME_CONFIG = {
    "1min": {
        "label": "1 Minute",
        "short_label": "1m",
        "multiplier": 1,
        "timespan": "minute",
        "days": 1,
        "available": False,
        "reason": "Requires Polygon.io paid plan",
        "category": "intraday",
    },
    "5min": {
        "label": "5 Minutes",
        "short_label": "5m",
        "multiplier": 5,
        "timespan": "minute",
        "days": 2,
        "available": False,
        "reason": "Requires Polygon.io paid plan",
        "category": "intraday",
    },
    "15min": {
        "label": "15 Minutes",
        "short_label": "15m",
        "multiplier": 15,
        "timespan": "minute",
        "days": 5,
        "available": False,
        "reason": "Requires Polygon.io paid plan",
        "category": "intraday",
    },
    "30min": {
        "label": "30 Minutes",
        "short_label": "30m",
        "multiplier": 30,
        "timespan": "minute",
        "days": 10,
        "available": False,
        "reason": "Requires Polygon.io paid plan",
        "category": "intraday",
    },
    "45min": {
        "label": "45 Minutes",
        "short_label": "45m",
        "multiplier": 45,
        "timespan": "minute",
        "days": 14,
        "available": False,
        "reason": "Requires Polygon.io paid plan",
        "category": "intraday",
    },
    "1H": {
        "label": "1 Hour",
        "short_label": "1H",
        "multiplier": 1,
        "timespan": "hour",
        "days": 30,
        "available": False,
        "reason": "Requires Polygon.io paid plan",
        "category": "intraday",
    },
    "1D": {
        "label": "1 Day",
        "short_label": "1D",
        "multiplier": 1,
        "timespan": "day",
        "days": 365,
        "available": True,
        "category": "higher",
    },
    "1W": {
        "label": "1 Week",
        "short_label": "1W",
        "multiplier": 1,
        "timespan": "week",
        "days": 730,
        "available": True,
        "category": "higher",
    },
    "1M": {
        "label": "1 Month",
        "short_label": "1M",
        "multiplier": 1,
        "timespan": "month",
        "days": 1825,
        "available": True,
        "category": "higher",
    },
    "1Y": {
        "label": "1 Year",
        "short_label": "1Y",
        "multiplier": 12,
        "timespan": "month",
        "days": 7300,
        "available": True,
        "category": "higher",
    },
}

TIMEFRAME_ALIASES = {key.lower(): key for key in TIMEFRAME_CONFIG}
INTRADAY_TIMEFRAMES = {
    key for key, config in TIMEFRAME_CONFIG.items() if config["category"] == "intraday"
}
TIMEFRAME_CHECK_SQL = "timeframe IN ({})".format(
    ", ".join(f"'{key}'" for key in TIMEFRAME_CONFIG)
)


def normalize_timeframe(value):
    normalized = str(value or "").strip()
    return TIMEFRAME_ALIASES.get(normalized.lower(), normalized)


def public_timeframes():
    return {
        key: {
            public_key: config[public_key]
            for public_key in ("label", "short_label", "available", "reason", "category")
            if public_key in config
        }
        for key, config in TIMEFRAME_CONFIG.items()
    }
