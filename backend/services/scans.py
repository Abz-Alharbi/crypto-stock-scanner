import json
import logging
import os
import time
from datetime import datetime

from backend.domain import (
    AssetClass,
    Instrument,
    MarketDataRequest,
    Timeframe,
    closed_bars,
    lookback_for,
    normalize_bars,
)
from backend.errors import ApiError
from backend.extensions import db
from backend.market_config import TIMEFRAME_CONFIG, data_limit_notice, public_timeframes
from backend.models.scan import ScanHistory, ScanResult
from backend.providers import ProviderError, get_provider
from backend.services.cache import cache_get, cache_set
from backend.services.technical import TechnicalAnalysis
from backend.services.universe.registry import (
    fallback_for_universe,
    resolve_scan_universe,
)
from backend import strategy_runtime
from backend.symbols import canonicalize_symbol

logger = logging.getLogger(__name__)

ta = TechnicalAnalysis()


# ============================================================
# TIMEFRAME MAPPING
# ============================================================
TIMEFRAME_MAP = TIMEFRAME_CONFIG


def _scan_debug_enabled():
    return os.getenv("SCAN_DEBUG", "false").lower() == "true"


def _scan_debug_sample_limit():
    return int(os.getenv("SCAN_DEBUG_SAMPLE_LIMIT", "8"))


def _debug_scan_log(message, **payload):
    if _scan_debug_enabled():
        logger.info(message, extra=payload)


def get_bars_with_meta(
    symbol,
    timeframe='1D',
    *,
    required_bars=None,
    venue=None,
    now=None,
):
    """Fetch OHLCV bars for a symbol based on timeframe"""
    canonical = canonicalize_symbol(symbol)
    tf = TIMEFRAME_MAP.get(timeframe)
    if not tf:
        raise ApiError("Invalid timeframe", 400, "validation_error", {"timeframe": timeframe})
    asset_class = AssetClass.from_wire(canonical.market)
    minimum = int(tf.get("min_bars", 0) or 0)
    requirement = max(minimum, int(required_bars or minimum))
    lookback = lookback_for(
        Timeframe(timeframe),
        requirement,
        asset_class,
        venue=venue,
        now=now,
    )
    from_date = lookback.start.date().isoformat()
    to_date = lookback.end.date().isoformat()
    instrument = Instrument.from_wire(
        canonical.provider_symbol,
        asset_class,
        venue=lookback.venue,
    )
    request = MarketDataRequest(
        instrument=instrument,
        timeframe=Timeframe(timeframe),
        start=lookback.start,
        end=lookback.end,
    )
    bars = normalize_bars(
        get_provider().get_bars(request, lookback=(lookback.start, lookback.end)),
        timeframe,
        asset_class,
        venue=lookback.venue,
        now=lookback.end,
    )
    complete = closed_bars(bars)
    bar_count = len(bars)
    return bars, {
        "timeframe": timeframe,
        "from_date": from_date,
        "to_date": to_date,
        "bar_count": bar_count,
        "closed_bar_count": len(complete),
        "partial_bar_count": bar_count - len(complete),
        "required_bars": requirement,
        "target_bars": lookback.target_bars,
        "lookback_cap_days": lookback.cap_days,
        "lookback_capped": lookback.capped,
        "venue": lookback.venue,
        "data_limit_notice": data_limit_notice(timeframe, bar_count),
    }


def get_bars(symbol, timeframe='1D'):
    bars, _meta = get_bars_with_meta(symbol, timeframe)
    return bars


def _symbol_fields(symbol, market=None):
    canonical = canonicalize_symbol(symbol, market)
    return {
        "symbol": canonical.display_symbol,
        "raw_symbol": canonical.provider_symbol,
        "provider_symbol": canonical.provider_symbol,
        "display_symbol": canonical.display_symbol,
        "market": canonical.market,
        "canonical_symbol": canonical.to_dict(),
    }


def get_flat_filters():
    """Compatibility shim over the canonical strategy registry."""
    return strategy_runtime.get_flat_filters()


FILTER_PRESETS = strategy_runtime.FILTER_PRESETS


def health_payload():
    from backend.services.universe import status_payload as universe_status_payload

    universe_status = universe_status_payload()
    dynamic_stock_count = universe_status["total_symbols"]
    fallback_stock_count = len(fallback_for_universe("us_stocks_top"))
    fallback_crypto_count = len(fallback_for_universe("crypto_static"))
    stock_universe = universe_status["universes"]["us_stocks_top"]
    crypto_universe = universe_status["universes"]["crypto_static"]
    active_stock_count = stock_universe["count"]

    return {
        "status": "healthy",
        "api_key_configured": get_provider().configured,
        "stock_symbols": active_stock_count,
        "crypto_symbols": fallback_crypto_count,
        "fallback_stock_symbols": fallback_stock_count,
        "fallback_crypto_symbols": fallback_crypto_count,
        "universe_counts": {
            "stocks": {
                "active": active_stock_count,
                "dynamic": dynamic_stock_count,
                "fallback": fallback_stock_count,
                "using_fallback": stock_universe["source"] == "fallback",
                "nasdaq": universe_status["nasdaq_count"],
                "nyse": universe_status["nyse_count"],
                "last_computed_at": universe_status["last_computed_at"],
            },
            "crypto": {
                "active": crypto_universe["count"],
                "dynamic": 0,
                "fallback": fallback_crypto_count,
                "using_fallback": crypto_universe["source"] == "fallback",
                "last_computed_at": None,
            },
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


def filters_payload():
    timeframes = public_timeframes()
    plan_timeframes = strategy_runtime.available_timeframes()
    for key, value in timeframes.items():
        value["available"] = key in plan_timeframes
    return {
        "filters": strategy_runtime.filters_payload(),
        "presets": strategy_runtime.FILTER_PRESETS,
        "timeframes": timeframes,
    }


def search_tickers(query, market):
    query = query.strip()
    if not query:
        return {"results": []}
    results = get_provider().search(query, AssetClass.from_wire(market))
    payload = []
    for item in results[:15]:
        fields = _symbol_fields(item.get("ticker"), item.get("market") or market)
        payload.append(
            {
                **fields,
                "ticker": fields["provider_symbol"],
                "name": item.get("name"),
                "type": item.get("type"),
                "currency": item.get("currency_name"),
            }
        )
    return {"results": payload}


def stock_detail(symbol, timeframe):
    canonical = canonicalize_symbol(symbol)
    cache_key = f"detail:{canonical.provider_symbol}:{timeframe}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    bars, bars_meta = get_bars_with_meta(canonical.provider_symbol, timeframe)
    if not bars:
        raise ApiError(f"No data available for {canonical.display_symbol}", 404, "not_found")

    analysis = ta.full_analysis(bars, timeframe=timeframe)
    if not analysis:
        raise ApiError(f"Insufficient data for analysis of {canonical.display_symbol}", 400, "insufficient_data")

    instrument = Instrument.from_wire(
        canonical.provider_symbol,
        AssetClass.from_wire(canonical.market),
    )
    details = get_provider().ticker_details(instrument)
    result = {
        **_symbol_fields(canonical.provider_symbol, details.get("market") if details else canonical.market),
        "name": details.get("name", canonical.display_symbol) if details else canonical.display_symbol,
        "timeframe": timeframe,
        "data_limit_notice": bars_meta.get("data_limit_notice"),
        "analysis": analysis,
        "trade_setup": analysis.get("trade_setup"),
        "chart_data": [
            {
                "t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"],
                "c": b["c"], "v": b.get("v", 0), "partial": b.get("partial", False),
            }
            for b in bars
        ],
    }
    cache_set(cache_key, result, ttl=120)
    return result


def chart_data(symbol, timeframe):
    canonical = canonicalize_symbol(symbol)
    bars, bars_meta = get_bars_with_meta(canonical.provider_symbol, timeframe)
    if not bars:
        raise ApiError(f"No chart data for {canonical.display_symbol}", 404, "not_found")

    return {
        **_symbol_fields(canonical.provider_symbol, canonical.market),
        "timeframe": timeframe,
        "data_limit_notice": bars_meta.get("data_limit_notice"),
        "data": [
            {
                "t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"],
                "c": b["c"], "v": b.get("v", 0), "partial": b.get("partial", False),
            }
            for b in bars
        ],
    }


def _emit_scan_progress(progress_callback, **payload):
    if progress_callback:
        progress_callback(payload)


def scan_market(
    market,
    selected_filters,
    timeframe,
    max_results,
    user_id=None,
    job_id=None,
    progress_callback=None,
    universe_key=None,
):
    provider = get_provider()
    if not provider.configured:
        raise ApiError(
            "Polygon API key is not configured. Set POLYGON_API_KEY in Railway backend and worker variables.",
            503,
            "provider_not_configured",
        )

    asset_class = AssetClass.from_wire(market)
    try:
        universe_resolution = resolve_scan_universe(asset_class, universe_key)
        strategy_runtime.validate_strategy_selection(
            selected_filters,
            asset_class=asset_class,
            timeframe=Timeframe(timeframe),
        )
        selected_strategies = strategy_runtime.get_strategies(selected_filters)
    except ValueError as exc:
        raise ApiError(str(exc), 400, "validation_error") from exc
    symbols = list(universe_resolution.symbols)
    valid_filters = list(selected_filters)
    feature_names = strategy_runtime.required_features(selected_strategies)
    timeframe_minimum = int(TIMEFRAME_MAP[timeframe].get("min_bars", 0) or 0)
    required_bars = max(
        [timeframe_minimum]
        + [strategy.required_history for strategy in selected_strategies]
    )
    venue_by_symbol = dict(universe_resolution.symbol_venues)

    start_time = time.time()
    results = []
    pending_scan_rows = {}
    attempted = 0
    scanned = 0
    errors = 0
    no_data = 0
    insufficient_data = 0
    analysis_failures = 0
    bars_fetched = 0
    bars_usable = 0
    pattern_computation_attempted = 0
    pattern_computation_errors = 0
    pattern_detected_symbols = 0
    pattern_matched_symbols = 0
    filter_errors = []
    symbol_failures = []
    symbol_outcomes = []
    outcome_by_symbol = {}
    insufficient_data_symbols = []
    provider_failures = 0
    persistence_failures = []
    bar_counts = []
    data_limit_notices = set()
    total_symbols = len(symbols)
    pattern_filter_keys = [
        strategy.identifier
        for strategy in selected_strategies
        if strategy.category == "patterns"
    ]
    pattern_scan_requested = bool(pattern_filter_keys)

    logger.info(
        "scan_started",
        extra={
            "job_id": job_id,
            "market": market,
            "timeframe": timeframe,
            "total_symbols": total_symbols,
            "filters": valid_filters,
            "max_results": max_results,
            "universe": universe_resolution.universe_key,
            "universe_source": universe_resolution.source,
        },
    )

    _emit_scan_progress(progress_callback, progress=0, scanned=0, total=total_symbols)

    for index, symbol in enumerate(symbols, start=1):
        _emit_scan_progress(
            progress_callback,
            progress=max(1, int((index - 1) / total_symbols * 100)),
            current_symbol=symbol,
            scanned=scanned,
            matched=len(results),
            errors=errors,
            total=total_symbols,
        )

        try:
            attempted += 1
            bars, bars_meta = get_bars_with_meta(
                symbol,
                timeframe,
                required_bars=required_bars,
                venue=venue_by_symbol.get(symbol),
            )
            if bars_meta.get("data_limit_notice"):
                data_limit_notices.add(bars_meta["data_limit_notice"])
            bar_count = len(bars or [])
            complete_bars = closed_bars(bars)
            complete_count = len(complete_bars)
            if bars:
                bars_fetched += 1
                bar_counts.append(bar_count)
            if complete_count < required_bars:
                if not bars:
                    no_data += 1
                insufficient_data += 1
                strategy_outcomes = {
                    strategy.identifier: {
                        "strategy_id": strategy.identifier,
                        "strategy_version": strategy.version,
                        "status": "insufficient_data",
                        "evaluated": False,
                        "direction": "no_signal",
                        "score": None,
                        "confidence": None,
                        "explanation": (
                            f"Requires {required_bars} closed bars for the selected "
                            f"timeframe/strategies; received {complete_count}"
                        ),
                        "evidence": {
                            "required_history": required_bars,
                            "strategy_required_history": strategy.required_history,
                            "available_history": complete_count,
                            "lookback_capped": bars_meta["lookback_capped"],
                        },
                    }
                    for strategy in selected_strategies
                }
                outcome = {
                    "symbol": symbol,
                    "status": "insufficient_data",
                    "bars": bar_count,
                    "closed_bars": complete_count,
                    "required_bars": required_bars,
                    "strategies": strategy_outcomes,
                }
                symbol_outcomes.append(outcome)
                outcome_by_symbol[symbol] = outcome
                insufficient_data_symbols.append(
                    {
                        "symbol": symbol,
                        "bars": complete_count,
                        "required": required_bars,
                    }
                )
                logger.warning(
                    "scan_symbol_data_rejected",
                    extra={
                        "job_id": job_id,
                        "symbol": symbol,
                        "bars": complete_count,
                        "reason": "no_data" if not bars else "insufficient_data",
                        "provider_error": provider.last_error,
                    },
                )
                continue

            bars_usable += 1
            analysis = ta.full_analysis(
                complete_bars,
                features=feature_names,
                timeframe=timeframe,
            )
            if not analysis:
                analysis_failures += 1
                logger.warning(
                    "scan_symbol_analysis_empty",
                    extra={"job_id": job_id, "symbol": symbol, "bars": bar_count},
                )
                errors += 1
                outcome = {
                    "symbol": symbol,
                    "status": "error",
                    "bars": bar_count,
                    "closed_bars": complete_count,
                    "required_bars": required_bars,
                    "error": "Technical analysis returned no result",
                    "strategies": {},
                }
                symbol_outcomes.append(outcome)
                outcome_by_symbol[symbol] = outcome
                continue

            scanned += 1
            if pattern_scan_requested:
                pattern_computation_attempted += 1
                patterns = analysis.get("patterns") or {}
                candle_patterns = patterns.get("candlestick") or []
                chart_patterns = patterns.get("chart") or []
                if candle_patterns or chart_patterns:
                    pattern_detected_symbols += 1
            matched_filters = []
            strategy_results = {}
            all_strategy_results = {}
            context = strategy_runtime.StrategyContext(
                bars=complete_bars,
                analysis=analysis,
                asset_class=asset_class,
                timeframe=Timeframe(timeframe),
                instrument=Instrument.from_wire(
                    canonicalize_symbol(symbol, market).provider_symbol,
                    asset_class,
                    venue=venue_by_symbol.get(symbol),
                ),
            )
            for strategy in selected_strategies:
                strategy_result = strategy.evaluate(context)
                all_strategy_results[strategy.identifier] = strategy_result.to_dict()
                if strategy_result.matched:
                    matched_filters.append(strategy.identifier)
                if not strategy.is_legacy_filter:
                    strategy_results[strategy.identifier] = strategy_result.to_dict()
                if strategy_result.status is strategy_runtime.StrategyStatus.ERROR:
                    if strategy.category == "patterns":
                        pattern_computation_errors += 1
                    filter_error = {
                        "symbol": symbol,
                        "filter": strategy.identifier,
                        "error": strategy_result.explanation,
                    }
                    filter_errors.append(filter_error)

            # ``strategy_results`` intentionally remains additive only on
            # matched result rows; symbol outcomes include every strategy.
            statuses = {
                item["status"] for item in all_strategy_results.values()
            }
            if "error" in statuses:
                symbol_status = "error"
            elif matched_filters:
                symbol_status = "matched"
            elif statuses == {"unsupported"}:
                symbol_status = "unsupported"
            else:
                symbol_status = "not_matched"
            outcome = {
                "symbol": symbol,
                "status": symbol_status,
                "bars": bar_count,
                "closed_bars": complete_count,
                "required_bars": required_bars,
                "strategies": all_strategy_results,
            }
            symbol_outcomes.append(outcome)
            outcome_by_symbol[symbol] = outcome

            if _scan_debug_enabled() and scanned <= _scan_debug_sample_limit():
                _debug_scan_log(
                    "scan_symbol_filter_result",
                    job_id=job_id,
                    symbol=symbol,
                    bars=len(bars),
                    filters=valid_filters,
                    matched_filters=matched_filters,
                    price=analysis.get("price"),
                    overall_signal=analysis.get("overall_signal"),
                )

            if matched_filters:
                # Preserve the existing successful-result wire payload. The
                # selective pass above avoids eager work for non-matches.
                result_analysis = ta.full_analysis(
                    complete_bars,
                    timeframe=timeframe,
                )
                if not result_analysis:
                    analysis_failures += 1
                    errors += 1
                    continue
                if pattern_scan_requested and any(key in pattern_filter_keys for key in matched_filters):
                    pattern_matched_symbols += 1
                canonical = canonicalize_symbol(symbol, market)
                trade = result_analysis.get("trade_setup") or {}
                result_payload = {
                        **_symbol_fields(canonical.provider_symbol, market),
                        "price": result_analysis["price"],
                        "matched_filters": matched_filters,
                        "match_count": len(matched_filters),
                        "total_filters": len(valid_filters),
                        "match_pct": round(len(matched_filters) / len(valid_filters) * 100, 1),
                        "overall_signal": result_analysis["overall_signal"],
                        "rsi": result_analysis["indicators"]["rsi"],
                        "macd": result_analysis["indicators"]["macd"]["line"],
                        "patterns": [
                            pattern["pattern"]
                            for pattern in result_analysis["patterns"]["candlestick"]
                            + result_analysis["patterns"]["chart"]
                        ],
                        "trade_setup": trade,
                    }
                if strategy_results:
                    result_payload["strategy_results"] = strategy_results
                results.append(result_payload)

                try:
                    scan = ScanResult(
                        user_id=user_id,
                        job_id=job_id,
                        symbol=canonical.display_symbol,
                        provider_symbol=canonical.provider_symbol,
                        display_symbol=canonical.display_symbol,
                        market=market,
                        timeframe=timeframe,
                        scan_type="filter_scan",
                        filters_matched=json.dumps(matched_filters),
                        indicator_values=json.dumps(
                            {
                                "rsi": result_analysis["indicators"]["rsi"],
                                "macd": result_analysis["indicators"]["macd"]["line"],
                            }
                        ),
                        last_price=result_analysis["price"]["last"],
                        volume=result_analysis["price"]["volume"],
                        signal=result_analysis["overall_signal"],
                    )
                    pending_scan_rows[canonical.provider_symbol] = scan
                except Exception as exc:
                    errors += 1
                    persistence_failures.append(
                        {
                            "symbol": canonical.provider_symbol,
                            "stage": "construct_scan_result",
                            "error": str(exc),
                        }
                    )
                    outcome["status"] = "error"
                    outcome["error"] = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "stage": "construct_scan_result",
                    }
                    logger.exception(
                        "scan_result_persist_failed",
                        extra={"job_id": job_id, "symbol": canonical.provider_symbol, "error": str(exc)},
                    )

        except ProviderError as exc:
            provider_failures += 1
            if len(symbol_failures) < 5:
                symbol_failures.append({"symbol": symbol, **exc.to_dict()})
            logger.exception(
                "scan_symbol_provider_failed",
                extra={"job_id": job_id, "symbol": symbol, **exc.context.to_dict()},
            )
            errors += 1
            outcome = {
                "symbol": symbol,
                "status": "error",
                "bars": 0,
                "closed_bars": 0,
                "required_bars": required_bars,
                "error": exc.to_dict(),
                "strategies": {},
            }
            symbol_outcomes.append(outcome)
            outcome_by_symbol[symbol] = outcome
        except Exception as exc:
            analysis_failures += 1
            if pattern_scan_requested:
                pattern_computation_errors += 1
            if len(symbol_failures) < 5:
                symbol_failures.append({"symbol": symbol, "error": str(exc)})
            logger.exception("scan_symbol_failed", extra={"job_id": job_id, "symbol": symbol})
            errors += 1
            outcome = {
                "symbol": symbol,
                "status": "error",
                "bars": 0,
                "closed_bars": 0,
                "required_bars": required_bars,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "strategies": {},
            }
            symbol_outcomes.append(outcome)
            outcome_by_symbol[symbol] = outcome

        _emit_scan_progress(
            progress_callback,
            progress=min(99, int(index / total_symbols * 100)),
            current_symbol=symbol,
            scanned=scanned,
            matched=len(results),
            errors=errors,
            total=total_symbols,
        )

    candidate_matches = len(results)
    results.sort(
        key=lambda item: (
            -item["match_pct"],
            -item["match_count"],
            item["provider_symbol"],
        )
    )
    results = results[:max_results]
    persisted_results = []
    for result in results:
        scan_row = pending_scan_rows.get(result["provider_symbol"])
        if scan_row is None:
            continue
        try:
            db.session.add(scan_row)
            persisted_results.append(result)
        except Exception as exc:
            errors += 1
            failure = {
                "symbol": result["provider_symbol"],
                "stage": "add_scan_result",
                "error": str(exc),
            }
            persistence_failures.append(failure)
            outcome = outcome_by_symbol.get(result["provider_symbol"])
            if outcome:
                outcome["status"] = "error"
                outcome["error"] = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stage": "add_scan_result",
                }
            logger.exception(
                "scan_result_persist_failed",
                extra={"job_id": job_id, **failure},
            )
    results = persisted_results

    duration = time.time() - start_time
    bar_count_summary = {
        "min": min(bar_counts) if bar_counts else 0,
        "max": max(bar_counts) if bar_counts else 0,
        "avg": round(sum(bar_counts) / len(bar_counts), 1) if bar_counts else 0,
    }
    scan_counter_payload = {
        "job_id": job_id,
        "market": market,
        "timeframe": timeframe,
        "total_symbols": total_symbols,
        "attempted": attempted,
        "bars_fetched": bars_fetched,
        "bars_usable": bars_usable,
        "pattern_scan_requested": pattern_scan_requested,
        "pattern_filter_keys": pattern_filter_keys,
        "pattern_computation_attempted": pattern_computation_attempted,
        "pattern_computation_errors": pattern_computation_errors,
        "pattern_detected_symbols": pattern_detected_symbols,
        "pattern_matched_symbols": pattern_matched_symbols,
        "matches": len(results),
        "candidate_matches": candidate_matches,
        "errors": errors,
        "no_data": no_data,
        "insufficient_data": insufficient_data,
        "analysis_failures": analysis_failures,
        "bar_counts": bar_count_summary,
        "data_limit_notices": sorted(data_limit_notices),
        "filter_errors": filter_errors,
        "symbol_failures": symbol_failures,
        "provider_failures": provider_failures,
        "persistence_failures": persistence_failures,
    }
    logger.info("scan_completed_counters", extra=scan_counter_payload)

    if scanned == 0 and (provider_failures or analysis_failures):
        provider_error = provider.last_error
        logger.error(
            "scan_no_symbols_analyzed",
            extra={
                "job_id": job_id,
                "market": market,
                "timeframe": timeframe,
                "total_symbols": total_symbols,
                "attempted": attempted,
                "no_data": no_data,
                "insufficient_data": insufficient_data,
                "analysis_failures": analysis_failures,
                "errors": errors,
                "provider_error": provider_error,
                "symbol_failures": symbol_failures,
                "filter_errors": filter_errors,
                "scan_counters": scan_counter_payload,
            },
        )
        if analysis_failures and not provider_failures:
            raise ApiError(
                "Scan failed while analyzing market data. Check worker logs for scan_symbol_failed.",
                500,
                "scan_analysis_failed",
                {
                    "market": market,
                    "timeframe": timeframe,
                    "total_symbols": total_symbols,
                    "attempted": attempted,
                    "no_data": no_data,
                    "insufficient_data": insufficient_data,
                    "analysis_failures": analysis_failures,
                    "symbol_failures": symbol_failures,
                    "filter_errors": filter_errors,
                    "scan_counters": scan_counter_payload,
                },
            )
        raise ApiError(
            "No usable market data was returned by Polygon. Check POLYGON_API_KEY, plan access, and timeframe.",
            502,
            "provider_data_unavailable",
            {
                "market": market,
                "timeframe": timeframe,
                "total_symbols": total_symbols,
                "attempted": attempted,
                "no_data": no_data,
                "insufficient_data": insufficient_data,
                "analysis_failures": analysis_failures,
                "provider_error": provider_error,
                "symbol_failures": symbol_failures,
                "filter_errors": filter_errors,
                "scan_counters": scan_counter_payload,
            },
        )

    try:
        history = ScanHistory(
            user_id=user_id,
            job_id=job_id,
            market=market,
            timeframe=timeframe,
            total_scanned=scanned,
            total_matched=len(results),
            filters_used=json.dumps(valid_filters),
            duration_seconds=round(duration, 2),
        )
        db.session.add(history)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception(
            "scan_history_persist_failed",
            extra={"job_id": job_id, "error": str(exc)},
        )
        raise ApiError(
            "Scan results could not be persisted",
            500,
            "persistence_error",
            {"job_id": job_id, "error_type": type(exc).__name__},
        ) from exc

    _emit_scan_progress(
        progress_callback,
        progress=100,
        scanned=scanned,
        matched=len(results),
        errors=errors,
        total=total_symbols,
    )
    return {
        "results": results,
        "meta": {
            "market": market,
            "universe": universe_resolution.universe_key,
            "universe_source": universe_resolution.source,
            "universe_degraded": universe_resolution.degraded,
            "universe_degraded_reason": universe_resolution.degraded_reason,
            "timeframe": timeframe,
            "total_scanned": scanned,
            "total_attempted": attempted,
            "total_symbols": total_symbols,
            "total_matched": len(results),
            "total_candidate_matches": candidate_matches,
            "errors": errors,
            "bars_fetched": bars_fetched,
            "bars_usable": bars_usable,
            "no_data": no_data,
            "insufficient_data": insufficient_data,
            "required_bars": required_bars,
            "insufficient_data_symbols": insufficient_data_symbols,
            "symbol_outcomes": symbol_outcomes,
            "provider_failures": provider_failures,
            "persistence_failures": persistence_failures,
            "analysis_failures": analysis_failures,
            "pattern_scan_requested": pattern_scan_requested,
            "pattern_computation_attempted": pattern_computation_attempted,
            "pattern_computation_errors": pattern_computation_errors,
            "pattern_detected_symbols": pattern_detected_symbols,
            "pattern_matched_symbols": pattern_matched_symbols,
            "bar_counts": bar_count_summary,
            "data_limit_notices": sorted(data_limit_notices),
            "filter_errors": filter_errors,
            "symbol_failures": symbol_failures,
            "duration_seconds": round(duration, 2),
            "filters_applied": valid_filters,
        },
    }


