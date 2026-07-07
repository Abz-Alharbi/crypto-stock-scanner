import json
import logging
import os
import time
from datetime import timedelta

from backend.errors import ApiError
from backend.extensions import db
from backend.models.scan_template import ScanTemplate
from backend.services import notifications
from backend.services import scans
from backend.services.redis_store import get_redis_client
from backend.services.scan_jobs import SCAN_JOB_TIMEOUT_SECONDS, SCAN_QUEUE_NAME, get_scan_queue

logger = logging.getLogger(__name__)

SCHEDULE_MARKER_KEY = "scan_templates:evaluation_scheduled"


def template_interval_seconds():
    return int(os.getenv("SCAN_TEMPLATE_EVALUATION_INTERVAL_SECONDS", "900"))


def template_initial_delay_seconds():
    return int(os.getenv("SCAN_TEMPLATE_INITIAL_DELAY_SECONDS", "60"))


def list_templates(user):
    templates = ScanTemplate.query.filter_by(user_id=user.id).order_by(ScanTemplate.created_at.desc()).all()
    return {"templates": [template.to_dict() for template in templates]}


def create_template(user, data):
    criteria = {
        "market": data.market,
        "timeframe": data.timeframe,
        "filters": data.filters,
        "limit": data.limit,
    }
    template = ScanTemplate(
        user_id=user.id,
        name=data.name,
        criteria_json=json.dumps(criteria, sort_keys=True),
    )
    db.session.add(template)
    db.session.commit()
    return {"template": template.to_dict()}


def delete_template(user, template_id):
    template = ScanTemplate.query.filter_by(id=template_id, user_id=user.id).first()
    if not template:
        raise ApiError("Scan template not found", 404, "not_found")
    db.session.delete(template)
    db.session.commit()
    return {"message": "Scan template deleted"}


def evaluate_template(template):
    criteria = template.criteria()
    payload = scans.scan_market(
        criteria.get("market", "stocks"),
        criteria.get("filters", []),
        criteria.get("timeframe", "1D"),
        criteria.get("limit", 30),
        user_id=template.user_id,
        job_id=f"template-{template.id}-{int(time.time())}",
    )
    created = 0
    for result in payload.get("results", []):
        notification = notifications.create_scan_template_match_notification(template, result)
        if notification:
            created += 1
    db.session.commit()
    return {
        "template_id": template.id,
        "matches": len(payload.get("results", [])),
        "notifications_created": created,
    }


def evaluate_template_for_user(user, template_id):
    template = ScanTemplate.query.filter_by(id=template_id, user_id=user.id).first()
    if not template:
        raise ApiError("Scan template not found", 404, "not_found")
    return {"evaluation": evaluate_template(template)}


def evaluate_all_templates():
    templates = ScanTemplate.query.order_by(ScanTemplate.created_at.asc()).all()
    results = []
    notifications_created = 0
    for template in templates:
        try:
            result = evaluate_template(template)
            results.append(result)
            notifications_created += result["notifications_created"]
        except Exception as exc:
            logger.error("Scan template evaluation failed for template %s: %s", template.id, exc)
            db.session.rollback()
            results.append({"template_id": template.id, "error": str(exc)})
    return {
        "templates_evaluated": len(templates),
        "notifications_created": notifications_created,
        "results": results,
    }


def clear_template_sweep_marker():
    client = get_redis_client()
    if client is not None:
        client.delete(SCHEDULE_MARKER_KEY)


def schedule_next_template_sweep(delay_seconds=None):
    delay = int(delay_seconds if delay_seconds is not None else template_interval_seconds())
    client = get_redis_client()
    if client is None:
        return False

    marker_ttl = max(delay * 2, delay + 60)
    if not client.set(SCHEDULE_MARKER_KEY, "1", ex=marker_ttl, nx=True):
        return False

    from worker import evaluate_scan_templates_job

    queue = get_scan_queue()
    queue.enqueue_in(
        timedelta(seconds=delay),
        evaluate_scan_templates_job,
        job_id=f"scan-template-sweep-{int(time.time())}",
        job_timeout=SCAN_JOB_TIMEOUT_SECONDS,
        result_ttl=template_interval_seconds(),
        failure_ttl=template_interval_seconds(),
    )
    logger.info(
        "scan_template_sweep_scheduled",
        extra={"queue": SCAN_QUEUE_NAME, "delay_seconds": delay},
    )
    return True


def ensure_template_sweep_scheduled():
    try:
        return schedule_next_template_sweep(template_initial_delay_seconds())
    except Exception as exc:
        logger.warning("Scan template scheduler was not started: %s", exc)
        return False
