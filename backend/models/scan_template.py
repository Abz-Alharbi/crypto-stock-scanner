import json
from datetime import datetime

from backend.extensions import db


class ScanTemplate(db.Model):
    __tablename__ = "scan_templates"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    criteria_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def criteria(self):
        try:
            return json.loads(self.criteria_json or "{}")
        except json.JSONDecodeError:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "criteria": self.criteria(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
