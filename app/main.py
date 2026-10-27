"""Main dashboard routes including empty-state handling and optional public demo."""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, current_app, abort
from flask_login import login_required, current_user
from app.models import Equipment, Alert, WorkOrder, TelemetryReading
from app.extensions import db

main_bp = Blueprint("main", __name__)


def facility_filter(query, model):
    """Apply facility isolation unless the user is a global admin with no facility."""
    if current_user.is_authenticated and current_user.is_admin() and current_user.facility_id is None:
        return query
    if not current_user.is_authenticated:
        return query.filter(False)  # no rows for anonymous
    return query.filter(model.facility_id == current_user.facility_id)


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

    # Last reading timestamp + stale indicator
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

    has_equipment = total_assets > 0
    has_telemetry = last_reading is not None
    has_alerts = open_alerts > 0 or recent_alerts
    has_workorders = open_workorders > 0 or recent_workorders

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
        has_equipment=has_equipment,
        has_telemetry=has_telemetry,
        has_alerts=has_alerts,
        has_workorders=has_workorders,
    )


@main_bp.route("/demo")
def demo():
    """Optional public read-only demonstration page.
    Shows only synthetic demo data. Never exposes users, emails, audit logs,
    tokens, or administrative controls.
    Controlled by PUBLIC_DEMO_ENABLED.
    """
    if not current_app.config.get("PUBLIC_DEMO_ENABLED"):
        abort(404)

    # Show only explicitly simulated equipment/readings (demo-safe)
    equipment = (
        Equipment.query.filter(Equipment.notes.isnot(None))
        .filter(Equipment.notes.like("%demonstration%"))
        .order_by(Equipment.asset_tag)
        .limit(12)
        .all()
    )
    # Fallback: if notes filter empty, show nothing private – just counts of simulated telemetry
    readings = (
        TelemetryReading.query.filter_by(is_simulated=True)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(10)
        .all()
    )
    alerts = (
        Alert.query.filter(Alert.message.like("%Simulated%"))
        .order_by(Alert.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "demo.html",
        equipment=equipment,
        readings=readings,
        alerts=alerts,
        total_assets=len(equipment),
        reading_count=TelemetryReading.query.filter_by(is_simulated=True).count(),
    )
