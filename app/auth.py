from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.models import User


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="respirosens-auth")


def issue_token(user: User) -> str:
    return _serializer().dumps({"user_id": user.id, "role": user.role.value})


def decode_token(token: str):
    max_age = int(current_app.config["JWT_EXPIRES"].total_seconds())
    return _serializer().loads(token, max_age=max_age)


def get_current_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except (BadSignature, SignatureExpired):
        return None
    return User.query.get(payload.get("user_id"))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None or not user.is_active:
            return jsonify({"error": "unauthorized", "message": "Token tidak valid atau kedaluwarsa."}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    role_values = {r.value if hasattr(r, "value") else r for r in roles}

    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if g.current_user.role.value not in role_values:
                return jsonify({"error": "forbidden", "message": "Peran Anda tidak memiliki akses ini."}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
