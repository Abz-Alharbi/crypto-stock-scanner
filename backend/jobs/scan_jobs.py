import logging

from backend.factory import create_app
from backend.errors import ApiError
from backend.services import scans
from backend.services.scan_jobs import (
    is_scan_cancel_requested,
    set_scan_job_state,
    scan_status_payload,
)

logger = logging.getLogger(__name__)


class ScanCancelled(Exception):
    pass


def run_scan_job(job_id, user_id, market, filters, timeframe, limit):
    app = create_app()

    def progress_callback(update):
        if is_scan_cancel_requested(job_id):
            raise ScanCancelled()
        set_scan_job_state(job_id, status="running", **update)

    try:
        set_scan_job_state(job_id, status="running", progress=1)
        with app.app_context():
            payload = scans.scan_market(
                market,
                filters,
                timeframe,
                limit,
                user_id=user_id,
                job_id=job_id,
                progress_callback=progress_callback,
            )
        state = set_scan_job_state(
            job_id,
            status="completed",
            progress=100,
            results=payload.get("results", []),
            meta=payload.get("meta"),
            error=None,
        )
        return scan_status_payload(state)
    except ScanCancelled:
        state = set_scan_job_state(job_id, status="canceled")
        return scan_status_payload(state)
    except ApiError as exc:
        logger.exception(
            "scan_job_api_failed",
            extra={
                "job_id": job_id,
                "market": market,
                "timeframe": timeframe,
                "code": exc.code,
                "status_code": exc.status_code,
            },
        )
        set_scan_job_state(
            job_id,
            status="failed",
            error={
                "message": exc.message,
                "code": exc.code,
                "status_code": exc.status_code,
                "details": exc.details,
            },
        )
        raise
    except Exception as exc:
        logger.exception(
            "scan_job_failed",
            extra={"job_id": job_id, "market": market, "timeframe": timeframe},
        )
        set_scan_job_state(job_id, status="failed", error=str(exc))
        raise
