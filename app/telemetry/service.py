"""Telemetry ingestion, validation, and threshold-based alert generation.

Thresholds are examples only – real limits depend on equipment, manufacturer,
sensor calibration and operating conditions.
"""
import math
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.models import Equipment, TelemetryReading, Alert


def parse_timestamp(value):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        raise ValueError("Invalid timestamp format; use ISO-8601")


def _finite_float(key, value, min_v=None, max_v=None):
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    if math.isnan(f) or math.isinf(f):
        raise ValueError(f"{key} must be a finite number (got NaN or infinity)")
    if min_v is not None and f < min_v:
        raise ValueError(f"{key} unreasonably low")
    if max_v is not None and f > max_v:
        raise ValueError(f"{key} unreasonably high")
    return f


def validate_reading(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object")

    asset_tag = (data.get("asset_tag") or "").strip()
    if not asset_tag:
        raise ValueError("asset_tag is required")

    ts = parse_timestamp(data.get("timestamp"))

    temperature_c = _finite_float("temperature_c", data.get("temperature_c"), -40, 250)
    vibration_mm_s = _finite_float("vibration_mm_s", data.get("vibration_mm_s"), 0, 100)
    pressure_bar = _finite_float("pressure_bar", data.get("pressure_bar"), 0, 100)
    rpm = _finite_float("rpm", data.get("rpm"), 0, 20000)
    current_a = _finite_float("current_a", data.get("current_a"), 0, 500)

    # is_simulated must be a real boolean when provided
    raw_sim = data.get("is_simulated", True)
    if isinstance(raw_sim, str):
        raise ValueError('is_simulated must be a JSON boolean (true/false), not a string')
    if not isinstance(raw_sim, bool):
        raise ValueError("is_simulated must be a boolean")
    is_simulated = raw_sim

    idempotency_key = (data.get("idempotency_key") or "").strip() or None
    if not idempotency_key:
        idempotency_key = f"{asset_tag}:{ts.strftime('%Y%m%d%H%M%S')}"

    return {
        "asset_tag": asset_tag,
        "timestamp": ts,
        "temperature_c": temperature_c,
        "vibration_mm_s": vibration_mm_s,
        "pressure_bar": pressure_bar,
        "rpm": rpm,
        "current_a": current_a,
        "data_source": data.get("data_source") or "simulator",
        "is_simulated": is_simulated,
        "idempotency_key": idempotency_key,
    }


def check_thresholds_and_alert(equipment: Equipment, reading: TelemetryReading):
    """Generate or escalate alerts for values exceeding example thresholds."""
    thresholds = current_app.config.get("DEFAULT_THRESHOLDS", {})
    created = []

    checks = [
        ("temperature_c", reading.temperature_c, thresholds.get("temperature_c")),
        ("vibration_mm_s", reading.vibration_mm_s, thresholds.get("vibration_mm_s")),
        ("pressure_bar", reading.pressure_bar, thresholds.get("pressure_bar")),
        ("current_a", reading.current_a, thresholds.get("current_a")),
    ]

    for metric, value, th in checks:
        if value is None or th is None:
            continue
        severity = None
        threshold_val = None
        if "critical" in th and value >= th["critical"]:
            severity = "critical"
            threshold_val = th["critical"]
        elif "warning" in th and value >= th["warning"]:
            severity = "warning"
            threshold_val = th["warning"]
        if severity is None:
            continue

        existing = (
            Alert.query.filter_by(equipment_id=equipment.id, metric=metric)
            .filter(Alert.status.in_(["open", "acknowledged"]))
            .first()
        )
        if existing:
            # Escalate severity if a critical reading follows a warning
            if severity == "critical" and existing.severity == "warning":
                existing.severity = "critical"
                existing.value = value
                existing.threshold = threshold_val
                existing.title = f"Critical {metric.replace('_', ' ')} on {equipment.asset_tag}"
                existing.message = (
                    f"{metric}={value} escalated to critical threshold {threshold_val}. "
                    f"{'Simulated demo reading.' if reading.is_simulated else 'Live reading.'}"
                )
            continue

        alert = Alert(
            equipment_id=equipment.id,
            facility_id=equipment.facility_id,
            severity=severity,
            title=f"{severity.title()} {metric.replace('_', ' ')} on {equipment.asset_tag}",
            message=(
                f"{metric}={value} exceeded {severity} threshold {threshold_val}. "
                f"{'Simulated demo reading.' if reading.is_simulated else 'Live reading.'}"
            ),
            metric=metric,
            value=value,
            threshold=threshold_val,
            status="open",
        )
        db.session.add(alert)
        created.append(alert)

    rpm_th = thresholds.get("rpm")
    if reading.rpm is not None and rpm_th:
        severity = None
        threshold_val = None
        if reading.rpm >= rpm_th.get("critical_high", 99999):
            severity, threshold_val = "critical", rpm_th["critical_high"]
        elif reading.rpm >= rpm_th.get("warning_high", 99999):
            severity, threshold_val = "warning", rpm_th["warning_high"]
        elif reading.rpm <= rpm_th.get("critical_low", -1):
            severity, threshold_val = "critical", rpm_th["critical_low"]
        elif reading.rpm <= rpm_th.get("warning_low", -1):
            severity, threshold_val = "warning", rpm_th["warning_low"]
        if severity:
            existing = (
                Alert.query.filter_by(equipment_id=equipment.id, metric="rpm")
                .filter(Alert.status.in_(["open", "acknowledged"]))
                .first()
            )
            if not existing:
                alert = Alert(
                    equipment_id=equipment.id,
                    facility_id=equipment.facility_id,
                    severity=severity,
                    title=f"{severity.title()} RPM on {equipment.asset_tag}",
                    message=f"RPM={reading.rpm} exceeded threshold {threshold_val}.",
                    metric="rpm",
                    value=reading.rpm,
                    threshold=threshold_val,
                    status="open",
                )
                db.session.add(alert)
                created.append(alert)
            elif severity == "critical" and existing.severity == "warning":
                existing.severity = "critical"
                existing.value = reading.rpm
                existing.threshold = threshold_val

    return created


def ingest_reading(data: dict, allowed_facility_ids=None):
    """
    Validate, persist, and evaluate a telemetry sample.
    Facility is derived from the equipment record – never trusted from the client payload.
    """
    normalized = validate_reading(data)

    existing = TelemetryReading.query.filter_by(idempotency_key=normalized["idempotency_key"]).first()
    if existing:
        # Same key must refer to the same asset
        if existing.equipment and existing.equipment.asset_tag != normalized["asset_tag"]:
            raise ValueError("idempotency_key already used for a different asset")
        return existing, []

    equipment = Equipment.query.filter_by(asset_tag=normalized["asset_tag"]).first()
    if equipment is None:
        raise ValueError(f"Unknown asset_tag: {normalized['asset_tag']}")

    if allowed_facility_ids is not None and equipment.facility_id not in allowed_facility_ids:
        raise ValueError("Equipment does not belong to an authorized facility for this token")

    reading = TelemetryReading(
        equipment_id=equipment.id,
        facility_id=equipment.facility_id,  # derived from equipment, not client
        timestamp=normalized["timestamp"],
        temperature_c=normalized["temperature_c"],
        vibration_mm_s=normalized["vibration_mm_s"],
        pressure_bar=normalized["pressure_bar"],
        rpm=normalized["rpm"],
        current_a=normalized["current_a"],
        data_source=normalized["data_source"],
        is_simulated=normalized["is_simulated"],
        idempotency_key=normalized["idempotency_key"],
    )
    try:
        db.session.add(reading)
        db.session.flush()
        alerts = check_thresholds_and_alert(equipment, reading)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return reading, alerts
