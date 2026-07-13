from collections import OrderedDict


TIMEFRAME_MAP = OrderedDict(
    [
        (
            "1m",
            {
                "label": "1 Minute",
                "short_label": "1m",
                "multiplier": 1,
                "timespan": "minute",
                "days": 5,
                "min_bars": 120,
                "pattern_window": 120,
                "category": "intraday",
            },
        ),
        (
            "5m",
            {
                "label": "5 Minutes",
                "short_label": "5m",
                "multiplier": 5,
                "timespan": "minute",
                "days": 10,
                "min_bars": 120,
                "pattern_window": 120,
                "category": "intraday",
            },
        ),
        (
            "15m",
            {
                "label": "15 Minutes",
                "short_label": "15m",
                "multiplier": 15,
                "timespan": "minute",
                "days": 21,
                "min_bars": 120,
                "pattern_window": 120,
                "category": "intraday",
            },
        ),
        (
            "30m",
            {
                "label": "30 Minutes",
                "short_label": "30m",
                "multiplier": 30,
                "timespan": "minute",
                "days": 45,
                "min_bars": 120,
                "pattern_window": 60,
                "category": "intraday",
            },
        ),
        (
            "45m",
            {
                "label": "45 Minutes",
                "short_label": "45m",
                "multiplier": 45,
                "timespan": "minute",
                "days": 60,
                "min_bars": 120,
                "pattern_window": 60,
                "category": "intraday",
            },
        ),
        (
            "1H",
            {
                "label": "1 Hour",
                "short_label": "1H",
                "multiplier": 1,
                "timespan": "hour",
                "days": 90,
                "min_bars": 120,
                "pattern_window": 60,
                "category": "intraday",
            },
        ),
        (
            "4H",
            {
                "label": "4 Hours",
                "short_label": "4H",
                "multiplier": 4,
                "timespan": "hour",
                "days": 240,
                "min_bars": 120,
                "pattern_window": 60,
                "category": "intraday",
            },
        ),
        (
            "1D",
            {
                "label": "1 Day",
                "short_label": "1D",
                "multiplier": 1,
                "timespan": "day",
                "days": 730,
                "min_bars": 120,
                "pattern_window": 60,
                "category": "higher",
            },
        ),
        (
            "1W",
            {
                "label": "1 Week",
                "short_label": "1W",
                "multiplier": 1,
                "timespan": "week",
                "days": 1825,
                "min_bars": 120,
                "pattern_window": 52,
                "category": "higher",
            },
        ),
        (
            "1M",
            {
                "label": "1 Month",
                "short_label": "1M",
                "multiplier": 1,
                "timespan": "month",
                "days": 3650,
                "min_bars": 120,
                "pattern_window": 36,
                "category": "higher",
            },
        ),
        (
            "1Y",
            {
                "label": "1 Year",
                "short_label": "1Y",
                "multiplier": 1,
                "timespan": "year",
                "days": 12775,
                "min_bars": 5,
                "pattern_window": 5,
                "category": "higher",
            },
        ),
    ]
)

TIMEFRAME_CONFIG = TIMEFRAME_MAP
CANONICAL_TIMEFRAMES = tuple(TIMEFRAME_MAP.keys())
INTRADAY_TIMEFRAMES = {
    key for key, config in TIMEFRAME_MAP.items() if config["category"] == "intraday"
}
TIMEFRAME_CHECK_SQL = "timeframe IN ({})".format(
    ", ".join(f"'{key}'" for key in CANONICAL_TIMEFRAMES)
)


def normalize_timeframe(value):
    # Timeframes are intentionally case-sensitive: 1m is minute, 1M is month.
    return str(value or "").strip()


def is_intraday_timeframe(timeframe):
    return timeframe in INTRADAY_TIMEFRAMES


def timeframe_config(timeframe):
    return TIMEFRAME_MAP.get(timeframe)


def data_limit_notice(timeframe, bar_count):
    config = timeframe_config(timeframe)
    if not config or not is_intraday_timeframe(timeframe):
        return None
    minimum = int(config.get("min_bars", 0) or 0)
    if bar_count >= minimum:
        return None
    return f"Historical data for this timeframe is limited to {bar_count} bars"


def public_timeframes():
    return {
        key: {
            public_key: config[public_key]
            for public_key in ("label", "short_label", "multiplier", "timespan", "category")
            if public_key in config
        }
        for key, config in TIMEFRAME_MAP.items()
    }
