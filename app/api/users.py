from flask import Blueprint, g, jsonify, request

from app.auth import roles_required
from app.extensions import db
from app.models import AuditLog, Facility, Role, User

bp = Blueprint("users", __name__, url_prefix="/api")


@bp.get("/users")
@roles_required(Role.ADMIN)
def list_users():
    q = User.query
    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(User.full_name.ilike(like), User.email.ilike(like)))
    role_filter = request.args.get("role")
    if role_filter in [r.value for r in Role]:
        q = q.filter(User.role == role_filter)
    users = q.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users])


@bp.post("/users")
@roles_required(Role.ADMIN)
def create_user():
    data = request.get_json(silent=True) or {}
    required = ["full_name", "email", "password", "role"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": "validation_error", "missing": missing}), 400

    if data["role"] not in [r.value for r in Role]:
        return jsonify({"error": "validation_error", "message": "Peran tidak valid."}), 400

    if User.query.filter_by(email=data["email"].strip().lower()).first():
        return jsonify({"error": "conflict", "message": "Email sudah terdaftar."}), 409

    user = User(
        full_name=data["full_name"],
        email=data["email"].strip().lower(),
        role=Role(data["role"]),
        facility_id=data.get("facility_id"),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.add(AuditLog(actor_user_id=g.current_user.id, action="create_user",
                             entity_type="user", entity_id=user.id))
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.patch("/users/<user_id>")
@roles_required(Role.ADMIN)
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if "full_name" in data:
        user.full_name = data["full_name"]
    if "role" in data and data["role"] in [r.value for r in Role]:
        user.role = Role(data["role"])
    if "facility_id" in data:
        user.facility_id = data["facility_id"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if "password" in data and data["password"]:
        user.set_password(data["password"])

    db.session.add(AuditLog(actor_user_id=g.current_user.id, action="update_user",
                             entity_type="user", entity_id=user.id, details=data))
    db.session.commit()
    return jsonify(user.to_dict())


@bp.delete("/users/<user_id>")
@roles_required(Role.ADMIN)
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.add(AuditLog(actor_user_id=g.current_user.id, action="deactivate_user",
                             entity_type="user", entity_id=user.id))
    db.session.commit()
    return jsonify({"status": "deactivated"})


@bp.get("/facilities")
@roles_required(Role.ADMIN, Role.DINKES, Role.NAKES)
def list_facilities():
    q = Facility.query
    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(Facility.name.ilike(like), Facility.district.ilike(like),
                             Facility.subdistrict.ilike(like)))
    facilities = q.order_by(Facility.name).all()
    return jsonify([f.to_dict() for f in facilities])


@bp.post("/facilities")
@roles_required(Role.ADMIN)
def create_facility():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "validation_error", "missing": ["name"]}), 400
    facility = Facility(name=data["name"], district=data.get("district"),
                         subdistrict=data.get("subdistrict"),
                         latitude=data.get("latitude"), longitude=data.get("longitude"))
    db.session.add(facility)
    db.session.commit()
    return jsonify(facility.to_dict()), 201
