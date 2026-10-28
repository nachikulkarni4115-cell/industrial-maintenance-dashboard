# Industrial Equipment Maintenance Dashboard

Flask-based maintenance dashboard with authenticated equipment, telemetry, alerts, work orders, and a telemetry-ingestion API. The Azure IoT Hub bridge is maintained separately under `azure-iot-dashboard-bridge/`.

## Architecture

- **Web application:** Flask + SQLAlchemy + Gunicorn
- **Telemetry API:** `POST /api/v1/telemetry` with a bearer ingestion token
- **Live dashboard:** `/dashboard/live-telemetry` is polled every 5 seconds while the dashboard is visible
- **Runtime:** Docker image deployed to Kubernetes namespace `capstone`
- **Persistence:** existing PVC `maintenance-dashboard-data`, mounted at `/data`
- **Dashboard CI/CD:** `Jenkinsfile.dashboard` tests, builds/pushes a versioned image, and updates only the `maintenance-dashboard` Deployment
- **Azure bridge:** separate image and pipeline in `azure-iot-dashboard-bridge/`

## Important production resources

The current Kubernetes manifests are written for the existing cluster. The PVC and Secrets are assumed to exist already. **Do not apply `k8s/pvc.yaml`**; it is documentation only and describes the already-bound claim.

Expected existing resources:

- Namespace: `capstone`
- Deployment: `maintenance-dashboard`
- Service: `maintenance-dashboard-service`
- PVC: `maintenance-dashboard-data`
- Secret: `maintenance-dashboard-secrets` with `SECRET_KEY`, `INGESTION_TOKEN`, `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, and `BOOTSTRAP_ADMIN_EMAIL`

Do not commit real secrets, `.env` files, a database file, or Git history containing credentials.

## Run locally

Use Python 3.12 or compatible Python 3.x and a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python run_local.py
```

`run_local.py` creates the local `instance/maintenance.db` if needed and seeds demo data idempotently. It binds to `127.0.0.1`; it is not the production server.

## Telemetry simulator

The simulator must send to the deployed website—not `127.0.0.1`—when you want production dashboard data:

```powershell
$env:DASHBOARD_API_URL = "https://maintenance.nachiketkulkarni.in/api/v1/telemetry"
$env:INGESTION_TOKEN = "<the same token stored in Kubernetes Secret maintenance-dashboard-secrets>"
$env:SAMPLE_INTERVAL = "5"
python .\\simulator\\telemetry_simulator.py
```

Keep the token private. Never commit it or paste it into screenshots/chat. The simulator sends clearly labelled synthetic readings.

For one batch only:

```powershell
$env:SINGLE_RUN = "1"
python .\\simulator\\telemetry_simulator.py
```

## Tests

```bash
python -m pip install -r requirements.txt
pytest -q
```

The test suite uses an in-memory SQLite database. It does not access or overwrite the production PVC.

## Jenkins CI/CD setup

The dashboard pipeline (`Jenkinsfile.dashboard`) expects:

1. Jenkins credential ID `dockerhub` as **Username with password** (Docker Hub username + access token/password).
2. Docker CLI available to the Jenkins agent.
3. `kubectl` available to the Jenkins agent.
4. A kubeconfig at `/var/lib/jenkins/kubeconfig`, usable by the `jenkins` OS account.
5. Permission for that identity to update and watch the `maintenance-dashboard` Deployment in `capstone`.

On each build, Jenkins validates Python, runs the tests, builds the dashboard image, pushes `nachiket1/industrial-maintenance-dashboard:<BUILD_NUMBER>` and `:latest`, then updates the existing Deployment to the numbered tag and waits for rollout. If your Docker Hub namespace differs, update `DOCKERHUB_NAMESPACE` in `Jenkinsfile.dashboard` and ensure the registry credentials match.

Configure the dashboard Jenkins job's Script Path as `Jenkinsfile.dashboard`. The existing root `Jenkinsfile` and `azure-iot-dashboard-bridge/Jenkinsfile` remain dedicated to the bridge workflow. The GitHub webhook / SCM polling trigger is configured in Jenkins itself, not by this repository alone. Set the dashboard job to build on your desired branch (normally `main`).

### Manual rollout / recovery

After a successful image build, the equivalent deployment update is:

```bash
sudo -u jenkins kubectl --kubeconfig=/var/lib/jenkins/kubeconfig \\
  -n capstone set image deployment/maintenance-dashboard \\
  maintenance-dashboard=nachiket1/industrial-maintenance-dashboard:<BUILD_NUMBER>

sudo -u jenkins kubectl --kubeconfig=/var/lib/jenkins/kubeconfig \\
  -n capstone rollout status deployment/maintenance-dashboard --timeout=180s
```

Do not delete the Deployment, Service, PVC, or Secrets to fix a failed rollout. Inspect `kubectl describe deployment`, `kubectl get pods`, and pod logs first.

## Health endpoints

- `/health`: liveness endpoint
- `/ready`: readiness endpoint; checks database connectivity
- `/api/v1/health`: telemetry API health endpoint

## Security and deployment notes

- Production startup rejects missing or placeholder `SECRET_KEY`, `INGESTION_TOKEN`, and `BOOTSTRAP_ADMIN_PASSWORD`.
- Kubernetes secrets are injected as environment variables; keep actual values out of YAML committed to Git.
- Dashboard pods run non-root and use the existing persistent volume. SQLite is configured for a single application replica; do not scale the dashboard Deployment horizontally without moving to a shared database.
- Synthetic telemetry is not physical sensor data.
