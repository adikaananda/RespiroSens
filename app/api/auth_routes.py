from flask import Blueprint, g, jsonify, request

from app.auth import issue_token, login_required
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active or not user.check_password(password):
        return jsonify({"error": "invalid_credentials", "message": "Email atau kata sandi salah."}), 401

    token = issue_token(user)
    return jsonify({"token": token, "user": user.to_dict()})


@bp.get("/me")
@login_required
def me():
    return jsonify(g.current_user.to_dict())
