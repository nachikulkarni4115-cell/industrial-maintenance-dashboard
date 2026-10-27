"""Extra validation and escalation tests for telemetry."""
import json
from datetime import datetime, timezone, timedelta


def _post(client, app, payload):
    token = app.config["INGESTION_TOKEN"]
    return client.post(
        "/api/v1/telemetry",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_reject_nan(client, app):
    r = _post(client, app, {"asset_tag": "MTR-001", "temperature_c": float("nan")})
    assert r.status_code == 400


def test_reject_infinity(client, app):
    r = _post(client, app, {"asset_tag": "MTR-001", "temperature_c": float("inf")})
    assert r.status_code == 400


def test_reject_string_is_simulated(client, app):
    r = _post(client, app, {
        "asset_tag": "MTR-001",
        "temperature_c": 50,
        "is_simulated": "false",
    })
    assert r.status_code == 400
    assert "boolean" in r.get_json()["message"].lower()


def test_idempotency_different_asset_rejected(client, app):
    key = "shared-key-conflict-test"
    r1 = _post(client, app, {
        "asset_tag": "MTR-001",
        "temperature_c": 50,
        "idempotency_key": key,
        "is_simulated": True,
    })
    assert r1.status_code == 201
    r2 = _post(client, app, {
        "asset_tag": "PMP-012",
        "temperature_c": 51,
        "idempotency_key": key,
        "is_simulated": True,
    })
    assert r2.status_code == 400


def test_idempotency_conflicting_value_rejected(client, app):
    """Same key + same asset but different metric value must be rejected."""
    key = "value-conflict-key-001"
    ts = datetime.now(timezone.utc).isoformat()
    r1 = _post(client, app, {
        "asset_tag": "MTR-001",
        "timestamp": ts,
        "temperature_c": 50.0,
        "idempotency_key": key,
        "is_simulated": True,
    })
    assert r1.status_code == 201
    r2 = _post(client, app, {
        "asset_tag": "MTR-001",
        "timestamp": ts,
        "temperature_c": 99.0,  # different value
        "idempotency_key": key,
        "is_simulated": True,
    })
    assert r2.status_code == 400
    assert "different" in r2.get_json()["message"].lower()


def test_idempotency_identical_retry_ok(client, app):
    key = "identical-retry-key-002"
    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "asset_tag": "MTR-001",
        "timestamp": ts,
        "temperature_c": 55.5,
        "vibration_mm_s": 2.1,
        "idempotency_key": key,
        "is_simulated": True,
    }
    r1 = _post(client, app, payload)
    r2 = _post(client, app, payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.get_json()["reading_id"] == r2.get_json()["reading_id"]
