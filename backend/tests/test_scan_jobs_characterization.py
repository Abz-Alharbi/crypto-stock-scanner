from contextlib import nullcontext

import pytest

from backend.errors import ApiError
from backend.jobs import scan_jobs
from backend.services.universe.providers import UniverseResolution


class FakeApp:
    def app_context(self):
        return nullcontext()


def test_worker_failure_state_preserves_structured_api_error(monkeypatch):
    state_updates = []

    def record_state(job_id, **updates):
        state = {"job_id": job_id, **updates}
        state_updates.append(state)
        return state

    def fail_scan(*_args, **_kwargs):
        raise ApiError(
            "No usable market data",
            502,
            "provider_data_unavailable",
            {"market": "crypto", "timeframe": "1D", "attempted": 15},
        )

    monkeypatch.setattr(scan_jobs, "create_app", lambda: FakeApp())
    monkeypatch.setattr(scan_jobs, "set_scan_job_state", record_state)
    monkeypatch.setattr(scan_jobs.scans, "scan_market", fail_scan)

    with pytest.raises(ApiError):
        scan_jobs.run_scan_job("job-1", None, "crypto", ["rsi_oversold"], "1D", 30)

    assert state_updates[-1] == {
        "job_id": "job-1",
        "status": "failed",
        "error": {
            "message": "No usable market data",
            "code": "provider_data_unavailable",
            "status_code": 502,
            "details": {"market": "crypto", "timeframe": "1D", "attempted": 15},
        },
    }


def test_provider_failure_context_survives_scan_worker_boundary(
    monkeypatch,
    app,
    fake_provider,
):
    state_updates = []

    def record_state(job_id, **updates):
        state = {"job_id": job_id, **updates}
        state_updates.append(state)
        return state

    fake_provider.fail(
        "get_bars",
        message="Unauthorized",
        error_type="http_error",
        status_code=401,
    )
    monkeypatch.setattr(scan_jobs, "create_app", lambda: app)
    monkeypatch.setattr(scan_jobs, "set_scan_job_state", record_state)
    monkeypatch.setattr(scan_jobs, "is_scan_cancel_requested", lambda _job_id: False)
    monkeypatch.setattr(
        scan_jobs.scans,
        "resolve_scan_universe",
        lambda asset_class, universe_key=None: UniverseResolution(
            universe_key or "us_stocks_top",
            asset_class,
            ("AAPL",),
            "test",
        ),
    )

    with pytest.raises(ApiError) as exc:
        scan_jobs.run_scan_job("job-provider", None, "stocks", ["rsi_oversold"], "1D", 10)

    assert exc.value.code == "provider_data_unavailable"
    error = state_updates[-1]["error"]
    assert error["code"] == "provider_data_unavailable"
    assert error["status_code"] == 502
    assert error["details"]["symbol_failures"][0] == {
        "symbol": "AAPL",
        "message": "Unauthorized",
        "provider": "fake",
        "operation": "get_bars",
        "error_type": "http_error",
        "status_code": 401,
        "instrument": "AAPL",
        "asset_class": "stocks",
        "timeframe": "1D",
    }
