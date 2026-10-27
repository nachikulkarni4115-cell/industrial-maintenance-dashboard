"""Machine-to-machine API. Protected by ingestion token, not browser sessions."""
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from app.telemetry.service import ingest_reading

api_bp = Blueprint("api", __name__)


def require_ingestion_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = None
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
        if not token:
            token = request.headers.get("X-Ingestion-Token", "").strip()
        expected = current_app.config.get("INGESTION_TOKEN")
        if not expected or token != expected:
            return jsonify({"error": "Unauthorized", "message": "Invalid or missing ingestion token"}), 401
        return f(*args, **kwargs)
    return decorated


@api_bp.route("/telemetry", methods=["POST"])
@require_ingestion_token
def post_telemetry():
    """
    Ingest a single telemetry sample.

    Headers:
      Authorization: Bearer <INGESTION_TOKEN>
      or X-Ingestion-Token: <INGESTION_TOKEN>

    JSON body example:
    {
      "asset_tag": "MTR-001",
      "timestamp": "2026-10-28T01:00:00Z",
      "temperature_c": 62.5,
      "vibration_mm_s": 3.2,
      "pressure_bar": null,
      "rpm": 1480,
      "current_a": 9.1,
      "data_source": "simulator",
      "is_simulated": true,
      "idempotency_key": "optional-unique-key"
    }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    data = request.get_json(silent=True) or {}
    try:
        reading, alerts = ingest_reading(data)
    except ValueError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Telemetry ingestion error")
        return jsonify({"error": "Internal error", "message": "Failed to process reading"}), 500

    return jsonify({
        "status": "accepted",
        "reading_id": reading.id,
        "equipment_id": reading.equipment_id,
        "facility_id": reading.facility_id,
        "timestamp": reading.timestamp.isoformat(),
        "alerts_created": len(alerts),
        "alert_ids": [a.id for a in alerts],
        "is_simulated": reading.is_simulated,
    }), 201


@api_bp.route("/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok", "service": "maintenance-dashboard-api"}), 200
