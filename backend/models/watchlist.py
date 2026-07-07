from datetime import datetime

from backend.extensions import db
from backend.symbols import canonicalize_symbol


class Watchlist(db.Model):
    __tablename__ = "watchlists"
    __table_args__ = (
        db.UniqueConstraint("user_id", "symbol", name="uq_watchlists_user_symbol"),
        db.CheckConstraint("market IN ('stocks', 'crypto')", name="ck_watchlists_market"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    provider_symbol = db.Column(db.String(20), nullable=False, index=True)
    display_symbol = db.Column(db.String(20), nullable=False)
    market = db.Column(db.String(10), nullable=False, default="stocks")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    def to_dict(self):
        canonical = canonicalize_symbol(
            self.provider_symbol or self.symbol,
            self.market,
        )
        provider_symbol = self.provider_symbol or canonical.provider_symbol
        display_symbol = provider_symbol if self.market == "crypto" else self.display_symbol or canonical.display_symbol
        return {
            "id": self.id,
            "symbol": display_symbol,
            "raw_symbol": provider_symbol,
            "provider_symbol": provider_symbol,
            "display_symbol": display_symbol,
            "market": self.market,
            "canonical_symbol": {
                "provider_symbol": provider_symbol,
                "display_symbol": display_symbol,
                "market": self.market,
            },
            "notes": self.notes,
            "added_at": self.added_at.isoformat() if self.added_at else None,
        }
