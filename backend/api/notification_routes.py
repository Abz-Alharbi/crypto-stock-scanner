from flask import Blueprint, jsonify

from backend.auth.service import token_required
from backend.services import notifications as notification_service

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@token_required
def list_notifications(current_user):
    return jsonify(notification_service.list_notifications(current_user))


@notifications_bp.route("/<int:notification_id>/read", methods=["PATCH"])
@token_required
def mark_notification_read(current_user, notification_id):
    return jsonify(notification_service.mark_notification_read(current_user, notification_id))
