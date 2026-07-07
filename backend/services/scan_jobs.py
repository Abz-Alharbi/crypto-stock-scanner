import os
import time
import uuid
import logging

from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError

from backend.errors import ApiError
from backend.services.redis_store import (
    get_redis_client,
    redis_exists,
    redis_get_json,
    redis_set_json,
    redis_set_value,
)

SCAN_QUEUE_NAME = os.getenv("SCAN_QUEUE_NAME", "scans")
SCAN_JOB_TTL_SECONDS = int(os.getenv("SCAN_JOB_TTL_SECONDS", "86400"))
SCAN_JOB_TIMEOUT_SECONDS = int(os.getenv("SCAN_JOB_TIMEOUT_SECONDS", "1800"))

logger = logging.getLogger(__name__)


def _state_key(job_id):
    return f"scan_job:{job_id}:state"


def _cancel_key(job_id):
    return f"scan_job:{job_id}:cancel"


def _state_age_seconds(state):
    try:
        created_at = float(state.get("created_at") or 0)
    except (TypeError, ValueError):
        return 0
    if not created_at:
        return 0
    return time.time() - created_at


def get_scan_queue():
    client = get_redis_client()
    if client is None:
        raise ApiError("Redis is unavailable", 503, "redis_unavailable")
    return Queue(SCAN_QUEUE_NAME, connection=client)


def set_scan_job_state(scan_job_id, **updates):
    current = redis_get_json(_state_key(scan_job_id)) or {}
    current.update(updates)
    current["updated_at"] = time.time()
    if not redis_set_json(_state_key(scan_job_id), current, ttl=SCAN_JOB_TTL_SECONDS):
        raise ApiError("Redis is unavailable", 503, "redis_unavailable")
    return current


def get_scan_job_state(job_id):
    state = redis_get_json(_state_key(job_id))
    if not state or state.get("status") in {"completed", "failed", "canceled"}:
        return state

    client = get_redis_client()
    if client is None:
        return state

    try:
        job = Job.fetch(job_id, connection=client)
    except NoSuchJobError:
        if _state_age_seconds(state) > 30:
            return set_scan_job_state(
                job_id,
                status="failed",
                error="Scan job disappeared from the queue. Please restart the worker service and try again.",
            )
        return state
    except Exception as exc:
        logger.exception("scan_job_status_fetch_failed", extra={"job_id": job_id})
        return set_scan_job_state(
            job_id,
            status="failed",
            error=f"Unable to read scan worker status: {exc}",
        )

    try:
        rq_status = job.get_status(refresh=True)
    except Exception as exc:
        logger.exception("scan_job_status_refresh_failed", extra={"job_id": job_id})
        return set_scan_job_state(
            job_id,
            status="failed",
            error=f"Unable to refresh scan worker status: {exc}",
        )
    if rq_status == "failed":
        error = job.exc_info or "The scan worker failed before it could report progress."
        return set_scan_job_state(job_id, status="failed", error=str(error).splitlines()[-1])
    if rq_status in {"canceled", "stopped"}:
        return set_scan_job_state(job_id, status="canceled")
    if state.get("status") == "queued" and rq_status in {"started", "busy"}:
        return set_scan_job_state(job_id, status="running", progress=state.get("progress", 1))

    return state


def require_scan_job_for_user(job_id, user):
    state = get_scan_job_state(job_id)
    if not state:
        raise ApiError("Scan job not found", 404, "not_found")
    if user.role != "admin" and state.get("user_id") != user.id:
        raise ApiError("Scan job not found", 404, "not_found")
    return state


def enqueue_scan_job(user_id, data):
    job_id = str(uuid.uuid4())
    set_scan_job_state(
        job_id,
        job_id=job_id,
        user_id=user_id,
        status="queued",
        progress=0,
        results=None,
        error=None,
        market=data.market,
        timeframe=data.timeframe,
        filters=data.filters,
        limit=data.limit,
        created_at=time.time(),
    )

    if os.getenv("SCAN_QUEUE_SYNC", "false").lower() == "true":
        from backend.jobs.scan_jobs import run_scan_job

        run_scan_job(job_id, user_id, data.market, data.filters, data.timeframe, data.limit)
        return job_id

    queue = get_scan_queue()
    queue.enqueue(
        "backend.jobs.scan_jobs.run_scan_job",
        job_id,
        user_id,
        data.market,
        data.filters,
        data.timeframe,
        data.limit,
        job_id=job_id,
        job_timeout=SCAN_JOB_TIMEOUT_SECONDS,
        result_ttl=SCAN_JOB_TTL_SECONDS,
        failure_ttl=SCAN_JOB_TTL_SECONDS,
    )
    return job_id


def request_scan_cancel(job_id, user):
    state = require_scan_job_for_user(job_id, user)
    status = state.get("status")
    if status in {"completed", "failed", "canceled"}:
        return state

    redis_set_value(_cancel_key(job_id), "1", ttl=SCAN_JOB_TTL_SECONDS)
    try:
        job = Job.fetch(job_id, connection=get_redis_client())
        job.cancel()
    except (NoSuchJobError, AttributeError):
        pass

    return set_scan_job_state(job_id, status="canceled", progress=state.get("progress", 0))


def is_scan_cancel_requested(job_id):
    return redis_exists(_cancel_key(job_id))


def scan_status_payload(state):
    return {
        "job_id": state.get("job_id"),
        "status": state.get("status", "unknown"),
        "progress": state.get("progress", 0),
        "results": state.get("results"),
        "error": state.get("error"),
        "meta": state.get("meta"),
    }
