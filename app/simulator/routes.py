"""Authenticated controls for running the Azure IoT telemetry simulator as a Job."""
import os
import re
import uuid

from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

simulator_bp = Blueprint("simulator", __name__)

JOB_LABEL = "app.kubernetes.io/name"
JOB_LABEL_VALUE = "maintenance-telemetry-simulator"
USER_LABEL = "maintenance-dashboard/user-id"
JOB_NAME_RE = re.compile(r"^telemetry-sim-[a-f0-9]{8}$")


def _batch_api():
    """Build an in-cluster Kubernetes client; never fall back to local kubeconfig."""
    config.load_incluster_config()
    return client.BatchV1Api()


def _job_status(job):
    status = job.status
    if status.succeeded:
        state = "succeeded"
    elif status.failed:
        state = "failed"
    elif status.active:
        state = "running"
    else:
        state = "starting"

    return {
        "job_name": job.metadata.name,
        "state": state,
        "active": status.active or 0,
        "succeeded": status.succeeded or 0,
        "failed": status.failed or 0,
        "message": (
            "Simulator Job finished. Telemetry may take a short time to pass through "
            "Azure IoT Hub and the existing bridge."
            if state == "succeeded"
            else "Simulator Job failed. Check the Job's pod logs in namespace capstone."
            if state == "failed"
            else "Simulator is running and sending telemetry to Azure IoT Hub."
        ),
    }


@simulator_bp.route("/dashboard/simulator/run", methods=["POST"])
@login_required
def run_simulator():
    """Start one finite simulator Job. Only authenticated dashboard users can call it."""
    namespace = current_app.config.get("SIMULATOR_JOB_NAMESPACE", "capstone")
    secret_name = current_app.config.get(
        "SIMULATOR_DEVICE_SECRET", "simulator-device-credentials"
    )
    image = current_app.config.get("SIMULATOR_JOB_IMAGE", "").strip()
    if not image:
        current_app.logger.error("SIMULATOR_JOB_IMAGE is not configured")
        return jsonify({"error": "Simulator image is not configured on the server."}), 503

    try:
        api = _batch_api()
        existing = api.list_namespaced_job(
            namespace=namespace,
            label_selector=f"{JOB_LABEL}={JOB_LABEL_VALUE}",
        )
        active = [
            item for item in existing.items
            if (item.status.active or 0) > 0
        ]
        if active:
            return jsonify({
                "error": "A telemetry simulation is already running.",
                "job": _job_status(active[0]),
            }), 409

        job_name = f"telemetry-sim-{uuid.uuid4().hex[:8]}"
        labels = {
            JOB_LABEL: JOB_LABEL_VALUE,
            USER_LABEL: str(current_user.get_id()),
        }
        container = client.V1Container(
            name="simulator",
            image=image,
            image_pull_policy="Always",
            env=[
                client.V1EnvVar(name="MAX_BATCHES", value="30"),
                client.V1EnvVar(name="SAMPLE_INTERVAL", value="2"),
                client.V1EnvVar(name="MAX_RETRIES", value="3"),
                client.V1EnvVar(name="FAULT_MODE", value="0"),
            ],
            env_from=[
                client.V1EnvFromSource(
                    secret_ref=client.V1SecretEnvSource(name=secret_name)
                )
            ],
            resources=client.V1ResourceRequirements(
                requests={"cpu": "50m", "memory": "96Mi"},
                limits={"cpu": "200m", "memory": "256Mi"},
            ),
            security_context=client.V1SecurityContext(
                allow_privilege_escalation=False,
                run_as_non_root=True,
                run_as_user=10001,
                capabilities=client.V1Capabilities(drop=["ALL"]),
            ),
        )
        pod_spec = client.V1PodSpec(
            restart_policy="Never",
            automount_service_account_token=False,
            security_context=client.V1PodSecurityContext(
                run_as_non_root=True,
                run_as_user=10001,
                run_as_group=10001,
            ),
            containers=[container],
        )
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name=job_name, labels=labels),
            spec=client.V1JobSpec(
                backoff_limit=0,
                active_deadline_seconds=300,
                ttl_seconds_after_finished=600,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
                    spec=pod_spec,
                ),
            ),
        )
        created = api.create_namespaced_job(namespace=namespace, body=job)
        return jsonify({
            "message": "Telemetry simulation started.",
            "job": {
                "job_name": created.metadata.name,
                "state": "starting",
                "message": "Connecting to Azure IoT Hub and preparing the first batch.",
            },
        }), 202

    except ApiException as exc:
        current_app.logger.exception("Kubernetes API rejected simulator Job request")
        if exc.status == 403:
            return jsonify({
                "error": "The dashboard service account is not permitted to create simulator Jobs."
            }), 503
        return jsonify({"error": "Unable to start the telemetry simulator."}), 502
    except ConfigException:
        current_app.logger.exception("Dashboard is not running with in-cluster Kubernetes configuration")
        return jsonify({"error": "Kubernetes in-cluster configuration is unavailable."}), 503
    except Exception:
        current_app.logger.exception("Unable to start telemetry simulator")
        return jsonify({"error": "Unable to start the telemetry simulator."}), 500


@simulator_bp.route("/dashboard/simulator/jobs/<job_name>", methods=["GET"])
@login_required
def simulator_job_status(job_name):
    """Return status only for a Job started by the requesting user."""
    if not JOB_NAME_RE.fullmatch(job_name):
        return jsonify({"error": "Job not found."}), 404

    namespace = current_app.config.get("SIMULATOR_JOB_NAMESPACE", "capstone")
    try:
        job = _batch_api().read_namespaced_job(name=job_name, namespace=namespace)
        labels = job.metadata.labels or {}
        if (
            labels.get(JOB_LABEL) != JOB_LABEL_VALUE
            or labels.get(USER_LABEL) != str(current_user.get_id())
        ):
            return jsonify({"error": "Job not found."}), 404
        return jsonify({"job": _job_status(job)}), 200
    except ApiException as exc:
        if exc.status == 404:
            return jsonify({"error": "Job not found."}), 404
        current_app.logger.exception("Unable to read simulator Job status")
        return jsonify({"error": "Unable to read simulator status."}), 502
    except ConfigException:
        return jsonify({"error": "Kubernetes in-cluster configuration is unavailable."}), 503
    except Exception:
        current_app.logger.exception("Unable to read simulator Job status")
        return jsonify({"error": "Unable to read simulator status."}), 500
