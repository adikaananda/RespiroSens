"""Uji integrasi Firebase -> Flask TANPA jaringan (Firebase di-mock)."""
import os, random, time

import pytest

os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Facility, Role, User  # noqa: E402
from app.device_integration.rs_core import firebase  # noqa: E402

PUSH = firebase.PUSH


def make_push_id(ts_ms):
    t, head = ts_ms, ""
    for _ in range(8):
        head = PUSH[t % 64] + head
        t //= 64
    return head + "".join(random.choice(PUSH) for _ in range(12))


def fake_record(n=62, breath=True):
    rows = ["timestamp_ms,gas_resistance_kohm,temperature_c,humidity,pressure_hpa,abs_hum_gm3,ens_tvoc_ppb,ens_eco2_ppm,ens_aqi,nh3_adc,nh3_voltage_mv,ratio_gas_baseline,device_state"]
    for i in range(n):
        eco = 450 + (600 * min(i, 30) / 30 if breath else 0) + random.uniform(-5, 5)
        gas = 120 - (30 * min(i, 30) / 30 if breath else 0) + random.uniform(-.5, .5)
        rows.append(f"{i*1000},{gas:.2f},30.1,62,1008.2,18.5,,{eco:.0f},2,1800,{1450+random.uniform(-5,5):.0f},0,SAMPLING")
    return {"nama": "Pasien_klinis", "label": "TBC", "device_id": "RS-01", "baseline_gas": 121.0,
            "duration_ms": (n - 1) * 1000, "csv": "\n".join(rows)}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app("testing")
    app.config["DEVICE_MODE"] = "firebase"
    with app.app_context():
        db.create_all()
        f = Facility(name="Puskesmas Uji")
        db.session.add(f); db.session.commit()
        u = User(full_name="Nakes", email="n@t.local", role=Role.NAKES, facility_id=f.id)
        u.set_password("pw12345"); db.session.add(u); db.session.commit()
        with app.test_client() as c:
            tok = c.post("/api/auth/login", json={"email": "n@t.local", "password": "pw12345"}).get_json()["token"]
            yield c, {"Authorization": f"Bearer {tok}"}


def test_firebase_flow(env, monkeypatch):
    c, h = env
    store = {}
    monkeypatch.setattr(firebase, "recent", lambda limit=40: dict(sorted(store.items())))

    pid = c.post("/api/patients/register", json={"full_name": "P", "consent_given": True}, headers=h).get_json()["id"]
    sid = c.post("/api/screening/sessions", json={"patient_id": pid}, headers=h).get_json()["id"]

    # rekaman LAMA (sebelum sesi mulai) harus diabaikan
    store[make_push_id(int(time.time() * 1000) - 3600_000)] = fake_record()

    r = c.post(f"/api/screening/sessions/{sid}/breath-test", headers=h)
    assert r.status_code == 202 and r.get_json()["status"] == "waiting_for_device"

    # belum ada rekaman baru -> tetap pending
    assert c.get(f"/api/screening/sessions/{sid}", headers=h).get_json()["status"] == "breath_test_pending"

    # alat mengunggah rekaman baru -> polling berikutnya mengambilnya
    new_key = make_push_id(int(time.time() * 1000) + 500)
    store[new_key] = fake_record()
    s = c.get(f"/api/screening/sessions/{sid}", headers=h).get_json()
    assert s["status"] == "breath_test_done"
    assert s["is_simulated"] is False
    voc = s["voc_reading"]
    assert voc["source"] == "firebase_device"
    from app.models import VOCReading
    assert VOCReading.query.filter_by(session_id=sid).one().raw_payload["firebase_key"] == new_key
    assert voc["features"]["diff_gas_resistance_drop_pct"] > 10

    # model demo TIDAK dipakai untuk data alat nyata; tanpa AI key -> 503 ai_unavailable
    monkeypatch.setattr(firebase, "one", lambda k: store.get(k))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = c.post(f"/api/screening/sessions/{sid}/predict", headers=h)
    assert r.status_code == 503 and r.get_json()["error"] == "ai_unavailable"

    # jalur analisis valid: QC (+AI bila API key ada)
    monkeypatch.setattr(firebase, "one", lambda k: store.get(k))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    a = c.get(f"/api/screening/sessions/{sid}/device-analysis", headers=h).get_json()
    assert a["qc"]["status"] in ("ok", "warn") and a["ai"]["available"] is False
    assert a["decision"]["decision"] == "menunggu_ai"


def _make_done_session(c, h, store, monkeypatch, record):
    monkeypatch.setattr(firebase, "recent", lambda limit=40: dict(sorted(store.items())))
    monkeypatch.setattr(firebase, "one", lambda k: store.get(k))
    pid = c.post("/api/patients/register", json={"full_name": "P", "consent_given": True}, headers=h).get_json()["id"]
    sid = c.post("/api/screening/sessions", json={"patient_id": pid}, headers=h).get_json()["id"]
    c.post(f"/api/screening/sessions/{sid}/breath-test", headers=h)
    store[make_push_id(int(time.time() * 1000) + 500)] = record
    assert c.get(f"/api/screening/sessions/{sid}", headers=h).get_json()["status"] == "breath_test_done"
    return sid


def test_predict_from_device_with_ai(env, monkeypatch):
    from app.device_integration.rs_core import ai
    c, h = env
    sid = _make_done_session(c, h, {}, monkeypatch, fake_record())
    monkeypatch.setattr(ai, "review", lambda f, p, q: {
        "available": True, "risk_level": "tinggi", "confidence": 0.8,
        "reasons": ["gas turun"], "data_concerns": [], "retest": False})
    s = c.post(f"/api/screening/sessions/{sid}/predict", headers=h).get_json()
    assert s["status"] == "predicted"
    p = s["prediction"]
    assert p["risk_category"] == "merah" and p["model_version"].startswith("device-qc+ai")
    assert p["shap_values"]["device_analysis"]["decision"] == "lolos_ganda"
    assert "ground_truth" not in str(p["shap_values"])  # label lapangan tidak bocor ke hasil
    # nakes bisa menutup alur: review -> rujukan
    r = c.post(f"/api/screening/sessions/{sid}/review", json={"note": "ok"}, headers=h)
    assert r.status_code == 200 and r.get_json()["status"] == "referred"


def test_uncertain_ai_goes_to_nakes_review(env, monkeypatch):
    from app.device_integration.rs_core import ai
    c, h = env
    sid = _make_done_session(c, h, {}, monkeypatch, fake_record())
    monkeypatch.setattr(ai, "review", lambda f, p, q: {
        "available": True, "risk_level": "tidak_dapat_ditentukan", "confidence": 0.3,
        "reasons": [], "data_concerns": ["RH tinggi"], "retest": True})
    p = c.post(f"/api/screening/sessions/{sid}/predict", headers=h).get_json()["prediction"]
    assert p["risk_category"] == "kuning"
    assert p["shap_values"]["device_analysis"]["decision"] == "review_nakes"


def test_empty_chamber_rejected_at_ingest(env, monkeypatch):
    c, h = env
    store = {}
    monkeypatch.setattr(firebase, "recent", lambda limit=40: dict(sorted(store.items())))
    pid = c.post("/api/patients/register", json={"full_name": "P", "consent_given": True}, headers=h).get_json()["id"]
    sid = c.post("/api/screening/sessions", json={"patient_id": pid}, headers=h).get_json()["id"]
    c.post(f"/api/screening/sessions/{sid}/breath-test", headers=h)
    store[make_push_id(int(time.time() * 1000) + 500)] = fake_record(breath=False)
    assert c.get(f"/api/screening/sessions/{sid}", headers=h).get_json()["status"] == "invalid_sample"
    r = c.post(f"/api/screening/sessions/{sid}/predict", headers=h)
    assert r.status_code == 412  # tidak ada fitur -> nakes harus ulang pengambilan napas
