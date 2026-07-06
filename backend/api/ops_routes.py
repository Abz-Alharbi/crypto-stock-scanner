from flask import Blueprint, jsonify
from sqlalchemy import text

from backend.extensions import db
from backend.services.patternDetection.yoloService import get_yolo_service
from backend.services.redis_store import get_redis_client

ops_bp = Blueprint("ops", __name__)


@ops_bp.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "db": _db_status(),
            "redis": _redis_status(),
        }
    )


@ops_bp.route("/ready", methods=["GET"])
def ready():
    db_status = _db_status()
    model_status = "ok" if get_yolo_service().is_loaded else "unavailable"
    payload = {
        "status": "ready" if db_status == "ok" and model_status == "ok" else "not_ready",
        "db": db_status,
        "model": model_status,
    }
    return jsonify(payload), 200 if payload["status"] == "ready" else 503


def _db_status():
    try:
        db.session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        db.session.rollback()
        return "unavailable"


def _redis_status():
    client = get_redis_client()
    if client is None:
        return "unavailable"
    try:
        client.ping()
        return "ok"
    except Exception:
        return "unavailable"
