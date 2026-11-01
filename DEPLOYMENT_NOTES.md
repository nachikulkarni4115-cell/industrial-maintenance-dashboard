# Deployment and Repository Verification Notes

This document distinguishes repository-defined behavior from live-environment facts. It is not a replacement for checking the deployed cluster and cloud consoles.

## Repository facts verified from source

- Flask dashboard code and the protected `POST /api/v1/telemetry` endpoint are in `app/`.
- The dashboard-triggered simulator Job is created by `app/simulator/routes.py`; the route requires an authenticated dashboard session and uses in-cluster Kubernetes configuration.
- Job configuration includes a finite deadline, no automatic Job retry, TTL cleanup, resource requests/limits and a non-root container security context.
- Job RBAC is defined in `k8s/dashboard-job-runner-rbac.yaml`; it grants Job create/get/list only in namespace `capstone`.
- The Azure IoT Hub device simulator is `simulator/azure_iot_simulator.py`; its image build is `simulator/Dockerfile.azure`.
- The optional laptop simulator `simulator/telemetry_simulator.py` sends directly to the dashboard API. It is a separate development/diagnostic path, not the dashboard-triggered IoT Hub Job path.
- The bridge consumer is `azure-iot-dashboard-bridge/bridge/consumer.py`; it reads Event Hubs-compatible events, validates/normalizes payloads, forwards to the dashboard API and uses Azure Blob checkpointing.
- The bridge Kubernetes YAML is a template with placeholder image/Secret names. It must not be described as a directly applicable, production-ready manifest without reconciliation.
- The root `Jenkinsfile` builds and pushes bridge, simulator and dashboard images, applies simulator Job RBAC, configures the dashboard ServiceAccount and simulator image, updates the dashboard image and waits for dashboard rollout.
- The root pipeline does not apply the bridge Deployment template. Image build/push is not the same as bridge deployment.
- The dashboard Deployment manifest defines one replica and uses an existing PVC-backed SQLite database. The PVC and Secret YAML files in `k8s/` are documentation-only safeguards, not manifests to apply.
- `monitoring/README.md` is primarily a guide/recommendation for monitoring setup; its presence does not prove that Container Insights, CloudWatch Agent, Fluent Bit, dashboards or alarms are installed.

## Items that need live evidence (not provable from repository source alone)

Before final submission, verify and capture evidence for:

1. `kubectl get nodes -o wide`, `kubectl get deploy,pods,svc,pvc -n capstone`, and `kubectl get jobs -n capstone`.
2. The running `azure-iot-dashboard-bridge` Deployment and its current image tag, ready replica count and recent logs.
3. The actual Kubernetes Secrets by **names and key names only**. Never display values.
4. Azure IoT Hub message ingestion and Azure Blob checkpoint container activity.
5. End-to-end telemetry after clicking Generate Telemetry: Job creation/completion, bridge acceptance logs, and readings visible in the dashboard.
6. Jenkins job configuration, Script Path (root `Jenkinsfile`), last successful build, console stages and webhook/SCM trigger settings.
7. Docker Hub repositories and image tags used by the live Deployments.
8. AWS EC2 state, load balancer listener/target group health, DNS records, Elastic IP association and HTTPS certificate location/expiry.
9. CloudWatch metrics/log groups proving what monitoring is actually enabled.
10. Terraform configuration and a safe record of the EC2 start/stop workflow.

## Safe verification commands

Run from the machine with the correct kubeconfig and cloud CLIs configured:

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl get deploy,pods,svc,pvc -n capstone -o wide
kubectl get jobs -n capstone
kubectl describe deployment maintenance-dashboard -n capstone
kubectl describe deployment azure-iot-dashboard-bridge -n capstone
kubectl logs deployment/azure-iot-dashboard-bridge -n capstone --tail=100
kubectl auth can-i create jobs --as=system:serviceaccount:capstone:dashboard-job-runner -n capstone
aws sts get-caller-identity
aws configure get region
az account show --output table
```

The last three commands identify the active CLI identities/context; redact account IDs, subscription IDs and sensitive values before sharing screenshots.

The repository's Terraform scope is EC2 start/stop lifecycle management only; do not describe it as provisioning the complete cloud architecture.

## Do not do during audit

- Do not restart or redeploy the live application merely to test documentation.
- Do not apply `k8s/pvc.yaml`, `k8s/secret.yaml` or the bridge template without review.
- Do not print Secrets, environment variables, connection strings, kubeconfig contents or private keys.
- Do not claim that a Jenkins image-build stage deployed the bridge; confirm the actual bridge Deployment separately.
- Do not claim that source code proves ALB, DNS, TLS, CloudWatch or Azure resources are currently healthy.
