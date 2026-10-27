from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import WorkOrder, Equipment, AuditLog
from app.workorders.forms import WorkOrderForm, WorkOrderStatusForm
from app.main import facility_filter

workorders_bp = Blueprint("workorders", __name__)


def require_manage_wo():
    if not current_user.can_manage_workorders():
        abort(403)


@workorders_bp.route("/")
@login_required
def list_workorders():
    status = request.args.get("status", "active")
    q = facility_filter(WorkOrder.query, WorkOrder)
    if status == "active":
        q = q.filter(WorkOrder.status.in_(["open", "assigned", "in_progress"]))
    elif status in WorkOrder.STATUSES:
        q = q.filter(WorkOrder.status == status)
    workorders = q.order_by(WorkOrder.created_at.desc()).limit(100).all()
    return render_template("workorders/list.html", workorders=workorders, current_status=status)


@workorders_bp.route("/<int:wo_id>")
@login_required
def detail(wo_id):
    wo = WorkOrder.query.get_or_404(wo_id)
    if not current_user.is_admin() or current_user.facility_id is not None:
        if wo.facility_id != current_user.facility_id:
            abort(403)
    status_form = WorkOrderStatusForm(obj=wo)
    return render_template("workorders/detail.html", workorder=wo, status_form=status_form)


@workorders_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    require_manage_wo()
    form = WorkOrderForm()
    # Equipment choices limited to user's facility
    equipment = facility_filter(Equipment.query, Equipment).order_by(Equipment.asset_tag).all()
    if request.method == "GET":
        return render_template("workorders/form.html", form=form, equipment=equipment, title="Create Work Order")

    if form.validate_on_submit():
        eq_id = request.form.get("equipment_id", type=int)
        eq = Equipment.query.get(eq_id)
        if not eq or eq.facility_id != current_user.facility_id:
            flash("Invalid equipment selection.", "danger")
            return render_template("workorders/form.html", form=form, equipment=equipment, title="Create Work Order")

        wo = WorkOrder(
            equipment_id=eq.id,
            facility_id=current_user.facility_id,
            title=form.title.data.strip(),
            description=form.description.data,
            priority=form.priority.data,
            assigned_to=form.assigned_to.data,
            due_date=form.due_date.data,
            created_by_id=current_user.id,
            status="open",
        )
        db.session.add(wo)
        db.session.flush()
        audit = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            facility_id=current_user.facility_id,
            action="create_workorder",
            resource_type="work_order",
            resource_id=wo.id,
            details=f"title={wo.title}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()
        flash("Work order created.", "success")
        return redirect(url_for("workorders.detail", wo_id=wo.id))
    return render_template("workorders/form.html", form=form, equipment=equipment, title="Create Work Order")


@workorders_bp.route("/<int:wo_id>/status", methods=["POST"])
@login_required
def update_status(wo_id):
    require_manage_wo()
    wo = WorkOrder.query.get_or_404(wo_id)
    if wo.facility_id != current_user.facility_id and not (current_user.is_admin() and current_user.facility_id is None):
        abort(403)
    form = WorkOrderStatusForm()
    if form.validate_on_submit():
        old_status = wo.status
        wo.status = form.status.data
        wo.completion_notes = form.completion_notes.data
        if form.status.data == "completed":
            wo.completed_at = datetime.now(timezone.utc)
        audit = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            facility_id=current_user.facility_id,
            action="update_workorder_status",
            resource_type="work_order",
            resource_id=wo.id,
            details=f"{old_status} -> {wo.status}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()
        flash("Work order status updated.", "success")
    return redirect(url_for("workorders.detail", wo_id=wo.id))
