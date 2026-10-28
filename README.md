# Azure IoT Hub → Industrial Maintenance Dashboard Bridge

Separate Kubernetes Deployment that consumes device-to-cloud telemetry from Azure IoT Hub (Event Hubs-compatible endpoint) and forwards it to the existing dashboard API.

**It does not modify the dashboard Deployment, Service, ALB, portfolio, or AgriSakha.**

## Contents

| Path | Purpose |
|------|---------|
| `bridge/consumer.py` | Event Hub consumer + Blob checkpoint store + HTTP forwarder |
| `bridge/Dockerfile` | Non-root Python 3.12 image |
| `bridge/requirements.txt` | azure-eventhub, checkpointstoreblob, requests |
| `kubernetes-deployment.template.yaml` | Ready-to-apply Deployment (replace image tag) |
| `Jenkinsfile` | Validates → builds → pushes versioned image (auto-deploy stage is commented out) |

## Behaviour summary

- Reads from IoT Hub Event Hubs-compatible endpoint using the `dashboard-telemetry-reader` policy.
- Persists checkpoints in Azure Blob container `iot-bridge-checkpoints`.
- Forwards only supported fields and forces `data_source=azure_iot_hub_bridge`.
- Checkpoints **after** the dashboard API accepts the message (or after intentionally discarding invalid events).
- On delivery failure the process exits so Kubernetes restarts it; the next start resumes from the last successful checkpoint.
- Uses the existing `maintenance-telemetry-secret` for the ingestion token.

## Required Kubernetes Secrets (namespace `capstone`)

| Secret name | Keys |
|-------------|------|
| `azure-iot-reader-secret` | `AZURE_IOTHUB_EVENTHUB_CONNECTION_STRING`, `AZURE_STORAGE_CONNECTION_STRING` |
| `maintenance-telemetry-secret` | `INGESTION_TOKEN` (already exists – do not change) |

## Safe first-time procedure

1. **Create the Azure reader secret** (on EC2, never print the values):

   ```bash
   # On EC2 – interactive, values never appear in history if you use read -s
   sudo -u jenkins kubectl \
     --kubeconfig=/var/lib/jenkins/kubeconfig \
     -n capstone create secret generic azure-iot-reader-secret \
     --from-literal=AZURE_IOTHUB_EVENTHUB_CONNECTION_STRING='...' \
     --from-literal=AZURE_STORAGE_CONNECTION_STRING='...'
   ```

2. **Run the bridge Jenkins job** (script path = `azure-iot-dashboard-bridge/Jenkinsfile`).  
   It will push `nachiket1/azure-iot-dashboard-bridge:<BUILD_NUMBER>`.

3. **Edit the template** – replace `REPLACE_WITH_TAG` with the actual build number.

4. **Apply only the bridge**:

   ```bash
   sudo -u jenkins kubectl \
     --kubeconfig=/var/lib/jenkins/kubeconfig \
     -n capstone apply -f azure-iot-dashboard-bridge/kubernetes-deployment.template.yaml
   ```

5. **Verify**:

   ```bash
   sudo -u jenkins kubectl \
     --kubeconfig=/var/lib/jenkins/kubeconfig \
     -n capstone get pods -l app=azure-iot-dashboard-bridge
   ```

6. Send a simulator batch and confirm new rows appear with `data_source=azure_iot_hub_bridge`.

## Enabling automatic deployment on every push

After the first manual deploy works:

1. Open `azure-iot-dashboard-bridge/Jenkinsfile`.
2. Uncomment the entire `Deploy bridge to Kubernetes` stage.
3. Commit & push. From then on every successful build will update the bridge Deployment only.

## Independent lifecycle

```bash
# Stop bridge only
sudo -u jenkins kubectl --kubeconfig=/var/lib/jenkins/kubeconfig \
  -n capstone scale deployment/azure-iot-dashboard-bridge --replicas=0

# Restart bridge only
sudo -u jenkins kubectl --kubeconfig=/var/lib/jenkins/kubeconfig \
  -n capstone scale deployment/azure-iot-dashboard-bridge --replicas=1

# Delete bridge only (does not affect dashboard)
sudo -u jenkins kubectl --kubeconfig=/var/lib/jenkins/kubeconfig \
  -n capstone delete deployment azure-iot-dashboard-bridge
```

## Security notes

- Never commit connection strings or keys.
- Never paste them into chat or screenshots.
- The bridge runs as non-root (UID 10001) with a read-only root filesystem.
