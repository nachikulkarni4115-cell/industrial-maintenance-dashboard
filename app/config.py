import os
from datetime import timedelta


class Config:
    """Base configuration. Secrets must come from environment variables in production."""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me-in-production"
    # Default local path; production/K8s uses /data/maintenance.db via DATABASE_URL
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///maintenance.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}
    }

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    APP_NAME = "Industrial Maintenance Dashboard"
    ITEMS_PER_PAGE = 20

    INGESTION_TOKEN = os.environ.get("INGESTION_TOKEN") or "demo-ingestion-token-change-me"

    BOOTSTRAP_ADMIN_USERNAME = os.environ.get("BOOTSTRAP_ADMIN_USERNAME") or "admin"
    BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or "ChangeMeImmediately!"
    BOOTSTRAP_ADMIN_EMAIL = os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "admin@example.com"

    # Public read-only demo page (no private data)
    PUBLIC_DEMO_ENABLED = os.environ.get("PUBLIC_DEMO_ENABLED", "false").lower() in ("1", "true", "yes")

    # Hours after which a reading is considered stale
    STALE_TELEMETRY_HOURS = int(os.environ.get("STALE_TELEMETRY_HOURS", "24"))

    # Example thresholds only – not universal safety limits
    DEFAULT_THRESHOLDS = {
        "temperature_c": {"warning": 70.0, "critical": 85.0},
        "vibration_mm_s": {"warning": 4.5, "critical": 7.1},
        "pressure_bar": {"warning": 8.0, "critical": 10.0},
        "rpm": {"warning_high": 1800, "critical_high": 2000, "warning_low": 800, "critical_low": 500},
        "current_a": {"warning": 15.0, "critical": 20.0},
    }


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")

    def __init__(self):
        super().__init__() if hasattr(super(), "__init__") else None

    @staticmethod
    def init_app(app):
        """Reject unsafe defaults in production."""
        unsafe = []
        sk = app.config.get("SECRET_KEY") or ""
        if not sk or sk in ("dev-only-change-me-in-production", "change-me", "secret"):
            unsafe.append("SECRET_KEY")
        tok = app.config.get("INGESTION_TOKEN") or ""
        if not tok or tok in ("demo-ingestion-token-change-me", "change-me"):
            unsafe.append("INGESTION_TOKEN")
        pw = app.config.get("BOOTSTRAP_ADMIN_PASSWORD") or ""
        if not pw or pw in ("ChangeMeImmediately!", "admin", "password"):
            unsafe.append("BOOTSTRAP_ADMIN_PASSWORD")
        if unsafe:
            raise RuntimeError(
                f"Production config refuses unsafe defaults for: {', '.join(unsafe)}. "
                "Set strong values via environment variables / Kubernetes Secret."
            )


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    INGESTION_TOKEN = "test-ingestion-token"
    SECRET_KEY = "test-secret-key"
    BOOTSTRAP_ADMIN_PASSWORD = "testadminpass"
    PUBLIC_DEMO_ENABLED = True
    STALE_TELEMETRY_HOURS = 24


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
