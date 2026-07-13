from datetime import datetime

from backend.extensions import db


def _default_universe_key(context):
    return {
        "NASDAQ": "nasdaq_top",
        "NYSE": "nyse_top",
    }.get(context.get_current_parameters().get("exchange"), "us_stocks_top")


def _default_venue(context):
    return {
        "NASDAQ": "XNAS",
        "NYSE": "XNYS",
    }.get(context.get_current_parameters().get("exchange"))


class UniverseSymbol(db.Model):
    __tablename__ = "universe_symbols"
    __table_args__ = (
        db.CheckConstraint(
            "asset_class IN ('equity', 'crypto')",
            name="ck_universe_symbols_asset_class",
        ),
        db.UniqueConstraint("symbol", name="uq_universe_symbols_symbol"),
        db.UniqueConstraint(
            "universe_key", "rank", name="uq_universe_symbols_universe_rank"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    asset_class = db.Column(
        db.String(10), nullable=False, default="equity", index=True
    )
    venue = db.Column(db.String(20), nullable=True, default=_default_venue, index=True)
    quote_currency = db.Column(db.String(10), nullable=True)
    universe_key = db.Column(
        db.String(64), nullable=False, default=_default_universe_key, index=True
    )
    exchange = db.Column(db.String(10), nullable=True, index=True)
    avg_daily_volume = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    computed_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "venue": self.venue,
            "quote_currency": self.quote_currency,
            "universe_key": self.universe_key,
            "exchange": self.exchange,
            "avg_daily_volume": self.avg_daily_volume,
            "rank": self.rank,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }
