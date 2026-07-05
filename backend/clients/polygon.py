import json
import logging
import os
import random
import time
from datetime import datetime, timedelta

import requests

from backend.services.cache import cache_get, cache_set
from backend.services.rate_limit import wait_for_rate_limit

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1
BACKOFF_JITTER_SECONDS = 0.5
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_PAUSE_SECONDS = 60
RATE_LIMIT_MAX_CALLS = 5
RATE_LIMIT_WINDOW_SECONDS = 60


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

    def _rate_limit(self):
        wait_for_rate_limit("polygon", RATE_LIMIT_MAX_CALLS, RATE_LIMIT_WINDOW_SECONDS)

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

    def _request(self, endpoint, params=None):
        cache_key = f"polygon:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

        if self._is_circuit_open():
            logger.warning("Polygon circuit breaker is open; skipping request to %s", endpoint)
            return None

        url = f"{self.base_url}{endpoint}"
        for attempt in range(MAX_RETRIES + 1):
            self._rate_limit()
            try:
                resp = self.session.get(url, params=params or {}, timeout=REQUEST_TIMEOUT_SECONDS)
            except (requests.Timeout, requests.ConnectionError) as exc:
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
                self._record_failure()
                logger.error("Polygon request failed: %s", exc)
                return None

            if resp.status_code == 200:
                data = resp.json()
                cache_set(cache_key, data)
                self._record_success()
                return data

            if resp.status_code == 429 and attempt < MAX_RETRIES:
                if self._record_failure():
                    return None
                wait_for_rate_limit("polygon_429", 1, 60)
                delay = self._retry_delay(attempt + 1)
                logger.warning("Polygon rate limited. Retrying in %.2fs", delay)
                time.sleep(delay)
                continue

            if self._record_failure():
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
            logger.info("Skipping %s OHLCV fetch; ticker missing from Polygon snapshot", ticker)
            return False

        day = snapshot.get("day") or snapshot.get("prevDay") or {}
        volume = day.get("v") if "v" in day else snapshot.get("volume")
        if volume is not None and float(volume) <= 0:
            logger.info("Skipping %s OHLCV fetch; snapshot volume is zero", ticker)
            return False
        return True

    def get_aggregates(self, ticker, timespan="day", multiplier=1, from_date=None, to_date=None, limit=365):
        """Get OHLCV bars for a ticker."""
        if not from_date:
            from_date = (datetime.now() - timedelta(days=limit * 2)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        if not self._snapshot_allows_ohlcv_fetch(ticker):
            return []

        endpoint = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        data = self._request(endpoint, {"adjusted": "true", "sort": "asc", "limit": 50000})
        if data and data.get("results"):
            return data["results"]
        return []

    def get_snapshot_stocks(self):
        """Get snapshot of all stock tickers (single API call)."""
        data = self._request("/v2/snapshot/locale/us/markets/stocks/tickers")
        if data and data.get("tickers"):
            return data["tickers"]
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
