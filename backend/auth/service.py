import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, has_app_context, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.errors import ApiError, error_response
from backend.extensions import db
from backend.models.user import User
from backend.services.redis_store import (
    redis_delete,
    redis_exists,
    redis_get_json,
    redis_set_json,
    redis_set_value,
    redis_ttl,
)

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
MOCK_AUTH_USER_PAYLOAD = {
    "id": 1,
    "username": "test",
    "email": "test@test.com",
    "role": "admin",
    "plan": "pro",
    "is_active": True,
}


class MockAuthUser:
    id = MOCK_AUTH_USER_PAYLOAD["id"]
    username = MOCK_AUTH_USER_PAYLOAD["username"]
    email = MOCK_AUTH_USER_PAYLOAD["email"]
    role = MOCK_AUTH_USER_PAYLOAD["role"]
    plan = MOCK_AUTH_USER_PAYLOAD["plan"]
    is_active = MOCK_AUTH_USER_PAYLOAD["is_active"]

    def to_dict(self):
        return dict(MOCK_AUTH_USER_PAYLOAD)


MOCK_AUTH_USER = MockAuthUser()


def _token_key(token):
    return f"auth:token:{token}"


def _blocklist_key(token):
    return f"auth:blocklist:{token}"


def auth_disabled():
    if has_app_context():
        return bool(current_app.config.get("AUTH_DISABLED", False))
    return os.getenv("AUTH_DISABLED", "false").lower() == "true"


def _ensure_auth_disabled_db_user():
    try:
        existing = db.session.get(User, MOCK_AUTH_USER.id)
        if existing:
            return

        user = User(
            id=MOCK_AUTH_USER.id,
            username=MOCK_AUTH_USER.username,
            email=MOCK_AUTH_USER.email,
            role="admin",
            plan="premium",
            is_active=True,
        )
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.flush()
        if db.engine.dialect.name == "postgresql":
            db.session.execute(
                text("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT COALESCE(MAX(id), 1) FROM users))")
            )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def generate_token(user_id):
    token = secrets.token_urlsafe(32)
    stored = redis_set_json(
        _token_key(token),
        {
        "user_id": user_id,
        "expires": (datetime.utcnow() + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat(),
        },
        ttl=TOKEN_TTL_SECONDS,
    )
    if not stored:
        raise ApiError("Authentication store is unavailable", 503, "auth_store_unavailable")
    return token


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1]


def revoke_token(token):
    if not token:
        return
    ttl = redis_ttl(_token_key(token)) or TOKEN_TTL_SECONDS
    if not redis_set_value(_blocklist_key(token), "1", ttl=ttl):
        raise ApiError("Authentication store is unavailable", 503, "auth_store_unavailable")
    redis_delete(_token_key(token))


def is_token_revoked(token):
    return redis_exists(_blocklist_key(token))


def get_user_for_token(token):
    if not token or is_token_revoked(token):
        return None
    token_data = redis_get_json(_token_key(token))
    if not token_data:
        return None
    try:
        expires = datetime.fromisoformat(token_data["expires"])
    except (KeyError, TypeError, ValueError):
        redis_delete(_token_key(token))
        return None
    if expires < datetime.utcnow():
        redis_delete(_token_key(token))
        return None
    user = db.session.get(User, token_data["user_id"])
    if not user or not user.is_active:
        return None
    return user


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # RE-ENABLE AUTH: remove this block
        if auth_disabled():
            _ensure_auth_disabled_db_user()
            return f(MOCK_AUTH_USER, *args, **kwargs)

        token = get_bearer_token()
        if not token:
            return error_response("Token is missing", 401, "auth_required")
        current_user = get_user_for_token(token)
        if current_user is None:
            return error_response("Token is invalid or expired", 401, "invalid_token")
        return f(current_user, *args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(current_user, *args, **kwargs):
        if current_user.role != "admin":
            return error_response("Admin access required", 403, "forbidden")
        return f(current_user, *args, **kwargs)

    return decorated


def register_user(data):
    if User.query.filter_by(email=data.email).first():
        raise ApiError("Email already registered", 400, "duplicate_email")
    if User.query.filter_by(username=data.username).first():
        raise ApiError("Username already taken", 400, "duplicate_username")

    user = User(username=data.username, email=data.email)
    user.set_password(data.password)
    db.session.add(user)
    db.session.commit()
    token = generate_token(user.id)
    return user, token


def login_user(data):
    user = User.query.filter((User.email == data.email) | (User.username == data.email)).first()
    if not user or not user.check_password(data.password):
        raise ApiError("Invalid email or password", 401, "invalid_credentials")
    if not user.is_active:
        raise ApiError("Account is disabled", 403, "account_disabled")

    token = generate_token(user.id)
    return user, token


def change_password(user, data):
    if not user.check_password(data.current_password):
        raise ApiError("Current password is incorrect", 400, "invalid_password")
    user.set_password(data.new_password)
    db.session.commit()


def logout_current_token():
    revoke_token(get_bearer_token())


def create_admin(email, password):
    existing = User.query.filter_by(email=email).first()
    if existing:
        existing.role = "admin"
        existing.is_active = True
        existing.set_password(password)
        db.session.commit()
        return existing, False

    username = email.split("@", 1)[0]
    base_username = username
    counter = 1
    while User.query.filter_by(username=username).first():
        counter += 1
        username = f"{base_username}{counter}"

    user = User(username=username, email=email, role="admin", is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, True
