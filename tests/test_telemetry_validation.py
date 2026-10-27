"""Extra validation and escalation tests for telemetry."""
import json
import math


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
