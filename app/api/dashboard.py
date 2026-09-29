from flask import Blueprint, g, jsonify

from app.auth import roles_required
from app.extensions import db
from app.models import Facility, Prediction, ReferralLetter, Role, ScreeningSession, User

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("/nakes/summary")
@roles_required(Role.NAKES)
def nakes_summary():
    q = ScreeningSession.query.filter_by(nakes_id=g.current_user.id)
    total = q.count()
    sessions = q.all()
    by_category = {"hijau": 0, "kuning": 0, "merah": 0}
    for s in sessions:
        if s.prediction:
            by_category[s.prediction.risk_category.value] += 1
    return jsonify({
        "total_screenings": total,
        "by_risk_category": by_category,
        "recent_sessions": [s.to_dict(include_related=False) for s in sessions[:10]],
    })


@bp.get("/dinkes/heatmap")
@roles_required(Role.DINKES, Role.ADMIN)
def dinkes_heatmap():
    """
    Three-layer heatmap per facility (used here as the small-area unit in the
    absence of real desa/kelurahan geodata; swap the group-by for a village
    field once that's available):
      L1 skrining lapangan  -> screening density + risk mix
      L2 validasi klinis    -> referral conversion (referred -> verified)
      L3 konfirmasi TCM     -> lab-confirmed cases
    """
    facilities = Facility.query.all()
    result = []
    for facility in facilities:
        sessions = ScreeningSession.query.filter_by(facility_id=facility.id).all()
        total_screenings = len(sessions)
        kuning = sum(1 for s in sessions if s.prediction and s.prediction.risk_category.value == "kuning")
        merah = sum(1 for s in sessions if s.prediction and s.prediction.risk_category.value == "merah")

        referrals = (
            db.session.query(ReferralLetter)
            .join(ScreeningSession, ReferralLetter.session_id == ScreeningSession.id)
            .filter(ScreeningSession.facility_id == facility.id)
            .all()
        )
        total_referrals = len(referrals)
        verified = sum(1 for r in referrals if r.verified_at is not None)
        tcm_positive = sum(1 for r in referrals if r.tcm_result == "positive")
        tcm_negative = sum(1 for r in referrals if r.tcm_result == "negative")

        result.append({
            "facility": facility.to_dict(),
            "layer1_field_screening": {
                "total_screenings": total_screenings,
                "kuning_count": kuning,
                "merah_count": merah,
            },
            "layer2_clinical_validation": {
                "total_referrals": total_referrals,
                "verified_referrals": verified,
                "conversion_rate": round(verified / total_referrals, 3) if total_referrals else None,
            },
            "layer3_tcm_confirmation": {
                "tcm_positive": tcm_positive,
                "tcm_negative": tcm_negative,
                "tcm_pending": total_referrals - tcm_positive - tcm_negative,
            },
        })

    result.sort(key=lambda r: r["layer1_field_screening"]["merah_count"], reverse=True)
    return jsonify(result)


@bp.get("/admin/summary")
@roles_required(Role.ADMIN)
def admin_summary():
    return jsonify({
        "total_users": User.query.count(),
        "users_by_role": {
            role.value: User.query.filter_by(role=role).count() for role in Role
        },
        "total_facilities": Facility.query.count(),
        "total_screenings": ScreeningSession.query.count(),
    })
