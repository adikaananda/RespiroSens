import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    """Base configuration. Values are overridden by environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'respirosens.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_EXPIRES = timedelta(hours=int(os.environ.get("JWT_EXPIRES_HOURS", 12)))

    # --- RespiroSens device integration ---
    # "simulation" (default, safe) or "http" / "mqtt" once a real device protocol
    # has been supplied. See README_DEVICE_INTEGRATION.md.
    DEVICE_MODE = os.environ.get("DEVICE_MODE", "simulation")
    DEVICE_HMAC_SECRET = os.environ.get("DEVICE_HMAC_SECRET", "dev-device-secret-change-me")
    # How long a device_capture_token stays valid while waiting for the real
    # hardware to push its reading (DEVICE_MODE=http only).
    DEVICE_CAPTURE_TIMEOUT_SEC = int(os.environ.get("DEVICE_CAPTURE_TIMEOUT_SEC", 180))

    # --- ML model ---
    MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(BASE_DIR, "app", "ml", "model_store"))
    MODEL_FILE = os.environ.get("MODEL_FILE", "xgb_respirosens_demo.json")
    MODEL_METADATA_FILE = os.environ.get("MODEL_METADATA_FILE", "model_metadata.json")

    # --- WhatsApp Business Cloud API ---
    # If credentials are not set, the WhatsApp client falls back to "console mode":
    # messages are logged/stored instead of sent, so the whole flow is testable
    # without a real Meta Business account.
    WHATSAPP_ENABLED = os.environ.get("WHATSAPP_ENABLED", "false").lower() == "true"
    WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v20.0")

    # --- File storage ---
    OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(BASE_DIR, "instance", "generated"))

    # --- CORS (frontend served separately, e.g. Vite dev server / static hosting) ---
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DEVICE_MODE = "simulation"


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
