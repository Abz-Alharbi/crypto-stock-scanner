import json

from backend.errors import ApiError
from backend.extensions import db
from backend.models.admin_audit_log import AdminAuditLog
from backend.models.scan import ScanHistory
from backend.models.user import User
from backend.services.cache import cache_size


def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return {"users": [user.to_dict() for user in users]}


def update_user(admin_user, user_id, data):
    if user_id < 1:
        raise ApiError("user_id must be at least 1", 400, "validation_error")
    user = db.session.get(User, user_id)
    if not user:
        raise ApiError("User not found", 404, "not_found")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise ApiError("At least one update field is required", 400, "validation_error")
    if "role" in updates:
        user.role = updates["role"]
    if "plan" in updates:
        user.plan = updates["plan"]
    if "is_active" in updates:
        user.is_active = updates["is_active"]
    db.session.add(
        AdminAuditLog(
            admin_user_id=admin_user.id,
            action="update_user",
            target_type="user",
            target_id=user.id,
            details=json.dumps(
                {
                    "updates": updates,
                    "target_email": user.email,
                },
                sort_keys=True,
            ),
        )
    )
    db.session.commit()
    return {"user": user.to_dict()}


def list_scans():
    scans = ScanHistory.query.order_by(ScanHistory.scan_date.desc()).limit(50).all()
    return {"scans": [scan.to_dict() for scan in scans]}


def stats():
    return {
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "total_scans": ScanHistory.query.count(),
        "cache_entries": cache_size(),
    }


def list_audit_logs():
    logs = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc()).limit(50).all()
    return {"audit_logs": [log.to_dict() for log in logs]}
