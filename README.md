# Industrial Equipment Maintenance Dashboard

Capstone project: Flask + SQLite dashboard for industrial equipment monitoring, alerts, work orders, and authenticated telemetry ingestion.

**The website remains available when the Windows laptop is off and the simulator is stopped.**  
Continuous simulation runs **only** on the operator laptop — never on EC2, Docker, Kubernetes, or Jenkins.

## Architecture

| Component | Location |
|-----------|----------|
| Flask dashboard + API | Kubernetes (`capstone` namespace) on existing EC2 |
| SQLite database | PVC `maintenance-dashboard-data` mounted at `/data/maintenance.db` |
| Telemetry simulator | Windows laptop only |
| Analytics / ML training | Windows laptop only (optional later stage) |

## Local quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_local.py
```

- Dashboard: http://127.0.0.1:5000  
- Login: `admin` / `ChangeMeImmediately!`  
- Public demo: http://127.0.0.1:5000/demo  

## Database commands (explicit, never auto-seed on every start)

```powershell
$env:FLASK_APP="wsgi:app"
flask init-db          # create tables only
flask seed-demo        # idempotent synthetic data (skips if facilities exist)
flask create-admin     # create/reset bootstrap admin
```

## Tests

```powershell
$env:FLASK_CONFIG="testing"
$env:PYTHONPATH="."
pytest tests/ -v --tb=short
```

## Laptop simulator

```powershell
$env:DASHBOARD_API_URL="http://127.0.0.1:5000/api/v1/telemetry"   # or deployed URL later
$env:INGESTION_TOKEN="demo-ingestion-token-change-me"
$env:SINGLE_RUN="1"
python simulator\telemetry_simulator.py
```

Stop the simulator at any time — the website and saved data remain available.

## Kubernetes (capstone namespace only)

1. Create Secret (never commit real values):
```bash
kubectl -n capstone create secret generic maintenance-dashboard-secrets \
  --from-literal=SECRET_KEY='LONG-RANDOM' \
  --from-literal=INGESTION_TOKEN='STRONG-TOKEN' \
  --from-literal=BOOTSTRAP_ADMIN_USERNAME='admin' \
  --from-literal=BOOTSTRAP_ADMIN_PASSWORD='STRONG-PASSWORD' \
  --from-literal=BOOTSTRAP_ADMIN_EMAIL='admin@example.com'
```

2. Ensure PVC `maintenance-dashboard-data` exists and is bound.

3. Apply Deployment + Service, then the init Job once:
```bash
kubectl -n capstone apply -f k8s/deployment.yaml
kubectl -n capstone apply -f k8s/service.yaml
kubectl -n capstone apply -f k8s/init-job.yaml
kubectl -n capstone logs job/maintenance-dashboard-init
```

4. Smoke test:
```bash
kubectl -n capstone port-forward svc/maintenance-dashboard-service 15000:80
# browser: http://127.0.0.1:15000
```

## Empty state & offline behaviour

- No equipment → “No equipment registered yet.”
- No telemetry → “No telemetry received yet.”
- Simulator stopped → last reading timestamp shown; stale badge after `STALE_TELEMETRY_HOURS`.
- Public `/demo` (when `PUBLIC_DEMO_ENABLED=true`) shows only synthetic data.

## Security notes (capstone level)

Implemented: password hashing, CSRF (forms + logout POST), safe redirect validation, server-side facility isolation, token-protected ingestion, finite-number validation, idempotent keys, production rejection of unsafe default secrets.

Still required before real production: HTTPS, rate limiting, formal review, secret rotation, network policies.

## Portfolio protection

This project uses only the `capstone` namespace, image `nachiket1/industrial-maintenance-dashboard`, and Jenkins job `Industrial-Maintenance-CI-CD`.  
The existing portfolio (`my-cicd-app`, `Serverless-Hub-CI-CD`, default namespace, ALB) is never modified.

## Persistent storage (existing PVC)

The PVC `maintenance-dashboard-data` in namespace `capstone` is **already bound (2 GiB)**.
**Do not apply `k8s/pvc.yaml`** — that file is documentation only.

Permission strategy for the host directory (GID 10001, mode 0770):
- Pod `runAsUser: 999`
- Pod `runAsGroup: 10001` and `fsGroup: 10001`
- SQLite path: `/data/maintenance.db` (same path for Deployment and init Job)

Backup note: this local volume does **not** protect against EC2 disk loss. Copy `/data/maintenance.db` periodically for recovery.

## Health vs readiness

- `/health` — liveness (process up). Always HTTP 200. Does not restart the pod on DB blips.
- `/ready` — readiness (DB reachable). Returns 503 when the database is unavailable.
