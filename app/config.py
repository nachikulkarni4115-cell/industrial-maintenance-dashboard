import os
from datetime import timedelta

class Config:
    """Base configuration. Secrets must come from environment variables."""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me-in-production"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///maintenance.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}  # required for SQLite + multi-thread
    }

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    # Set SESSION_COOKIE_SECURE = True when HTTPS is active

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Application
    APP_NAME = "Industrial Maintenance Dashboard"
    ITEMS_PER_PAGE = 20

    # Telemetry ingestion token (machine credential)
    INGESTION_TOKEN = os.environ.get("INGESTION_TOKEN") or "demo-ingestion-token-change-me"

    # Admin bootstrap (used only on first init if no admin exists)
    BOOTSTRAP_ADMIN_USERNAME = os.environ.get("BOOTSTRAP_ADMIN_USERNAME") or "admin"
    BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or "ChangeMeImmediately!"
    BOOTSTRAP_ADMIN_EMAIL = os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "admin@example.com"

    # Threshold defaults (examples only – not universal safety limits)
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
    SESSION_COOKIE_SECURE = True  # enable when HTTPS is available

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    INGESTION_TOKEN = "test-ingestion-token"
    SECRET_KEY = "test-secret-key"
    BOOTSTRAP_ADMIN_PASSWORD = "testadminpass"

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
