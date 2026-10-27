#!/usr/bin/env python3
"""
Laptop-based industrial equipment telemetry simulator.

Runs on the operator's Windows laptop (or any local machine).
Sends authenticated readings to the dashboard ingestion API.
Does NOT run on the EC2 / Kubernetes side.

Environment variables:
  DASHBOARD_API_URL   e.g. http://127.0.0.1:15000/api/v1/telemetry
  INGESTION_TOKEN     must match the server INGESTION_TOKEN
  SAMPLE_INTERVAL     seconds between samples (default 30)
  ASSET_TAGS          comma-separated list (default MTR-001,PMP-012,CMP-003)
  FAULT_MODE          set to 1 to inject elevated temperature/vibration
  SINGLE_RUN          set to 1 to send one batch and exit
  MAX_RETRIES         bounded retries on network failure (default 5)
"""
import os
import sys
import time
import json
import random
import hashlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

# Local buffer for offline resilience
BUFFER_FILE = Path(__file__).parent / "pending_readings.jsonl"


def env(key, default=None):
    return os.environ.get(key, default)


API_URL = env("DASHBOARD_API_URL", "http://127.0.0.1:15000/api/v1/telemetry")
TOKEN = env("INGESTION_TOKEN", "demo-ingestion-token-change-me")
INTERVAL = int(env("SAMPLE_INTERVAL", "30"))
ASSETS = [a.strip() for a in env("ASSET_TAGS", "MTR-001,PMP-012,CMP-003").split(",") if a.strip()]
FAULT_MODE = env("FAULT_MODE", "0") == "1"
SINGLE_RUN = env("SINGLE_RUN", "0") == "1"
MAX_RETRIES = int(env("MAX_RETRIES", "5"))


def make_reading(asset_tag: str, fault: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    temp = 48 + random.uniform(-4, 8)
    vib = 2.2 + random.uniform(0, 1.2)
    rpm = 1450 + random.uniform(-40, 40)
    current = 8.0 + random.uniform(-1, 2)

    if fault and asset_tag.startswith("MTR"):
        temp = 88 + random.uniform(0, 5)
        vib = 7.5 + random.uniform(0, 1.5)
        current = 18 + random.uniform(0, 3)

    # Idempotency key: asset + second-resolution timestamp + small hash
    ts_str = now.strftime("%Y%m%d%H%M%S")
    key = f"{asset_tag}:{ts_str}:{hashlib.md5(f'{temp}{vib}'.encode()).hexdigest()[:8]}"

    return {
        "asset_tag": asset_tag,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "temperature_c": round(temp, 1),
        "vibration_mm_s": round(vib, 2),
        "pressure_bar": round(5.2 + random.uniform(-0.3, 0.8), 2) if "PMP" in asset_tag or "CMP" in asset_tag else None,
        "rpm": round(rpm, 0),
        "current_a": round(current, 2) if asset_tag.startswith("MTR") else None,
        "data_source": "simulator",
        "is_simulated": True,
        "idempotency_key": key,
    }


def send_one(payload: dict) -> bool:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "IndustrialTelemetrySimulator/1.0 (laptop; simulated data)",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(API_URL, json=payload, headers=headers, timeout=15)
            if r.status_code in (200, 201):
                body = r.json()
                print(f"[OK] {payload['asset_tag']} @ {payload['timestamp']}  "
                      f"alerts={body.get('alerts_created', 0)}")
                return True
            if r.status_code == 401:
                print("[ERROR] Unauthorized – check INGESTION_TOKEN")
                return False
            if r.status_code == 400:
                print(f"[WARN] Validation rejected: {r.text[:200]}")
                return False  # do not retry bad data
            print(f"[WARN] HTTP {r.status_code}: {r.text[:150]} (attempt {attempt})")
        except requests.exceptions.RequestException as e:
            print(f"[WARN] Network error: {e} (attempt {attempt})")
        if attempt < MAX_RETRIES:
            backoff = min(2 ** attempt, 30)
            time.sleep(backoff)
    return False


def buffer_reading(payload: dict):
    with open(BUFFER_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
    print(f"[BUFFERED] {payload['asset_tag']} saved to {BUFFER_FILE}")


def flush_buffer():
    if not BUFFER_FILE.exists():
        return
    remaining = []
    with open(BUFFER_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not send_one(payload):
                remaining.append(payload)
    if remaining:
        with open(BUFFER_FILE, "w", encoding="utf-8") as f:
            for p in remaining:
                f.write(json.dumps(p) + "\n")
    else:
        BUFFER_FILE.unlink(missing_ok=True)
        print("[BUFFER] All pending readings flushed.")


def main():
    print("=" * 60)
    print("Industrial Equipment Telemetry Simulator (LAPTOP)")
    print("All values are SIMULATED – not from physical sensors.")
    print(f"API URL     : {API_URL}")
    print(f"Assets      : {ASSETS}")
    print(f"Interval    : {INTERVAL}s")
    print(f"Fault mode  : {FAULT_MODE}")
    print(f"Single run  : {SINGLE_RUN}")
    print("=" * 60)

    flush_buffer()

    while True:
        for tag in ASSETS:
            payload = make_reading(tag, fault=FAULT_MODE)
            ok = send_one(payload)
            if not ok:
                buffer_reading(payload)
        if SINGLE_RUN:
            print("Single-run complete.")
            break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
