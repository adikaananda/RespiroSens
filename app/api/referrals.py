from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file

from app.auth import roles_required
from app.extensions import db
from app.models import ReferralLetter, Role, ScreeningSession

bp = Blueprint("referrals", __name__, url_prefix="/api/referrals")


@bp.get("")
@roles_required(Role.NAKES, Role.DINKES, Role.ADMIN)
def list_referrals():
    """Lists referrals with their patient/session context — used for the
    TCM confirmation worklist (Lapisan 3 of the heatmap)."""
    q = ReferralLetter.query.join(ScreeningSession, ReferralLetter.session_id == ScreeningSession.id)

    if g.current_user.role == Role.NAKES:
        q = q.filter(ScreeningSession.nakes_id == g.current_user.id)
    elif g.current_user.role == Role.DINKES and g.current_user.facility_id:
        q = q.filter(ScreeningSession.facility_id == g.current_user.facility_id)

    tcm_result = request.args.get("tcm_result")
    if tcm_result in ("pending", "positive", "negative"):
        q = q.filter(ReferralLetter.tcm_result == tcm_result)

    referrals = q.order_by(ReferralLetter.created_at.desc()).limit(100).all()
    result = []
    for r in referrals:
        d = r.to_dict()
        d["patient_name"] = r.session.patient.full_name if r.session and r.session.patient else None
        d["facility_name"] = r.session.facility.name if r.session and r.session.facility else None
        d["risk_score"] = r.session.prediction.risk_score if r.session and r.session.prediction else None
        d["risk_category"] = (
            r.session.prediction.risk_category.value
            if r.session and r.session.prediction else None
        )
        result.append(d)
    return jsonify(result)


@bp.get("/verify/<token>")
def verify_referral(token):
    """Public, lightweight verification page a receiving facility opens after
    scanning the QR on the referral PDF — closes the 'lost paper referral'
    gap described in the proposal. No auth required (this is meant to be
    scanned by staff at any facility), but only returns non-identifying
    triage info, not the full patient record."""
    referral = ReferralLetter.query.filter_by(qr_verification_token=token).first()
    if not referral:
        return jsonify({"error": "not_found", "message": "Kode verifikasi tidak ditemukan."}), 404

    session = referral.session
    prediction = session.prediction
    return jsonify({
        "referral_code": referral.referral_code,
        "screening_date": session.created_at.isoformat(),
        "risk_category": prediction.risk_category.value if prediction else None,
        "risk_score": prediction.risk_score if prediction else None,
        "trained_on_demo_data": prediction.trained_on_demo_data if prediction else None,
        "already_verified": referral.verified_at is not None,
        "verified_at": referral.verified_at.isoformat() if referral.verified_at else None,
    })


@bp.post("/verify/<token>")
def confirm_verification(token):
    """Receiving facility confirms they've seen the patient — updates
    Lapisan 2 (validasi klinis) of the heatmap."""
    referral = ReferralLetter.query.filter_by(qr_verification_token=token).first()
    if not referral:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    referral.verified_at = datetime.utcnow()
    referral.verified_by_facility = data.get("facility_name")
    db.session.commit()
    return jsonify(referral.to_dict())


@bp.patch("/<referral_id>/tcm-result")
@roles_required(Role.NAKES, Role.DINKES)
def set_tcm_result(referral_id):
    """Records the Xpert MTB/RIF (TCM) confirmation result — Lapisan 3 of the
    epidemiology heatmap. Entered manually since TCM testing happens outside
    RespiroSens itself."""
    referral = ReferralLetter.query.get_or_404(referral_id)
    data = request.get_json(silent=True) or {}
    result = data.get("tcm_result")
    if result not in ("pending", "positive", "negative"):
        return jsonify({"error": "validation_error", "message": "tcm_result harus pending/positive/negative."}), 400
    referral.tcm_result = result
    referral.tcm_result_at = datetime.utcnow()
    db.session.commit()
    return jsonify(referral.to_dict())


@bp.get("/<referral_id>/pdf")
def download_pdf(referral_id):
    referral = ReferralLetter.query.get_or_404(referral_id)
    if not referral.pdf_path:
        return jsonify({"error": "not_found", "message": "PDF belum tersedia."}), 404
    return send_file(referral.pdf_path, as_attachment=True,
                      download_name=f"{referral.referral_code}.pdf")
