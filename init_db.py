"""
Creates all database tables and seeds:
  - demo login accounts for the 3 existing roles (nakes / dinkes / admin)
  - a few demo facilities (matching names already used in the existing
    frontend prototype, so the dashboards look consistent)
  - a handful of DEMO/SIMULATION screening sessions so the dashboards aren't
    empty on first run

Everything this script inserts is either an account you're meant to log in
with, or is explicitly generated via Simulation Mode (is_simulated=True) —
never real patient data.

Run: python init_db.py
Add --with-demo-sessions to also generate sample screening sessions
(requires a trained model — see README_INSTALL.md).
"""

import random
import sys
from datetime import datetime, timedelta

from app import create_app
from app.device_integration.simulation_adapter import SimulationAdapter
from app.extensions import db
from app.ml import pipeline as ml_pipeline
from app.ml.features import extract_features, quality_control
from app.models import (
    Facility,
    Patient,
    Prediction,
    Role,
    RiskCategory,
    ScreeningSession,
    ScreeningStatus,
    User,
    VOCReading,
)

DEMO_USERS = [
    {"full_name": "Ns. Demo Nakes", "email": "nakes.demo@respirosens.id", "password": "nakes123", "role": Role.NAKES},
    {"full_name": "Demo Dinas Kesehatan", "email": "dinkes.demo@respirosens.id", "password": "dinkes123", "role": Role.DINKES},
    {"full_name": "Demo Administrator", "email": "admin.demo@respirosens.id", "password": "admin123", "role": Role.ADMIN},
]

DEMO_FACILITIES = [
    {"name": "Puskesmas Mengwi I", "district": "Badung", "subdistrict": "Mengwi", "latitude": -8.5765, "longitude": 115.1691},
    {"name": "Puskesmas Kuta Utara", "district": "Badung", "subdistrict": "Kuta Utara", "latitude": -8.6786, "longitude": 115.1701},
    {"name": "Klinik Sehat Abiansemal", "district": "Badung", "subdistrict": "Abiansemal", "latitude": -8.5945, "longitude": 115.2274},
    {"name": "Puskesmas Petang", "district": "Badung", "subdistrict": "Petang", "latitude": -8.3197, "longitude": 115.2129},
]


def seed_core():
    for f in DEMO_FACILITIES:
        if not Facility.query.filter_by(name=f["name"]).first():
            db.session.add(Facility(**f))
    db.session.commit()

    default_facility = Facility.query.filter_by(name=DEMO_FACILITIES[0]["name"]).first()
    for u in DEMO_USERS:
        if User.query.filter_by(email=u["email"]).first():
            continue
        user = User(full_name=u["full_name"], email=u["email"], role=u["role"],
                    facility_id=default_facility.id if u["role"] == Role.NAKES else None)
        user.set_password(u["password"])
        db.session.add(user)
    db.session.commit()
    print("Seeded facilities and demo login accounts:")
    for u in DEMO_USERS:
        print(f"  - {u['role'].value:8s} {u['email']:32s} / {u['password']}")


OCCUPATIONS = ["Buruh Pabrik", "Petani", "Pedagang Pasar", "Sopir Angkutan",
               "Nelayan", "Guru", "Tukang Bangunan", "Wiraswasta",
               "Pegawai Swasta", "Ibu Rumah Tangga", "Buruh Bangunan", "Pengrajin"]


def _vitals_for_risk(risk_hint):
    """Deterministic-ish (seeded) vitals per risk band so demo data reads as
    clinically coherent instead of random noise, while still varying between
    patients within a band."""
    if risk_hint == "low":
        return dict(
            heart_rate_bpm=random.randint(70, 84), spo2_pct=round(random.uniform(96, 99), 1),
            body_temp_c=round(random.uniform(36.3, 36.9), 1), resp_rate_per_min=random.randint(14, 18),
            fvc_pct=random.randint(85, 98), fev1_pct=random.randint(85, 97),
            symptoms=dict(cough_gt_2weeks=False, fever=False, night_sweats=False,
                          weight_loss=False, shortness_of_breath=False, chest_pain=False),
        )
    if risk_hint == "moderate":
        return dict(
            heart_rate_bpm=random.randint(85, 98), spo2_pct=round(random.uniform(92, 96), 1),
            body_temp_c=round(random.uniform(37.0, 37.8), 1), resp_rate_per_min=random.randint(19, 24),
            fvc_pct=random.randint(65, 84), fev1_pct=random.randint(60, 82),
            symptoms=dict(cough_gt_2weeks=True, fever=random.random() > 0.5, night_sweats=True,
                          weight_loss=False, shortness_of_breath=random.random() > 0.4, chest_pain=False),
        )
    return dict(
        heart_rate_bpm=random.randint(96, 112), spo2_pct=round(random.uniform(87, 92), 1),
        body_temp_c=round(random.uniform(37.6, 38.6), 1), resp_rate_per_min=random.randint(25, 32),
        fvc_pct=random.randint(45, 66), fev1_pct=random.randint(40, 62),
        symptoms=dict(cough_gt_2weeks=True, fever=True, night_sweats=True,
                      weight_loss=random.random() > 0.4, shortness_of_breath=True,
                      chest_pain=random.random() > 0.5),
    )


def _build_predicted_session(app, adapter, patient, nakes, facility, risk_hint, created_at=None):
    """Creates one full-pipeline (vitals + symptoms + breath test + prediction)
    ScreeningSession for `patient` and returns it, or None if the model isn't
    trained yet."""
    vitals = _vitals_for_risk(risk_hint)
    symptoms = vitals.pop("symptoms")

    session = ScreeningSession(
        patient_id=patient.id, nakes_id=nakes.id, facility_id=facility.id,
        status=ScreeningStatus.PREDICTED, is_simulated=True,
        smoking_history=random.choice(["never", "former", "active", "active"]),
        known_tb_contact=random.random() > 0.85,
        **vitals,
        symptom_cough_gt_2weeks=symptoms["cough_gt_2weeks"],
        symptom_fever=symptoms["fever"],
        symptom_night_sweats=symptoms["night_sweats"],
        symptom_weight_loss=symptoms["weight_loss"],
        symptom_shortness_of_breath=symptoms["shortness_of_breath"],
        symptom_chest_pain=symptoms["chest_pain"],
    )
    if created_at:
        session.created_at = created_at
        session.updated_at = created_at
    db.session.add(session)
    db.session.flush()

    sample = adapter.acquire_breath_sample(session_id=session.id, risk_hint=risk_hint)
    if quality_control(sample.raw_payload) != "valid":
        return None
    features = extract_features(sample.raw_payload, sample.baseline_payload)
    db.session.add(VOCReading(
        session_id=session.id, source="simulation", is_simulated=True,
        device_id=sample.device_id, raw_payload=sample.raw_payload,
        baseline_payload=sample.baseline_payload, features=features, quality_flag="valid",
    ))

    result = ml_pipeline.predict(features, app.config)
    db.session.add(Prediction(
        session_id=session.id, risk_score=result["risk_score"],
        risk_category=RiskCategory(result["risk_category"]),
        shap_values=result["shap_values"], model_version=result["model_version"],
        trained_on_demo_data=result["trained_on_demo_data"],
    ))
    return session


def seed_demo_sessions(app, n=12):
    """Generates n end-to-end DEMO/SIMULATION screening sessions (with real
    symptoms/vitals/risk factors, not just a name) so the nakes/dinkes/admin
    dashboards — including the patient overview card and the respiration
    trend chart — have real, varied, non-static data to render on first run.
    """
    nakes = User.query.filter_by(role=Role.NAKES).first()
    facility = nakes.facility
    adapter = SimulationAdapter()

    names = ["Wayan Sudarma", "Made Ayu Lestari", "Nyoman Sutrisna", "Kadek Wira Adi",
             "Ketut Purnama", "Putu Ratih", "Komang Ardana", "Ni Luh Sari",
             "I Gede Suarjana", "Ni Made Widi", "I Wayan Yasa", "Ni Kadek Ayu"]

    try:
        for i, name in enumerate(names[:n]):
            sex = "L" if i % 2 == 0 else "P"
            height = random.randint(150, 178) if sex == "P" else random.randint(160, 182)
            weight = round(height * random.uniform(0.36, 0.46), 1)  # keeps BMI in a plausible band

            patient = Patient(
                full_name=f"{name} (DEMO)", registered_via="fallback_form",
                facility_id=facility.id, consent_given=True,
                age=random.randint(19, 64), sex=sex,
                occupation=OCCUPATIONS[i % len(OCCUPATIONS)],
                height_cm=height, weight_kg=weight,
            )
            db.session.add(patient)
            db.session.flush()

            risk_hint = ["low", "moderate", "high"][i % 3]

            # Give the first 3 demo patients a short screening history (instead
            # of a single point in time) so the "Tren Frekuensi Napas" chart on
            # the nakes dashboard has real week-over-week data to plot, not a
            # flat/empty line.
            if i < 3:
                now = datetime.utcnow()
                for days_ago in (6, 3):
                    _build_predicted_session(
                        app, adapter, patient, nakes, facility, risk_hint,
                        created_at=now - timedelta(days=days_ago),
                    )

            _build_predicted_session(app, adapter, patient, nakes, facility, risk_hint)
    except ml_pipeline.ModelNotTrainedError:
        print("Model not trained yet — skipping demo predictions. "
              "Run generate_demo_dataset.py + train.py first, then re-run with --with-demo-sessions.")
        db.session.rollback()
        return

    db.session.commit()
    print(f"Seeded {n} DEMO/SIMULATION patients with full screening history "
          f"(symptoms, vitals, risk score) — not just names.")


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_core()
        if "--with-demo-sessions" in sys.argv:
            seed_demo_sessions(app)


if __name__ == "__main__":
    main()
