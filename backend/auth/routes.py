from flask import Blueprint, jsonify

from backend.auth import service
from backend.auth.schemas import ChangePasswordRequest, LoginRequest, RegisterRequest
from backend.schemas.common import parse_json

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = parse_json(RegisterRequest)
    user, token = service.register_user(data)
    return jsonify({"user": user.to_dict(), "token": token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = parse_json(LoginRequest)
    user, token = service.login_user(data)
    return jsonify({"user": user.to_dict(), "token": token})


@auth_bp.route("/me", methods=["GET"])
@service.token_required
def me(current_user):
    return jsonify({"user": current_user.to_dict()})


@auth_bp.route("/change-password", methods=["POST"])
@service.token_required
def change_password(current_user):
    data = parse_json(ChangePasswordRequest)
    service.change_password(current_user, data)
    return jsonify({"message": "Password updated successfully"})


@auth_bp.route("/logout", methods=["POST"])
@service.token_required
def logout(_current_user):
    service.logout_current_token()
    return jsonify({"message": "Logged out successfully"})
