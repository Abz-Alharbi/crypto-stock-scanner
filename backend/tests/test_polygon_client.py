import unittest
from unittest.mock import patch

import requests

from backend.clients import polygon as polygon_module
from backend.clients.polygon import PolygonClient, REQUEST_TIMEOUT_SECONDS


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.params = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class PolygonClientTests(unittest.TestCase):
    def setUp(self):
        self.cache_get = patch("backend.clients.polygon.cache_get", return_value=None)
        self.cache_set = patch("backend.clients.polygon.cache_set")
        self.sleep = patch("backend.clients.polygon.time.sleep")
        self.jitter = patch("backend.clients.polygon.random.uniform", return_value=0)
        self.cache_get.start()
        self.cache_set.start()
        self.sleep.start()
        self.jitter.start()

    def tearDown(self):
        polygon_module.SNAPSHOT_PREFILTER_ENABLED = False
        patch.stopall()

    def test_429_retries_iteratively_with_backoff_and_timeout(self):
        client = PolygonClient("test-key")
        client.session = FakeSession(
            [
                FakeResponse(429, text="rate limited"),
                FakeResponse(429, text="rate limited"),
                FakeResponse(200, {"results": [{"c": 1}]}),
            ]
        )

        result = client._request("/v2/example", {"symbol": "AAPL"})

        self.assertEqual(result, {"results": [{"c": 1}]})
        self.assertEqual(len(client.session.calls), 3)
        self.assertTrue(all(call["timeout"] == REQUEST_TIMEOUT_SECONDS for call in client.session.calls))
        self.assertEqual(client.consecutive_failures, 0)

    def test_timeout_retries_and_opens_circuit_after_five_failures(self):
        client = PolygonClient("test-key")
        client.session = FakeSession(
            [
                requests.Timeout("timeout 1"),
                requests.Timeout("timeout 2"),
                requests.Timeout("timeout 3"),
                requests.Timeout("timeout 4"),
                requests.Timeout("timeout 5"),
            ]
        )

        first = client._request("/v2/example", {"symbol": "AAPL"})
        second = client._request("/v2/example", {"symbol": "MSFT"})
        calls_after_open = len(client.session.calls)
        third = client._request("/v2/example", {"symbol": "NVDA"})

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertIsNone(third)
        self.assertEqual(calls_after_open, 5)
        self.assertEqual(len(client.session.calls), calls_after_open)
        self.assertGreater(client.circuit_open_until, 0)
        self.assertTrue(all(call["timeout"] == REQUEST_TIMEOUT_SECONDS for call in client.session.calls))

    def test_snapshot_preflight_falls_back_when_ticker_missing(self):
        polygon_module.SNAPSHOT_PREFILTER_ENABLED = True
        client = PolygonClient("test-key")
        client._snapshot_indexes["stocks"] = {"MSFT": {"ticker": "MSFT", "day": {"v": 100}}}

        with patch.object(client, "_request", return_value={"results": [{"c": 10}]}) as request:
            result = client.get_aggregates("AAPL")

        self.assertEqual(result, [{"c": 10}])
        request.assert_called_once()

    def test_missing_api_key_sets_provider_error(self):
        client = PolygonClient("")

        result = client._request("/v2/example", {"symbol": "AAPL"})

        self.assertIsNone(result)
        self.assertEqual(client.last_error["type"], "missing_api_key")

    def test_aggregates_skip_snapshot_prefilter_by_default(self):
        polygon_module.SNAPSHOT_PREFILTER_ENABLED = False
        client = PolygonClient("test-key")

        with patch.object(client, "_snapshot_allows_ohlcv_fetch") as snapshot, patch.object(
            client, "_request", return_value={"results": [{"c": 10}]}
        ):
            result = client.get_aggregates("AAPL")

        self.assertEqual(result, [{"c": 10}])
        snapshot.assert_not_called()

    def test_reference_tickers_paginates_next_url(self):
        client = PolygonClient("test-key")
        client.session = FakeSession(
            [
                FakeResponse(200, {"results": [{"ticker": "AAA"}], "next_url": "https://api.polygon.io/v3/reference/tickers?cursor=next"}),
                FakeResponse(200, {"results": [{"ticker": "BBB"}]}),
            ]
        )

        result = client.get_reference_tickers("XNAS")

        self.assertEqual(result, [{"ticker": "AAA"}, {"ticker": "BBB"}])
        self.assertEqual(len(client.session.calls), 2)
        self.assertEqual(client.session.calls[0]["params"]["exchange"], "XNAS")
        self.assertEqual(client.session.calls[1]["params"], {})

    def test_aggregate_pagination_fixes_original_stale_truncation_and_deduplicates(self):
        client = PolygonClient("test-key")
        first_page = {
            "results": [{"t": 1, "c": 101}, {"t": 2, "c": 102}],
            "next_url": "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/hour/next",
        }
        client.session = FakeSession(
            [
                FakeResponse(200, first_page),
                FakeResponse(
                    200,
                    {"results": [{"t": 2, "c": 202}, {"t": 3, "c": 103}]},
                ),
            ]
        )

        # This is the pre-Phase-6 truncation: only the first page was used,
        # ending at stale timestamp 2 even though a continuation was supplied.
        self.assertEqual(first_page["results"][-1]["t"], 2)

        result = client.get_aggregates(
            "AAPL",
            timespan="hour",
            multiplier=1,
            from_date="2026-01-01",
            to_date="2026-07-14",
        )

        self.assertEqual(len(client.session.calls), 2)
        self.assertEqual([bar["t"] for bar in result], [1, 2, 3])
        self.assertEqual(result[1]["c"], 202)
        self.assertEqual(result[-1]["t"], 3)


if __name__ == "__main__":
    unittest.main()
