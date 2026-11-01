# Azure IoT Hub to Industrial Maintenance Dashboard bridge

This folder contains the bridge consumer source and a Kubernetes **deployment template**. The bridge is a separate long-running workload from the on-demand simulator Job.

## Data path

Azure IoT Hub device-to-cloud events are read through the IoT Hub Event Hubs-compatible endpoint. The consumer validates UTF-8 JSON, requires an asset identifier, timestamp, boolean `is_simulated` and an `idempotency_key`, forwards only dashboard-supported fields to the Flask ingestion API, then updates the Azure Blob checkpoint.

Default in-cluster destination:

`http://maintenance-dashboard-service:80/api/v1/telemetry`

Checkpoint container used by the project:

`iot-bridge-checkpoints`

The dashboard API requires the same ingestion token configured in the dashboard's Kubernetes Secret. The bridge does not access the SQLite database directly.

## Source files

- `bridge/consumer.py` — event consumer, payload validation, API forwarding and Blob checkpointing.
- `bridge/Dockerfile` — non-root bridge container image.
- `bridge/requirements.txt` — bridge runtime dependencies.
- `kubernetes-deployment.template.yaml` — example Deployment requiring environment-specific reconciliation.

## Important deployment status distinction

The root repository `Jenkinsfile` includes a stage to build and push the bridge image. It does **not** apply this bridge Deployment template. The YAML is not a record of the exact live manifest: it contains a placeholder image and Secret names. Confirm the actual running Deployment, image tag and Secret references with `kubectl get deployment azure-iot-dashboard-bridge -n capstone -o yaml` (redact Secret values) before describing it as the deployed configuration.

The project report describes a running bridge Deployment. That live claim must be supported by current cluster evidence; source code and an image-build stage alone are insufficient.

## Required configuration

- `AZURE_IOTHUB_EVENTHUB_CONNECTION_STRING` — IoT Hub Event Hubs-compatible endpoint connection string with appropriate ServiceConnect permissions.
- `AZURE_IOTHUB_CONSUMER_GROUP` — defaults to `$Default`.
- `AZURE_STORAGE_CONNECTION_STRING` — Azure Storage connection string for checkpointing.
- `AZURE_STORAGE_CONTAINER_NAME` — use `iot-bridge-checkpoints`.
- `DASHBOARD_API_URL` — in-cluster dashboard telemetry API URL.
- `INGESTION_TOKEN` — must match the dashboard's ingestion token.

Use Kubernetes Secrets for sensitive values. Never commit credentials, paste them into chat, or include them in logs/screenshots.

## Delivery and replay behavior

The consumer checkpoints an event after the dashboard API confirms acceptance. A crash between API acceptance and checkpoint persistence can cause replay; the event idempotency key is used by the dashboard ingestion service to suppress duplicate records. Invalid payloads are logged without printing full event contents and are checkpointed so a poison message does not repeatedly block a partition. Delivery/configuration failures stop the consumer so Kubernetes can restart it after the underlying issue is corrected.

## Build

From the repository root:

```bash
docker build --pull -f azure-iot-dashboard-bridge/bridge/Dockerfile -t <registry>/<namespace>/azure-iot-dashboard-bridge:<tag> .
```

Use a versioned tag and confirm the image name matches the root Jenkins pipeline's actual push destination. The root Jenkinsfile constructs the bridge image namespace from the Docker Hub credential username; the dashboard and simulator image names are explicitly configured in the Jenkinsfile. Image publishing does not deploy this bridge.

## Deployment template warning

Before using `kubernetes-deployment.template.yaml`, replace the placeholder image and reconcile Secret names/key names with the live namespace. Review permissions, resource settings and probes. Do not apply it blindly to a working cluster.
