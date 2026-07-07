import json
import logging
import os
import time
from datetime import datetime, timedelta

from backend.clients.polygon import polygon
from backend.errors import ApiError
from backend.extensions import db
from backend.market_config import TIMEFRAME_CONFIG, data_limit_notice, public_timeframes
from backend.models.scan import ScanHistory, ScanResult
from backend.services.cache import cache_get, cache_set
from backend.services.technical import TechnicalAnalysis
from backend.symbols import canonicalize_symbol

logger = logging.getLogger(__name__)

ta = TechnicalAnalysis()

# STOCK / CRYPTO SYMBOL LISTS
# ============================================================
NASDAQ_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'COST', 'NFLX',
    'AMD', 'PEP', 'ADBE', 'CSCO', 'CMCSA', 'INTC', 'TMUS', 'INTU', 'TXN', 'QCOM',
    'AMAT', 'HON', 'AMGN', 'SBUX', 'ISRG', 'BKNG', 'VRTX', 'ADI', 'GILD', 'MDLZ',
    'REGN', 'LRCX', 'PYPL', 'ADP', 'PANW', 'KLAC', 'SNPS', 'CDNS', 'MELI', 'ABNB',
    'ASML', 'MNST', 'FTNT', 'MAR', 'NXPI', 'MRVL', 'ORLY', 'ADSK', 'CTAS', 'WDAY',
]

NYSE_SYMBOLS = [
    'JPM', 'V', 'WMT', 'JNJ', 'PG', 'MA', 'HD', 'UNH', 'BAC', 'DIS',
    'KO', 'MRK', 'PFE', 'ABT', 'TMO', 'CVX', 'XOM', 'LLY', 'ABBV', 'NKE',
    'CRM', 'DHR', 'NEE', 'UPS', 'RTX', 'LOW', 'GS', 'BLK', 'BA', 'CAT',
]

CRYPTO_SYMBOLS = [
    'X:BTCUSD', 'X:ETHUSD', 'X:SOLUSD', 'X:ADAUSD', 'X:DOTUSD',
    'X:DOGEUSD', 'X:AVAXUSD', 'X:MATICUSD', 'X:LINKUSD', 'X:UNIUSD',
    'X:XRPUSD', 'X:LTCUSD', 'X:ATOMUSD', 'X:ALGOUSD', 'X:NEARUSD',
]

ALL_STOCK_SYMBOLS = NASDAQ_SYMBOLS + NYSE_SYMBOLS


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


def _stock_scan_symbols():
    from backend.services.universe import get_scan_universe_symbols

    return get_scan_universe_symbols(ALL_STOCK_SYMBOLS)


def get_bars_with_meta(symbol, timeframe='1D'):
    """Fetch OHLCV bars for a symbol based on timeframe"""
    canonical = canonicalize_symbol(symbol)
    tf = TIMEFRAME_MAP.get(timeframe)
    if not tf:
        raise ApiError("Invalid timeframe", 400, "validation_error", {"timeframe": timeframe})
    from_date = (datetime.now() - timedelta(days=tf['days'])).strftime('%Y-%m-%d')
    to_date = datetime.now().strftime('%Y-%m-%d')
    bars = polygon.get_aggregates(canonical.provider_symbol, tf['timespan'], tf['multiplier'], from_date, to_date)
    bar_count = len(bars or [])
    return bars, {
        "timeframe": timeframe,
        "from_date": from_date,
        "to_date": to_date,
        "bar_count": bar_count,
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


# ============================================================
# FILTER HELPERS
# ============================================================
def _check_fib_confluence(analysis):
    """Check if price is near a Fibonacci confluence zone (cluster of levels)"""
    fib = analysis.get('fibonacci')
    if not fib or not fib.get('zones'):
        return False
    price = analysis['price']['last']
    for zone in fib['zones']:
        if zone['strength'] >= 2 and abs(price - zone['mid']) / price < 0.025:
            return True
    return False


# ============================================================
# FILTER DEFINITIONS
# ============================================================
FILTER_DEFINITIONS = {
    'oscillators': {
        'rsi_oversold': {'name': 'RSI Oversold', 'description': 'RSI below 30', 'category': 'oscillators',
                         'check': lambda a: a['indicators']['rsi'] is not None and a['indicators']['rsi'] < 30},
        'rsi_overbought': {'name': 'RSI Overbought', 'description': 'RSI above 70', 'category': 'oscillators',
                           'check': lambda a: a['indicators']['rsi'] is not None and a['indicators']['rsi'] > 70},
        'stoch_oversold': {'name': 'Stochastic Oversold', 'description': 'Stochastic %K below 20', 'category': 'oscillators',
                           'check': lambda a: a['indicators']['stochastic']['k'] is not None and a['indicators']['stochastic']['k'] < 20},
        'stoch_overbought': {'name': 'Stochastic Overbought', 'description': 'Stochastic %K above 80', 'category': 'oscillators',
                             'check': lambda a: a['indicators']['stochastic']['k'] is not None and a['indicators']['stochastic']['k'] > 80},
    },
    'moving_averages': {
        'ema_golden_cross': {'name': 'EMA Golden Cross', 'description': 'EMA 50 above EMA 200', 'category': 'moving_averages',
                             'check': lambda a: a['indicators']['ema']['ema_50'] is not None and a['indicators']['ema']['ema_200'] is not None and a['indicators']['ema']['ema_50'] > a['indicators']['ema']['ema_200']},
        'ema_death_cross': {'name': 'EMA Death Cross', 'description': 'EMA 50 below EMA 200', 'category': 'moving_averages',
                            'check': lambda a: a['indicators']['ema']['ema_50'] is not None and a['indicators']['ema']['ema_200'] is not None and a['indicators']['ema']['ema_50'] < a['indicators']['ema']['ema_200']},
        'price_above_sma200': {'name': 'Price Above SMA 200', 'description': 'Current price above 200-day SMA', 'category': 'moving_averages',
                               'check': lambda a: a['indicators']['sma']['sma_200'] is not None and a['price']['last'] > a['indicators']['sma']['sma_200']},
        'macd_bullish': {'name': 'MACD Bullish', 'description': 'MACD line above signal line', 'category': 'moving_averages',
                         'check': lambda a: a['indicators']['macd']['line'] is not None and a['indicators']['macd']['signal'] is not None and a['indicators']['macd']['line'] > a['indicators']['macd']['signal']},
        'macd_bearish': {'name': 'MACD Bearish', 'description': 'MACD line below signal line', 'category': 'moving_averages',
                         'check': lambda a: a['indicators']['macd']['line'] is not None and a['indicators']['macd']['signal'] is not None and a['indicators']['macd']['line'] < a['indicators']['macd']['signal']},
    },
    'volatility': {
        'bb_squeeze': {'name': 'Bollinger Squeeze', 'description': 'Price near lower Bollinger Band', 'category': 'volatility',
                       'check': lambda a: a['indicators']['bollinger_bands']['lower'] is not None and a['price']['last'] <= a['indicators']['bollinger_bands']['lower'] * 1.02},
        'bb_breakout': {'name': 'Bollinger Breakout', 'description': 'Price above upper Bollinger Band', 'category': 'volatility',
                        'check': lambda a: a['indicators']['bollinger_bands']['upper'] is not None and a['price']['last'] >= a['indicators']['bollinger_bands']['upper'] * 0.98},
    },
    'patterns': {
        'bullish_pattern': {'name': 'Bullish Pattern', 'description': 'Any bullish candlestick pattern detected', 'category': 'patterns',
                            'check': lambda a: any(p['type'] == 'bullish' for p in a['patterns']['candlestick'])},
        'bearish_pattern': {'name': 'Bearish Pattern', 'description': 'Any bearish candlestick pattern detected', 'category': 'patterns',
                            'check': lambda a: any(p['type'] == 'bearish' for p in a['patterns']['candlestick'])},
        'chart_pattern_bullish': {'name': 'Bullish Chart Pattern', 'description': 'Bullish chart pattern (double bottom, flag, etc.)', 'category': 'patterns',
                                  'check': lambda a: any(p['type'] == 'bullish' for p in a['patterns']['chart'])},
    },
    'fibonacci': {
        'near_fib_support': {'name': 'Near Fibonacci Support', 'description': 'Price within 2% of a Fibonacci support level', 'category': 'fibonacci',
                             'check': lambda a: a['fibonacci'] is not None and a['fibonacci']['nearest_support'] is not None and abs(a['price']['last'] - a['fibonacci']['nearest_support']) / a['price']['last'] < 0.02},
        'near_fib_resistance': {'name': 'Near Fibonacci Resistance', 'description': 'Price within 2% of a Fibonacci resistance level', 'category': 'fibonacci',
                                'check': lambda a: a['fibonacci'] is not None and a['fibonacci']['nearest_resistance'] is not None and abs(a['price']['last'] - a['fibonacci']['nearest_resistance']) / a['price']['last'] < 0.02},
        'fib_golden_zone': {'name': 'In Golden Pocket (50-61.8%)', 'description': 'Price in the golden zone — highest probability reversal area', 'category': 'fibonacci',
                            'check': lambda a: a['fibonacci'] is not None and a['fibonacci'].get('price_zone') == 'golden_zone'},
        'fib_shallow_retrace': {'name': 'Shallow Retracement (23.6-38.2%)', 'description': 'Price in shallow pullback — strong trend continuation signal', 'category': 'fibonacci',
                                'check': lambda a: a['fibonacci'] is not None and a['fibonacci'].get('price_zone') == 'shallow_retrace'},
        'fib_deep_retrace': {'name': 'Deep Retracement (61.8-78.6%)', 'description': 'Price in deep retracement — potential bottom or trend change', 'category': 'fibonacci',
                             'check': lambda a: a['fibonacci'] is not None and a['fibonacci'].get('price_zone') in ('deep_retrace', 'very_deep')},
        'fib_uptrend': {'name': 'Fibonacci Uptrend', 'description': 'Fibonacci structure shows uptrend (swing low before swing high)', 'category': 'fibonacci',
                        'check': lambda a: a['fibonacci'] is not None and a['fibonacci'].get('trend') == 'uptrend'},
        'fib_downtrend': {'name': 'Fibonacci Downtrend', 'description': 'Fibonacci structure shows downtrend (swing high before swing low)', 'category': 'fibonacci',
                          'check': lambda a: a['fibonacci'] is not None and a['fibonacci'].get('trend') == 'downtrend'},
        'fib_confluence_zone': {'name': 'Fibonacci Confluence Zone', 'description': 'Price near a cluster of multiple Fibonacci levels (strong S/R)', 'category': 'fibonacci',
                                'check': lambda a: _check_fib_confluence(a)},
    }
}


def get_flat_filters():
    """Return flat dict of all filters"""
    flat = {}
    for cat in FILTER_DEFINITIONS.values():
        flat.update(cat)
    return flat


# ============================================================
# FILTER PRESETS
# ============================================================
FILTER_PRESETS = {
    'bullish_momentum': {
        'name': 'Bullish Momentum',
        'description': 'Stocks showing strong buying signals',
        'filters': ['rsi_oversold', 'macd_bullish', 'ema_golden_cross', 'bullish_pattern']
    },
    'bearish_reversal': {
        'name': 'Bearish Reversal',
        'description': 'Stocks showing potential downturn',
        'filters': ['rsi_overbought', 'macd_bearish', 'ema_death_cross', 'bearish_pattern']
    },
    'oversold_bounce': {
        'name': 'Oversold Bounce',
        'description': 'Deeply oversold with reversal potential',
        'filters': ['rsi_oversold', 'stoch_oversold', 'bb_squeeze', 'near_fib_support']
    },
    'trend_following': {
        'name': 'Trend Following',
        'description': 'Strong uptrend with momentum',
        'filters': ['ema_golden_cross', 'price_above_sma200', 'macd_bullish']
    },
    'fib_golden_pocket': {
        'name': 'Fibonacci Golden Pocket',
        'description': 'Price in the 50-61.8% golden zone — highest probability reversal',
        'filters': ['fib_golden_zone', 'fib_uptrend', 'near_fib_support']
    },
    'fib_confluence_play': {
        'name': 'Fibonacci Confluence',
        'description': 'Price near cluster of multiple Fibonacci levels (strong S/R)',
        'filters': ['fib_confluence_zone', 'near_fib_support']
    }
}


def health_payload():
    return {
        "status": "healthy",
        "api_key_configured": bool(polygon.api_key),
        "stock_symbols": len(ALL_STOCK_SYMBOLS),
        "crypto_symbols": len(CRYPTO_SYMBOLS),
        "timestamp": datetime.utcnow().isoformat(),
    }


def filters_payload():
    result = {}
    for category, filters in FILTER_DEFINITIONS.items():
        result[category] = {}
        for key, filter_def in filters.items():
            result[category][key] = {
                "name": filter_def["name"],
                "description": filter_def["description"],
                "category": filter_def["category"],
            }
    return {
        "filters": result,
        "presets": FILTER_PRESETS,
        "timeframes": public_timeframes(),
    }


def search_tickers(query, market):
    query = query.strip()
    if not query:
        return {"results": []}
    results = polygon.search_tickers(query, market)
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

    analysis = ta.full_analysis(bars)
    if not analysis:
        raise ApiError(f"Insufficient data for analysis of {canonical.display_symbol}", 400, "insufficient_data")

    details = polygon.get_ticker_details(canonical.provider_symbol)
    result = {
        **_symbol_fields(canonical.provider_symbol, details.get("market") if details else canonical.market),
        "name": details.get("name", canonical.display_symbol) if details else canonical.display_symbol,
        "timeframe": timeframe,
        "data_limit_notice": bars_meta.get("data_limit_notice"),
        "analysis": analysis,
        "trade_setup": analysis.get("trade_setup"),
        "chart_data": [
            {"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b.get("v", 0)}
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
            {"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b.get("v", 0)}
            for b in bars
        ],
    }


def _emit_scan_progress(progress_callback, **payload):
    if progress_callback:
        progress_callback(payload)


def scan_market(market, selected_filters, timeframe, max_results, user_id=None, job_id=None, progress_callback=None):
    if not polygon.api_key:
        raise ApiError(
            "Polygon API key is not configured. Set POLYGON_API_KEY in Railway backend and worker variables.",
            503,
            "provider_not_configured",
        )

    symbols = CRYPTO_SYMBOLS if market == "crypto" else _stock_scan_symbols()
    flat_filters = get_flat_filters()
    valid_filters = [item for item in selected_filters if item in flat_filters]
    if not valid_filters:
        raise ApiError("No valid filters selected", 400, "validation_error")

    start_time = time.time()
    results = []
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
    bar_counts = []
    data_limit_notices = set()
    total_symbols = len(symbols)
    pattern_filter_keys = [
        key for key in valid_filters
        if flat_filters[key].get("category") == "patterns"
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
        },
    )

    _emit_scan_progress(progress_callback, progress=0, scanned=0, total=total_symbols)

    for index, symbol in enumerate(symbols, start=1):
        if len(results) >= max_results:
            break

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
            bars, bars_meta = get_bars_with_meta(symbol, timeframe)
            if bars_meta.get("data_limit_notice"):
                data_limit_notices.add(bars_meta["data_limit_notice"])
            bar_count = len(bars or [])
            if bars:
                bars_fetched += 1
                bar_counts.append(bar_count)
            if not bars or len(bars) < 30:
                if not bars:
                    no_data += 1
                else:
                    insufficient_data += 1
                logger.warning(
                    "scan_symbol_data_rejected",
                    extra={
                        "job_id": job_id,
                        "symbol": symbol,
                        "bars": bar_count,
                        "reason": "no_data" if not bars else "insufficient_data",
                        "provider_error": getattr(polygon, "last_error", None),
                    },
                )
                errors += 1
                continue

            bars_usable += 1
            analysis = ta.full_analysis(bars)
            if not analysis:
                analysis_failures += 1
                logger.warning(
                    "scan_symbol_analysis_empty",
                    extra={"job_id": job_id, "symbol": symbol, "bars": bar_count},
                )
                errors += 1
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
            for filter_key in valid_filters:
                try:
                    if flat_filters[filter_key]["check"](analysis):
                        matched_filters.append(filter_key)
                except (KeyError, TypeError, ValueError) as exc:
                    if flat_filters[filter_key].get("category") == "patterns":
                        pattern_computation_errors += 1
                    filter_error = {"symbol": symbol, "filter": filter_key, "error": str(exc)}
                    filter_errors.append(filter_error)
                    logger.exception(
                        "scan_filter_check_failed",
                        extra={"job_id": job_id, **filter_error},
                    )

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
                if pattern_scan_requested and any(key in pattern_filter_keys for key in matched_filters):
                    pattern_matched_symbols += 1
                canonical = canonicalize_symbol(symbol, market)
                trade = analysis.get("trade_setup") or {}
                results.append(
                    {
                        **_symbol_fields(canonical.provider_symbol, market),
                        "price": analysis["price"],
                        "matched_filters": matched_filters,
                        "match_count": len(matched_filters),
                        "total_filters": len(valid_filters),
                        "match_pct": round(len(matched_filters) / len(valid_filters) * 100, 1),
                        "overall_signal": analysis["overall_signal"],
                        "rsi": analysis["indicators"]["rsi"],
                        "macd": analysis["indicators"]["macd"]["line"],
                        "patterns": [
                            pattern["pattern"]
                            for pattern in analysis["patterns"]["candlestick"] + analysis["patterns"]["chart"]
                        ],
                        "trade_setup": trade,
                    }
                )

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
                                "rsi": analysis["indicators"]["rsi"],
                                "macd": analysis["indicators"]["macd"]["line"],
                            }
                        ),
                        last_price=analysis["price"]["last"],
                        volume=analysis["price"]["volume"],
                        signal=analysis["overall_signal"],
                    )
                    db.session.add(scan)
                except Exception as exc:
                    logger.exception(
                        "scan_result_persist_failed",
                        extra={"job_id": job_id, "symbol": canonical.provider_symbol, "error": str(exc)},
                    )

        except Exception as exc:
            analysis_failures += 1
            if pattern_scan_requested:
                pattern_computation_errors += 1
            if len(symbol_failures) < 5:
                symbol_failures.append({"symbol": symbol, "error": str(exc)})
            logger.exception("scan_symbol_failed", extra={"job_id": job_id, "symbol": symbol})
            errors += 1

        _emit_scan_progress(
            progress_callback,
            progress=min(99, int(index / total_symbols * 100)),
            current_symbol=symbol,
            scanned=scanned,
            matched=len(results),
            errors=errors,
            total=total_symbols,
        )

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
        "errors": errors,
        "no_data": no_data,
        "insufficient_data": insufficient_data,
        "analysis_failures": analysis_failures,
        "bar_counts": bar_count_summary,
        "data_limit_notices": sorted(data_limit_notices),
        "filter_errors": filter_errors,
        "symbol_failures": symbol_failures,
    }
    logger.info("scan_completed_counters", extra=scan_counter_payload)

    if scanned == 0:
        provider_error = getattr(polygon, "last_error", None)
        provider_only_failure = attempted > 0 and (no_data + insufficient_data) == attempted
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
        if not provider_only_failure:
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
    except Exception:
        db.session.rollback()

    results.sort(key=lambda item: item["match_pct"], reverse=True)
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
            "timeframe": timeframe,
            "total_scanned": scanned,
            "total_attempted": attempted,
            "total_symbols": total_symbols,
            "total_matched": len(results),
            "errors": errors,
            "bars_fetched": bars_fetched,
            "bars_usable": bars_usable,
            "no_data": no_data,
            "insufficient_data": insufficient_data,
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


