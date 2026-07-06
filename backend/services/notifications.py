import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import current_app

from backend.errors import ApiError
from backend.extensions import db
from backend.models.notification import Notification
from backend.models.user import User

logger = logging.getLogger(__name__)

DEDUP_WINDOW_SECONDS = 3600


def list_notifications(user, unread_only=False, limit=50):
    query = Notification.query.filter_by(user_id=user.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    items = query.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = Notification.query.filter_by(user_id=user.id).filter(Notification.read_at.is_(None)).count()
    return {
        "notifications": [item.to_dict() for item in items],
        "unread_count": unread_count,
    }


def mark_notification_read(user, notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first()
    if not notification:
        raise ApiError("Notification not found", 404, "not_found")
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.session.commit()
    return {"notification": notification.to_dict()}


def create_scan_template_match_notification(template, result):
    provider_symbol = result.get("provider_symbol") or result.get("raw_symbol") or result.get("symbol")
    display_symbol = result.get("display_symbol") or result.get("symbol") or provider_symbol
    signal = result.get("overall_signal") or result.get("signal") or "match"
    matched_filters = sorted(result.get("matched_filters") or [])
    dedupe_key = f"scan_template:{template.id}:{provider_symbol}:{signal}:{','.join(matched_filters)}"
    cutoff = datetime.utcnow() - timedelta(seconds=DEDUP_WINDOW_SECONDS)

    existing = (
        Notification.query.filter_by(user_id=template.user_id, dedupe_key=dedupe_key)
        .filter(Notification.created_at >= cutoff)
        .first()
    )
    if existing:
        return None

    title = f"{template.name}: {display_symbol} matched"
    message = f"{display_symbol} matched {len(matched_filters)} filter(s) with a {signal} signal."
    notification = Notification(
        user_id=template.user_id,
        type="scan_template_match",
        title=title,
        message=message,
        dedupe_key=dedupe_key,
        payload_json=json.dumps(
            {
                "template_id": template.id,
                "template_name": template.name,
                "symbol": display_symbol,
                "provider_symbol": provider_symbol,
                "market": result.get("market"),
                "signal": signal,
                "matched_filters": matched_filters,
                "match_pct": result.get("match_pct"),
            },
            sort_keys=True,
        ),
    )
    db.session.add(notification)
    db.session.flush()
    _send_email_if_configured(notification)
    return notification


def _send_email_if_configured(notification):
    smtp_host = current_app.config.get("SMTP_HOST")
    smtp_from = current_app.config.get("SMTP_FROM")
    if not smtp_host or not smtp_from:
        return

    user = db.session.get(User, notification.user_id)
    if not user or not user.email:
        return

    message = EmailMessage()
    message["Subject"] = notification.title
    message["From"] = smtp_from
    message["To"] = user.email
    message.set_content(notification.message)

    try:
        with smtplib.SMTP(smtp_host, int(current_app.config.get("SMTP_PORT", 587)), timeout=10) as smtp:
            if current_app.config.get("SMTP_USE_TLS"):
                smtp.starttls()
            username = current_app.config.get("SMTP_USERNAME")
            password = current_app.config.get("SMTP_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        logger.warning("SMTP notification failed: %s", exc)
