from backend.errors import ApiError
from backend.extensions import db
from backend.models.watchlist import Watchlist
from backend.symbols import canonicalize_symbol


def list_watchlist(user):
    items = (
        Watchlist.query.filter_by(user_id=user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )
    return {"watchlist": [item.to_dict() for item in items]}


def add_watchlist_item(user, symbol, market, notes):
    canonical = canonicalize_symbol(symbol, market)
    existing = Watchlist.query.filter_by(user_id=user.id, symbol=canonical.provider_symbol).first()
    if existing:
        raise ApiError("Already in watchlist", 409, "duplicate_symbol")

    item = Watchlist(
        user_id=user.id,
        symbol=canonical.provider_symbol,
        provider_symbol=canonical.provider_symbol,
        display_symbol=canonical.display_symbol,
        market=canonical.market,
        notes=notes,
    )
    db.session.add(item)
    db.session.commit()
    return {"message": f"{canonical.display_symbol} added to watchlist", "id": item.id}


def remove_watchlist_item(user, item_id):
    item = Watchlist.query.filter_by(id=item_id, user_id=user.id).first()
    if not item:
        raise ApiError("Item not found", 404, "not_found")
    db.session.delete(item)
    db.session.commit()
    return {"message": "Removed from watchlist"}
