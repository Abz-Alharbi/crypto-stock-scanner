from datetime import datetime

from backend.extensions import db
from backend.market_config import TIMEFRAME_CHECK_SQL
from backend.symbols import canonicalize_symbol


class ScanResult(db.Model):
    __tablename__ = "scan_results"
    __table_args__ = (
        db.CheckConstraint("market IN ('stocks', 'crypto')", name="ck_scan_results_market"),
        db.CheckConstraint(TIMEFRAME_CHECK_SQL, name="ck_scan_results_timeframe"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    job_id = db.Column(db.String(64), index=True)
    symbol = db.Column(db.String(20), index=True)
    provider_symbol = db.Column(db.String(20), index=True)
    display_symbol = db.Column(db.String(20))
    market = db.Column(db.String(10), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False, default="1D")
    scan_type = db.Column(db.String(50))
    scan_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    filters_matched = db.Column(db.Text)
    indicator_values = db.Column(db.Text)
    last_price = db.Column(db.Float)
    volume = db.Column(db.BigInteger)
    signal = db.Column(db.String(20))

    def to_dict(self):
        canonical = canonicalize_symbol(
            self.provider_symbol or self.symbol,
            self.market,
        )
        display_symbol = self.display_symbol or canonical.display_symbol
        provider_symbol = self.provider_symbol or canonical.provider_symbol
        return {
            "id": self.id,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "symbol": display_symbol,
            "raw_symbol": provider_symbol,
            "provider_symbol": provider_symbol,
            "display_symbol": display_symbol,
            "canonical_symbol": {
                "provider_symbol": provider_symbol,
                "display_symbol": display_symbol,
                "market": self.market,
            },
            "market": self.market,
            "timeframe": self.timeframe,
            "scan_type": self.scan_type,
            "scan_date": self.scan_date.isoformat() if self.scan_date else None,
            "filters_matched": self.filters_matched,
            "indicator_values": self.indicator_values,
            "last_price": self.last_price,
            "volume": self.volume,
            "signal": self.signal,
        }


class ScanHistory(db.Model):
    __tablename__ = "scan_history"
    __table_args__ = (
        db.CheckConstraint("market IN ('stocks', 'crypto')", name="ck_scan_history_market"),
        db.CheckConstraint(TIMEFRAME_CHECK_SQL, name="ck_scan_history_timeframe"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    job_id = db.Column(db.String(64), index=True)
    scan_date = db.Column(db.DateTime, default=datetime.utcnow)
    market = db.Column(db.String(10), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False, default="1D")
    total_scanned = db.Column(db.Integer)
    total_matched = db.Column(db.Integer)
    filters_used = db.Column(db.Text)
    duration_seconds = db.Column(db.Float)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "date": self.scan_date.isoformat() if self.scan_date else None,
            "market": self.market,
            "timeframe": self.timeframe,
            "total_scanned": self.total_scanned,
            "total_matched": self.total_matched,
            "filters_used": self.filters_used,
            "duration": self.duration_seconds,
        }
