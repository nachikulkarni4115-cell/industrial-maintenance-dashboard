"""Tests for empty-state dashboard, public demo, idempotent seed, and startup."""


def test_dashboard_with_seeded_data(client):
    client.post("/auth/login", data={"username": "admin", "password": "testadminpass"})
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"Operations Overview" in r.data
    assert b"MTR-001" in r.data or b"Registered Assets" in r.data


def test_dashboard_empty_database(app, client):
    """Fresh empty DB shows useful empty-state messages, not a traceback."""
    from app.extensions import db
    from app.models import Facility, Equipment, TelemetryReading, Alert, WorkOrder, User, AuditLog
    with app.app_context():
        # Wipe all data
        for model in (AuditLog, WorkOrder, Alert, TelemetryReading, Equipment, User, Facility):
            db.session.query(model).delete()
        db.session.commit()

    # Re-create admin so we can log in
    with app.app_context():
        from app.models import User
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("testadminpass")
        db.session.add(admin)
        db.session.commit()

    client.post("/auth/login", data={"username": "admin", "password": "testadminpass"})
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"No equipment registered yet" in r.data or b"Empty database" in r.data
    assert b"No telemetry received yet" in r.data or b"No telemetry" in r.data


def test_public_demo_enabled(client):
    r = client.get("/demo")
    assert r.status_code == 200
    assert b"Demonstration" in r.data or b"demo" in r.data.lower()


def test_public_demo_disabled(app, client):
    app.config["PUBLIC_DEMO_ENABLED"] = False
    r = client.get("/demo")
    assert r.status_code == 404


def test_seed_idempotent(app):
    from app.seed import seed_database
    from app.models import Facility, Equipment
    with app.app_context():
        count1 = Facility.query.count()
        seed_database()  # should skip
        count2 = Facility.query.count()
        assert count1 == count2
        assert count1 >= 1


def test_health_and_ready(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json["status"] in ("ok", "degraded")
    r2 = client.get("/ready")
    assert r2.status_code == 200
    assert r2.json["status"] == "ready"


def test_logout_requires_post(client):
    client.post("/auth/login", data={"username": "admin", "password": "testadminpass"})
    r = client.get("/auth/logout")
    assert r.status_code in (405, 404)  # method not allowed
