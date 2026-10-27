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

    # Production secret validation (raises RuntimeError on unsafe/missing values)
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

    app.register_blueprint(main_bp)
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
        """Create the bootstrap admin user only if it does not already exist.
        Does NOT reset an existing admin password (avoids surprise lockouts on re-run).
        """
        from app.models import User
        with app.app_context():
            username = app.config["BOOTSTRAP_ADMIN_USERNAME"]
            admin = User.query.filter_by(username=username).first()
            if admin is not None:
                print(f"Admin user '{username}' already exists – password left unchanged.")
                return
            password = app.config["BOOTSTRAP_ADMIN_PASSWORD"]
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

    @app.before_request
    def ensure_tables():
        if not getattr(app, "_tables_ready", False):
            try:
                db.create_all()
                app._tables_ready = True
            except Exception as e:
                logger.warning("Could not ensure tables: %s", e)

    @app.route("/health")
    def health():
        """Liveness probe: process is up. Always 200 so a temporary DB blip
        does not trigger a container restart. DB status is informational only.
        """
        db_status = "unknown"
        try:
            db.session.execute(db.text("SELECT 1"))
            db_status = "reachable"
        except Exception:
            db_status = "unreachable"
        return jsonify({
            "status": "ok",
            "service": "maintenance-dashboard",
            "database": db_status,
        }), 200

    @app.route("/ready")
    def ready():
        """Readiness probe: only ready when the database is reachable."""
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ready"}), 200
        except Exception as e:
            return jsonify({"status": "not_ready", "reason": str(e)}), 503

    return app
