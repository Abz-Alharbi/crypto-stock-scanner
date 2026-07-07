from datetime import datetime

from backend.extensions import db


class UniverseSymbol(db.Model):
    __tablename__ = "universe_symbols"
    __table_args__ = (
        db.CheckConstraint("exchange IN ('NASDAQ', 'NYSE')", name="ck_universe_symbols_exchange"),
        db.UniqueConstraint("symbol", name="uq_universe_symbols_symbol"),
        db.UniqueConstraint("exchange", "rank", name="uq_universe_symbols_exchange_rank"),
    )

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    exchange = db.Column(db.String(10), nullable=False, index=True)
    avg_daily_volume = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    computed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "avg_daily_volume": self.avg_daily_volume,
            "rank": self.rank,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }
