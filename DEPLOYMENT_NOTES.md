# Deployment Notes — Industrial Maintenance Dashboard

## What changed

- Fixed the live dashboard polling bug: the browser now fetches the declared `telemetryUrl` instead of an undefined variable.
- Dashboard telemetry rows, last-reading/staleness status, and four KPI counts refresh every 5 seconds without reloading the page.
- Added no-cache headers to the live telemetry endpoint and a regression test for its response contract.
- Added `requirements-prod.txt`; the dashboard image no longer installs pytest tooling.
- Made `run_local.py` portable instead of tying its database path to one Windows user directory.
- Set secure session cookies for the production Kubernetes deployment.
- Added `Jenkinsfile.dashboard` for dashboard test/build/push/rollout while preserving the existing root bridge `Jenkinsfile`.
- Made `k8s/secret.yaml` documentation-only so placeholder values cannot accidentally overwrite the existing production Secret.
- Updated the project README with the live simulator URL and deployment prerequisites.

## Jenkins configuration

Create or update a **separate dashboard Jenkins job**:

- Script Path: `Jenkinsfile.dashboard`
- Jenkins credential: `dockerhub` (Username with password/token)
- Credential username must match `DOCKERHUB_NAMESPACE` in `Jenkinsfile.dashboard` (currently `nachiket1`)
- Agent prerequisites: Python 3, Docker CLI/daemon, `kubectl`, and access to `/var/lib/jenkins/kubeconfig`
- The `jenkins` OS user must be allowed to update and watch the `maintenance-dashboard` Deployment in namespace `capstone`
- Configure GitHub webhook or SCM polling in Jenkins for the branch you want deployed

The pipeline runs tests before building/pushing the image, then updates only the existing dashboard Deployment to the numbered image tag and waits for rollout. It does not recreate the Service, PVC, Secrets, ALB, or bridge.

## Existing cluster resources

The manifests expect the current `capstone` namespace, Deployment, Service, PVC, and Secret to exist. Do not apply `k8s/pvc.yaml` or `k8s/secret.yaml` to the live cluster. They are documentation only.

## Telemetry simulator

For data to reach the deployed website, configure the laptop simulator to post to:

`https://maintenance.nachiketkulkarni.in/api/v1/telemetry`

`INGESTION_TOKEN` must match the value already stored in the Kubernetes Secret. Keep it private.

## Validation performed on this source bundle

- Python source compilation: passed
- Dashboard JavaScript syntax check: passed
- Kubernetes YAML manifest parsing: passed
- Full pytest suite: not run successfully in this packaging environment because Flask dependencies were not installed and package-network access was unavailable. The dashboard Jenkins pipeline installs requirements and runs `pytest -q` before publishing an image.

A successful local/package syntax check does not confirm the external Jenkins agent, Docker Hub credentials, Kubernetes access, production Secret, PVC, or live website. The first pipeline run is the end-to-end deployment confirmation.
