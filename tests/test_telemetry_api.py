import json
from datetime import datetime, timezone


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json["status"] == "ok"


def test_api_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_telemetry_requires_token(client):
    r = client.post("/api/v1/telemetry", json={
        "asset_tag": "MTR-001",
        "temperature_c": 50,
    })
    assert r.status_code == 401


def test_telemetry_valid_ingestion(client, app):
    token = app.config["INGESTION_TOKEN"]
    payload = {
        "asset_tag": "MTR-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": 55.0,
        "vibration_mm_s": 2.5,
        "rpm": 1470,
        "current_a": 9.0,
        "is_simulated": True,
        "idempotency_key": "test-unique-key-001",
    }
    r = client.post(
        "/api/v1/telemetry",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "accepted"
    assert body["is_simulated"] is True


def test_telemetry_unknown_asset(client, app):
    token = app.config["INGESTION_TOKEN"]
    r = client.post(
        "/api/v1/telemetry",
        json={"asset_tag": "UNKNOWN-999", "temperature_c": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "Unknown asset_tag" in r.get_json()["message"]


def test_telemetry_idempotent(client, app):
    token = app.config["INGESTION_TOKEN"]
    payload = {
        "asset_tag": "MTR-001",
        "temperature_c": 52.0,
        "idempotency_key": "idempotent-test-key-xyz",
    }
    headers = {"Authorization": f"Bearer {token}"}
    r1 = client.post("/api/v1/telemetry", json=payload, headers=headers)
    r2 = client.post("/api/v1/telemetry", json=payload, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    # second call returns existing reading, no new alerts forced
    assert r1.get_json()["reading_id"] == r2.get_json()["reading_id"]


def test_telemetry_malformed(client, app):
    token = app.config["INGESTION_TOKEN"]
    r = client.post(
        "/api/v1/telemetry",
        json={"asset_tag": "MTR-001", "temperature_c": "not-a-number"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
