"""Azure IoT Hub -> existing Industrial Maintenance Dashboard API bridge.

This service forwards device-to-cloud telemetry only. It does not connect to
physical equipment and does not modify the dashboard database directly.
"""

import json
import logging
import os
import signal
import sys
import time
from typing import Any

import requests
from azure.eventhub import EventHubConsumerClient
from azure.eventhub.extensions.checkpointstoreblob import BlobCheckpointStore

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("azure-iot-dashboard-bridge")

CONNECTION_STRING = os.getenv("AZURE_IOTHUB_EVENTHUB_CONNECTION_STRING", "").strip()
CONSUMER_GROUP = os.getenv("AZURE_IOTHUB_CONSUMER_GROUP", "$Default").strip()
DASHBOARD_API_URL = os.getenv(
    "DASHBOARD_API_URL",
    "http://maintenance-dashboard-service:80/api/v1/telemetry",
).strip()
INGESTION_TOKEN = os.getenv("INGESTION_TOKEN", "").strip()
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
BLOB_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "").strip()
HTTP_TIMEOUT_SECONDS = max(2, int(os.getenv("HTTP_TIMEOUT_SECONDS", "10")))
HTTP_MAX_RETRIES = max(1, int(os.getenv("HTTP_MAX_RETRIES", "5")))
HTTP_RETRY_BASE_SECONDS = max(1, float(os.getenv("HTTP_RETRY_BASE_SECONDS", "1")))

# Keep this list aligned with app/telemetry/service.py's supported schema.
ALLOWED_FIELDS = (
    "asset_tag",
    "timestamp",
    "temperature_c",
    "vibration_mm_s",
    "pressure_bar",
    "rpm",
    "current_a",
    "is_simulated",
    "idempotency_key",
)

session = requests.Session()
stop_requested = False


def request_stop(signum: int, _frame: Any) -> None:
    global stop_requested
    stop_requested = True
    logger.info("Stop signal received (%s); shutting down after current event", signum)


def parse_event(event: Any) -> dict[str, Any]:
    """Decode EventData body into JSON without logging message contents."""
    try:
        body_text = event.body_as_str(encoding="UTF-8")
        payload = json.loads(body_text)
    except Exception as exc:
        raise ValueError("Event body is not valid UTF-8 JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Event JSON must be an object")

    return payload


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate required identifiers and pass only dashboard-supported fields."""
    asset_tag = payload.get("asset_tag")
    timestamp = payload.get("timestamp")
    if not isinstance(asset_tag, str) or not asset_tag.strip():
        raise ValueError("Telemetry is missing asset_tag")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ValueError("Telemetry is missing timestamp")
    if not isinstance(payload.get("is_simulated"), bool):
        raise ValueError("Telemetry is_simulated must be a JSON boolean")

    result = {key: payload[key] for key in ALLOWED_FIELDS if key in payload}
    result["asset_tag"] = asset_tag.strip()
    result["timestamp"] = timestamp
    result["data_source"] = "azure_iot_hub_bridge"
    result["is_simulated"] = payload["is_simulated"]
    # Preserve the simulator UUID; API idempotency prevents duplicate readings
    # when the Event Hubs stream is replayed after a restart.
    if not result.get("idempotency_key"):
        raise ValueError("Telemetry is missing idempotency_key")
    return result


def forward_to_dashboard(payload: dict[str, Any]) -> None:
    headers = {
        "Authorization": f"Bearer {INGESTION_TOKEN}",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None

    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        try:
            response = session.post(
                DASHBOARD_API_URL,
                json=payload,
                headers=headers,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code in (200, 201):
                logger.info(
                    "Forwarded telemetry asset_tag=%s status=%s",
                    payload["asset_tag"], response.status_code,
                )
                return

            # A 4xx response generally means invalid credentials or payload.
            # Retrying it repeatedly will not fix the issue, so stop the bridge
            # and let Kubernetes restart it after the configuration is corrected.
            if 400 <= response.status_code < 500:
                raise RuntimeError(
                    f"Dashboard rejected telemetry with HTTP {response.status_code}"
                )
            last_error = RuntimeError(
                f"Dashboard returned HTTP {response.status_code}"
            )
        except requests.RequestException as exc:
            last_error = exc
        except RuntimeError:
            raise

        if attempt < HTTP_MAX_RETRIES:
            delay = min(HTTP_RETRY_BASE_SECONDS * (2 ** (attempt - 1)), 15)
            logger.warning(
                "Dashboard request failed (attempt %s/%s); retrying in %.1fs",
                attempt, HTTP_MAX_RETRIES, delay,
            )
            time.sleep(delay)

    raise RuntimeError("Dashboard delivery failed after retries") from last_error


def on_event(partition_context: Any, event: Any) -> None:
    if event is None:
        return
    try:
        raw_payload = parse_event(event)
        payload = normalize_payload(raw_payload)
    except ValueError as exc:
        # Invalid messages are intentionally discarded and checkpointed so a
        # poison event cannot cause an infinite restart/replay loop.
        logger.error("Dropping invalid telemetry event: %s", exc)
        try:
            partition_context.update_checkpoint(event)
        except Exception:
            logger.exception("Could not checkpoint invalid event; stopping for replay")
            os._exit(1)
        return

    try:
        # Checkpoint only after the API confirms acceptance. If the process stops
        # between POST and checkpoint, the event is replayed; idempotency_key
        # lets the dashboard suppress the duplicate.
        forward_to_dashboard(payload)
        partition_context.update_checkpoint(event)
        logger.debug("Checkpoint updated for partition %s", partition_context.partition_id)
    except Exception:
        logger.exception("Delivery/checkpoint failed; stopping bridge for safe replay")
        os._exit(1)


def main() -> int:
    if not CONNECTION_STRING:
        logger.error("Missing AZURE_IOTHUB_EVENTHUB_CONNECTION_STRING")
        return 2
    if not INGESTION_TOKEN:
        logger.error("Missing INGESTION_TOKEN")
        return 2
    if not STORAGE_CONNECTION_STRING:
        logger.error("Missing AZURE_STORAGE_CONNECTION_STRING")
        return 2
    if not BLOB_CONTAINER_NAME:
        logger.error("Missing AZURE_STORAGE_CONTAINER_NAME")
        return 2
    if not DASHBOARD_API_URL.startswith(("http://", "https://")):
        logger.error("DASHBOARD_API_URL must be an HTTP(S) URL")
        return 2

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info("Starting Azure IoT Hub telemetry bridge")
    logger.info("Consumer group: %s", CONSUMER_GROUP)
    logger.info("Dashboard endpoint configured (URL omitted from logs)")
    logger.info("Persistent Azure Blob checkpointing is enabled")

    checkpoint_store = None
    try:
        checkpoint_store = BlobCheckpointStore.from_connection_string(
            STORAGE_CONNECTION_STRING, BLOB_CONTAINER_NAME
        )
        with EventHubConsumerClient.from_connection_string(
            conn_str=CONNECTION_STRING,
            consumer_group=CONSUMER_GROUP,
            checkpoint_store=checkpoint_store,
        ) as client:
            # On first run, start at the earliest retained event; after that, the
            # checkpoint store resumes each partition from its last checkpoint.
            client.receive(
                on_event=on_event,
                starting_position="-1",
                max_wait_time=5,
            )
        return 0
    except Exception:
        logger.exception("Azure Event Hubs consumer stopped")
        return 1
    finally:
        session.close()
        if checkpoint_store is not None:
            try:
                checkpoint_store.close()
            except Exception:
                logger.exception("Error closing checkpoint store")
        logger.info("Bridge stopped")


if __name__ == "__main__":
    raise SystemExit(main())
