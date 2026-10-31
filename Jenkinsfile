pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        IMAGE_NAME = 'nachiket1/industrial-maintenance-dashboard'
        SIMULATOR_IMAGE_NAME = 'nachiket1/industrial-maintenance-simulator'
        K8S_NAMESPACE = 'capstone'
        K8S_DEPLOYMENT = 'maintenance-dashboard'
        K8S_CONTAINER = 'maintenance-dashboard'
        KUBECONFIG_PATH = '/var/lib/jenkins/kubeconfig'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Validate dashboard and simulator') {
            steps {
                sh '''
                    set -eu
                    test -f app/__init__.py
                    test -f app/templates/base.html
                    test -f app/templates/dashboard.html
                    test -f app/static/css/dashboard.css
                    test -f app/static/js/dashboard-live.js
                    test -f simulator/azure_iot_simulator.py
                    test -f simulator/requirements-azure.txt
                    test -f simulator/Dockerfile.azure
                    python3 -m compileall -q app wsgi.py
                    python3 -m py_compile simulator/azure_iot_simulator.py
                    grep -F 'name="MAX_BATCHES", value="30"' app/simulator/routes.py
                    grep -F 'name="SAMPLE_INTERVAL", value="2"' app/simulator/routes.py
                '''
            }
        }

        stage('Install and test') {
            steps {
                sh '''
                    set -eu
                    python3 -m venv .venv-ci
                    . .venv-ci/bin/activate
                    python -m pip install --upgrade pip
                    python -m pip install -r requirements.txt
                    export PYTHONPATH="$WORKSPACE${PYTHONPATH:+:$PYTHONPATH}"
                    python -c "from app import create_app; print('Application import successful')"
                    python -m pytest -q
                '''
            }
        }

        stage('Validate IoT bridge') {
            steps {
                sh '''
                    set -eu
                    test -f azure-iot-dashboard-bridge/bridge/consumer.py
                    test -f azure-iot-dashboard-bridge/bridge/requirements.txt
                    python3 -m py_compile azure-iot-dashboard-bridge/bridge/consumer.py
                '''
            }
        }

        stage('Build and push IoT bridge image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_TOKEN'
                )]) {
                    sh '''
                        set -eu
                        set +x
                        BRIDGE_IMAGE="${DOCKER_USER}/azure-iot-dashboard-bridge"
                        BRIDGE_TAG="${BUILD_NUMBER}"
                        docker build --pull --file azure-iot-dashboard-bridge/bridge/Dockerfile --tag "${BRIDGE_IMAGE}:${BRIDGE_TAG}" azure-iot-dashboard-bridge/bridge
                        printf '%s' "$DOCKER_TOKEN" | docker login --username "$DOCKER_USER" --password-stdin
                        trap 'docker logout >/dev/null 2>&1 || true' EXIT
                        docker push "${BRIDGE_IMAGE}:${BRIDGE_TAG}"
                        echo "Published bridge image ${BRIDGE_IMAGE}:${BRIDGE_TAG}"
                    '''
                }
            }
        }

        stage('Build and push simulator image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_TOKEN'
                )]) {
                    sh '''
                        set -eu
                        set +x
                        SIMULATOR_TAG="${BUILD_NUMBER}"
                        docker build --pull --file simulator/Dockerfile.azure --tag "${SIMULATOR_IMAGE_NAME}:${SIMULATOR_TAG}" .
                        printf '%s' "$DOCKER_TOKEN" | docker login --username "$DOCKER_USER" --password-stdin
                        trap 'docker logout >/dev/null 2>&1 || true' EXIT
                        docker push "${SIMULATOR_IMAGE_NAME}:${SIMULATOR_TAG}"
                        echo "Published ${SIMULATOR_IMAGE_NAME}:${SIMULATOR_TAG}"
                    '''
                }
            }
        }

        stage('Build and push dashboard image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_TOKEN'
                )]) {
                    sh '''
                        set -eu
                        set +x
                        IMAGE_TAG="${IMAGE_NAME}:${BUILD_NUMBER}"
                        printf '%s' "$DOCKER_TOKEN" | docker login --username "$DOCKER_USER" --password-stdin
                        trap 'docker logout >/dev/null 2>&1 || true' EXIT
                        docker build --pull -t "$IMAGE_TAG" -t "${IMAGE_NAME}:latest" .
                        docker push "$IMAGE_TAG"
                        docker push "${IMAGE_NAME}:latest"
                        echo "Published $IMAGE_TAG"
                    '''
                }
            }
        }

        stage('Deploy dashboard and simulator configuration') {
            steps {
                sh '''
                    set -eu
                    test -r "$KUBECONFIG_PATH"
                    K="kubectl --kubeconfig=$KUBECONFIG_PATH"
                    $K get deployment "$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE"
                    $K apply -f k8s/dashboard-job-runner-rbac.yaml
                    $K patch deployment "$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE" --type=merge -p '{"spec":{"template":{"spec":{"serviceAccountName":"dashboard-job-runner"}}}}'
                    $K set env "deployment/$K8S_DEPLOYMENT" SIMULATOR_JOB_IMAGE="${SIMULATOR_IMAGE_NAME}:${BUILD_NUMBER}" -n "$K8S_NAMESPACE"
                    $K set image "deployment/$K8S_DEPLOYMENT" "$K8S_CONTAINER=${IMAGE_NAME}:${BUILD_NUMBER}" -n "$K8S_NAMESPACE"
                    $K rollout status "deployment/$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE" --timeout=180s
                    $K get deployment "$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE"
                '''
            }
        }
    }

    post {
        always { sh 'rm -rf .venv-ci || true' }
        success { echo 'SUCCESS: Tests passed; simulator and dashboard images published; dashboard deployed.' }
        failure { echo 'FAILED: Check the first failing stage in the console log.' }
    }
}
