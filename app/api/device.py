from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.device_integration.http_adapter import parse_payload, verify_hmac_signature
from app.extensions import db
from app.ml.features import extract_features, quality_control
from app.models import AuditLog, ScreeningSession, ScreeningStatus, VOCReading

bp = Blueprint("device", __name__, url_prefix="/api/device")


@bp.get("/status")
def device_status():
    """Lets a bench-test script / the device firmware itself sanity-check
    the field-mapping config before sending real data."""
    from app.device_integration.http_adapter import HttpDeviceAdapter
    return jsonify(HttpDeviceAdapter().health_check())


@bp.post("/ingest")
def ingest_device_payload():
    """
    Push endpoint for real RespiroSens hardware (or a bridge script sitting
    between the device's native protocol and HTTP). Active only when
    DEVICE_MODE=http.

    Required headers:
      X-Device-Token   — any non-empty per-device identifier/secret you assign
      X-Signature      — hex HMAC-SHA256 of the raw request body, using
                          DEVICE_HMAC_SECRET as the key
    Required body field:
      capture_token    — the device_capture_token returned by
                          POST /screening/sessions/<id>/breath-test, so this
                          reading gets attached to the right patient session.
    """
    if current_app.config.get("DEVICE_MODE") != "http":
        return jsonify({
            "error": "device_mode_disabled",
            "message": "Server sedang berjalan di DEVICE_MODE=simulation. Set DEVICE_MODE=http "
                       "di .env untuk mengaktifkan penerimaan data perangkat nyata.",
        }), 503

    device_token = request.headers.get("X-Device-Token")
    signature = request.headers.get("X-Signature")
    if not device_token:
        return jsonify({"error": "unauthorized", "message": "Header X-Device-Token wajib diisi."}), 401
    if not verify_hmac_signature(request.get_data(), signature):
        return jsonify({"error": "unauthorized", "message": "Tanda tangan HMAC tidak valid."}), 401

    body = request.get_json(silent=True) or {}
    capture_token = body.get("capture_token")
    if not capture_token:
        return jsonify({"error": "validation_error", "message": "Field 'capture_token' wajib diisi."}), 400

    session = ScreeningSession.query.filter_by(device_capture_token=capture_token).first()
    if not session:
        return jsonify({"error": "not_found",
                         "message": "capture_token tidak ditemukan atau sudah dipakai/kedaluwarsa."}), 404
    if session.device_capture_expires_at and session.device_capture_expires_at < datetime.utcnow():
        session.device_capture_token = None
        db.session.commit()
        return jsonify({"error": "expired", "message": "capture_token sudah kedaluwarsa. Ulangi dari aplikasi nakes."}), 410

    try:
        parsed = parse_payload(body)
    except FileNotFoundError:
        return jsonify({
            "error": "device_not_configured",
            "message": "device_field_map.json belum dibuat. Salin dari device_field_map.example.json "
                       "dan sesuaikan nama field dengan firmware Anda.",
        }), 501
    except (KeyError, TypeError) as exc:
        return jsonify({"error": "field_map_error", "message": f"device_field_map.json tidak valid: {exc}"}), 500

    raw_payload = parsed["raw_payload"]
    baseline_payload = parsed["baseline_payload"]
    device_vitals = parsed.get("vitals", {})
    quality_flag = quality_control(raw_payload)

    # Consume the token either way — one physical reading per issued token.
    session.device_capture_token = None
    session.device_capture_expires_at = None
    session.is_simulated = False

    if quality_flag != "valid":
        session.status = ScreeningStatus.INVALID_SAMPLE
        reading = VOCReading(
            session_id=session.id, source="http_device", is_simulated=False,
            device_id=device_token, raw_payload=raw_payload,
            baseline_payload=baseline_payload, features=None, quality_flag=quality_flag,
        )
        db.session.add(reading)
        db.session.add(AuditLog(action="device_ingest_invalid_sample", entity_type="screening_session",
                                 entity_id=session.id, details={"quality_flag": quality_flag}))
        db.session.commit()
        return jsonify({"status": "invalid_sample", "quality_flag": quality_flag}), 422

    features = extract_features(raw_payload, baseline_payload)
    reading = VOCReading(
        session_id=session.id, source="http_device", is_simulated=False,
        device_id=device_token, raw_payload=raw_payload,
        baseline_payload=baseline_payload, features=features, quality_flag=quality_flag,
    )
    # Real-time vitals from the same device upload, if the attached rig
    # includes a vitals module and device_field_map.json maps it — see
    # device_field_map.example.json's "vitals" section. Anything the device
    # didn't send is left untouched for the nakes to fill in manually.
    for field in ["heart_rate_bpm", "spo2_pct", "body_temp_c", "resp_rate_per_min", "fvc_pct", "fev1_pct"]:
        if field in device_vitals:
            setattr(session, field, device_vitals[field])
    session.status = ScreeningStatus.BREATH_TEST_DONE
    db.session.add(reading)
    db.session.add(AuditLog(action="device_ingest_completed", entity_type="screening_session",
                             entity_id=session.id, details={"is_simulated": False, "vitals_from_device": bool(device_vitals)}))
    db.session.commit()

    return jsonify({"status": "ok", "session_id": session.id, "reading": reading.to_dict()}), 202
