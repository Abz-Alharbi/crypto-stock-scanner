"""Approved Phase 6 market calendars, lookbacks, and candle closure rules."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as exchange_calendars
import pandas as pd
from dateutil.relativedelta import relativedelta

from backend.domain.asset import AssetClass
from backend.domain.timeframes import Timeframe

EQUITY_TIMEZONE = ZoneInfo("America/New_York")
UTC = timezone.utc
FIXED_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "45m": 45,
    "1H": 60,
    "4H": 240,
}
CALENDAR_TIMEFRAMES = frozenset({"1D", "1W", "1M", "1Y"})


@dataclass(frozen=True)
class Lookback:
    start: datetime
    end: datetime
    required_bars: int
    target_bars: int
    cap_days: int
    capped: bool
    venue: str


@lru_cache(maxsize=2)
def equity_calendar(venue: str):
    normalized = str(venue or "XNYS").upper()
    if normalized not in {"XNAS", "XNYS"}:
        raise ValueError(f"Unsupported equity calendar venue: {venue}")
    return exchange_calendars.get_calendar(normalized)


def required_with_margin(required_bars: int) -> int:
    required = max(1, int(required_bars))
    return required + max(5, math.ceil(required * 0.10))


def _calendar_start(now: datetime, timeframe: str, target_bars: int) -> datetime:
    if timeframe == "1D":
        return now - timedelta(days=target_bars)
    if timeframe == "1W":
        return now - timedelta(weeks=target_bars)
    if timeframe == "1M":
        return now - relativedelta(months=target_bars)
    if timeframe == "1Y":
        return now - relativedelta(years=target_bars)
    raise ValueError(f"Not a calendar timeframe: {timeframe}")


def lookback_for(
    timeframe: Timeframe | str,
    required_bars: int,
    asset_class: AssetClass | str,
    *,
    venue: str | None = None,
    now: datetime | None = None,
) -> Lookback:
    parsed_timeframe = Timeframe.from_wire(timeframe)
    parsed_asset = AssetClass.from_wire(asset_class)
    end = now or datetime.now(UTC)
    end = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)
    target_bars = required_with_margin(required_bars)
    cap_days = int(parsed_timeframe.config["days"])
    cap_start = end - timedelta(days=cap_days)
    resolved_venue = venue or (
        "GLOBAL_CRYPTO" if parsed_asset is AssetClass.CRYPTO else "XNYS"
    )

    if parsed_timeframe.value in FIXED_MINUTES:
        minutes = FIXED_MINUTES[parsed_timeframe.value]
        if parsed_asset is AssetClass.CRYPTO:
            computed_start = end - timedelta(minutes=minutes * target_bars)
        else:
            calendar = equity_calendar(resolved_venue)
            bars_per_session = math.ceil(390 / minutes)
            sessions_needed = math.ceil(target_bars / bars_per_session) + 1
            sessions = calendar.sessions_in_range(cap_start.date(), end.date())
            if len(sessions) >= sessions_needed:
                computed_start = calendar.session_open(
                    sessions[-sessions_needed]
                ).to_pydatetime()
            else:
                computed_start = cap_start
    elif parsed_timeframe.value in CALENDAR_TIMEFRAMES:
        if parsed_asset is AssetClass.EQUITY and parsed_timeframe.value == "1D":
            calendar = equity_calendar(resolved_venue)
            sessions = calendar.sessions_in_range(cap_start.date(), end.date())
            sessions_needed = target_bars + 1
            if len(sessions) >= sessions_needed:
                computed_start = calendar.session_open(
                    sessions[-sessions_needed]
                ).to_pydatetime()
            else:
                computed_start = cap_start
        else:
            computed_start = _calendar_start(
                end,
                parsed_timeframe.value,
                target_bars,
            )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported timeframe: {parsed_timeframe.value}")

    start = max(computed_start.astimezone(UTC), cap_start)
    return Lookback(
        start=start,
        end=end,
        required_bars=max(1, int(required_bars)),
        target_bars=target_bars,
        cap_days=cap_days,
        capped=computed_start < cap_start,
        venue=resolved_venue,
    )


def _bar_datetime(bar) -> datetime | None:
    timestamp = bar.get("t")
    if not isinstance(timestamp, (int, float)) or timestamp < 946_684_800_000:
        return None
    return datetime.fromtimestamp(timestamp / 1000, tz=UTC)


def _session_bounds(calendar, value: datetime):
    label = pd.Timestamp(value.astimezone(EQUITY_TIMEZONE).date())
    if not calendar.is_session(label):
        return None
    return (
        calendar.session_open(label).to_pydatetime(),
        calendar.session_close(label).to_pydatetime(),
    )


def _equity_calendar_close(calendar, value: datetime, timeframe: str):
    local_date = value.astimezone(EQUITY_TIMEZONE).date()
    if timeframe == "1D":
        start_date = end_date = local_date
    elif timeframe == "1W":
        start_date = local_date - timedelta(days=local_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif timeframe == "1M":
        start_date = local_date.replace(day=1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
    elif timeframe == "1Y":
        start_date = local_date.replace(month=1, day=1)
        end_date = local_date.replace(month=12, day=31)
    else:  # pragma: no cover
        raise ValueError(timeframe)
    sessions = calendar.sessions_in_range(start_date, end_date)
    if not len(sessions):
        return None
    return calendar.session_close(sessions[-1]).to_pydatetime()


def _crypto_calendar_close(value: datetime, timeframe: str):
    start = value.astimezone(UTC)
    if timeframe == "1D":
        boundary = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return boundary + timedelta(days=1)
    if timeframe == "1W":
        boundary = (start - timedelta(days=start.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return boundary + timedelta(weeks=1)
    if timeframe == "1M":
        boundary = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return boundary + relativedelta(months=1)
    if timeframe == "1Y":
        boundary = start.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return boundary + relativedelta(years=1)
    raise ValueError(timeframe)


def normalize_bars(
    bars,
    timeframe: Timeframe | str,
    asset_class: AssetClass | str,
    *,
    venue: str | None = None,
    now: datetime | None = None,
):
    """Sort/deduplicate bars, enforce sessions, and label partial candles."""
    parsed_timeframe = Timeframe.from_wire(timeframe)
    parsed_asset = AssetClass.from_wire(asset_class)
    current = now or datetime.now(UTC)
    current = (
        current.replace(tzinfo=UTC)
        if current.tzinfo is None
        else current.astimezone(UTC)
    )
    calendar = (
        equity_calendar(venue or "XNYS")
        if parsed_asset is AssetClass.EQUITY
        else None
    )

    by_timestamp = {}
    for original in bars or []:
        bar = dict(original)
        value = _bar_datetime(bar)
        if value is None:
            bar["partial"] = bool(bar.get("partial", False))
            by_timestamp[bar.get("t", len(by_timestamp))] = bar
            continue

        if parsed_timeframe.value in FIXED_MINUTES:
            natural_close = value + timedelta(
                minutes=FIXED_MINUTES[parsed_timeframe.value]
            )
            if parsed_asset is AssetClass.EQUITY:
                bounds = _session_bounds(calendar, value)
                if bounds is None:
                    continue
                session_open, session_close = bounds
                if value < session_open or value >= session_close:
                    continue
                candle_close = min(natural_close, session_close)
            else:
                candle_close = natural_close
        elif parsed_asset is AssetClass.EQUITY:
            candle_close = _equity_calendar_close(
                calendar,
                value,
                parsed_timeframe.value,
            )
            if candle_close is None:
                continue
        else:
            candle_close = _crypto_calendar_close(value, parsed_timeframe.value)

        bar["partial"] = current < candle_close
        by_timestamp[bar["t"]] = bar

    return [by_timestamp[key] for key in sorted(by_timestamp)]


def closed_bars(bars):
    return [bar for bar in bars or [] if not bar.get("partial", False)]


__all__ = [
    "CALENDAR_TIMEFRAMES",
    "EQUITY_TIMEZONE",
    "FIXED_MINUTES",
    "Lookback",
    "closed_bars",
    "equity_calendar",
    "lookback_for",
    "normalize_bars",
    "required_with_margin",
]
