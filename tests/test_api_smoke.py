"""
End-to-end smoke test for the RespiroSens API.

Exercises: login -> patient registration -> screening session -> symptoms ->
vitals -> Simulation Mode breath test -> ML prediction -> clinical review ->
(when risk is kuning/merah) referral creation. Uses an in-memory SQLite DB
and the trained demo model, so `python -m app.ml.generate_demo_dataset` and
`python -m app.ml.train` must have been run at least once before this test
(see README_INSTALL.md / TESTING.md) — the test skips gracefully otherwise.

Run: pytest -v
"""

import os

import pytest

os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Facility, Role, User  # noqa: E402
from app.ml import pipeline as ml_pipeline  # noqa: E402


@pytest.fixture
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        facility = Facility(name="Puskesmas Uji Coba")
        db.session.add(facility)
        db.session.commit()

        nakes = User(full_name="Nakes Uji", email="nakes@test.local", role=Role.NAKES,
                     facility_id=facility.id)
        nakes.set_password("test1234")
        db.session.add(nakes)

        admin = User(full_name="Admin Uji", email="admin@test.local", role=Role.ADMIN)
        admin.set_password("test1234")
        db.session.add(admin)

        dinkes = User(full_name="Dinkes Uji", email="dinkes@test.local", role=Role.DINKES,
                      facility_id=facility.id)
        dinkes.set_password("test1234")
        db.session.add(dinkes)
        db.session.commit()

        with app.test_client() as c:
            yield c
        ml_pipeline.reset_cache()


def _login_as(client, email, password="test1234"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def _login(client):
    resp = client.post("/api/auth/login", json={"email": "nakes@test.local", "password": "test1234"})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_login_rejects_bad_password(client):
    resp = client.post("/api/auth/login", json={"email": "nakes@test.local", "password": "wrong"})
    assert resp.status_code == 401


def test_full_screening_flow(client):
    if not os.path.exists(os.path.join("app", "ml", "model_store", "xgb_respirosens_demo.json")):
        pytest.skip("Model not trained yet — run generate_demo_dataset.py + train.py first.")

    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Register patient (fallback form path)
    resp = client.post("/api/patients/register", json={
        "full_name": "Pasien Uji Coba", "consent_given": True,
    }, headers=headers)
    assert resp.status_code == 201
    patient_id = resp.get_json()["id"]

    # Create screening session
    resp = client.post("/api/screening/sessions", json={"patient_id": patient_id}, headers=headers)
    assert resp.status_code == 201
    session_id = resp.get_json()["id"]

    # Symptoms
    resp = client.patch(f"/api/screening/sessions/{session_id}/symptoms",
                         json={"cough_gt_2weeks": True}, headers=headers)
    assert resp.status_code == 200

    # Vitals
    resp = client.patch(f"/api/screening/sessions/{session_id}/vitals",
                         json={"spo2_pct": 93, "heart_rate_bpm": 90}, headers=headers)
    assert resp.status_code == 200

    # Breath test (Simulation Mode, biased high-risk so we exercise the referral path)
    resp = client.post(f"/api/screening/sessions/{session_id}/breath-test",
                        json={"_simulation_risk_hint": "high"}, headers=headers)
    assert resp.status_code == 200

    # Prediction
    resp = client.post(f"/api/screening/sessions/{session_id}/predict", headers=headers)
    assert resp.status_code == 200
    prediction = resp.get_json()["prediction"]
    assert 0 <= prediction["risk_score"] <= 100
    assert prediction["risk_category"] in ("hijau", "kuning", "merah")
    assert prediction["trained_on_demo_data"] is True  # must stay true until real clinical training data is used

    # Clinical review (human-in-the-loop)
    resp = client.post(f"/api/screening/sessions/{session_id}/review",
                        json={"note": "Ditinjau oleh nakes uji coba."}, headers=headers)
    assert resp.status_code == 200


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/screening/sessions")
    assert resp.status_code == 401


def test_role_restricted_endpoint(client):
    token = _login(client)
    # Nakes should NOT be able to hit admin-only endpoints.
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_facility_search_and_creation_with_coordinates(client):
    admin_token = _login_as(client, "admin@test.local")
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.post("/api/facilities", json={
        "name": "Puskesmas Baru Denpasar", "district": "Denpasar",
        "subdistrict": "Denpasar Timur", "latitude": -8.6478, "longitude": 115.2385,
    }, headers=headers)
    assert resp.status_code == 201
    created = resp.get_json()
    assert created["latitude"] == -8.6478
    assert created["longitude"] == 115.2385

    resp = client.get("/api/facilities?search=Denpasar", headers=headers)
    assert resp.status_code == 200
    names = [f["name"] for f in resp.get_json()]
    assert "Puskesmas Baru Denpasar" in names

    resp = client.get("/api/facilities?search=NoSuchPlaceXYZ", headers=headers)
    assert resp.get_json() == []


def test_user_search(client):
    admin_token = _login_as(client, "admin@test.local")
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.get("/api/users?search=Nakes", headers=headers)
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.get_json()]
    assert "nakes@test.local" in emails
    assert "admin@test.local" not in emails


def test_session_search_by_patient_name(client):
    if not os.path.exists(os.path.join("app", "ml", "model_store", "xgb_respirosens_demo.json")):
        pytest.skip("Model not trained yet — run generate_demo_dataset.py + train.py first.")

    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/patients/register", json={
        "full_name": "Ni Kadek Search Test", "consent_given": True,
    }, headers=headers)
    patient_id = resp.get_json()["id"]
    resp = client.post("/api/screening/sessions", json={"patient_id": patient_id}, headers=headers)
    session_id = resp.get_json()["id"]

    resp = client.get("/api/screening/sessions?search=Kadek", headers=headers)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.get_json()]
    assert session_id in ids
    # patient_name shortcut should be populated directly on the list response
    matching = [s for s in resp.get_json() if s["id"] == session_id][0]
    assert matching["patient_name"] == "Ni Kadek Search Test"

    resp = client.get("/api/screening/sessions?search=NoSuchNameXYZ", headers=headers)
    assert resp.get_json() == []


def test_referral_list_and_tcm_confirmation(client):
    if not os.path.exists(os.path.join("app", "ml", "model_store", "xgb_respirosens_demo.json")):
        pytest.skip("Model not trained yet — run generate_demo_dataset.py + train.py first.")

    nakes_token = _login(client)
    nakes_headers = {"Authorization": f"Bearer {nakes_token}"}

    resp = client.post("/api/patients/register", json={
        "full_name": "Pasien TCM Uji", "consent_given": True,
    }, headers=nakes_headers)
    patient_id = resp.get_json()["id"]
    resp = client.post("/api/screening/sessions", json={"patient_id": patient_id}, headers=nakes_headers)
    session_id = resp.get_json()["id"]

    client.post(f"/api/screening/sessions/{session_id}/breath-test",
                json={"_simulation_risk_hint": "high"}, headers=nakes_headers)
    client.post(f"/api/screening/sessions/{session_id}/predict", headers=nakes_headers)
    resp = client.post(f"/api/screening/sessions/{session_id}/review", json={}, headers=nakes_headers)
    referral = resp.get_json().get("referral")
    if referral is None:
        pytest.skip("Simulated sample landed in a non-referral (hijau) risk category this run.")

    dinkes_token = _login_as(client, "dinkes@test.local")
    dinkes_headers = {"Authorization": f"Bearer {dinkes_token}"}

    resp = client.get("/api/referrals?tcm_result=pending", headers=dinkes_headers)
    assert resp.status_code == 200
    codes = [r["referral_code"] for r in resp.get_json()]
    assert referral["referral_code"] in codes

    resp = client.patch(f"/api/referrals/{referral['id']}/tcm-result",
                         json={"tcm_result": "positive"}, headers=dinkes_headers)
    assert resp.status_code == 200
    assert resp.get_json()["tcm_result"] == "positive"

    resp = client.get("/api/referrals?tcm_result=pending", headers=dinkes_headers)
    codes = [r["referral_code"] for r in resp.get_json()]
    assert referral["referral_code"] not in codes
