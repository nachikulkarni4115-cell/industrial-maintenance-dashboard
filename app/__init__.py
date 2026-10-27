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

    # Production safety check
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

    # --- CLI: create tables only (no seed) ---
    @app.cli.command("init-db")
    def init_db_cmd():
        """Create database tables if they do not exist. Does NOT seed data."""
        with app.app_context():
            db.create_all()
            print("Database tables created (or already exist). No seed data applied.")

    # --- CLI: seed synthetic demo data (idempotent) ---
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
                raise

    @app.cli.command("create-admin")
    def create_admin_cmd():
        """Create or reset the bootstrap admin user."""
        from app.models import User
        with app.app_context():
            admin = User.query.filter_by(username=app.config["BOOTSTRAP_ADMIN_USERNAME"]).first()
            if admin is None:
                admin = User(
                    username=app.config["BOOTSTRAP_ADMIN_USERNAME"],
                    email=app.config["BOOTSTRAP_ADMIN_EMAIL"],
                    role="admin",
                    facility_id=None,
                )
                admin.set_password(app.config["BOOTSTRAP_ADMIN_PASSWORD"])
                db.session.add(admin)
                db.session.commit()
                print(f"Admin user '{admin.username}' created.")
            else:
                admin.set_password(app.config["BOOTSTRAP_ADMIN_PASSWORD"])
                db.session.commit()
                print(f"Admin password reset for '{admin.username}'.")

    # Ensure tables exist on first request in non-testing modes (safe, no seed)
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
        """Liveness-friendly health check. Returns 200 if process is up.
        Includes a lightweight DB ping for operational visibility.
        """
        db_ok = False
        try:
            db.session.execute(db.text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        status = "ok" if db_ok else "degraded"
        code = 200 if db_ok else 503
        return jsonify({
            "status": status,
            "service": "maintenance-dashboard",
            "database": "reachable" if db_ok else "unreachable",
        }), code

    @app.route("/ready")
    def ready():
        """Readiness: application can serve requests only if DB is reachable."""
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "ready"}), 200
        except Exception as e:
            return jsonify({"status": "not_ready", "reason": str(e)}), 503

    return app
