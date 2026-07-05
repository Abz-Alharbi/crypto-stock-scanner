from flask import Blueprint, jsonify

from backend.schemas.common import parse_query
from backend.schemas.market import NewsQuery, normalize_symbol
from backend.services.news import get_news

news_bp = Blueprint("news", __name__, url_prefix="/api/news")


@news_bp.route("/<symbol>", methods=["GET"])
def news(symbol):
    query = parse_query(NewsQuery)
    return jsonify(
        get_news(
            normalize_symbol(symbol),
            limit=query.limit,
            days=query.days,
            sentiment_filter=query.sentiment,
            source_filter=query.source,
        )
    )
