# Azure IoT Hub â†’ Industrial Maintenance Dashboard bridge (review package)

This is a **separate service template**, not a deployment. It consumes device-to-cloud events from the IoT Hub Event Hubs-compatible endpoint and forwards supported telemetry to the existing Flask API. It does not connect to physical equipment and does not access the database directly.

## Included

- `bridge/consumer.py` â€” consumer and API forwarder
- `bridge/requirements.txt` â€” bridge-only Python dependencies
- `bridge/Dockerfile` â€” non-root container image
- `kubernetes-deployment.template.yaml` â€” separate Deployment in `capstone`; image name is intentionally a placeholder

## Important behavior and limitations

- The bridge passes only dashboard-supported fields and sets `data_source=azure_iot_hub_bridge`.
- The simulator's `idempotency_key` is preserved so the existing ingestion service can suppress duplicate inserts on replay.
- The bridge uses persistent Azure Blob checkpointing through `BlobCheckpointStore`. Configure `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_STORAGE_CONTAINER_NAME` through Kubernetes environment variables and Secrets. The checkpoint container is `iot-bridge-checkpoints`.

The consumer checkpoints an event after the dashboard API accepts it. If the process stops after API acceptance but before the checkpoint is saved, the event may be replayed. The idempotency key helps prevent duplicate readings during retries. Invalid events are intentionally discarded and checkpointed so they do not block a partition.
- Invalid telemetry is logged without printing the full payload. A dashboard 4xx response or delivery failure stops the process so Kubernetes can restart it; investigate logs before deploying this version in a live environment.
- `fault_type` is not stored by the current dashboard schema; the numeric metrics still go through the existing threshold alert engine.
- This package does not modify the dashboard app, dashboard Deployment, existing Jenkinsfile, ALB, portfolio, or AgriSakha.

## Azure credential

The IoT Hub's built-in endpoint is Event Hubs-compatible. The connection string needs the compatible endpoint/path and a policy with `ServiceConnect` permission. The policy name created for this project is `dashboard-telemetry-reader`.

**Never paste a key or connection string into source control, chat, shell command arguments, or logs.** Create a Kubernetes Secret from a local protected file or secure secret workflow only after reviewing this template. Do not use device connection strings for event consumption.

## Review locally (no deployment)

From the repository root in PowerShell:

```powershell
# Inspect files and verify no tracked dashboard files changed
git status --short

# Optional syntax check
.\.venv\Scripts\python.exe -m py_compile .\bridge\consumer.py
```

The template references `maintenance-telemetry-secret/INGESTION_TOKEN`, which is already present in the `capstone` namespace. The Azure reader credential must be added separately as `azure-iot-reader-secret/AZURE_IOTHUB_EVENTHUB_CONNECTION_STRING` before any deployment.

Do not apply the Kubernetes YAML until the image tag, checkpoint plan, and credential handling have been reviewed and explicitly approved.

