import json
import logging
import os
import random
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

from backend.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1
BACKOFF_JITTER_SECONDS = 0.5
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_PAUSE_SECONDS = 60
POLYGON_MAX_CONCURRENT_REQUESTS = int(os.getenv("POLYGON_MAX_CONCURRENT_REQUESTS", "10"))
SNAPSHOT_PREFILTER_ENABLED = os.getenv("POLYGON_SNAPSHOT_PREFILTER", "false").lower() == "true"


class PolygonClient:
    """Rate-limited Polygon.io API client with caching."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = POLYGON_BASE_URL
        self.session = requests.Session()
        self.session.params = {"apiKey": self.api_key}
        self.consecutive_failures = 0
        self.circuit_open_until = 0
        self._snapshot_indexes = {}
        self.last_error = None
        self.max_concurrent_requests = max(1, POLYGON_MAX_CONCURRENT_REQUESTS)
        self._request_semaphore = threading.BoundedSemaphore(self.max_concurrent_requests)

    def _debug_enabled(self):
        return os.getenv("POLYGON_DEBUG", "false").lower() == "true"

    @staticmethod
    def _safe_params(params=None):
        safe = dict(params or {})
        if "apiKey" in safe:
            safe["apiKey"] = "<redacted>"
        return safe

    def _debug_log_response(self, endpoint, status_code, body):
        if not self._debug_enabled():
            return
        logger.info(
            "polygon_response",
            extra={
                "endpoint": endpoint,
                "status_code": status_code,
                "body": str(body)[:1000],
            },
        )

    def _set_error(self, error_type, message, status_code=None, endpoint=None):
        self.last_error = {
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "endpoint": endpoint,
        }

    def _is_circuit_open(self):
        return time.time() < self.circuit_open_until

    def _record_success(self):
        self.consecutive_failures = 0
        self.circuit_open_until = 0

    def _record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            self.circuit_open_until = time.time() + CIRCUIT_BREAKER_PAUSE_SECONDS
            self.consecutive_failures = 0
            logger.warning("Polygon circuit breaker opened for %ss", CIRCUIT_BREAKER_PAUSE_SECONDS)
            return True
        return False

    def _retry_delay(self, retry_number):
        backoff = BACKOFF_BASE_SECONDS * (2 ** max(retry_number - 1, 0))
        jitter = random.uniform(0, BACKOFF_JITTER_SECONDS)
        return min(CIRCUIT_BREAKER_PAUSE_SECONDS, backoff + jitter)

    def _request_url(self, endpoint):
        if str(endpoint).startswith("http://") or str(endpoint).startswith("https://"):
            return endpoint
        return f"{self.base_url}{endpoint}"

    def _request(self, endpoint, params=None):
        if not self.api_key:
            self._set_error("missing_api_key", "POLYGON_API_KEY is not configured", endpoint=endpoint)
            logger.error("polygon_api_key_missing", extra={"endpoint": endpoint})
            return None

        cache_key = f"polygon:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
        cached = cache_get(cache_key)
        if cached is not None:
            self.last_error = None
            return cached

        if self._is_circuit_open():
            self._set_error("circuit_open", "Polygon circuit breaker is open", endpoint=endpoint)
            logger.warning("Polygon circuit breaker is open; skipping request to %s", endpoint)
            return None

        url = self._request_url(endpoint)
        if self._debug_enabled():
            logger.info(
                "polygon_request",
                extra={
                    "url": url,
                    "params": self._safe_params(params),
                    "api_key_configured": bool(self.api_key),
                },
            )
        for attempt in range(MAX_RETRIES + 1):
            try:
                with self._request_semaphore:
                    resp = self.session.get(url, params=params or {}, timeout=REQUEST_TIMEOUT_SECONDS)
            except (requests.Timeout, requests.ConnectionError) as exc:
                self._set_error("network_error", str(exc), endpoint=endpoint)
                if self._record_failure():
                    return None
                if attempt >= MAX_RETRIES:
                    logger.error("Polygon request failed after retry exhaustion: %s", exc)
                    return None
                delay = self._retry_delay(attempt + 1)
                logger.warning("Polygon timeout/network error. Retrying in %.2fs", delay)
                time.sleep(delay)
                continue
            except requests.RequestException as exc:
                self._set_error("request_error", str(exc), endpoint=endpoint)
                self._record_failure()
                logger.error("Polygon request failed: %s", exc)
                return None

            self._debug_log_response(endpoint, resp.status_code, resp.text)
            if resp.status_code == 200:
                data = resp.json()
                cache_set(cache_key, data)
                self._record_success()
                self.last_error = None
                return data

            if resp.status_code == 429 and attempt < MAX_RETRIES:
                self._set_error("rate_limited", resp.text[:300], status_code=resp.status_code, endpoint=endpoint)
                retry_after = getattr(resp, "headers", {}).get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else self._retry_delay(attempt + 1)
                except (TypeError, ValueError):
                    delay = self._retry_delay(attempt + 1)
                logger.warning("Polygon rate limited. Retrying in %.2fs", delay)
                time.sleep(delay)
                continue

            self._set_error("http_error", resp.text[:300], status_code=resp.status_code, endpoint=endpoint)
            if resp.status_code >= 500 and self._record_failure():
                return None
            logger.error("Polygon API error %s: %s", resp.status_code, resp.text[:200])
            return None

        return None

    def _snapshot_index_for_market(self, market):
        if market in self._snapshot_indexes:
            return self._snapshot_indexes[market]

        snapshots = self.get_snapshot_crypto() if market == "crypto" else self.get_snapshot_stocks()
        if not snapshots:
            self._snapshot_indexes[market] = None
            return None

        index = {}
        for item in snapshots:
            ticker = (item.get("ticker") or item.get("symbol") or "").upper()
            if ticker:
                index[ticker] = item
        self._snapshot_indexes[market] = index or None
        return self._snapshot_indexes[market]

    def _snapshot_allows_ohlcv_fetch(self, ticker):
        market = "crypto" if ticker.upper().startswith("X:") else "stocks"
        index = self._snapshot_index_for_market(market)
        if index is None:
            return True

        snapshot = index.get(ticker.upper())
        if snapshot is None:
            logger.info("polygon_snapshot_missing", extra={"ticker": ticker, "action": "fallback_to_aggregates"})
            return True

        day = snapshot.get("day") or snapshot.get("prevDay") or {}
        volume = day.get("v") if "v" in day else snapshot.get("volume")
        if volume is not None and float(volume) <= 0:
            logger.info("polygon_ohlcv_skipped", extra={"ticker": ticker, "reason": "zero_snapshot_volume"})
            return False
        return True

    def get_aggregates(self, ticker, timespan="day", multiplier=1, from_date=None, to_date=None, limit=365):
        """Get OHLCV bars for a ticker."""
        if not from_date:
            from_date = (datetime.now() - timedelta(days=limit * 2)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        if SNAPSHOT_PREFILTER_ENABLED and not self._snapshot_allows_ohlcv_fetch(ticker):
            return []

        endpoint = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}
        next_url = endpoint
        pages_seen = set()
        bars_by_timestamp = {}
        bars_without_timestamp = []
        while next_url:
            if next_url in pages_seen:
                self._set_error(
                    "pagination_loop",
                    "Polygon aggregates returned a repeated next_url",
                    endpoint=endpoint,
                )
                return []
            pages_seen.add(next_url)
            data = self._request(next_url, params)
            params = None
            if not data:
                # Never return a successful-looking partial history when a
                # later page failed. PolygonProvider will raise the typed error.
                return []
            for bar in data.get("results") or []:
                if "t" in bar:
                    bars_by_timestamp[bar["t"]] = bar
                else:
                    bars_without_timestamp.append(bar)
            next_url = data.get("next_url")

        return [bars_by_timestamp[key] for key in sorted(bars_by_timestamp)] + bars_without_timestamp

    def debug_aggregates_raw(self, ticker, from_date, to_date, timespan="day", multiplier=1):
        if not self.api_key:
            return {
                "status_code": None,
                "url": f"{self.base_url}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
                "params": {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": "<missing>"},
                "body": "POLYGON_API_KEY is not configured",
            }

        endpoint = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}
        response = self.session.get(
            f"{self.base_url}{endpoint}",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return {
            "status_code": response.status_code,
            "url": f"{self.base_url}{endpoint}",
            "params": self._safe_params({**params, "apiKey": self.api_key}),
            "body": response.text[:5000],
            "full_url_redacted": f"{self.base_url}{endpoint}?{urlencode(self._safe_params({**params, 'apiKey': self.api_key}))}",
        }

    def get_snapshot_stocks(self):
        """Get snapshot of all stock tickers (single API call)."""
        data = self._request("/v2/snapshot/locale/us/markets/stocks/tickers")
        if data and data.get("tickers"):
            return data["tickers"]
        return []

    def get_reference_tickers(self, exchange, limit=1000):
        """Fetch all active common stock tickers for a primary exchange."""
        tickers = []
        next_url = "/v3/reference/tickers"
        params = {
            "market": "stocks",
            "type": "CS",
            "exchange": exchange,
            "active": "true",
            "limit": limit,
        }

        while next_url:
            data = self._request(next_url, params)
            if not data:
                break
            tickers.extend(data.get("results") or [])
            next_url = data.get("next_url")
            params = None
        return tickers

    def get_reference_crypto_tickers(self, limit=1000):
        """Fetch every active crypto ticker, following reference pagination."""
        tickers = []
        next_url = "/v3/reference/tickers"
        params = {
            "market": "crypto",
            "active": "true",
            "limit": limit,
        }

        while next_url:
            data = self._request(next_url, params)
            if not data:
                break
            tickers.extend(data.get("results") or [])
            next_url = data.get("next_url")
            params = None
        return tickers

    def get_grouped_daily_stocks(self, date):
        """Fetch grouped US stock aggregates for one trading date."""
        endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{date}"
        data = self._request(endpoint, {"adjusted": "true"})
        if data and data.get("results"):
            return data["results"]
        return []

    def get_grouped_daily_crypto(self, date):
        """Fetch grouped global crypto aggregates for one UTC date."""
        endpoint = f"/v2/aggs/grouped/locale/global/market/crypto/{date}"
        data = self._request(endpoint, {"adjusted": "true"})
        if data and data.get("results"):
            return data["results"]
        return []

    def get_snapshot_crypto(self):
        """Get snapshot of all crypto tickers (single API call)."""
        data = self._request("/v2/snapshot/locale/global/markets/crypto/tickers")
        if data and data.get("tickers"):
            return data["tickers"]
        return []

    def get_ticker_details(self, ticker):
        """Get details for a specific ticker."""
        data = self._request(f"/v3/reference/tickers/{ticker}")
        if data and data.get("results"):
            return data["results"]
        return None

    def search_tickers(self, query, market="stocks", limit=20):
        """Search for tickers."""
        params = {"search": query, "active": "true", "limit": limit}
        if market == "stocks":
            params["market"] = "stocks"
            params["locale"] = "us"
        elif market == "crypto":
            params["market"] = "crypto"
        data = self._request("/v3/reference/tickers", params)
        if data and data.get("results"):
            return data["results"]
        return []

    def get_previous_close(self, ticker):
        """Get previous day close data."""
        data = self._request(f"/v2/aggs/ticker/{ticker}/prev")
        if data and data.get("results"):
            return data["results"][0]
        return None

    def get_news(self, ticker, limit=20):
        """Get recent news articles for a ticker."""
        params = {
            "ticker": ticker,
            "limit": min(limit, 50),
            "sort": "published_utc",
            "order": "desc",
        }
        data = self._request("/v2/reference/news", params)
        if data and data.get("results"):
            return data["results"]
        return []

    def get_financials(self, ticker, limit=5, timeframe="annual"):
        """Get financial statements from Polygon.io Stock Financials vX API."""
        params = {
            "ticker": ticker,
            "limit": limit,
            "timeframe": timeframe,
            "order": "desc",
            "sort": "filing_date",
        }
        data = self._request("/vX/reference/financials", params)
        if data and data.get("results"):
            return data["results"]
        return []

    def get_dividends(self, ticker, limit=4):
        """Get recent dividend payments."""
        params = {
            "ticker": ticker,
            "limit": limit,
            "order": "desc",
            "sort": "pay_date",
        }
        data = self._request("/v3/reference/dividends", params)
        if data and data.get("results"):
            return data["results"]
        return []


polygon = PolygonClient(os.getenv("POLYGON_API_KEY", ""))
