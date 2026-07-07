from datetime import datetime

from backend.extensions import db


class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    admin_user = db.relationship("User", foreign_keys=[admin_user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "admin_user_id": self.admin_user_id,
            "admin_email": self.admin_user.email if self.admin_user else None,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
