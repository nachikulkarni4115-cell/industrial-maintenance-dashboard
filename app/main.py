"""Main dashboard routes."""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Equipment, Alert, WorkOrder, TelemetryReading, Facility
from app.extensions import db
from sqlalchemy import func

main_bp = Blueprint("main", __name__)


def facility_filter(query, model):
    """Apply facility isolation unless the user is a global admin."""
    if current_user.is_admin() and current_user.facility_id is None:
        return query
    return query.filter(model.facility_id == current_user.facility_id)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    # Counts with facility isolation
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

    # Latest telemetry summary (last 20 readings across facility)
    latest_readings = (
        facility_filter(TelemetryReading.query, TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(12)
        .all()
    )

    # Equipment health snapshot
    equipment_list = eq_q.order_by(Equipment.criticality.desc(), Equipment.asset_tag).limit(12).all()

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
    )
