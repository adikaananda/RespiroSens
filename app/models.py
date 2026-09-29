import enum
import secrets
import uuid
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def _uid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Roles — kept identical to the 3 roles already present in the existing
# frontend prototype (login tabs: Nakes / Dinkes / Admin). Patients are
# records managed BY nakes, not a separate login role, matching the UI.
# ---------------------------------------------------------------------------
class Role(str, enum.Enum):
    NAKES = "nakes"          # Medical staff / clinician at a Puskesmas or clinic
    DINKES = "dinkes"        # Health department / district health office (policy dashboard)
    ADMIN = "admin"          # System administrator (manages users & facilities)


class ScreeningStatus(str, enum.Enum):
    REGISTERED = "registered"
    SYMPTOMS_DONE = "symptoms_done"
    RISK_FACTORS_DONE = "risk_factors_done"
    VITALS_DONE = "vitals_done"
    BREATH_TEST_PENDING = "breath_test_pending"
    BREATH_TEST_DONE = "breath_test_done"
    PROCESSING = "processing"
    PREDICTED = "predicted"
    CLINICAL_REVIEW = "clinical_review"
    REFERRED = "referred"
    COMPLETED = "completed"
    INVALID_SAMPLE = "invalid_sample"


class RiskCategory(str, enum.Enum):
    HIJAU = "hijau"     # green - education / observation
    KUNING = "kuning"   # yellow - priority referral
    MERAH = "merah"     # red - urgent referral


class Facility(db.Model):
    __tablename__ = "facilities"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    name = db.Column(db.String(200), nullable=False)
    district = db.Column(db.String(120))
    subdistrict = db.Column(db.String(120))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", back_populates="facility")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "district": self.district,
            "subdistrict": self.subdistrict,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_active": self.is_active,
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False)
    facility_id = db.Column(db.String(36), db.ForeignKey("facilities.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    facility = db.relationship("Facility", back_populates="users")

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role.value if isinstance(self.role, Role) else self.role,
            "facility": self.facility.to_dict() if self.facility else None,
            "is_active": self.is_active,
        }


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    full_name = db.Column(db.String(200), nullable=False)
    nik = db.Column(db.String(32), nullable=True, index=True)  # may be null for fallback form
    date_of_birth = db.Column(db.Date, nullable=True)
    sex = db.Column(db.String(10), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    occupation = db.Column(db.String(120), nullable=True)
    # Physical attributes captured by the nakes at registration (KTP does not
    # carry these) — used to compute IMT/BMI and render the patient card
    # instead of static placeholder numbers.
    age = db.Column(db.Integer, nullable=True)
    height_cm = db.Column(db.Float, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    whatsapp_number_hash = db.Column(db.String(128), nullable=True)  # salted hash, never raw
    whatsapp_number_last4 = db.Column(db.String(8), nullable=True)   # display only
    registered_via = db.Column(db.String(20), default="ktp_ocr")     # ktp_ocr | fallback_form
    facility_id = db.Column(db.String(36), db.ForeignKey("facilities.id"), nullable=True)
    consent_given = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    facility = db.relationship("Facility")

    @property
    def bmi(self):
        if not self.height_cm or not self.weight_kg:
            return None
        height_m = self.height_cm / 100
        if height_m <= 0:
            return None
        return round(self.weight_kg / (height_m ** 2), 1)

    @staticmethod
    def bmi_category(bmi):
        if bmi is None:
            return None
        if bmi < 18.5:
            return "kurang"
        if bmi < 25:
            return "normal"
        if bmi < 30:
            return "berlebih"
        return "obesitas"

    def to_dict(self):
        bmi = self.bmi
        return {
            "id": self.id,
            "full_name": self.full_name,
            "nik_masked": _mask_nik(self.nik) if self.nik else None,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "sex": self.sex,
            "address": self.address,
            "occupation": self.occupation,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "bmi": bmi,
            "bmi_category": self.bmi_category(bmi),
            "registered_via": self.registered_via,
            "consent_given": self.consent_given,
            "created_at": self.created_at.isoformat(),
        }


def _mask_nik(nik: str) -> str:
    if not nik or len(nik) < 8:
        return "****"
    return nik[:4] + "*" * (len(nik) - 8) + nik[-4:]


class ScreeningSession(db.Model):
    """One end-to-end patient pass through the RespiroSens flow."""

    __tablename__ = "screening_sessions"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    patient_id = db.Column(db.String(36), db.ForeignKey("patients.id"), nullable=False)
    nakes_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    facility_id = db.Column(db.String(36), db.ForeignKey("facilities.id"), nullable=True)

    status = db.Column(db.Enum(ScreeningStatus), default=ScreeningStatus.REGISTERED)

    # Clinical symptoms (booleans matching the existing frontend checklist)
    symptom_cough_gt_2weeks = db.Column(db.Boolean, default=False)
    symptom_fever = db.Column(db.Boolean, default=False)
    symptom_night_sweats = db.Column(db.Boolean, default=False)
    symptom_weight_loss = db.Column(db.Boolean, default=False)
    symptom_shortness_of_breath = db.Column(db.Boolean, default=False)
    symptom_chest_pain = db.Column(db.Boolean, default=False)

    # Risk factors
    smoking_history = db.Column(db.String(20), nullable=True)  # never | former | active
    known_tb_contact = db.Column(db.Boolean, default=False)
    diabetes = db.Column(db.Boolean, default=False)
    immunocompromised = db.Column(db.Boolean, default=False)
    sputum_produces = db.Column(db.Boolean, nullable=True)  # can patient produce sputum?

    # Vitals
    heart_rate_bpm = db.Column(db.Float, nullable=True)
    spo2_pct = db.Column(db.Float, nullable=True)
    body_temp_c = db.Column(db.Float, nullable=True)
    resp_rate_per_min = db.Column(db.Float, nullable=True)
    fvc_pct = db.Column(db.Float, nullable=True)
    fev1_pct = db.Column(db.Float, nullable=True)

    is_simulated = db.Column(db.Boolean, default=True)  # True until a real device session is used

    # Real-hardware capture handshake: issued when DEVICE_MODE=http and the
    # nakes starts a breath-test — the device/bridge script includes this
    # token when it pushes to POST /api/device/ingest so the backend knows
    # which session the reading belongs to. Cleared once consumed or expired.
    device_capture_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    device_capture_expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = db.relationship("Patient")
    nakes = db.relationship("User")
    facility = db.relationship("Facility")
    voc_reading = db.relationship("VOCReading", back_populates="session", uselist=False)
    prediction = db.relationship("Prediction", back_populates="session", uselist=False)
    referral = db.relationship("ReferralLetter", back_populates="session", uselist=False)

    def to_dict(self, include_related=True):
        data = {
            "id": self.id,
            "patient_id": self.patient_id,
            "nakes_id": self.nakes_id,
            "facility_id": self.facility_id,
            "status": self.status.value if isinstance(self.status, ScreeningStatus) else self.status,
            "symptoms": {
                "cough_gt_2weeks": self.symptom_cough_gt_2weeks,
                "fever": self.symptom_fever,
                "night_sweats": self.symptom_night_sweats,
                "weight_loss": self.symptom_weight_loss,
                "shortness_of_breath": self.symptom_shortness_of_breath,
                "chest_pain": self.symptom_chest_pain,
            },
            "risk_factors": {
                "smoking_history": self.smoking_history,
                "known_tb_contact": self.known_tb_contact,
                "diabetes": self.diabetes,
                "immunocompromised": self.immunocompromised,
                "sputum_produces": self.sputum_produces,
            },
            "vitals": {
                "heart_rate_bpm": self.heart_rate_bpm,
                "spo2_pct": self.spo2_pct,
                "body_temp_c": self.body_temp_c,
                "resp_rate_per_min": self.resp_rate_per_min,
                "fvc_pct": self.fvc_pct,
                "fev1_pct": self.fev1_pct,
            },
            "is_simulated": self.is_simulated,
            "device_capture_token": self.device_capture_token,
            "patient_name": self.patient.full_name if self.patient else None,
            "smoking_history": self.smoking_history,
            "risk_score": self.prediction.risk_score if self.prediction else None,
            "risk_category": (
                self.prediction.risk_category.value
                if self.prediction and isinstance(self.prediction.risk_category, RiskCategory)
                else None
            ),
            "clinician_note": self.prediction.clinician_note if self.prediction else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_related:
            data["patient"] = self.patient.to_dict() if self.patient else None
            data["prediction"] = self.prediction.to_dict() if self.prediction else None
            data["referral"] = self.referral.to_dict() if self.referral else None
            data["voc_reading"] = self.voc_reading.to_dict() if self.voc_reading else None
        return data


class VOCReading(db.Model):
    """Raw + preprocessed VOC sensor payload for one screening session.

    `raw_payload` keeps exactly what came from the device (or the simulator),
    `is_simulated` and `source` make it explicit whether this is real hardware
    data or DEMO/SIMULATION data — the two must never be conflated.
    """

    __tablename__ = "voc_readings"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    session_id = db.Column(db.String(36), db.ForeignKey("screening_sessions.id"), nullable=False)

    source = db.Column(db.String(20), default="simulation")  # simulation | http_device | mqtt_device
    is_simulated = db.Column(db.Boolean, default=True)

    device_id = db.Column(db.String(120), nullable=True)
    raw_payload = db.Column(db.JSON, nullable=True)          # raw sensor channels as received
    baseline_payload = db.Column(db.JSON, nullable=True)     # ambient purge baseline
    features = db.Column(db.JSON, nullable=True)             # extracted feature vector fed to the model
    quality_flag = db.Column(db.String(20), default="valid")  # valid | invalid_short_breath | invalid_noise

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("ScreeningSession", back_populates="voc_reading")

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "is_simulated": self.is_simulated,
            "quality_flag": self.quality_flag,
            "device_id": self.device_id,
            "duration_sec": (self.raw_payload or {}).get("duration_sec"),
            "features": self.features,
            "created_at": self.created_at.isoformat(),
        }


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    session_id = db.Column(db.String(36), db.ForeignKey("screening_sessions.id"), nullable=False)

    risk_score = db.Column(db.Float, nullable=False)  # 0-100
    risk_category = db.Column(db.Enum(RiskCategory), nullable=False)
    shap_values = db.Column(db.JSON, nullable=True)   # {feature: contribution}
    model_version = db.Column(db.String(50), nullable=True)
    trained_on_demo_data = db.Column(db.Boolean, default=True)

    reviewed_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    clinician_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("ScreeningSession", back_populates="prediction")

    def to_dict(self):
        return {
            "id": self.id,
            "risk_score": self.risk_score,
            "risk_category": self.risk_category.value if isinstance(self.risk_category, RiskCategory) else self.risk_category,
            "shap_values": self.shap_values,
            "model_version": self.model_version,
            "trained_on_demo_data": self.trained_on_demo_data,
            "reviewed_by_id": self.reviewed_by_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "clinician_note": self.clinician_note,
            "created_at": self.created_at.isoformat(),
            "disclaimer": (
                "Hasil ini adalah skor skrining/triase, bukan diagnosis medis. "
                "Wajib ditinjau tenaga kesehatan dan ditindaklanjuti dengan pemeriksaan "
                "konfirmasi baku." if True else None
            ),
        }


class ReferralLetter(db.Model):
    __tablename__ = "referral_letters"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    session_id = db.Column(db.String(36), db.ForeignKey("screening_sessions.id"), nullable=False)
    referral_code = db.Column(db.String(40), unique=True, nullable=False)
    target_facility_name = db.Column(db.String(200), nullable=True)
    pdf_path = db.Column(db.String(500), nullable=True)
    qr_verification_token = db.Column(db.String(64), unique=True, default=lambda: secrets.token_hex(16))
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by_facility = db.Column(db.String(200), nullable=True)
    whatsapp_sent = db.Column(db.Boolean, default=False)
    whatsapp_send_log = db.Column(db.JSON, nullable=True)
    # Lapisan 3 (konfirmasi TCM) of the heatmap: entered manually by nakes/dinkes
    # once the lab result comes back, since RespiroSens does not itself perform
    # Xpert MTB/RIF testing — this just closes the data loop for the dashboard.
    tcm_result = db.Column(db.String(20), default="pending")  # pending | positive | negative
    tcm_result_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("ScreeningSession", back_populates="referral")

    def to_dict(self):
        return {
            "id": self.id,
            "referral_code": self.referral_code,
            "target_facility_name": self.target_facility_name,
            "pdf_path": self.pdf_path,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verified_by_facility": self.verified_by_facility,
            "whatsapp_sent": self.whatsapp_sent,
            "tcm_result": self.tcm_result,
            "tcm_result_at": self.tcm_result_at.isoformat() if self.tcm_result_at else None,
            "created_at": self.created_at.isoformat(),
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=_uid)
    actor_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    entity_type = db.Column(db.String(60), nullable=True)
    entity_id = db.Column(db.String(36), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }
