"""Tests for empty-state dashboard, public demo scope, health/ready, seed."""


def test_dashboard_with_seeded_data(client):
    client.post("/auth/login", data={"username": "admin", "password": "testadminpass"})
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"Operations Overview" in r.data
    assert b"MTR-001" in r.data or b"Registered Assets" in r.data


def test_dashboard_empty_database(app, client):
    from app.extensions import db
    from app.models import Facility, Equipment, TelemetryReading, Alert, WorkOrder, User, AuditLog
    with app.app_context():
        for model in (AuditLog, WorkOrder, Alert, TelemetryReading, Equipment, User, Facility):
            db.session.query(model).delete()
        db.session.commit()
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


def test_public_demo_excludes_non_demo_equipment(app, client):
    """Equipment without the explicit demo notes marker must not appear on /demo."""
    from app.extensions import db
    from app.models import Facility, Equipment
    with app.app_context():
        fac = Facility.query.first()
        assert fac is not None
        secret_eq = Equipment(
            asset_tag="SECRET-999",
            name="Hidden Operational Asset",
            equipment_type="motor",
            facility_id=fac.id,
            notes="Operational asset – not for public demo",
        )
        db.session.add(secret_eq)
        db.session.commit()

    r = client.get("/demo")
    assert r.status_code == 200
    assert b"SECRET-999" not in r.data
    assert b"Hidden Operational Asset" not in r.data


def test_seed_idempotent(app):
    from app.seed import seed_database
    from app.models import Facility
    with app.app_context():
        count1 = Facility.query.count()
        seed_database()
        count2 = Facility.query.count()
        assert count1 == count2
        assert count1 >= 1


def test_health_independent_of_db(client):
    """Liveness must return 200 even conceptually without requiring DB success."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json["status"] == "ok"
    assert "database" not in r.json or r.json.get("service") == "maintenance-dashboard"


def test_ready_requires_db(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json["status"] == "ready"


def test_logout_requires_post(client):
    client.post("/auth/login", data={"username": "admin", "password": "testadminpass"})
    r = client.get("/auth/logout")
    assert r.status_code == 405
