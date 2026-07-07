import json
import time

from flask import Blueprint, Response, jsonify, stream_with_context

from backend.auth.service import token_required
from backend.schemas.common import parse_json, parse_query
from backend.schemas.market import ChartQuery, ScanRequest, ScanTemplateCreateRequest, SearchQuery, normalize_symbol
from backend.services import scan_jobs
from backend.services import scan_templates
from backend.services import scans as scan_service
from backend.services.universe import universe_builder

scan_bp = Blueprint("scan_api", __name__, url_prefix="/api")


@scan_bp.route("/health", methods=["GET"])
def health():
    return jsonify(scan_service.health_payload())


@scan_bp.route("/filters", methods=["GET"])
def filters():
    return jsonify(scan_service.filters_payload())


@scan_bp.route("/universe/status", methods=["GET"])
def universe_status():
    return jsonify(universe_builder.status_payload())


@scan_bp.route("/search", methods=["GET"])
def search():
    query = parse_query(SearchQuery)
    return jsonify(scan_service.search_tickers(query.q, query.market))


@scan_bp.route("/stock/<symbol>", methods=["GET"])
def stock(symbol):
    query = parse_query(ChartQuery)
    return jsonify(scan_service.stock_detail(normalize_symbol(symbol), query.timeframe))


@scan_bp.route("/chart/<symbol>", methods=["GET"])
def chart(symbol):
    query = parse_query(ChartQuery)
    return jsonify(scan_service.chart_data(normalize_symbol(symbol), query.timeframe))


@scan_bp.route("/scan", methods=["POST"])
@token_required
def scan(current_user):
    data = parse_json(ScanRequest)
    job_id = scan_jobs.enqueue_scan_job(current_user.id, data)
    return jsonify({"job_id": job_id}), 202


@scan_bp.route("/scan/templates", methods=["GET"])
@token_required
def list_scan_templates(current_user):
    return jsonify(scan_templates.list_templates(current_user))


@scan_bp.route("/scan/templates", methods=["POST"])
@token_required
def create_scan_template(current_user):
    data = parse_json(ScanTemplateCreateRequest)
    return jsonify(scan_templates.create_template(current_user, data)), 201


@scan_bp.route("/scan/templates/<int:template_id>", methods=["DELETE"])
@token_required
def delete_scan_template(current_user, template_id):
    return jsonify(scan_templates.delete_template(current_user, template_id))


@scan_bp.route("/scan/templates/<int:template_id>/evaluate", methods=["POST"])
@token_required
def evaluate_scan_template(current_user, template_id):
    return jsonify(scan_templates.evaluate_template_for_user(current_user, template_id))


@scan_bp.route("/scan/status/<job_id>", methods=["GET"])
@token_required
def scan_status(current_user, job_id):
    state = scan_jobs.require_scan_job_for_user(job_id, current_user)
    return jsonify(scan_jobs.scan_status_payload(state))


@scan_bp.route("/scan/<job_id>", methods=["DELETE"])
@token_required
def cancel_scan(current_user, job_id):
    state = scan_jobs.request_scan_cancel(job_id, current_user)
    return jsonify(scan_jobs.scan_status_payload(state))


@scan_bp.route("/scan/stream/<job_id>", methods=["GET"])
@token_required
def stream_scan(current_user, job_id):
    scan_jobs.require_scan_job_for_user(job_id, current_user)

    def event_stream():
        last_payload = None
        while True:
            state = scan_jobs.require_scan_job_for_user(job_id, current_user)
            payload = scan_jobs.scan_status_payload(state)
            encoded = json.dumps(payload, separators=(",", ":"))
            if encoded != last_payload:
                yield f"data: {encoded}\n\n"
                last_payload = encoded
            if payload["status"] in {"completed", "failed", "canceled"}:
                break
            time.sleep(1)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
