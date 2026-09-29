import os
from datetime import timedelta

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

IS_SERVERLESS = bool(
    os.environ.get("VERCEL")
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
)

_WRITABLE_ROOT = (
    "/tmp"
    if IS_SERVERLESS
    else os.path.join(BASE_DIR, "instance")
)


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-secret-change-me"
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_WRITABLE_ROOT, 'respirosens.db')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_EXPIRES = timedelta(
        hours=int(
            os.environ.get("JWT_EXPIRES_HOURS", 12)
        )
    )

    DEVICE_MODE = os.environ.get(
        "DEVICE_MODE",
        "simulation"
    )

    DEVICE_HMAC_SECRET = os.environ.get(
        "DEVICE_HMAC_SECRET",
        "dev-device-secret-change-me"
    )

    DEVICE_CAPTURE_TIMEOUT_SEC = int(
        os.environ.get(
            "DEVICE_CAPTURE_TIMEOUT_SEC",
            180
        )
    )

    MODEL_DIR = os.environ.get(
        "MODEL_DIR",
        os.path.join(
            BASE_DIR,
            "app",
            "ml",
            "model_store"
        )
    )

    MODEL_FILE = os.environ.get(
        "MODEL_FILE",
        "xgb_respirosens_demo.json"
    )

    MODEL_METADATA_FILE = os.environ.get(
        "MODEL_METADATA_FILE",
        "model_metadata.json"
    )

    WHATSAPP_ENABLED = (
        os.environ.get(
            "WHATSAPP_ENABLED",
            "false"
        ).lower() == "true"
    )

    WHATSAPP_TOKEN = os.environ.get(
        "WHATSAPP_TOKEN",
        ""
    )

    WHATSAPP_PHONE_NUMBER_ID = os.environ.get(
        "WHATSAPP_PHONE_NUMBER_ID",
        ""
    )

    WHATSAPP_API_VERSION = os.environ.get(
        "WHATSAPP_API_VERSION",
        "v20.0"
    )

    OUTPUT_DIR = os.environ.get(
        "OUTPUT_DIR",
        os.path.join(
            _WRITABLE_ROOT,
            "generated"
        )
    )

    CORS_ORIGINS = os.environ.get(
        "CORS_ORIGINS",
        "*"
    )


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