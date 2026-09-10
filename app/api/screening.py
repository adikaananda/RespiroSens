import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request

from app.auth import roles_required
from app.device_integration import get_device_adapter
from app.extensions import db
from app.ml import pipeline as ml_pipeline
from app.ml.features import extract_features, quality_control
from app.models import (
    AuditLog,
    Patient,
    Prediction,
    ReferralLetter,
    Role,
    RiskCategory,
    ScreeningSession,
    ScreeningStatus,
    VOCReading,
)
from app.utils.pdf_generator import generate_referral_pdf
from app.utils.security import generate_referral_code
from app.utils.whatsapp import WhatsAppClient

bp = Blueprint("screening", __name__, url_prefix="/api/screening")


def _get_session_or_404(session_id):
    return ScreeningSession.query.get_or_404(session_id)


def _log(action, entity_id, details=None):
    db.session.add(AuditLog(actor_user_id=g.current_user.id, action=action,
                             entity_type="screening_session", entity_id=entity_id, details=details))


@bp.post("/sessions")
@roles_required(Role.NAKES)
def create_session():
    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id")
    if not patient_id or not Patient.query.get(patient_id):
        return jsonify({"error": "validation_error", "message": "patient_id tidak valid."}), 400

    session = ScreeningSession(
        patient_id=patient_id,
        nakes_id=g.current_user.id,
        facility_id=g.current_user.facility_id,
        status=ScreeningStatus.REGISTERED,
    )
    db.session.add(session)
    _log("create_session", session.id)
    db.session.commit()
    return jsonify(session.to_dict()), 201


@bp.get("/sessions")
@roles_required(Role.NAKES, Role.DINKES, Role.ADMIN)
def list_sessions():
    q = ScreeningSession.query
    if g.current_user.role == Role.NAKES:
        q = q.filter_by(nakes_id=g.current_user.id)
    elif g.current_user.role == Role.DINKES and g.current_user.facility_id:
        q = q.filter_by(facility_id=g.current_user.facility_id)

    search = request.args.get("search")
    if search:
        q = q.join(Patient, ScreeningSession.patient_id == Patient.id).filter(
            Patient.full_name.ilike(f"%{search}%")
        )

    status_filter = request.args.get("status")
    if status_filter:
        q = q.filter(ScreeningSession.status == status_filter)

    patient_id_filter = request.args.get("patient_id")
    if patient_id_filter:
        q = q.filter(ScreeningSession.patient_id == patient_id_filter)

    sessions = q.order_by(ScreeningSession.created_at.desc()).limit(200).all()
    return jsonify([s.to_dict(include_related=False) for s in sessions])


@bp.get("/sessions/<session_id>")
@roles_required(Role.NAKES, Role.DINKES, Role.ADMIN)
def get_session(session_id):
    return jsonify(_get_session_or_404(session_id).to_dict())


@bp.patch("/sessions/<session_id>/symptoms")
@roles_required(Role.NAKES)
def update_symptoms(session_id):
    session = _get_session_or_404(session_id)
    data = request.get_json(silent=True) or {}
    fields = [
        "symptom_cough_gt_2weeks", "symptom_fever", "symptom_night_sweats",
        "symptom_weight_loss", "symptom_shortness_of_breath", "symptom_chest_pain",
    ]
    for f in fields:
        key = f.replace("symptom_", "")
        if key in data:
            setattr(session, f, bool(data[key]))
    session.status = ScreeningStatus.SYMPTOMS_DONE
    db.session.commit()
    return jsonify(session.to_dict())


@bp.patch("/sessions/<session_id>/risk-factors")
@roles_required(Role.NAKES)
def update_risk_factors(session_id):
    session = _get_session_or_404(session_id)
    data = request.get_json(silent=True) or {}
    if "smoking_history" in data:
        session.smoking_history = data["smoking_history"]
    if "known_tb_contact" in data:
        session.known_tb_contact = bool(data["known_tb_contact"])
    if "diabetes" in data:
        session.diabetes = bool(data["diabetes"])
    if "immunocompromised" in data:
        session.immunocompromised = bool(data["immunocompromised"])
    if "sputum_produces" in data:
        session.sputum_produces = bool(data["sputum_produces"])
    session.status = ScreeningStatus.RISK_FACTORS_DONE
    db.session.commit()
    return jsonify(session.to_dict())


@bp.patch("/sessions/<session_id>/vitals")
@roles_required(Role.NAKES)
def update_vitals(session_id):
    session = _get_session_or_404(session_id)
    data = request.get_json(silent=True) or {}
    for f in ["heart_rate_bpm", "spo2_pct", "body_temp_c", "resp_rate_per_min", "fvc_pct", "fev1_pct"]:
        if f in data and data[f] not in (None, ""):
            try:
                setattr(session, f, float(data[f]))
            except (TypeError, ValueError):
                return jsonify({"error": "validation_error", "message": f"{f} harus berupa angka."}), 400
    session.status = ScreeningStatus.VITALS_DONE
    db.session.commit()
    return jsonify(session.to_dict())


@bp.post("/sessions/<session_id>/breath-test")
@roles_required(Role.NAKES)
def run_breath_test(session_id):
    """
    Runs (or starts) one RespiroSens purge -> sample -> upload cycle, per the
    pipeline: RespiroSens Device -> Flask API -> Validation -> Preprocessing -> ...

    - DEVICE_MODE=simulation: synchronous, returns the result immediately
      (unchanged from before).
    - DEVICE_MODE=http: asynchronous — issues a device_capture_token and
      returns right away with status "waiting_for_device". The frontend
      should poll GET /screening/sessions/<id> until status moves past
      "breath_test_pending" (the real device pushes the reading to
      POST /api/device/ingest once the breath sample is ready).
    """
    session = _get_session_or_404(session_id)
    device_mode = current_app.config.get("DEVICE_MODE", "simulation")

    if device_mode == "http":
        token = secrets.token_hex(16)
        session.device_capture_token = token
        session.device_capture_expires_at = datetime.utcnow() + timedelta(
            seconds=current_app.config.get("DEVICE_CAPTURE_TIMEOUT_SEC", 180)
        )
        session.status = ScreeningStatus.BREATH_TEST_PENDING
        _log("device_capture_started", session.id)
        db.session.commit()
        return jsonify({
            "status": "waiting_for_device",
            "device_capture_token": token,
            "expires_in_sec": current_app.config.get("DEVICE_CAPTURE_TIMEOUT_SEC", 180),
            "message": "Menunggu data dari perangkat RespiroSens. Mulai pengambilan napas di alat, "
                       "sertakan capture_token ini saat perangkat mengirim data ke /api/device/ingest.",
        }), 202

    data = request.get_json(silent=True) or {}
    risk_hint = data.get("_simulation_risk_hint", "random")  # test/demo only, ignored by real devices

    adapter = get_device_adapter()
    try:
        sample = adapter.acquire_breath_sample(session_id=session.id, risk_hint=risk_hint)
    except NotImplementedError as exc:
        return jsonify({"error": "device_not_configured", "message": str(exc)}), 501

    quality_flag = quality_control(sample.raw_payload)
    if quality_flag != "valid":
        session.status = ScreeningStatus.INVALID_SAMPLE
        reading = VOCReading(
            session_id=session.id, source=sample.source, is_simulated=sample.is_simulated,
            device_id=sample.device_id, raw_payload=sample.raw_payload,
            baseline_payload=sample.baseline_payload, features=None, quality_flag=quality_flag,
        )
        db.session.add(reading)
        db.session.commit()
        return jsonify({
            "status": "invalid_sample",
            "quality_flag": quality_flag,
            "message": "Sampel napas tidak valid (durasi/volume kurang). Ulangi pengambilan sampel.",
        }), 422

    features = extract_features(sample.raw_payload, sample.baseline_payload)
    reading = VOCReading(
        session_id=session.id, source=sample.source, is_simulated=sample.is_simulated,
        device_id=sample.device_id, raw_payload=sample.raw_payload,
        baseline_payload=sample.baseline_payload, features=features, quality_flag=quality_flag,
    )
    session.is_simulated = sample.is_simulated
    # Real-time vitals from the same device reading (see BreathSampleResult.vitals)
    # replace the old "type it in by hand" step — whichever fields the device
    # didn't supply are simply left as-is for the nakes to fill in manually.
    for field in ["heart_rate_bpm", "spo2_pct", "body_temp_c", "resp_rate_per_min", "fvc_pct", "fev1_pct"]:
        value = sample.vitals.get(field)
        if value is not None:
            setattr(session, field, float(value))
    session.status = ScreeningStatus.BREATH_TEST_DONE
    db.session.add(reading)
    _log("breath_test_completed", session.id, {"is_simulated": sample.is_simulated, "vitals_from_device": bool(sample.vitals)})
    db.session.commit()
    return jsonify({"status": "ok", "reading": reading.to_dict(), "session": session.to_dict()})


@bp.post("/sessions/<session_id>/predict")
@roles_required(Role.NAKES)
def predict_session(session_id):
    session = _get_session_or_404(session_id)
    if not session.voc_reading or not session.voc_reading.features:
        return jsonify({"error": "precondition_failed",
                         "message": "Lakukan breath-test terlebih dahulu sebelum prediksi."}), 412

    session.status = ScreeningStatus.PROCESSING
    db.session.commit()

    try:
        result = ml_pipeline.predict(session.voc_reading.features, current_app.config)
    except ml_pipeline.ModelNotTrainedError as exc:
        return jsonify({"error": "model_not_trained", "message": str(exc)}), 503

    prediction = Prediction(
        session_id=session.id,
        risk_score=result["risk_score"],
        risk_category=RiskCategory(result["risk_category"]),
        shap_values=result["shap_values"],
        model_version=result["model_version"],
        trained_on_demo_data=result["trained_on_demo_data"],
    )
    session.status = ScreeningStatus.PREDICTED
    db.session.add(prediction)
    _log("prediction_created", session.id, {"risk_score": result["risk_score"]})
    db.session.commit()
    return jsonify(session.to_dict())


@bp.post("/sessions/<session_id>/review")
@roles_required(Role.NAKES)
def review_session(session_id):
    """Human-in-the-loop clinical review: the nakes must explicitly approve
    before any referral/notification goes out. AI output stays a
    recommendation; referral authority stays with the clinician."""
    session = _get_session_or_404(session_id)
    if not session.prediction:
        return jsonify({"error": "precondition_failed", "message": "Belum ada hasil prediksi."}), 412

    data = request.get_json(silent=True) or {}
    prediction = session.prediction
    prediction.reviewed_by_id = g.current_user.id
    prediction.reviewed_at = datetime.utcnow()
    prediction.clinician_note = data.get("note")
    session.status = ScreeningStatus.CLINICAL_REVIEW

    referral_payload = None
    if prediction.risk_category in (RiskCategory.KUNING, RiskCategory.MERAH):
        referral = ReferralLetter(
            session_id=session.id,
            referral_code=generate_referral_code(),
            target_facility_name=data.get("target_facility_name"),
        )
        db.session.add(referral)
        db.session.flush()  # get referral.id / qr_verification_token

        verification_url = f"{request.host_url.rstrip('/')}/api/referrals/verify/{referral.qr_verification_token}"
        pdf_path = generate_referral_pdf(
            output_dir=current_app.config["OUTPUT_DIR"],
            referral_code=referral.referral_code,
            verification_url=verification_url,
            patient_name=session.patient.full_name,
            nik_masked=session.patient.to_dict()["nik_masked"],
            facility_name=session.facility.name if session.facility else None,
            target_facility_name=referral.target_facility_name,
            risk_score=prediction.risk_score,
            risk_category=prediction.risk_category.value,
            screening_date=session.created_at.strftime("%d %B %Y"),
        )
        referral.pdf_path = pdf_path
        session.status = ScreeningStatus.REFERRED

        whatsapp = WhatsAppClient(current_app.config)
        send_result = whatsapp.send_result_notification(
            to_number=data.get("whatsapp_number_for_sending", ""),
            to_number_hash=session.patient.whatsapp_number_hash or "unknown",
            patient_name=session.patient.full_name,
            risk_score=prediction.risk_score,
            risk_category=prediction.risk_category.value,
            referral_pdf_path=pdf_path,
        )
        referral.whatsapp_sent = send_result.get("status") in ("sent", "logged_only")
        referral.whatsapp_send_log = send_result
        referral_payload = referral.to_dict()
    else:
        session.status = ScreeningStatus.COMPLETED
        whatsapp = WhatsAppClient(current_app.config)
        whatsapp.send_result_notification(
            to_number=data.get("whatsapp_number_for_sending", ""),
            to_number_hash=session.patient.whatsapp_number_hash or "unknown",
            patient_name=session.patient.full_name,
            risk_score=prediction.risk_score,
            risk_category=prediction.risk_category.value,
        )

    _log("clinical_review_completed", session.id, {"category": prediction.risk_category.value})
    db.session.commit()

    response = session.to_dict()
    if referral_payload:
        response["referral"] = referral_payload
    return jsonify(response)
