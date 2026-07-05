from flask import Blueprint, jsonify

from backend.schemas.market import normalize_symbol
from backend.services.fundamentals import get_fundamentals

fundamentals_bp = Blueprint("fundamentals", __name__, url_prefix="/api/fundamentals")


@fundamentals_bp.route("/<symbol>", methods=["GET"])
def fundamentals(symbol):
    return jsonify(get_fundamentals(normalize_symbol(symbol)))
