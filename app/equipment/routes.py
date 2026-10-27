from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Equipment, TelemetryReading, Alert, WorkOrder, AuditLog
from app.equipment.forms import EquipmentForm
from app.main import facility_filter

equipment_bp = Blueprint("equipment", __name__)


def require_manage_equipment():
    if not current_user.can_manage_equipment():
        abort(403)


@equipment_bp.route("/")
@login_required
def list_equipment():
    q = facility_filter(Equipment.query, Equipment)
    equipment = q.order_by(Equipment.asset_tag).all()
    return render_template("equipment/list.html", equipment=equipment)


@equipment_bp.route("/<int:eq_id>")
@login_required
def detail(eq_id):
    eq = Equipment.query.get_or_404(eq_id)
    if not current_user.is_admin() or current_user.facility_id is not None:
        if eq.facility_id != current_user.facility_id:
            abort(403)
    readings = (
        TelemetryReading.query.filter_by(equipment_id=eq.id)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(50)
        .all()
    )
    alerts = (
        Alert.query.filter_by(equipment_id=eq.id)
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )
    workorders = (
        WorkOrder.query.filter_by(equipment_id=eq.id)
        .order_by(WorkOrder.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "equipment/detail.html",
        equipment=eq,
        readings=readings,
        alerts=alerts,
        workorders=workorders,
    )


@equipment_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    require_manage_equipment()
    form = EquipmentForm()
    if form.validate_on_submit():
        # Unique asset tag within facility
        existing = Equipment.query.filter_by(
            asset_tag=form.asset_tag.data.strip(),
            facility_id=current_user.facility_id,
        ).first()
        if existing:
            flash("Asset tag already exists in this facility.", "danger")
            return render_template("equipment/form.html", form=form, title="Add Equipment")

        eq = Equipment(
            asset_tag=form.asset_tag.data.strip(),
            name=form.name.data.strip(),
            equipment_type=form.equipment_type.data,
            facility_id=current_user.facility_id,
            location=form.location.data,
            criticality=form.criticality.data,
            status=form.status.data,
            manufacturer=form.manufacturer.data,
            model=form.model.data,
            install_date=form.install_date.data,
            notes=form.notes.data,
        )
        db.session.add(eq)
        db.session.flush()
        audit = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            facility_id=current_user.facility_id,
            action="create_equipment",
            resource_type="equipment",
            resource_id=eq.id,
            details=f"asset_tag={eq.asset_tag}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()
        flash(f"Equipment {eq.asset_tag} created.", "success")
        return redirect(url_for("equipment.detail", eq_id=eq.id))
    return render_template("equipment/form.html", form=form, title="Add Equipment")


@equipment_bp.route("/<int:eq_id>/edit", methods=["GET", "POST"])
@login_required
def edit(eq_id):
    require_manage_equipment()
    eq = Equipment.query.get_or_404(eq_id)
    if eq.facility_id != current_user.facility_id and not (current_user.is_admin() and current_user.facility_id is None):
        abort(403)
    form = EquipmentForm(obj=eq)
    if form.validate_on_submit():
        # Check uniqueness if asset_tag changed
        if form.asset_tag.data.strip() != eq.asset_tag:
            existing = Equipment.query.filter_by(
                asset_tag=form.asset_tag.data.strip(),
                facility_id=eq.facility_id,
            ).first()
            if existing:
                flash("Asset tag already exists in this facility.", "danger")
                return render_template("equipment/form.html", form=form, title="Edit Equipment", equipment=eq)

        eq.asset_tag = form.asset_tag.data.strip()
        eq.name = form.name.data.strip()
        eq.equipment_type = form.equipment_type.data
        eq.location = form.location.data
        eq.criticality = form.criticality.data
        eq.status = form.status.data
        eq.manufacturer = form.manufacturer.data
        eq.model = form.model.data
        eq.install_date = form.install_date.data
        eq.notes = form.notes.data
        audit = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            facility_id=current_user.facility_id,
            action="update_equipment",
            resource_type="equipment",
            resource_id=eq.id,
            details=f"asset_tag={eq.asset_tag}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()
        flash("Equipment updated.", "success")
        return redirect(url_for("equipment.detail", eq_id=eq.id))
    return render_template("equipment/form.html", form=form, title="Edit Equipment", equipment=eq)
