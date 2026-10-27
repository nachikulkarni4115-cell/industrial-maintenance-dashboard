"""Database models for Industrial Maintenance Dashboard.

All multi-tenant queries MUST filter by facility_id (except explicit admin actions).
"""
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class Facility(db.Model):
    __tablename__ = "facilities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False)
    location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=utcnow)

    users = db.relationship("User", back_populates="facility", lazy="dynamic")
    equipment = db.relationship("Equipment", back_populates="facility", lazy="dynamic")

    def __repr__(self):
        return f"<Facility {self.code}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="viewer")  # admin, maintenance_manager, technician, viewer
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=True)  # null only for global admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime)

    facility = db.relationship("Facility", back_populates="users")

    ROLES = ("admin", "maintenance_manager", "technician", "viewer")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_manage_equipment(self) -> bool:
        return self.role in ("admin", "maintenance_manager")

    def can_manage_workorders(self) -> bool:
        return self.role in ("admin", "maintenance_manager", "technician")

    def can_acknowledge_alerts(self) -> bool:
        return self.role in ("admin", "maintenance_manager", "technician")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Equipment(db.Model):
    __tablename__ = "equipment"
    id = db.Column(db.Integer, primary_key=True)
    asset_tag = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    equipment_type = db.Column(db.String(64), nullable=False)  # motor, pump, compressor, conveyor, fan
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False, index=True)
    location = db.Column(db.String(200))
    criticality = db.Column(db.String(20), default="medium")  # low, medium, high, critical
    status = db.Column(db.String(32), default="operational")  # operational, maintenance, offline, decommissioned
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    install_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    facility = db.relationship("Facility", back_populates="equipment")
    telemetry = db.relationship("TelemetryReading", back_populates="equipment", lazy="dynamic", cascade="all, delete-orphan")
    alerts = db.relationship("Alert", back_populates="equipment", lazy="dynamic", cascade="all, delete-orphan")
    work_orders = db.relationship("WorkOrder", back_populates="equipment", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("asset_tag", "facility_id", name="uq_asset_tag_facility"),
    )

    EQUIPMENT_TYPES = ("motor", "pump", "compressor", "conveyor", "fan", "other")
    CRITICALITIES = ("low", "medium", "high", "critical")
    STATUSES = ("operational", "maintenance", "offline", "decommissioned")

    def latest_reading(self):
        return self.telemetry.order_by(TelemetryReading.timestamp.desc()).first()

    def open_alerts_count(self):
        return self.alerts.filter(Alert.status.in_(["open", "acknowledged"])).count()

    def __repr__(self):
        return f"<Equipment {self.asset_tag}>"


class TelemetryReading(db.Model):
    __tablename__ = "telemetry_readings"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=False, index=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    temperature_c = db.Column(db.Float)
    vibration_mm_s = db.Column(db.Float)  # RMS velocity mm/s
    pressure_bar = db.Column(db.Float)
    rpm = db.Column(db.Float)
    current_a = db.Column(db.Float)
    data_source = db.Column(db.String(32), default="simulator")  # simulator, historical, sensor
    is_simulated = db.Column(db.Boolean, default=True)
    raw_payload = db.Column(db.Text)  # optional original JSON for audit
    created_at = db.Column(db.DateTime, default=utcnow)

    # Idempotency key to prevent duplicate samples on retransmit
    idempotency_key = db.Column(db.String(128), unique=True, index=True)

    equipment = db.relationship("Equipment", back_populates="telemetry")

    def __repr__(self):
        return f"<Telemetry {self.equipment_id} @ {self.timestamp}>"


class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=False, index=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False)  # info, warning, critical
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    metric = db.Column(db.String(64))  # temperature_c, vibration_mm_s, etc.
    value = db.Column(db.Float)
    threshold = db.Column(db.Float)
    status = db.Column(db.String(20), default="open")  # open, acknowledged, resolved
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    acknowledged_at = db.Column(db.DateTime)
    acknowledged_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    resolution_notes = db.Column(db.Text)

    equipment = db.relationship("Equipment", back_populates="alerts")
    acknowledged_by = db.relationship("User", foreign_keys=[acknowledged_by_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])

    SEVERITIES = ("info", "warning", "critical")
    STATUSES = ("open", "acknowledged", "resolved")

    def __repr__(self):
        return f"<Alert {self.id} {self.severity} {self.status}>"


class WorkOrder(db.Model):
    __tablename__ = "work_orders"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=False, index=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default="medium")  # low, medium, high, urgent
    status = db.Column(db.String(20), default="open")  # open, assigned, in_progress, completed, cancelled
    assigned_to = db.Column(db.String(100))
    due_date = db.Column(db.Date)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime)
    completion_notes = db.Column(db.Text)

    equipment = db.relationship("Equipment", back_populates="work_orders")
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    PRIORITIES = ("low", "medium", "high", "urgent")
    STATUSES = ("open", "assigned", "in_progress", "completed", "cancelled")

    def __repr__(self):
        return f"<WorkOrder {self.id} {self.status}>"


class AuditLog(db.Model):
    """Auditable history of important actions. No passwords or tokens stored."""
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username = db.Column(db.String(64))  # denormalized for history after user deletion
    facility_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(64), nullable=False)  # login, create_equipment, acknowledge_alert, etc.
    resource_type = db.Column(db.String(32))  # equipment, alert, work_order, user
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON or plain text summary
    ip_address = db.Column(db.String(45))

    user = db.relationship("User")

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.username}>"
