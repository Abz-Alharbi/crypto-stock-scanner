import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from flask import current_app, has_app_context
from sqlalchemy import func

from backend.domain import AssetClass
from backend.extensions import db
from backend.models.universe import UniverseSymbol
from backend.providers import get_provider
from backend.services.redis_store import get_redis_client
from backend.services.redis_store import redis_get_json, redis_set_json
from backend.services.scan_jobs import SCAN_JOB_TIMEOUT_SECONDS, get_scan_queue
from backend.services.universe.registry import registry

logger = logging.getLogger(__name__)

SCHEDULE_MARKER_KEY = "universe:refresh_scheduled"
BUILD_STATUS_KEY = "universe:last_build_status"
EXCHANGE_CONFIG = {
    "NASDAQ": {"polygon_exchange": "XNAS", "target_config": "UNIVERSE_NASDAQ_SIZE"},
    "NYSE": {"polygon_exchange": "XNYS", "target_config": "UNIVERSE_NYSE_SIZE"},
}
_last_build_status = None


class UniverseCandidateError(ValueError):
    """Raised before persistence when a rebuild candidate is unsafe."""


def _set_build_status(**status):
    global _last_build_status
    _last_build_status = {**status, "recorded_at": datetime.utcnow().isoformat()}
    redis_set_json(BUILD_STATUS_KEY, _last_build_status)
    return _last_build_status


def _get_build_status():
    return redis_get_json(BUILD_STATUS_KEY) or _last_build_status


def _config_value(name, default):
    if has_app_context():
        return current_app.config.get(name, default)
    return os.getenv(name, default)


def _int_config(name, default):
    return int(_config_value(name, default))


def _float_config(name, default):
    return float(_config_value(name, default))


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


def fetch_eligible_symbols(provider=None):
    provider = provider or get_provider()
    eligible = {}
    counts = {}
    for exchange, config in EXCHANGE_CONFIG.items():
        rows = provider.reference_universe(
            AssetClass.EQUITY,
            config["polygon_exchange"],
        )
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


def _fetch_grouped_day(day, provider):
    date_text = day.isoformat()
    try:
        return date_text, provider.grouped_daily_stocks(date_text), None
    except Exception as exc:
        return date_text, [], str(exc)


def build_volume_history(eligible_symbols, lookback_days, provider=None):
    provider = provider or get_provider()
    volume_sum = defaultdict(float)
    volume_count = defaultdict(int)
    processed_days = 0
    skipped_days = 0
    skipped_samples = []
    dates = list(_date_range(lookback_days))
    max_workers = max(
        1,
        int(getattr(provider, "max_concurrent_requests", _int_config("POLYGON_MAX_CONCURRENT_REQUESTS", 10))),
    )

    symbol_exchange = {}
    for exchange, symbols in eligible_symbols.items():
        for symbol in symbols:
            symbol_exchange[symbol] = exchange

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_grouped_day, day, provider): day for day in dates}
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


def fetch_eligible_crypto_symbols(provider=None):
    provider = provider or get_provider()
    rows = provider.reference_universe(AssetClass.CRYPTO, None)
    symbols = {
        symbol
        for item in rows
        for symbol in [_extract_symbol(item)]
        if symbol
        # Massive's live crypto payload identifies the quote as currency_symbol
        # (for example BTC is base_currency_symbol and USD is currency_symbol).
        # The fallback retains compatibility with older/documented variants.
        and str(
            item.get("currency_symbol")
            or item.get("base_currency_symbol")
            or ""
        ).upper()
        == "USD"
    }
    logger.info(
        "crypto_universe_reference_tickers_fetched",
        extra={"crypto_usd_count": len(symbols)},
    )
    return symbols


def _fetch_crypto_grouped_day(day, provider):
    date_text = day.isoformat()
    try:
        return date_text, provider.grouped_daily_crypto(date_text), None
    except Exception as exc:
        return date_text, [], str(exc)


def build_crypto_volume_history(eligible_symbols, lookback_days, provider=None):
    """Accumulate daily USD notional as base volume multiplied by VWAP."""
    provider = provider or get_provider()
    notional_sum = defaultdict(float)
    volume_count = defaultdict(int)
    processed_days = 0
    skipped_days = 0
    invalid_rows = 0
    skipped_samples = []
    dates = list(_date_range(lookback_days))
    request_interval = (
        _float_config("UNIVERSE_CRYPTO_REQUEST_INTERVAL_SECONDS", 13.0)
        if getattr(provider, "provider_id", None) == "polygon"
        else 0.0
    )
    # Count the preceding reference-ticker request in the same rate window.
    previous_request_started = time.monotonic() if request_interval > 0 else None
    max_attempts = max(1, _int_config("UNIVERSE_CRYPTO_DATE_MAX_ATTEMPTS", 2))
    pending_dates = dates
    final_failures = []
    for attempt in range(1, max_attempts + 1):
        retry_dates = []
        failure_details = []
        for day in pending_dates:
            if request_interval > 0 and previous_request_started is not None:
                remaining = request_interval - (
                    time.monotonic() - previous_request_started
                )
                if remaining > 0:
                    time.sleep(remaining)
            previous_request_started = time.monotonic()
            date_text, rows, error = _fetch_crypto_grouped_day(day, provider)
            if error or not rows:
                retry_dates.append(day)
                failure_details.append(
                    {"date": date_text, "error": error or "no grouped data"}
                )
                continue

            processed_days += 1
            for row in rows:
                symbol = _extract_symbol(row)
                if symbol not in eligible_symbols:
                    continue
                try:
                    volume = float(row["v"])
                    vwap = float(row["vw"])
                except (KeyError, TypeError, ValueError):
                    invalid_rows += 1
                    continue
                if volume < 0 or vwap <= 0:
                    invalid_rows += 1
                    continue
                notional_sum[symbol] += volume * vwap
                volume_count[symbol] += 1

        if not retry_dates:
            final_failures = []
            break
        if attempt < max_attempts:
            logger.warning(
                "crypto_universe_grouped_dates_retrying",
                extra={
                    "attempt": attempt,
                    "remaining_dates": len(retry_dates),
                    "failure_samples": failure_details[:10],
                },
            )
            pending_dates = retry_dates
            continue
        final_failures = failure_details

    skipped_days = len(final_failures)
    skipped_samples = final_failures[:10]
    for failure in final_failures:
        logger.info("crypto_universe_grouped_day_skipped", extra=failure)

    logger.info(
        "crypto_universe_grouped_days_processed",
        extra={
            "lookback_days": lookback_days,
            "processed_days": processed_days,
            "skipped_days": skipped_days,
            "invalid_rows": invalid_rows,
            "skipped_samples": skipped_samples,
        },
    )
    return notional_sum, volume_count, processed_days, skipped_days


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
                    asset_class="equity",
                    venue=config["polygon_exchange"],
                    universe_key=(
                        "nasdaq_top" if exchange == "NASDAQ" else "nyse_top"
                    ),
                    exchange=exchange,
                    avg_daily_volume=avg_volume,
                    rank=rank,
                    computed_at=computed_at,
                )
            )
    return ranked_records, final_counts


def rank_crypto_symbols(
    eligible_symbols,
    notional_sum,
    volume_count,
    computed_at,
    *,
    window_days=None,
):
    target_size = _int_config("UNIVERSE_CRYPTO_SIZE", 100)
    denominator = int(
        window_days
        if window_days is not None
        else _int_config("UNIVERSE_CRYPTO_LOOKBACK_DAYS", 90)
    )
    if denominator <= 0:
        raise UniverseCandidateError("crypto ranking window must be positive")
    scored = []
    for symbol in eligible_symbols:
        count = volume_count.get(symbol, 0)
        if count <= 0:
            continue
        scored.append((symbol, notional_sum[symbol] / denominator))

    scored.sort(key=lambda item: (-item[1], item[0]))
    selected = scored[:target_size]
    if len(selected) < target_size:
        logger.warning(
            "crypto_universe_ranked_count_below_target",
            extra={"target": target_size, "actual": len(selected)},
        )

    records = [
        UniverseSymbol(
            symbol=symbol,
            asset_class="crypto",
            venue="GLOBAL_CRYPTO",
            quote_currency="USD",
            universe_key="crypto_static",
            exchange=None,
            avg_daily_volume=avg_notional_volume,
            rank=rank,
            computed_at=computed_at,
        )
        for rank, (symbol, avg_notional_volume) in enumerate(selected, start=1)
    ]
    return records, {"crypto_static": len(records)}


def validate_candidate(
    records,
    final_counts,
    computed_at,
    *,
    processed_days=None,
    expected_counts=None,
    minimum_processed_days=None,
):
    if not records:
        raise UniverseCandidateError("candidate universe is empty")
    if processed_days is not None and processed_days <= 0:
        raise UniverseCandidateError("candidate has no successfully processed market days")
    if (
        minimum_processed_days is not None
        and int(processed_days or 0) < int(minimum_processed_days)
    ):
        raise UniverseCandidateError(
            "candidate processed "
            f"{int(processed_days or 0)} days; required {int(minimum_processed_days)}"
        )

    if expected_counts is None:
        expected_counts = {
            exchange: _int_config(
                config["target_config"], 500 if exchange == "NASDAQ" else 300
            )
            for exchange, config in EXCHANGE_CONFIG.items()
        }
    for scope, expected in expected_counts.items():
        actual = int(final_counts.get(scope, 0))
        if actual < expected:
            raise UniverseCandidateError(
                f"candidate {scope} count {actual} is below required {expected}"
            )

    max_age = _int_config("UNIVERSE_MAX_CANDIDATE_AGE_SECONDS", 3600)
    age = max(0.0, (datetime.utcnow() - computed_at).total_seconds())
    if age > max_age:
        raise UniverseCandidateError(
            f"candidate is stale ({round(age)}s old; maximum {max_age}s)"
        )


def save_universe(
    records,
    *,
    final_counts=None,
    computed_at=None,
    processed_days=None,
    replace_universe_keys=None,
    expected_counts=None,
    minimum_processed_days=None,
):
    records = list(records)
    computed_at = computed_at or (
        max((record.computed_at for record in records), default=datetime.utcnow())
    )
    if final_counts is None:
        final_counts = {
            exchange: sum(record.exchange == exchange for record in records)
            for exchange in EXCHANGE_CONFIG
        }
    validate_candidate(
        records,
        final_counts,
        computed_at,
        processed_days=processed_days,
        expected_counts=expected_counts,
        minimum_processed_days=minimum_processed_days,
    )
    replacement_keys = set(replace_universe_keys or ())
    if not replacement_keys:
        replacement_keys = {record.universe_key for record in records}
    if not replacement_keys:
        raise UniverseCandidateError("candidate has no universe replacement scope")
    if any(record.universe_key not in replacement_keys for record in records):
        raise UniverseCandidateError(
            "candidate contains rows outside its universe replacement scope"
        )
    try:
        UniverseSymbol.query.filter(
            UniverseSymbol.universe_key.in_(replacement_keys)
        ).delete(synchronize_session=False)
        db.session.bulk_save_objects(records)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def build_and_save_universe():
    started = time.time()
    lookback_days = _int_config("UNIVERSE_LOOKBACK_DAYS", 730)
    computed_at = datetime.utcnow()
    market_data_provider = get_provider()
    universe_provider = registry.get("us_stocks_top")
    try:
        candidate = universe_provider.build_candidate(
            market_data_provider,
            lookback_days,
            computed_at,
        )
        records = candidate["records"]
        reference_counts = candidate["reference_counts"]
        processed_days = candidate["processed_days"]
        skipped_days = candidate["skipped_days"]
        final_counts = candidate["final_counts"]
    except Exception as exc:
        _set_build_status(
            status="failed",
            degraded=True,
            degraded_reason=f"{type(exc).__name__}: {exc}",
            retained_previous=True,
        )
        raise

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
    payload = {
        "reference_counts": reference_counts,
        "processed_days": processed_days,
        "skipped_days": skipped_days,
        "final_counts": final_counts,
        "total_symbols": len(records),
        "computed_at": computed_at.isoformat(),
        "duration_seconds": round(time.time() - started, 2),
    }
    try:
        save_universe(
            records,
            final_counts=final_counts,
            computed_at=computed_at,
            processed_days=processed_days,
        )
    except UniverseCandidateError as exc:
        logger.error(
            "universe_candidate_rejected_retaining_previous",
            extra={"reason": str(exc), **payload},
        )
        payload.update(
            {
                "status": "degraded",
                "degraded": True,
                "degraded_reason": str(exc),
                "retained_previous": True,
                "stored_symbols": UniverseSymbol.query.count(),
            }
        )
        _set_build_status(**payload)
        return payload

    payload.update(
        {
            "status": "healthy",
            "degraded": False,
            "degraded_reason": None,
            "retained_previous": False,
        }
    )
    _set_build_status(**payload)
    return payload


def build_and_save_crypto_universe():
    started = time.time()
    lookback_days = _int_config("UNIVERSE_CRYPTO_LOOKBACK_DAYS", 90)
    target_size = _int_config("UNIVERSE_CRYPTO_SIZE", 100)
    computed_at = datetime.utcnow()
    market_data_provider = get_provider()
    universe_provider = registry.get("crypto_static")
    try:
        candidate = universe_provider.build_candidate(
            market_data_provider,
            lookback_days,
            computed_at,
        )
        records = candidate["records"]
        reference_counts = candidate["reference_counts"]
        processed_days = candidate["processed_days"]
        skipped_days = candidate["skipped_days"]
        final_counts = candidate["final_counts"]
    except Exception as exc:
        _set_build_status(
            asset_class="crypto",
            status="failed",
            degraded=True,
            degraded_reason=f"{type(exc).__name__}: {exc}",
            retained_previous=True,
        )
        raise

    payload = {
        "asset_class": "crypto",
        "reference_counts": reference_counts,
        "processed_days": processed_days,
        "skipped_days": skipped_days,
        "final_counts": final_counts,
        "total_symbols": len(records),
        "lookback_days": lookback_days,
        "ranking_metric": "average_daily_usd_notional_volume",
        "computed_at": computed_at.isoformat(),
        "duration_seconds": round(time.time() - started, 2),
    }
    logger.info("crypto_universe_rebuild_verification", extra=payload)
    try:
        save_universe(
            records,
            final_counts=final_counts,
            computed_at=computed_at,
            processed_days=processed_days,
            replace_universe_keys={"crypto_static"},
            expected_counts={"crypto_static": target_size},
            minimum_processed_days=lookback_days,
        )
    except UniverseCandidateError as exc:
        logger.error(
            "crypto_universe_candidate_rejected_retaining_previous",
            extra={"reason": str(exc), **payload},
        )
        payload.update(
            {
                "status": "degraded",
                "degraded": True,
                "degraded_reason": str(exc),
                "retained_previous": True,
                "stored_symbols": UniverseSymbol.query.filter_by(
                    universe_key="crypto_static"
                ).count(),
            }
        )
        _set_build_status(**payload)
        return payload

    payload.update(
        {
            "status": "healthy",
            "degraded": False,
            "degraded_reason": None,
            "retained_previous": False,
        }
    )
    _set_build_status(**payload)
    return payload


def build_and_save_all_universes():
    """Run both asset-class refreshes from the shared scheduled job."""
    results = {}
    failures = []
    for asset_class, builder in (
        ("equity", build_and_save_universe),
        ("crypto", build_and_save_crypto_universe),
    ):
        try:
            results[asset_class] = builder()
        except Exception as exc:
            logger.exception(
                "scheduled_universe_rebuild_failed",
                extra={"asset_class": asset_class},
            )
            failures.append((asset_class, exc))
    if failures:
        detail = "; ".join(
            f"{asset_class}: {type(exc).__name__}: {exc}"
            for asset_class, exc in failures
        )
        _set_build_status(
            status="failed",
            degraded=True,
            degraded_reason=detail,
            retained_previous=True,
            assets=results,
        )
        raise RuntimeError(f"One or more universe rebuilds failed: {detail}") from failures[0][1]
    _set_build_status(
        status="healthy",
        degraded=False,
        degraded_reason=None,
        retained_previous=False,
        assets=results,
    )
    return results


def get_scan_universe_symbols(fallback_symbols):
    from backend.services.universe.registry import registry

    return list(
        registry.resolve(
            AssetClass.EQUITY,
            "us_stocks_top",
            fallback_symbols=fallback_symbols,
        ).symbols
    )


def status_payload():
    equity_total = UniverseSymbol.query.filter_by(asset_class="equity").count()
    crypto_count = UniverseSymbol.query.filter_by(asset_class="crypto").count()
    total_persisted = equity_total + crypto_count
    nasdaq_count = UniverseSymbol.query.filter_by(exchange="NASDAQ").count()
    nyse_count = UniverseSymbol.query.filter_by(exchange="NYSE").count()
    equity_last_computed_at = db.session.query(
        func.max(UniverseSymbol.computed_at)
    ).filter(UniverseSymbol.asset_class == "equity").scalar()
    crypto_last_computed_at = db.session.query(
        func.max(UniverseSymbol.computed_at)
    ).filter(UniverseSymbol.asset_class == "crypto").scalar()
    from backend.services.universe.registry import (
        fallback_for_universe,
        registry,
    )

    universes = {}
    for provider in registry.all():
        resolution = registry.resolve(
            provider.asset_class,
            provider.universe_key,
            fallback_symbols=fallback_for_universe(provider.universe_key),
        )
        universes[provider.universe_key] = {
            "key": provider.universe_key,
            "name": provider.display_name,
            "asset_class": provider.asset_class.value,
            "count": len(resolution.symbols),
            "source": resolution.source,
            "degraded": resolution.degraded,
            "degraded_reason": resolution.degraded_reason,
            "last_computed_at": (
                resolution.computed_at.isoformat()
                if resolution.computed_at
                else None
            ),
        }

    return {
        # Backwards-compatible equity fields retained for existing consumers.
        "total_symbols": equity_total,
        "total_persisted_symbols": total_persisted,
        "crypto_count": crypto_count,
        "nasdaq_count": nasdaq_count,
        "nyse_count": nyse_count,
        "last_computed_at": (
            equity_last_computed_at.isoformat() if equity_last_computed_at else None
        ),
        "crypto_last_computed_at": (
            crypto_last_computed_at.isoformat() if crypto_last_computed_at else None
        ),
        "universes": universes,
        "last_build": _get_build_status(),
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
