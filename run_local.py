#!/usr/bin/env python3
"""Local development runner. Creates tables and seeds if needed."""
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = PROJECT_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_FILE = INSTANCE_DIR / "maintenance.db"
os.environ.setdefault("DATABASE_URL", "sqlite:///" + DATABASE_FILE.as_posix())
os.environ.setdefault("FLASK_CONFIG", "development")
os.environ.setdefault("SECRET_KEY", "local-dev-secret-change-me")
os.environ.setdefault("INGESTION_TOKEN", "demo-ingestion-token-change-me")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMeImmediately!")
os.environ.setdefault("PUBLIC_DEMO_ENABLED", "true")

from app import create_app
from app.extensions import db
from app.seed import seed_database

app = create_app()

with app.app_context():
    db.create_all()
    seed_database()

if __name__ == "__main__":
    print("Starting development server on http://127.0.0.1:5000")
    print("Login: admin / ChangeMeImmediately!")
    print("Public demo: http://127.0.0.1:5000/demo")
    app.run(host="127.0.0.1", port=5000, debug=True)
