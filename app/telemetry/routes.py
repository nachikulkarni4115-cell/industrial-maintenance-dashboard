"""Browser-facing telemetry views (read-only for most roles)."""
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.models import TelemetryReading
from app.main import facility_filter

telemetry_bp = Blueprint("telemetry", __name__)


@telemetry_bp.route("/")
@login_required
def list_readings():
    readings = (
        facility_filter(TelemetryReading.query, TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(100)
        .all()
    )
    return render_template("telemetry/list.html", readings=readings)
