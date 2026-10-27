"""Idempotent synthetic demo data seeder.

Safe to re-run: skips creation when facilities / users / equipment already exist.
Never deletes or overwrites an existing persistent database.
All generated readings are labelled is_simulated=True / data_source='simulator'.
"""
from datetime import datetime, timedelta, timezone, date
import random
from flask import current_app
from app.extensions import db
from app.models import Facility, User, Equipment, TelemetryReading, Alert, WorkOrder


def seed_database():
    """Insert demonstration data only when the database is empty of facilities."""
    if Facility.query.first() is not None:
        print("Database already contains facilities – skipping seed (idempotent).")
        return

    try:
        _do_seed()
    except Exception:
        db.session.rollback()
        raise


def _do_seed():
    random.seed(42)

    fac1 = Facility(name="North Manufacturing Plant", code="NMP", location="Mumbai Industrial Zone")
    fac2 = Facility(name="South Assembly Facility", code="SAF", location="Pune Industrial Park")
    db.session.add_all([fac1, fac2])
    db.session.flush()

    admin = User(
        username=current_app.config["BOOTSTRAP_ADMIN_USERNAME"],
        email=current_app.config["BOOTSTRAP_ADMIN_EMAIL"],
        role="admin",
        facility_id=None,
    )
    admin.set_password(current_app.config["BOOTSTRAP_ADMIN_PASSWORD"])

    mgr = User(username="mgr_north", email="mgr.north@example.com", role="maintenance_manager", facility_id=fac1.id)
    mgr.set_password("Manager123!")
    tech = User(username="tech_north", email="tech.north@example.com", role="technician", facility_id=fac1.id)
    tech.set_password("Tech123!")
    viewer = User(username="viewer_north", email="viewer.north@example.com", role="viewer", facility_id=fac1.id)
    viewer.set_password("Viewer123!")
    mgr2 = User(username="mgr_south", email="mgr.south@example.com", role="maintenance_manager", facility_id=fac2.id)
    mgr2.set_password("Manager123!")

    db.session.add_all([admin, mgr, tech, viewer, mgr2])
    db.session.flush()

    eq_data = [
        ("MTR-001", "Main Drive Motor A", "motor", "Bay 1", "critical"),
        ("PMP-012", "Coolant Pump 12", "pump", "Bay 2", "high"),
        ("CMP-003", "Air Compressor 3", "compressor", "Utility Room", "high"),
        ("CNV-007", "Assembly Conveyor 7", "conveyor", "Line 3", "medium"),
        ("FAN-021", "Exhaust Fan 21", "fan", "Roof Level", "low"),
        ("MTR-014", "Spindle Motor 14", "motor", "CNC Cell", "critical"),
    ]
    equipment = []
    for tag, name, etype, loc, crit in eq_data:
        e = Equipment(
            asset_tag=tag,
            name=name,
            equipment_type=etype,
            facility_id=fac1.id,
            location=loc,
            criticality=crit,
            status="operational",
            manufacturer="DemoCorp",
            model="DC-2024",
            install_date=date(2022, 6, 15),
            notes="Synthetic demonstration equipment – not a physical asset.",
        )
        equipment.append(e)
        db.session.add(e)

    e2 = Equipment(
        asset_tag="MTR-S01",
        name="South Main Motor",
        equipment_type="motor",
        facility_id=fac2.id,
        location="South Bay",
        criticality="high",
        status="operational",
        notes="Synthetic demonstration equipment – facility isolation test asset.",
    )
    db.session.add(e2)
    db.session.flush()

    now = datetime.now(timezone.utc)
    for eq in equipment:
        for i in range(12):
            ts = now - timedelta(hours=2 * i)
            base_temp = 45 + random.uniform(-5, 10)
            base_vib = 2.0 + random.uniform(0, 1.5)
            if i == 1 and eq.asset_tag == "MTR-001":
                base_temp = 88.5
                base_vib = 7.8
            reading = TelemetryReading(
                equipment_id=eq.id,
                facility_id=fac1.id,
                timestamp=ts,
                temperature_c=round(base_temp, 1),
                vibration_mm_s=round(base_vib, 2),
                pressure_bar=round(5.0 + random.uniform(-0.5, 1.0), 2) if eq.equipment_type in ("pump", "compressor") else None,
                rpm=round(1450 + random.uniform(-50, 50), 0) if eq.equipment_type in ("motor", "fan", "pump") else None,
                current_a=round(8.5 + random.uniform(-1, 2), 2) if eq.equipment_type == "motor" else None,
                data_source="simulator",
                is_simulated=True,
                idempotency_key=f"seed-{eq.asset_tag}-{i}",
            )
            db.session.add(reading)

    db.session.flush()

    critical_alert = Alert(
        equipment_id=equipment[0].id,
        facility_id=fac1.id,
        severity="critical",
        title="High temperature and vibration on Main Drive Motor A",
        message="Temperature 88.5 °C exceeded critical threshold 85 °C; vibration 7.8 mm/s exceeded 7.1 mm/s. Simulated demo reading.",
        metric="temperature_c",
        value=88.5,
        threshold=85.0,
        status="open",
    )
    db.session.add(critical_alert)

    wo1 = WorkOrder(
        equipment_id=equipment[0].id,
        facility_id=fac1.id,
        title="Investigate high temperature on MTR-001",
        description="Review cooling system and bearing condition after elevated temperature/vibration alert. (Demo work order)",
        priority="high",
        status="open",
        assigned_to="tech_north",
        due_date=date.today() + timedelta(days=2),
        created_by_id=mgr.id,
    )
    wo2 = WorkOrder(
        equipment_id=equipment[1].id,
        facility_id=fac1.id,
        title="Scheduled lubrication – Coolant Pump 12",
        description="Quarterly preventive maintenance. (Demo work order)",
        priority="medium",
        status="assigned",
        assigned_to="tech_north",
        due_date=date.today() + timedelta(days=7),
        created_by_id=mgr.id,
    )
    db.session.add_all([wo1, wo2])
    db.session.commit()
    print("Synthetic demo data seeded (2 facilities, 7 equipment, users, telemetry, alerts, work orders).")
