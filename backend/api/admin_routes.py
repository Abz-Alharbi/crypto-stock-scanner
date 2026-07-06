from flask import Blueprint, jsonify

from backend.auth.service import admin_required
from backend.schemas.common import parse_json
from backend.schemas.market import UpdateUserRequest
from backend.services import admin as admin_service

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/users", methods=["GET"])
@admin_required
def get_users(_current_user):
    return jsonify(admin_service.list_users())


@admin_bp.route("/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(current_user, user_id):
    data = parse_json(UpdateUserRequest)
    return jsonify(admin_service.update_user(current_user, user_id, data))


@admin_bp.route("/scans", methods=["GET"])
@admin_required
def get_scans(_current_user):
    return jsonify(admin_service.list_scans())


@admin_bp.route("/stats", methods=["GET"])
@admin_required
def get_stats(_current_user):
    return jsonify(admin_service.stats())


@admin_bp.route("/audit-logs", methods=["GET"])
@admin_required
def get_audit_logs(_current_user):
    return jsonify(admin_service.list_audit_logs())
