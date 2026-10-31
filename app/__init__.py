"""Industrial Equipment Maintenance Dashboard – Flask application factory."""
import os
import logging
from flask import Flask, jsonify
from app.config import config_by_name
from app.extensions import db, login_manager, csrf

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    if config_name == "production":
        from app.config import ProductionConfig
        ProductionConfig.init_app(app)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.auth.routes import auth_bp
    from app.equipment.routes import equipment_bp
    from app.telemetry.routes import telemetry_bp
    from app.alerts.routes import alerts_bp
    from app.workorders.routes import workorders_bp
    from app.api.routes import api_bp
    from app.main import main_bp
    from app.simulator.routes import simulator_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(simulator_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(equipment_bp, url_prefix="/equipment")
    app.register_blueprint(telemetry_bp, url_prefix="/telemetry")
    app.register_blueprint(alerts_bp, url_prefix="/alerts")
    app.register_blueprint(workorders_bp, url_prefix="/workorders")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    csrf.exempt(api_bp)

    @app.cli.command("init-db")
    def init_db_cmd():
        """Create database tables if they do not exist. Does NOT seed data."""
        with app.app_context():
            db.create_all()
            print("Database tables created (or already exist). No seed data applied.")

    @app.cli.command("seed-demo")
    def seed_demo_cmd():
        """Insert synthetic demonstration data if not already present. Safe to re-run."""
        from app.seed import seed_database
        with app.app_context():
            try:
                seed_database()
            except Exception as e:
                db.session.rollback()
                print(f"Seed failed and was rolled back: {e}")
                raise SystemExit(1)

    @app.cli.command("create-admin")
    def create_admin_cmd():
        """Create the bootstrap admin only if missing. Never resets an existing password.

        Safe recovery path: if facilities already exist (seed was skipped) but the
        admin account is absent, this still creates the admin.
        """
        from app.models import User
        with app.app_context():
            username = app.config["BOOTSTRAP_ADMIN_USERNAME"]
            admin = User.query.filter_by(username=username).first()
            if admin is not None:
                print(f"Admin user '{username}' already exists – password left unchanged.")
                return
            password = app.config.get("BOOTSTRAP_ADMIN_PASSWORD") or ""
            if not password:
                print("BOOTSTRAP_ADMIN_PASSWORD is empty; cannot create admin.")
                raise SystemExit(1)
            admin = User(
                username=username,
                email=app.config["BOOTSTRAP_ADMIN_EMAIL"],
                role="admin",
                facility_id=None,
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f"Admin user '{username}' created.")

    # NOTE: db.create_all() is NOT called on every request.
    # Tables are created only via `flask init-db` or the Kubernetes init Job.

    @app.route("/health")
    def health():
        """Liveness: process is running. Never depends on the database.
        Always returns 200 so a temporary DB issue does not restart the pod.
        """
        return jsonify({
            "status": "ok",
            "service": "maintenance-dashboard",
        }), 200

    @app.route("/ready")
    def ready():
        """Readiness: database must be reachable to serve DB-backed requests."""
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ready"}), 200
        except Exception as e:
            return jsonify({"status": "not_ready", "reason": str(e)}), 503

    return app
