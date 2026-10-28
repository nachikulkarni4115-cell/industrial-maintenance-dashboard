"""Main dashboard routes including empty-state handling and optional public demo."""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from app.models import Equipment, Alert, WorkOrder, TelemetryReading
from app.extensions import db

main_bp = Blueprint("main", __name__)

# Explicit marker used by seed data for public-demo-safe equipment only.
DEMO_NOTES_MARKER = "Synthetic demonstration equipment"


def facility_filter(query, model):
    """Apply facility isolation unless the user is a global admin with no facility."""
    if current_user.is_authenticated and current_user.is_admin() and current_user.facility_id is None:
        return query
    if not current_user.is_authenticated:
        return query.filter(False)
    return query.filter(model.facility_id == current_user.facility_id)


def _demo_equipment_query():
    """Only equipment explicitly designated as synthetic demonstration assets."""
    return Equipment.query.filter(Equipment.notes.isnot(None)).filter(
        Equipment.notes.like(f"%{DEMO_NOTES_MARKER}%")
    )


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if current_app.config.get("PUBLIC_DEMO_ENABLED"):
        return redirect(url_for("main.demo"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    eq_q = facility_filter(Equipment.query, Equipment)
    alert_q = facility_filter(Alert.query.filter(Alert.status.in_(["open", "acknowledged"])), Alert)
    wo_q = facility_filter(WorkOrder.query.filter(WorkOrder.status.in_(["open", "assigned", "in_progress"])), WorkOrder)

    total_assets = eq_q.count()
    open_alerts = alert_q.count()
    critical_alerts = alert_q.filter(Alert.severity == "critical").count()
    open_workorders = wo_q.count()

    recent_alerts = (
        facility_filter(Alert.query, Alert)
        .order_by(Alert.created_at.desc())
        .limit(8)
        .all()
    )
    recent_workorders = (
        facility_filter(WorkOrder.query, WorkOrder)
        .order_by(WorkOrder.created_at.desc())
        .limit(8)
        .all()
    )
    latest_readings = (
        facility_filter(TelemetryReading.query, TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(12)
        .all()
    )
    equipment_list = eq_q.order_by(Equipment.criticality.desc(), Equipment.asset_tag).limit(12).all()

    last_reading = (
        facility_filter(TelemetryReading.query, TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .first()
    )
    last_reading_ts = last_reading.timestamp if last_reading else None
    stale_hours = current_app.config.get("STALE_TELEMETRY_HOURS", 24)
    is_stale = False
    if last_reading_ts is not None:
        age = datetime.now(timezone.utc) - (
            last_reading_ts if last_reading_ts.tzinfo else last_reading_ts.replace(tzinfo=timezone.utc)
        )
        is_stale = age > timedelta(hours=stale_hours)

    return render_template(
        "dashboard.html",
        total_assets=total_assets,
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        open_workorders=open_workorders,
        recent_alerts=recent_alerts,
        recent_workorders=recent_workorders,
        latest_readings=latest_readings,
        equipment_list=equipment_list,
        last_reading_ts=last_reading_ts,
        is_stale=is_stale,
        stale_hours=stale_hours,
        has_equipment=total_assets > 0,
        has_telemetry=last_reading is not None,
        has_alerts=bool(recent_alerts) or open_alerts > 0,
        has_workorders=bool(recent_workorders) or open_workorders > 0,
    )


@main_bp.route("/demo")
def demo():
    """Public read-only page. Only explicitly designated synthetic demo equipment.

    Does NOT expose records merely because is_simulated=True or the word
    "Simulated" appears in an alert message. Controlled by PUBLIC_DEMO_ENABLED.
    """
    if not current_app.config.get("PUBLIC_DEMO_ENABLED"):
        abort(404)

    equipment = _demo_equipment_query().order_by(Equipment.asset_tag).limit(20).all()
    demo_ids = [e.id for e in equipment]

    if demo_ids:
        readings = (
            TelemetryReading.query.filter(TelemetryReading.equipment_id.in_(demo_ids))
            .order_by(TelemetryReading.timestamp.desc())
            .limit(10)
            .all()
        )
        alerts = (
            Alert.query.filter(Alert.equipment_id.in_(demo_ids))
            .order_by(Alert.created_at.desc())
            .limit(5)
            .all()
        )
        reading_count = TelemetryReading.query.filter(
            TelemetryReading.equipment_id.in_(demo_ids)
        ).count()
    else:
        readings = []
        alerts = []
        reading_count = 0

    return render_template(
        "demo.html",
        equipment=equipment,
        readings=readings,
        alerts=alerts,
        total_assets=len(equipment),
        reading_count=reading_count,
    )
