"""Main dashboard routes including empty-state handling and optional public demo."""

from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    current_app,
    abort,
    jsonify,
    make_response,
)
from flask_login import login_required, current_user

from app.models import Equipment, Alert, WorkOrder, TelemetryReading
from app.extensions import db


main_bp = Blueprint("main", __name__)

# Explicit marker used by seed data for public-demo-safe equipment only.
DEMO_NOTES_MARKER = "Synthetic demonstration equipment"


def facility_filter(query, model):
    """Apply facility isolation unless the user is a global admin with no facility."""
    if (
        current_user.is_authenticated
        and current_user.is_admin()
        and current_user.facility_id is None
    ):
        return query

    if not current_user.is_authenticated:
        return query.filter(False)

    return query.filter(model.facility_id == current_user.facility_id)


def _demo_equipment_query():
    """Only equipment explicitly designated as synthetic demonstration assets."""
    return (
        Equipment.query.filter(Equipment.notes.isnot(None))
        .filter(Equipment.notes.like(f"%{DEMO_NOTES_MARKER}%"))
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

    alert_q = facility_filter(
        Alert.query.filter(Alert.status.in_(["open", "acknowledged"])),
        Alert,
    )

    wo_q = facility_filter(
        WorkOrder.query.filter(
            WorkOrder.status.in_(["open", "assigned", "in_progress"])
        ),
        WorkOrder,
    )

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

    equipment_list = (
        eq_q.order_by(Equipment.criticality.desc(), Equipment.asset_tag)
        .limit(12)
        .all()
    )

    last_reading = (
        facility_filter(TelemetryReading.query, TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .first()
    )

    last_reading_ts = last_reading.timestamp if last_reading else None
    stale_hours = current_app.config.get("STALE_TELEMETRY_HOURS", 24)
    is_stale = False

    if last_reading_ts is not None:
        timestamp_utc = (
            last_reading_ts
            if last_reading_ts.tzinfo
            else last_reading_ts.replace(tzinfo=timezone.utc)
        )

        age = datetime.now(timezone.utc) - timestamp_utc
        is_stale = age > timedelta(hours=stale_hours)

    page = make_response(render_template(
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
    ))
    # Ensure a browser/proxy doesn't keep serving an old dashboard template after deployment.
    page.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    page.headers["Pragma"] = "no-cache"
    return page


@main_bp.route("/dashboard/live-telemetry")
@login_required
def live_telemetry():
    """Return the latest telemetry for the authenticated user's facility."""

    readings = (
        facility_filter(TelemetryReading.query, TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(12)
        .all()
    )

    last_reading = readings[0] if readings else None
    last_reading_ts = last_reading.timestamp if last_reading else None

    stale_hours = current_app.config.get("STALE_TELEMETRY_HOURS", 24)
    is_stale = False

    if last_reading_ts is not None:
        timestamp_utc = (
            last_reading_ts
            if last_reading_ts.tzinfo
            else last_reading_ts.replace(tzinfo=timezone.utc)
        )

        is_stale = (
            datetime.now(timezone.utc) - timestamp_utc
        ) > timedelta(hours=stale_hours)

    # Recalculate dashboard KPIs so the overview updates without a full-page reload.
    equipment_query = facility_filter(Equipment.query, Equipment)
    open_alert_query = facility_filter(
        Alert.query.filter(Alert.status.in_(["open", "acknowledged"])),
        Alert,
    )
    open_workorder_query = facility_filter(
        WorkOrder.query.filter(
            WorkOrder.status.in_(["open", "assigned", "in_progress"])
        ),
        WorkOrder,
    )

    response = jsonify(
        {
            "kpis": {
                "total_assets": equipment_query.count(),
                "open_alerts": open_alert_query.count(),
                "critical_alerts": open_alert_query.filter(
                    Alert.severity == "critical"
                ).count(),
                "open_workorders": open_workorder_query.count(),
            },
            "readings": [
                {
                    "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "asset_tag": (
                        r.equipment.asset_tag
                        if r.equipment
                        else str(r.equipment_id)
                    ),
                    "temperature_c": r.temperature_c,
                    "vibration_mm_s": r.vibration_mm_s,
                    "rpm": r.rpm,
                    "current_a": r.current_a,
                    "is_simulated": r.is_simulated,
                }
                for r in readings
            ],
            "last_reading": (
                last_reading_ts.strftime("%Y-%m-%d %H:%M:%S UTC")
                if last_reading_ts
                else None
            ),
            "is_stale": is_stale,
            "stale_hours": stale_hours,
        }
    )
    # Prevent browsers and reverse proxies from serving stale JSON between polls.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@main_bp.route("/demo")
def demo():
    """Public read-only page. Only explicitly designated synthetic demo equipment.

    Does NOT expose records merely because is_simulated=True or the word
    "Simulated" appears in an alert message. Controlled by PUBLIC_DEMO_ENABLED.
    """
    if not current_app.config.get("PUBLIC_DEMO_ENABLED"):
        abort(404)

    equipment = (
        _demo_equipment_query()
        .order_by(Equipment.asset_tag)
        .limit(20)
        .all()
    )

    demo_ids = [e.id for e in equipment]

    if demo_ids:
        readings = (
            TelemetryReading.query.filter(
                TelemetryReading.equipment_id.in_(demo_ids)
            )
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