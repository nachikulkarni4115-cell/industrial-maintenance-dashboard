# Monitoring and logging — AWS (proposed guidance, not deployment evidence)

This guide is a set of recommendations, not a record that monitoring has been installed. It does not change the dashboard Deployment, Service, PVC, Secret, telemetry API, or Jenkinsfile.

## Recommended first step

Use Amazon CloudWatch for the existing Kubernetes workload:
- **Container Insights** for cluster, node, pod, CPU, memory, network, and restart visibility.
- **CloudWatch Logs** for stdout/stderr from the dashboard container and platform components.
- **CloudWatch dashboards and alarms** for a small set of actionable signals.

AWS supports Container Insights for both Amazon EKS and Kubernetes running on Amazon EC2. The installation path and permissions differ, so identify the live cluster before applying anything.

Official documentation:
- Container Insights: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html
- EKS CloudWatch Observability add-on: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Observability-EKS-addon.html
- CloudWatch pricing: https://aws.amazon.com/cloudwatch/pricing/

## 1. Verify the actual cluster before installation

Run these commands from a machine that already has the intended cluster's kubeconfig and AWS CLI configured. Do not paste kubeconfig contents, tokens, or secrets into chat or commit them.

```bash
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
kubectl get namespace capstone
kubectl get deployment maintenance-dashboard -n capstone
aws sts get-caller-identity
aws configure get region
```

For EKS, also run:

```bash
aws eks list-clusters --region <your-region>
```

If the current context is EKS, record the exact cluster name and region and check that the AWS identity has permission to manage EKS add-ons and the required IAM permissions. If the context is self-managed Kubernetes on EC2, use the CloudWatch Agent/Fluent Bit Helm-chart path instead; do not run EKS add-on commands.

## 2. EKS installation path (only after confirming EKS)

The AWS-managed CloudWatch Observability EKS add-on is the preferred learning path because it can install the CloudWatch Agent and Fluent Bit for metrics and container logs. First inspect current add-on state:

```bash
aws eks describe-cluster --name <cluster-name> --region <region> --query 'cluster.{status:status,version:version,platformVersion:platformVersion,roleArn:roleArn}'
aws eks list-addons --cluster-name <cluster-name> --region <region>
```

Review the cluster's IAM/Pod Identity or IRSA setup and the add-on prerequisites before installing. Do not blindly copy a role ARN or cluster name from an example. Follow the official add-on documentation above, and check the resulting DaemonSets and logs after installation.

## 3. Kubernetes on EC2 (not EKS)

For Kubernetes clusters not hosted on EKS, use the AWS-documented CloudWatch Agent and Fluent Bit installation path appropriate to the cluster. Validate the current chart/version and permissions before installation; do not assume the EKS add-on applies. Confirm the nodes can reach AWS endpoints and configure least-privilege AWS credentials for the collector. Do not use EKS add-on commands against a self-managed cluster.

Official general guidance: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html

## 4. Start with a small alert set

Create alarms only after the relevant metrics are visible in CloudWatch. Suggested initial alarms:

1. **Dashboard pod unavailable / repeated restarts** — investigate deployment events and container logs.
2. **CPU or memory near configured limits** — the existing container requests 50m CPU / 96Mi memory and limits 300m CPU / 256Mi memory; alert thresholds should be tuned from observed baseline, not guessed.
3. **Node not ready** — cluster-level operational alert.
4. **Application readiness failures** — monitor failed readiness checks or add a CloudWatch metric filter for an explicit, non-sensitive log signal if needed.
5. **Telemetry ingestion errors** — monitor error counts without logging bearer tokens, credentials, or raw secrets.

Keep alerting low-noise: start with a small number of alarms and a notification target you control.

## 5. Cost controls for a learning environment

CloudWatch is usage-based. Costs can come from log ingestion/storage, custom metrics, dashboards, alarms, and enhanced Container Insights features. The free tier is not a guarantee that every monitoring configuration will be free.

- Begin with standard Container Insights and a short log-retention period (for example, 7 days) where retention can be configured.
- Avoid enhanced observability and high-cardinality custom metrics until you understand the expected bill.
- Keep verbose/debug logs disabled in production.
- Check CloudWatch usage and the AWS Pricing page after the first day and week; set an AWS Budget alert separately.
- Do not assume a Budget alert prevents charges; it notifies you after configured thresholds are reached.

Pricing reference: https://aws.amazon.com/cloudwatch/pricing/

## 6. Preserve the application as it is

The current dashboard uses the existing `capstone/maintenance-dashboard-data` PVC for SQLite, the `maintenance-dashboard-secrets` Secret, and the `/health` and `/ready` probes. Monitoring setup should be additive:
- Do not recreate or delete the PVC.
- Do not print environment variables or secrets in logs.
- Keep the existing telemetry API and authentication unchanged.
- Keep the single root `Jenkinsfile`; monitoring agents are cluster infrastructure and should not be installed from the dashboard build pipeline.

## Validation checklist

- [ ] Confirmed current kube context and cloud provider.
- [ ] Confirmed cluster name, region, Kubernetes version, and node OS.
- [ ] Confirmed AWS IAM/Pod Identity/IRSA permissions and network egress.
- [ ] Installed the correct collector path for EKS or self-managed Kubernetes.
- [ ] Verified pod/node metrics and dashboard logs appear in CloudWatch.
- [ ] Created only the initial low-noise alarms.
- [ ] Checked actual usage/cost before enabling more telemetry.
- [ ] Verified the dashboard Deployment, PVC, Secret, and telemetry API remain healthy.
