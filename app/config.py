import os
from datetime import timedelta

# Known-unsafe placeholder values that must never be used in production
_UNSAFE_SECRETS = frozenset({
    "",
    "dev-only-change-me-in-production",
    "change-me",
    "secret",
    "secret-key",
    "demo-ingestion-token-change-me",
    "ChangeMeImmediately!",
    "admin",
    "password",
    "changeme",
})


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me-in-production"
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

    PUBLIC_DEMO_ENABLED = os.environ.get("PUBLIC_DEMO_ENABLED", "false").lower() in ("1", "true", "yes")
    STALE_TELEMETRY_HOURS = int(os.environ.get("STALE_TELEMETRY_HOURS", "24"))

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
    """Production: secrets must come from the live environment (validated in init_app)."""
    DEBUG = False
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")

    @staticmethod
    def init_app(app):
        """Load secrets from the current environment and reject unsafe values.

        Reading here (not only at class import time) ensures tests can monkeypatch
        os.environ and that container env vars are always used at startup.
        """
        sk = (os.environ.get("SECRET_KEY") or "").strip()
        tok = (os.environ.get("INGESTION_TOKEN") or "").strip()
        pw = (os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
        user = (os.environ.get("BOOTSTRAP_ADMIN_USERNAME") or "admin").strip()
        email = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "admin@example.com").strip()

        app.config["SECRET_KEY"] = sk
        app.config["INGESTION_TOKEN"] = tok
        app.config["BOOTSTRAP_ADMIN_PASSWORD"] = pw
        app.config["BOOTSTRAP_ADMIN_USERNAME"] = user
        app.config["BOOTSTRAP_ADMIN_EMAIL"] = email

        # Optional production overrides from env
        if "DATABASE_URL" in os.environ:
            app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
        if "PUBLIC_DEMO_ENABLED" in os.environ:
            app.config["PUBLIC_DEMO_ENABLED"] = os.environ["PUBLIC_DEMO_ENABLED"].lower() in ("1", "true", "yes")
        if "STALE_TELEMETRY_HOURS" in os.environ:
            app.config["STALE_TELEMETRY_HOURS"] = int(os.environ["STALE_TELEMETRY_HOURS"])
        if "SESSION_COOKIE_SECURE" in os.environ:
            app.config["SESSION_COOKIE_SECURE"] = os.environ["SESSION_COOKIE_SECURE"].lower() in ("1", "true", "yes")

        unsafe = []
        if not sk or sk in _UNSAFE_SECRETS or len(sk) < 16:
            unsafe.append("SECRET_KEY (required, >=16 chars, not a placeholder)")
        if not tok or tok in _UNSAFE_SECRETS or len(tok) < 12:
            unsafe.append("INGESTION_TOKEN (required, >=12 chars, not a placeholder)")
        if not pw or pw in _UNSAFE_SECRETS or len(pw) < 10:
            unsafe.append("BOOTSTRAP_ADMIN_PASSWORD (required, >=10 chars, not a placeholder)")
        if unsafe:
            raise RuntimeError(
                "Production configuration refuses unsafe or missing secrets:\n  - "
                + "\n  - ".join(unsafe)
                + "\nSet strong values via environment variables / Kubernetes Secret."
            )


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    INGESTION_TOKEN = "test-ingestion-token"
    SECRET_KEY = "test-secret-key-for-pytest-only"
    BOOTSTRAP_ADMIN_PASSWORD = "testadminpass"
    PUBLIC_DEMO_ENABLED = True
    STALE_TELEMETRY_HOURS = 24


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}