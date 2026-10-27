"""Industrial Equipment Maintenance Dashboard – Flask application factory."""
import os
from flask import Flask
from app.config import config_by_name
from app.extensions import db, login_manager, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Blueprints
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

    # Exempt API from CSRF (uses token auth)
    csrf.exempt(api_bp)

    # CLI helpers
    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed demo data."""
        from app.seed import seed_database
        with app.app_context():
            db.create_all()
            seed_database()
            print("Database initialized and seeded.")

    @app.cli.command("create-admin")
    def create_admin():
        """Create or reset the bootstrap admin user."""
        from app.models import User, Facility
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

    # Health endpoint (no auth)
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "maintenance-dashboard"}, 200

    return app
