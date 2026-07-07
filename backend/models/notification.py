import json
from datetime import datetime

from backend.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(80), nullable=False, default="scan_template_match")
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    payload_json = db.Column(db.Text, nullable=True)
    dedupe_key = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True, index=True)

    def payload(self):
        try:
            return json.loads(self.payload_json or "{}")
        except json.JSONDecodeError:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "payload": self.payload(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "is_read": self.read_at is not None,
        }
