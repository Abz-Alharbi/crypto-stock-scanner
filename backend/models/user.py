from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from backend.extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        db.CheckConstraint("plan IN ('free', 'premium')", name="ck_users_plan"),
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    plan = db.Column(db.String(20), nullable=False, default="free")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    watchlists = db.relationship(
        "Watchlist",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "plan": self.plan,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }
