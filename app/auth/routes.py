from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, AuditLog
from app.auth.forms import LoginForm

auth_bp = Blueprint("auth", __name__)


def log_audit(action, resource_type=None, resource_id=None, details=None):
    entry = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        username=current_user.username if current_user.is_authenticated else None,
        facility_id=current_user.facility_id if current_user.is_authenticated else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    # commit is done by caller when appropriate


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password.", "danger")
            # Do not log the attempted password
            log_audit("login_failed", details=f"username={form.username.data}")
            db.session.commit()
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("Account is disabled. Contact an administrator.", "warning")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        user.last_login = datetime.now(timezone.utc)
        log_audit("login_success")
        db.session.commit()
        flash(f"Welcome, {user.username}.", "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_audit("logout")
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
