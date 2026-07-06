from flask import Blueprint, jsonify

from backend.auth.service import token_required
from backend.errors import ApiError
from backend.schemas.common import parse_json
from backend.schemas.patterns import PatternDetectRequest
from backend.services import pattern_detection

pattern_bp = Blueprint("pattern_api", __name__, url_prefix="/api")


@pattern_bp.route("/patterns/detect", methods=["POST"])
@token_required
def detect_patterns(current_user):
    try:
        data = parse_json(PatternDetectRequest)
        pattern_detection.ensure_pattern_rate_limit(current_user.id)
        return jsonify(pattern_detection.detect_pattern_for_user(current_user, data))
    except ApiError as exc:
        return jsonify({"error": exc.message, "signal_priority": None}), exc.status_code
