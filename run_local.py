#!/usr/bin/env python3
"""Local development runner. Creates DB and seeds if needed."""
import os
os.environ.setdefault("FLASK_CONFIG", "development")
os.environ.setdefault("SECRET_KEY", "local-dev-secret-change-me")
os.environ.setdefault("INGESTION_TOKEN", "demo-ingestion-token-change-me")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMeImmediately!")

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
    app.run(host="127.0.0.1", port=5000, debug=True)
