"""Telemetry ingestion, validation, and threshold-based alert generation.

Thresholds are examples only – real limits depend on equipment, manufacturer,
sensor calibration and operating conditions.
"""
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.models import Equipment, TelemetryReading, Alert


def parse_timestamp(value):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    # ISO format
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        raise ValueError("Invalid timestamp format; use ISO-8601")


def validate_reading(data: dict) -> dict:
    """Validate and normalize incoming telemetry payload. Raises ValueError on bad data."""
    asset_tag = (data.get("asset_tag") or "").strip()
    if not asset_tag:
        raise ValueError("asset_tag is required")

    ts = parse_timestamp(data.get("timestamp"))

    def _float(key, min_v=None, max_v=None):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number")
        if min_v is not None and f < min_v:
            raise ValueError(f"{key} unreasonably low")
        if max_v is not None and f > max_v:
            raise ValueError(f"{key} unreasonably high")
        return f

    # Reasonable physical bounds (very wide – not safety limits)
    temperature_c = _float("temperature_c", -40, 250)
    vibration_mm_s = _float("vibration_mm_s", 0, 100)
    pressure_bar = _float("pressure_bar", 0, 100)
    rpm = _float("rpm", 0, 20000)
    current_a = _float("current_a", 0, 500)

    idempotency_key = (data.get("idempotency_key") or "").strip() or None
    if not idempotency_key:
        # Generate a deterministic key from asset + timestamp (second resolution)
        idempotency_key = f"{asset_tag}:{ts.strftime('%Y%m%d%H%M%S')}"

    return {
        "asset_tag": asset_tag,
        "timestamp": ts,
        "temperature_c": temperature_c,
        "vibration_mm_s": vibration_mm_s,
        "pressure_bar": pressure_bar,
        "rpm": rpm,
        "current_a": current_a,
        "data_source": data.get("data_source", "simulator"),
        "is_simulated": bool(data.get("is_simulated", True)),
        "idempotency_key": idempotency_key,
        "raw_payload": None,
    }


def check_thresholds_and_alert(equipment: Equipment, reading: TelemetryReading):
    """Generate alerts for values exceeding example thresholds.
    Suppresses duplicate open alerts for the same metric on the same equipment.
    """
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

        # Suppress if an open/acknowledged alert already exists for same metric
        existing = (
            Alert.query.filter_by(equipment_id=equipment.id, metric=metric)
            .filter(Alert.status.in_(["open", "acknowledged"]))
            .first()
        )
        if existing:
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

    # RPM high/low
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

    return created


def ingest_reading(data: dict, allowed_facility_ids=None):
    """
    Validate, persist, and evaluate a telemetry sample.
    allowed_facility_ids: if provided, reject equipment outside this set.
    Returns (reading, alerts_created) or raises ValueError.
    """
    normalized = validate_reading(data)

    # Idempotency check
    existing = TelemetryReading.query.filter_by(idempotency_key=normalized["idempotency_key"]).first()
    if existing:
        return existing, []  # already ingested – no duplicate, no new alerts

    equipment = Equipment.query.filter_by(asset_tag=normalized["asset_tag"]).first()
    if equipment is None:
        raise ValueError(f"Unknown asset_tag: {normalized['asset_tag']}")

    if allowed_facility_ids is not None and equipment.facility_id not in allowed_facility_ids:
        raise ValueError("Equipment does not belong to an authorized facility for this token")

    reading = TelemetryReading(
        equipment_id=equipment.id,
        facility_id=equipment.facility_id,
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
    db.session.add(reading)
    db.session.flush()

    alerts = check_thresholds_and_alert(equipment, reading)
    db.session.commit()
    return reading, alerts
