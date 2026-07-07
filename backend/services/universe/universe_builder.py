import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from flask import current_app, has_app_context
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from backend.clients.polygon import polygon
from backend.extensions import db
from backend.models.universe import UniverseSymbol
from backend.services.redis_store import get_redis_client
from backend.services.scan_jobs import SCAN_JOB_TIMEOUT_SECONDS, get_scan_queue

logger = logging.getLogger(__name__)

SCHEDULE_MARKER_KEY = "universe:refresh_scheduled"
EXCHANGE_CONFIG = {
    "NASDAQ": {"polygon_exchange": "XNAS", "target_config": "UNIVERSE_NASDAQ_SIZE"},
    "NYSE": {"polygon_exchange": "XNYS", "target_config": "UNIVERSE_NYSE_SIZE"},
}


def _config_value(name, default):
    if has_app_context():
        return current_app.config.get(name, default)
    return os.getenv(name, default)


def _int_config(name, default):
    return int(_config_value(name, default))


def _today_utc():
    return datetime.utcnow().date()


def _date_range(lookback_days):
    end_date = _today_utc() - timedelta(days=1)
    start_date = end_date - timedelta(days=max(lookback_days - 1, 0))
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _extract_symbol(item):
    return str(item.get("ticker") or item.get("symbol") or item.get("T") or "").upper().strip()


def fetch_eligible_symbols():
    eligible = {}
    counts = {}
    for exchange, config in EXCHANGE_CONFIG.items():
        rows = polygon.get_reference_tickers(config["polygon_exchange"])
        symbols = {
            symbol
            for item in rows
            for symbol in [_extract_symbol(item)]
            if symbol and str(item.get("type") or "CS").upper() == "CS"
        }
        eligible[exchange] = symbols
        counts[exchange] = len(symbols)
    logger.info(
        "universe_reference_tickers_fetched",
        extra={
            "nasdaq_count": counts.get("NASDAQ", 0),
            "nyse_count": counts.get("NYSE", 0),
        },
    )
    return eligible, counts


def _fetch_grouped_day(day):
    date_text = day.isoformat()
    try:
        return date_text, polygon.get_grouped_daily_stocks(date_text), None
    except Exception as exc:
        return date_text, [], str(exc)


def build_volume_history(eligible_symbols, lookback_days):
    volume_sum = defaultdict(float)
    volume_count = defaultdict(int)
    processed_days = 0
    skipped_days = 0
    skipped_samples = []
    dates = list(_date_range(lookback_days))
    max_workers = max(1, int(getattr(polygon, "max_concurrent_requests", _int_config("POLYGON_MAX_CONCURRENT_REQUESTS", 10))))

    symbol_exchange = {}
    for exchange, symbols in eligible_symbols.items():
        for symbol in symbols:
            symbol_exchange[symbol] = exchange

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_grouped_day, day): day for day in dates}
        for future in as_completed(future_map):
            date_text, rows, error = future.result()
            if error or not rows:
                skipped_days += 1
                if len(skipped_samples) < 10:
                    skipped_samples.append({"date": date_text, "error": error or "no grouped data"})
                logger.info(
                    "universe_grouped_day_skipped",
                    extra={"date": date_text, "error": error or "no grouped data"},
                )
                continue

            processed_days += 1
            for row in rows:
                symbol = _extract_symbol(row)
                exchange = symbol_exchange.get(symbol)
                if not exchange:
                    continue
                volume = row.get("v")
                if volume is None:
                    continue
                try:
                    volume_sum[symbol] += float(volume)
                    volume_count[symbol] += 1
                except (TypeError, ValueError):
                    continue

    logger.info(
        "universe_grouped_days_processed",
        extra={
            "lookback_days": lookback_days,
            "processed_days": processed_days,
            "skipped_days": skipped_days,
            "skipped_samples": skipped_samples,
        },
    )
    return volume_sum, volume_count, processed_days, skipped_days


def rank_symbols(eligible_symbols, volume_sum, volume_count, computed_at):
    ranked_records = []
    final_counts = {}
    for exchange, config in EXCHANGE_CONFIG.items():
        target_size = _int_config(config["target_config"], 500 if exchange == "NASDAQ" else 300)
        scored = []
        for symbol in eligible_symbols.get(exchange, set()):
            count = volume_count.get(symbol, 0)
            if count <= 0:
                continue
            scored.append((symbol, volume_sum[symbol] / count))

        scored.sort(key=lambda item: (-item[1], item[0]))
        selected = scored[:target_size]
        final_counts[exchange] = len(selected)
        if len(selected) < target_size:
            logger.warning(
                "universe_ranked_count_below_target",
                extra={"exchange": exchange, "target": target_size, "actual": len(selected)},
            )

        for rank, (symbol, avg_volume) in enumerate(selected, start=1):
            ranked_records.append(
                UniverseSymbol(
                    symbol=symbol,
                    exchange=exchange,
                    avg_daily_volume=avg_volume,
                    rank=rank,
                    computed_at=computed_at,
                )
            )
    return ranked_records, final_counts


def save_universe(records):
    try:
        UniverseSymbol.query.delete()
        db.session.bulk_save_objects(records)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def build_and_save_universe():
    started = time.time()
    lookback_days = _int_config("UNIVERSE_LOOKBACK_DAYS", 730)
    computed_at = datetime.utcnow()
    eligible_symbols, reference_counts = fetch_eligible_symbols()
    volume_sum, volume_count, processed_days, skipped_days = build_volume_history(eligible_symbols, lookback_days)
    records, final_counts = rank_symbols(eligible_symbols, volume_sum, volume_count, computed_at)

    logger.info(
        "universe_rebuild_verification",
        extra={
            "reference_counts": reference_counts,
            "processed_days": processed_days,
            "skipped_days": skipped_days,
            "final_counts": final_counts,
            "total_symbols": len(records),
            "lookback_days": lookback_days,
        },
    )
    save_universe(records)
    return {
        "reference_counts": reference_counts,
        "processed_days": processed_days,
        "skipped_days": skipped_days,
        "final_counts": final_counts,
        "total_symbols": len(records),
        "computed_at": computed_at.isoformat(),
        "duration_seconds": round(time.time() - started, 2),
    }


def get_scan_universe_symbols(fallback_symbols):
    try:
        rows = (
            UniverseSymbol.query.order_by(UniverseSymbol.exchange.asc(), UniverseSymbol.rank.asc())
            .all()
        )
    except RuntimeError:
        logger.warning("universe_lookup_without_app_context")
        return list(fallback_symbols)
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.warning(
            "universe_lookup_failed_using_fallback",
            extra={"error": str(exc), "fallback_count": len(fallback_symbols)},
        )
        return list(fallback_symbols)

    if not rows:
        logger.warning("universe_symbols_empty_using_fallback", extra={"fallback_count": len(fallback_symbols)})
        return list(fallback_symbols)
    return [row.symbol for row in rows]


def status_payload():
    total = UniverseSymbol.query.count()
    nasdaq_count = UniverseSymbol.query.filter_by(exchange="NASDAQ").count()
    nyse_count = UniverseSymbol.query.filter_by(exchange="NYSE").count()
    last_computed_at = db.session.query(func.max(UniverseSymbol.computed_at)).scalar()
    return {
        "total_symbols": total,
        "nasdaq_count": nasdaq_count,
        "nyse_count": nyse_count,
        "last_computed_at": last_computed_at.isoformat() if last_computed_at else None,
    }


def _refresh_interval_seconds():
    value = str(_config_value("UNIVERSE_REFRESH_CRON", "weekly")).strip().lower()
    if value == "weekly":
        return 7 * 24 * 60 * 60
    if value == "daily":
        return 24 * 60 * 60
    if value == "hourly":
        return 60 * 60
    try:
        return max(60, int(value))
    except ValueError:
        logger.warning("invalid_universe_refresh_cron", extra={"value": value, "fallback": "weekly"})
        return 7 * 24 * 60 * 60


def clear_universe_refresh_marker():
    client = get_redis_client()
    if client is not None:
        client.delete(SCHEDULE_MARKER_KEY)


def schedule_next_universe_rebuild(delay_seconds=None):
    delay = int(delay_seconds if delay_seconds is not None else _refresh_interval_seconds())
    client = get_redis_client()
    if client is None:
        return False

    marker_ttl = max(delay * 2, delay + 60)
    if not client.set(SCHEDULE_MARKER_KEY, "1", ex=marker_ttl, nx=True):
        return False

    from worker import rebuild_universe_job

    queue = get_scan_queue()
    queue.enqueue_in(
        timedelta(seconds=delay),
        rebuild_universe_job,
        job_id=f"universe-rebuild-{int(time.time())}",
        job_timeout=max(SCAN_JOB_TIMEOUT_SECONDS, 7200),
        result_ttl=delay,
        failure_ttl=delay,
    )
    logger.info("universe_rebuild_scheduled", extra={"delay_seconds": delay})
    return True


def ensure_universe_rebuild_scheduled():
    try:
        return schedule_next_universe_rebuild(60)
    except Exception as exc:
        logger.warning("Universe scheduler was not started: %s", exc)
        return False
