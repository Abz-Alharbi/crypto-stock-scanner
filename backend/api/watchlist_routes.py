from flask import Blueprint, jsonify

from backend.auth.service import token_required
from backend.schemas.common import parse_json
from backend.schemas.market import WatchlistAddRequest
from backend.services import watchlist as watchlist_service

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")


@watchlist_bp.route("", methods=["GET"])
@token_required
def get_watchlist(current_user):
    return jsonify(watchlist_service.list_watchlist(current_user))


@watchlist_bp.route("", methods=["POST"])
@token_required
def add_watchlist(current_user):
    data = parse_json(WatchlistAddRequest)
    payload = watchlist_service.add_watchlist_item(
        current_user,
        data.symbol,
        data.market,
        data.notes,
    )
    return jsonify(payload), 201


@watchlist_bp.route("/<int:item_id>", methods=["DELETE"])
@token_required
def remove_watchlist(current_user, item_id):
    return jsonify(watchlist_service.remove_watchlist_item(current_user, item_id))
