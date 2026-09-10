from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from app.auth import roles_required
from app.extensions import db
from app.models import Patient, Role
from app.utils.ocr import extract_ktp_fields
from app.utils.security import hash_phone

bp = Blueprint("patients", __name__, url_prefix="/api/patients")


@bp.post("/ocr-scan")
@roles_required(Role.NAKES)
def ocr_scan():
    """Step 1 of the ~15s registration flow: nakes uploads a KTP photo, gets
    back extracted fields for a one-tap confirmation. Nothing is saved yet."""
    if "image" not in request.files:
        return jsonify({"error": "validation_error", "message": "Field 'image' (file) wajib diisi."}), 400

    image_bytes = request.files["image"].read()
    result = extract_ktp_fields(image_bytes)
    return jsonify(result)


@bp.post("/register")
@roles_required(Role.NAKES)
def register_patient():
    """Registers a patient either from confirmed OCR fields or the manual
    fallback form (for patients without a KTP: children, vulnerable groups,
    or a failed/low-confidence scan) — nobody is blocked by missing documents."""
    data = request.get_json(silent=True) or {}

    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return jsonify({"error": "validation_error", "missing": ["full_name"]}), 400

    if not data.get("consent_given"):
        return jsonify({"error": "validation_error",
                         "message": "Persetujuan (informed consent) pasien wajib dicatat sebelum registrasi."}), 400

    dob = None
    if data.get("date_of_birth"):
        try:
            dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "validation_error", "message": "Format tanggal lahir: YYYY-MM-DD"}), 400

    whatsapp_hash, whatsapp_last4 = (None, None)
    if data.get("whatsapp_number"):
        whatsapp_hash, whatsapp_last4 = hash_phone(
            data["whatsapp_number"], current_app.config["SECRET_KEY"]
        )

    def _to_number(value, cast):
        if value in (None, ""):
            return None
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None

    patient = Patient(
        full_name=full_name,
        nik=data.get("nik"),
        date_of_birth=dob,
        age=_to_number(data.get("age"), int),
        sex=data.get("sex"),
        address=data.get("address"),
        occupation=data.get("occupation"),
        height_cm=_to_number(data.get("height_cm"), float),
        weight_kg=_to_number(data.get("weight_kg"), float),
        whatsapp_number_hash=whatsapp_hash,
        whatsapp_number_last4=whatsapp_last4,
        registered_via="ktp_ocr" if data.get("nik") else "fallback_form",
        facility_id=g.current_user.facility_id,
        consent_given=True,
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify(patient.to_dict()), 201


@bp.get("/<patient_id>")
@roles_required(Role.NAKES, Role.DINKES, Role.ADMIN)
def get_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return jsonify(patient.to_dict())


@bp.get("")
@roles_required(Role.NAKES, Role.DINKES, Role.ADMIN)
def list_patients():
    q = Patient.query
    if g.current_user.role == Role.NAKES and g.current_user.facility_id:
        q = q.filter_by(facility_id=g.current_user.facility_id)
    search = request.args.get("search")
    if search:
        q = q.filter(Patient.full_name.ilike(f"%{search}%"))
    patients = q.order_by(Patient.created_at.desc()).limit(200).all()
    return jsonify([p.to_dict() for p in patients])
