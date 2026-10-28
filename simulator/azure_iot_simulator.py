
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

from azure.iot.device import IoTHubDeviceClient, Message


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INTERVAL = max(1, int(os.getenv("SAMPLE_INTERVAL", "5")))
MAX_BATCHES = max(1, int(os.getenv("MAX_BATCHES", "3")))
MAX_RETRIES = max(1, int(os.getenv("MAX_RETRIES", "3")))
FAULT_MODE = os.getenv("FAULT_MODE", "0") == "1"

DEVICE_ENV = {
    "MTR-001": "IOTHUB_DEVICE_CONN_MTR_001",
    "PMP-012": "IOTHUB_DEVICE_CONN_PMP_012",
    "CMP-003": "IOTHUB_DEVICE_CONN_CMP_003",
}


# --------------------------------------------------
# TELEMETRY GENERATION
# --------------------------------------------------

def make_reading(asset_tag, batch_number):
    """Generate normal or simulated fault telemetry."""

    temperature = round(48 + random.uniform(-4, 8), 1)
    vibration = round(2.2 + random.uniform(0, 1.2), 2)
    rpm = round(1450 + random.uniform(-40, 40))
    current = round(8 + random.uniform(-1, 2), 2)
    pressure = None
    fault_type = None

    if asset_tag in ("PMP-012", "CMP-003"):
        pressure = round(5.2 + random.uniform(-0.3, 0.8), 2)

    if FAULT_MODE:
        # Different simulated fault for each device.
        if asset_tag == "MTR-001":
            temperature = round(random.uniform(88, 93), 1)
            vibration = round(random.uniform(7.5, 9.0), 2)
            current = round(random.uniform(18, 21), 2)
            fault_type = "motor_overheating_high_vibration"

        elif asset_tag == "PMP-012":
            pressure = round(random.uniform(8.5, 9.5), 2)
            vibration = round(random.uniform(6.5, 8.0), 2)
            rpm = round(random.uniform(850, 1050))
            fault_type = "pump_pressure_anomaly"

        elif asset_tag == "CMP-003":
            temperature = round(random.uniform(85, 92), 1)
            vibration = round(random.uniform(7.0, 9.0), 2)
            pressure = round(random.uniform(8.5, 9.5), 2)
            fault_type = "compressor_overheating_vibration"

    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "asset_tag": asset_tag,
        "timestamp": timestamp,
        "temperature_c": temperature,
        "vibration_mm_s": vibration,
        "pressure_bar": pressure,
        "rpm": rpm,
        "current_a": current if asset_tag == "MTR-001" else None,
        "data_source": "azure_iot_hub_simulator",
        "is_simulated": True,
        "fault_mode": FAULT_MODE,
        "fault_type": fault_type,
        "batch_number": batch_number,
        "idempotency_key": str(uuid.uuid4()),
    }


# --------------------------------------------------
# SEND TELEMETRY WITH RETRIES
# --------------------------------------------------

def send_with_retries(client, asset_tag, payload):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            message = Message(json.dumps(payload))
            message.content_type = "application/json"
            message.content_encoding = "utf-8"

            client.send_message(message)

            status = (
                f"FAULT: {payload['fault_type']}"
                if payload["fault_type"]
                else "NORMAL"
            )

            print(
                f"[SENT] {asset_tag} | "
                f"Temperature={payload['temperature_c']} C | "
                f"Vibration={payload['vibration_mm_s']} mm/s | "
                f"Status={status}"
            )
            return True

        except Exception as exc:
            print(
                f"[WARN] {asset_tag}: send failed "
                f"(attempt {attempt}/{MAX_RETRIES}): "
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt, 10))

    print(f"[ERROR] {asset_tag}: all send attempts failed")
    return False


# --------------------------------------------------
# MAIN SIMULATION
# --------------------------------------------------

def main():
    clients = {}

    try:
        # Validate all credentials before connecting.
        for asset_tag, env_name in DEVICE_ENV.items():
            connection_string = os.getenv(env_name)

            if not connection_string:
                print(
                    f"[ERROR] Missing environment variable: {env_name}"
                )
                return 2

        # Create and connect all three device clients.
        for asset_tag, env_name in DEVICE_ENV.items():
            connection_string = os.getenv(env_name)

            print(f"[CONNECTING] {asset_tag}")
            client = IoTHubDeviceClient.create_from_connection_string(
                connection_string
            )
            client.connect()
            clients[asset_tag] = client
            print(f"[CONNECTED] {asset_tag}")

        print("\nAzure IoT Hub telemetry simulator")
        print("Simulation only; no physical equipment is connected.")
        print(f"Fault mode: {'ON' if FAULT_MODE else 'OFF'}")
        print(f"Interval between batches: {INTERVAL} seconds")
        print(f"Number of batches: {MAX_BATCHES}")
        print(f"Expected messages: {MAX_BATCHES * len(clients)}")

        attempted_sends = 0
        successful_sends = 0

        for batch_number in range(1, MAX_BATCHES + 1):
            print(
                f"\n=== Batch {batch_number}/{MAX_BATCHES} ==="
            )

            for asset_tag, client in clients.items():
                payload = make_reading(asset_tag, batch_number)
                attempted_sends += 1

                if send_with_retries(client, asset_tag, payload):
                    successful_sends += 1

            if batch_number < MAX_BATCHES:
                print(
                    f"Waiting {INTERVAL} seconds before next batch..."
                )
                time.sleep(INTERVAL)

        print("\n========== SIMULATION SUMMARY ==========")
        print(f"Messages attempted: {attempted_sends}")
        print(f"Successful sends: {successful_sends}")
        print(f"Failed messages: {attempted_sends - successful_sends}")
        print("========================================")

        return 0 if successful_sends == attempted_sends else 1

    except KeyboardInterrupt:
        print("\n[STOPPED] Simulation interrupted by user.")
        return 130

    except Exception as exc:
        print(
            f"[ERROR] Simulator stopped: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    finally:
        for asset_tag, client in clients.items():
            try:
                client.shutdown()
                print(f"[DISCONNECTED] {asset_tag}")
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
