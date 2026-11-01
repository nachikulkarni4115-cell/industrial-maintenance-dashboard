# Industrial Maintenance Dashboard

A Flask-based industrial equipment maintenance dashboard with authenticated equipment, telemetry, alerts, work orders and a protected telemetry-ingestion API. The solution integrates AWS-hosted Kubernetes workloads with Microsoft Azure IoT Hub.

**Public application:** https://maintenance.nachiketkulkarni.in

> Telemetry is synthetic. This project does not connect to physical industrial sensors.

## Architecture at a glance

1. The Flask dashboard runs as the `maintenance-dashboard` Deployment in the `capstone` namespace of a **self-managed Kubernetes cluster on AWS EC2** (not Amazon EKS).
2. When an authenticated user selects **Generate Telemetry**, the Flask backend uses in-cluster Kubernetes credentials to create a short-lived simulator Job.
3. The Job runs `simulator/azure_iot_simulator.py` in a container and sends synthetic readings for MTR-001, PMP-012 and CMP-003 to Azure IoT Hub.
4. A separate, long-running `azure-iot-dashboard-bridge` Deployment consumes IoT Hub events through its Event Hubs-compatible endpoint, checkpoints progress in Azure Blob Storage, and posts validated events to `http://maintenance-dashboard-service:80/api/v1/telemetry`.
5. The Flask API validates the ingestion token and payload, then stores readings in SQLite at `/data/maintenance.db`, backed by the existing `maintenance-dashboard-data` PVC.

The bridge and simulator are separate workloads: the simulator is an on-demand Kubernetes Job; the bridge is a continuously running Deployment.

## Technology

- **AWS:** EC2 hosts the self-managed Kubernetes cluster. CloudWatch monitoring is a separately verifiable environment capability; this repository does not prove collectors or alarms are installed.
- **Kubernetes:** v1.34.12, containerd 2.2.1 and Flannel were the versions/components recorded during project deployment; check the live cluster before treating these as current.
- **Azure:** IoT Hub device-to-cloud ingestion, Event Hubs-compatible event consumption and Blob checkpoint storage.
- **Application:** Python Flask, SQLAlchemy, SQLite and Gunicorn.
- **Containers / delivery:** Docker images, Jenkins Pipeline and GitHub source control.
- **Infrastructure lifecycle:** Terraform scope is limited to EC2 start/stop lifecycle operations; it is not full AWS/Azure provisioning.

## Repository map

- `app/` — Flask application, blueprints, templates, static assets and simulator Job API.
- `simulator/azure_iot_simulator.py` — Azure IoT Hub device simulator used by the Kubernetes Job.
- `simulator/telemetry_simulator.py` — optional laptop/local simulator that posts directly to the dashboard API; not the dashboard-triggered Azure IoT Hub Job path.
- `simulator/Dockerfile.azure` — image build for the Azure IoT Hub simulator.
- `azure-iot-dashboard-bridge/bridge/` — Azure Event Hubs-compatible consumer and dashboard API forwarder.
- `azure-iot-dashboard-bridge/kubernetes-deployment.template.yaml` — **template only** for the bridge Deployment; its image and Secret names are placeholders and must be reviewed before use.
- `k8s/` — dashboard Deployment/Service, simulator Job RBAC and related supporting manifests.
- `Jenkinsfile` — the repository's root Jenkins pipeline.
- `tests/` — application and API tests.
- `monitoring/README.md` — proposed monitoring guidance only; it does not establish that collectors, dashboards or alarms are installed.

## Important: actual Jenkins pipeline scope

The current repository contains **one root-level `Jenkinsfile`**. It validates and tests the application, validates the bridge source, builds and pushes bridge, simulator and dashboard images, applies the simulator Job RBAC, configures the dashboard Deployment's ServiceAccount and simulator image, updates the dashboard image, and waits for its rollout.

The pipeline does **not** apply `azure-iot-dashboard-bridge/kubernetes-deployment.template.yaml`. That file is a template, not an applied/live manifest. Therefore, the existence of the bridge source and image-build stage alone does not prove that Jenkins deploys the bridge. The running bridge Deployment described in the project report must be confirmed from the live cluster / deployment evidence.

The pipeline uses the Docker Hub credential ID `dockerhub`. It builds the bridge image using the credential username as its namespace, while the dashboard and simulator image names are currently set to `nachiket1/...` in the Jenkinsfile. Ensure the credential can push to those repositories. Do not change image names or pipeline stages without checking the live Deployment and registry first.

GitHub webhook / SCM polling triggers are configured in Jenkins job settings, not established by the Jenkinsfile alone.

## Kubernetes resources and safety

The manifests expect the existing `capstone` namespace and live dashboard resources.

- Dashboard Deployment: `maintenance-dashboard`
- Dashboard Service: `maintenance-dashboard-service` (ClusterIP port 80 to container port 5000)
- Existing PVC: `maintenance-dashboard-data`, mounted at `/data`
- Dashboard Secret: `maintenance-dashboard-secrets`
- Simulator ServiceAccount: `dashboard-job-runner`
- Simulator RBAC: `dashboard-simulator-job-manager` Role and RoleBinding, scoped to Job create/get/list in `capstone`

**Do not blindly apply every YAML file.**
- `k8s/pvc.yaml` is documentation only; the PVC already exists.
- `k8s/secret.yaml` is documentation only; it is not a Secret manifest and contains instructions/placeholders.
- `k8s/maintenance-dashboard-serviceaccount-patch.yaml` is a strategic-merge patch, not a standalone Kubernetes resource.
- The bridge Deployment YAML is a template with placeholder image/Secret names.

Never commit real credentials, kubeconfigs, database files, private keys, connection strings or tokens. Keep production Secrets in Kubernetes and provide values through secure secret-management procedures.

## Run locally

Use Python 3.12 and a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python run_local.py
```

`run_local.py` starts the local development application and creates/seeds a local SQLite database as documented by the code. It is not the production server.

## Run tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The test suite uses a test configuration / in-memory SQLite database. A passing local test suite does not prove the external Azure IoT Hub, Blob Storage, Jenkins agent, Docker Hub credentials or live Kubernetes deployment is healthy.

## Simulator image

Build the Azure IoT Hub simulator image from the repository root:

```bash
docker build --pull -f simulator/Dockerfile.azure -t nachiket1/industrial-maintenance-simulator:<TAG> .
```

The simulator Job expects the existing Secret `simulator-device-credentials` in `capstone`, with keys:
- `IOTHUB_DEVICE_CONN_MTR_001`
- `IOTHUB_DEVICE_CONN_PMP_012`
- `IOTHUB_DEVICE_CONN_CMP_003`

Do not put the values in source control or command history.

## Dashboard-triggered simulator setup

The root Jenkins pipeline applies `k8s/dashboard-job-runner-rbac.yaml`, patches the dashboard Deployment to use `dashboard-job-runner`, sets `SIMULATOR_JOB_IMAGE` to the build-number-tagged simulator image, updates the dashboard image and waits for rollout.

For manual verification (read-only):

```bash
kubectl get deploy,pods,svc,pvc -n capstone
kubectl get jobs -n capstone
kubectl auth can-i create jobs --as=system:serviceaccount:capstone:dashboard-job-runner -n capstone
kubectl auth can-i get jobs --as=system:serviceaccount:capstone:dashboard-job-runner -n capstone
kubectl auth can-i list jobs --as=system:serviceaccount:capstone:dashboard-job-runner -n capstone
```

The RBAC checks should return `yes`. A successful Job means the simulator completed its process; it does not by itself guarantee every event was accepted by Azure IoT Hub, consumed by the bridge, and stored by the dashboard. Check simulator logs, bridge logs and dashboard telemetry to verify the complete path.

## Bridge deployment

The bridge source is in `azure-iot-dashboard-bridge/bridge/`. Its deployment YAML is a **template** and currently contains placeholder image and Secret names. Before applying it, reconcile those names with the actual live namespace resources and the image tag produced by Jenkins. The bridge needs:
- Event Hubs-compatible IoT Hub consumer connection string with appropriate ServiceConnect permissions.
- Azure Storage connection string and Blob container `iot-bridge-checkpoints`.
- Dashboard ingestion token matching the dashboard's `INGESTION_TOKEN`.
- Dashboard API URL `http://maintenance-dashboard-service:80/api/v1/telemetry`.

The bridge checkpoints an event after dashboard API acceptance. If the process stops after acceptance but before checkpoint persistence, the event can be replayed; the idempotency key is intended to prevent duplicate readings. Invalid messages are logged without printing full payloads and checkpointed to avoid poison-message loops.

## Health endpoints

- `/health` — application liveness
- `/ready` — application readiness / database connectivity
- `/api/v1/health` — telemetry API health

## Deployment verification boundary

This repository describes and configures application components. It cannot, by itself, prove the current live state of AWS EC2, load balancer listeners/target groups, DNS records, Certbot certificate installation/renewal, Azure IoT Hub, Blob Storage, CloudWatch agent installation, Jenkins job triggers or the live Kubernetes bridge Deployment. Verify those items from their respective consoles and live command outputs before submission. Do not treat a template, screenshot placeholder or recommendation as evidence of a currently running resource.
