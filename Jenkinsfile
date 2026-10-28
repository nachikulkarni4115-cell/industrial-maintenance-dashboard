pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        // Uses the existing Jenkins credential ID "dockerhub"
        // Image will be: <dockerhub-user>/azure-iot-dashboard-bridge:<BUILD_NUMBER>
        IMAGE_NAME = 'azure-iot-dashboard-bridge'
    }

    stages {
        stage('Validate bridge source') {
            steps {
                sh '''set -eu
                echo "=== Bridge source validation ==="
                test -f azure-iot-dashboard-bridge/bridge/consumer.py
                test -f azure-iot-dashboard-bridge/bridge/requirements.txt
                test -f azure-iot-dashboard-bridge/bridge/Dockerfile
                python3 -m py_compile azure-iot-dashboard-bridge/bridge/consumer.py
                echo "Source validation passed"
                '''
            }
        }

        stage('Build and push bridge image') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKERHUB_USER',
                    passwordVariable: 'DOCKERHUB_TOKEN'
                )]) {
                    sh '''set -eu
                    set +x
                    FULL_IMAGE="${DOCKERHUB_USER}/${IMAGE_NAME}"
                    TAG="${BUILD_NUMBER}"

                    echo "Building ${FULL_IMAGE}:${TAG}"
                    docker build --pull \
                      --file azure-iot-dashboard-bridge/bridge/Dockerfile \
                      --tag "${FULL_IMAGE}:${TAG}" \
                      --tag "${FULL_IMAGE}:latest" \
                      azure-iot-dashboard-bridge/bridge

                    printf '%s' "$DOCKERHUB_TOKEN" | \
                      docker login --username "$DOCKERHUB_USER" --password-stdin

                    trap 'docker logout >/dev/null 2>&1 || true' EXIT

                    docker push "${FULL_IMAGE}:${TAG}"
                    docker push "${FULL_IMAGE}:latest"

                    echo "================================================"
                    echo "BRIDGE IMAGE PUSHED SUCCESSFULLY"
                    echo "  Image : ${FULL_IMAGE}:${TAG}"
                    echo "  Also  : ${FULL_IMAGE}:latest"
                    echo "================================================"
                    echo "Next: replace REPLACE_WITH_TAG in the Kubernetes"
                    echo "manifest with ${TAG} and apply the Deployment."
                    '''
                }
            }
        }

        // -----------------------------------------------------------------
        // OPTIONAL AUTO-DEPLOY STAGE
        // Keep this stage commented out until the first manual deploy works
        // and you explicitly want automatic deployment on every push.
        // Uncomment the entire stage below when ready.
        // -----------------------------------------------------------------
        /*
        stage('Deploy bridge to Kubernetes') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKERHUB_USER',
                    passwordVariable: 'DOCKERHUB_TOKEN'
                )]) {
                    sh '''set -eu
                    FULL_IMAGE="${DOCKERHUB_USER}/${IMAGE_NAME}:${BUILD_NUMBER}"

                    # Generate a concrete manifest from the template
                    sed "s|REPLACE_WITH_TAG|${BUILD_NUMBER}|g; \
                         s|nachiket1/azure-iot-dashboard-bridge|${DOCKERHUB_USER}/azure-iot-dashboard-bridge|g" \
                      azure-iot-dashboard-bridge/kubernetes-deployment.template.yaml \
                      > /tmp/bridge-deploy.yaml

                    echo "Applying bridge Deployment only (namespace=capstone)"
                    sudo -u jenkins kubectl \
                      --kubeconfig=/var/lib/jenkins/kubeconfig \
                      -n capstone apply -f /tmp/bridge-deploy.yaml

                    echo "Waiting for rollout..."
                    sudo -u jenkins kubectl \
                      --kubeconfig=/var/lib/jenkins/kubeconfig \
                      -n capstone rollout status deployment/azure-iot-dashboard-bridge --timeout=120s

                    echo "Bridge Deployment updated to ${FULL_IMAGE}"
                    '''
                }
            }
        }
        */
    }

    post {
        success {
            echo "Bridge pipeline succeeded. Image is on Docker Hub. Deployment was NOT performed (auto-deploy stage is disabled by default)."
        }
        failure {
            echo "Bridge pipeline failed. Check the console log above."
        }
        always {
            echo "Bridge pipeline finished. Existing dashboard / portfolio / AgriSakha were not touched."
        }
    }
}
