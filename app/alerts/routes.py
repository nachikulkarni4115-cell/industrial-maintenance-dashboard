from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Alert, AuditLog
from app.main import facility_filter

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/")
@login_required
def list_alerts():
    status = request.args.get("status", "open")
    q = facility_filter(Alert.query, Alert)
    if status == "open":
        q = q.filter(Alert.status.in_(["open", "acknowledged"]))
    elif status in ("acknowledged", "resolved", "all"):
        if status != "all":
            q = q.filter(Alert.status == status)
    alerts = q.order_by(Alert.created_at.desc()).limit(100).all()
    return render_template("alerts/list.html", alerts=alerts, current_status=status)


@alerts_bp.route("/<int:alert_id>")
@login_required
def detail(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    if not current_user.is_admin() or current_user.facility_id is not None:
        if alert.facility_id != current_user.facility_id:
            abort(403)
    return render_template("alerts/detail.html", alert=alert)


@alerts_bp.route("/<int:alert_id>/acknowledge", methods=["POST"])
@login_required
def acknowledge(alert_id):
    if not current_user.can_acknowledge_alerts():
        abort(403)
    alert = Alert.query.get_or_404(alert_id)
    if alert.facility_id != current_user.facility_id and not (current_user.is_admin() and current_user.facility_id is None):
        abort(403)
    if alert.status != "open":
        flash("Only open alerts can be acknowledged.", "warning")
        return redirect(url_for("alerts.detail", alert_id=alert.id))

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by_id = current_user.id
    audit = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        facility_id=current_user.facility_id,
        action="acknowledge_alert",
        resource_type="alert",
        resource_id=alert.id,
        details=f"severity={alert.severity}",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()
    flash("Alert acknowledged.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert.id))


@alerts_bp.route("/<int:alert_id>/resolve", methods=["POST"])
@login_required
def resolve(alert_id):
    if not current_user.can_acknowledge_alerts():
        abort(403)
    alert = Alert.query.get_or_404(alert_id)
    if alert.facility_id != current_user.facility_id and not (current_user.is_admin() and current_user.facility_id is None):
        abort(403)
    if alert.status == "resolved":
        flash("Alert is already resolved.", "info")
        return redirect(url_for("alerts.detail", alert_id=alert.id))

    notes = request.form.get("resolution_notes", "").strip()
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by_id = current_user.id
    alert.resolution_notes = notes or None
    audit = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        facility_id=current_user.facility_id,
        action="resolve_alert",
        resource_type="alert",
        resource_id=alert.id,
        details=f"notes={notes[:100] if notes else ''}",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()
    flash("Alert resolved.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert.id))
