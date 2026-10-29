
pipeline {
    triggers {
    githubPush()
}
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        choice(
            name: 'COMPONENT',
            choices: ['dashboard', 'bridge', 'both'],
            description: 'dashboard: test, build, push and deploy. bridge: build and push only. both: run both pipelines.'
        )
    }

    environment {
        DASHBOARD_IMAGE = 'nachiket1/industrial-maintenance-dashboard'
        K8S_NAMESPACE = 'capstone'
        K8S_DEPLOYMENT = 'maintenance-dashboard'
        K8S_CONTAINER = 'maintenance-dashboard'
        KUBECONFIG_PATH = '/var/lib/jenkins/kubeconfig'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo 'Repository checked out successfully.'
            }
        }

        stage('Validate Dashboard') {
            when {
                expression {
                    params.COMPONENT in ['dashboard', 'both']
                }
            }
            steps {
                sh '''
                    set -eu
                    test -f app/__init__.py
                    test -f wsgi.py
                    test -f requirements.txt
                    test -f Dockerfile
                    echo "Dashboard files validated."
                '''
            }
        }

        stage('Test Dashboard') {
            when {
                expression {
                    params.COMPONENT in ['dashboard', 'both']
                }
            }
            steps {
                sh '''
                    set -eu

                    python3 -m venv .venv-ci
                    . .venv-ci/bin/activate

                    python -m pip install --upgrade pip
                    python -m pip install -r requirements.txt

                    export PYTHONPATH="$WORKSPACE${PYTHONPATH:+:$PYTHONPATH}"

                    python -c "from app import create_app; print('App import successful')"
                    python -m compileall -q app wsgi.py
                    python -m pytest -q
                '''
            }
        }

        stage('Build and Push Dashboard') {
            when {
                expression {
                    params.COMPONENT in ['dashboard', 'both']
                }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_TOKEN'
                    )
                ]) {
                    sh '''
                        set -eu
                        set +x

                        IMAGE_TAG="${DASHBOARD_IMAGE}:${BUILD_NUMBER}"

                        printf '%s' "$DOCKER_TOKEN" |
                            docker login \
                                --username "$DOCKER_USER" \
                                --password-stdin

                        trap 'docker logout >/dev/null 2>&1 || true' EXIT

                        docker build --pull \
                            -t "$IMAGE_TAG" \
                            -t "${DASHBOARD_IMAGE}:latest" \
                            .

                        docker push "$IMAGE_TAG"
                        docker push "${DASHBOARD_IMAGE}:latest"

                        echo "Dashboard image pushed: $IMAGE_TAG"
                    '''
                }
            }
        }

        stage('Deploy Dashboard to Kubernetes') {
            when {
                expression {
                    params.COMPONENT in ['dashboard', 'both']
                }
            }
            steps {
                sh '''
                    set -eu

                    test -r "$KUBECONFIG_PATH"

                    kubectl \
                        --kubeconfig="$KUBECONFIG_PATH" \
                        get deployment "$K8S_DEPLOYMENT" \
                        -n "$K8S_NAMESPACE"

                    kubectl \
                        --kubeconfig="$KUBECONFIG_PATH" \
                        set image "deployment/$K8S_DEPLOYMENT" \
                        "$K8S_CONTAINER=${DASHBOARD_IMAGE}:${BUILD_NUMBER}" \
                        -n "$K8S_NAMESPACE"

                    kubectl \
                        --kubeconfig="$KUBECONFIG_PATH" \
                        rollout status "deployment/$K8S_DEPLOYMENT" \
                        -n "$K8S_NAMESPACE" \
                        --timeout=180s

                    kubectl \
                        --kubeconfig="$KUBECONFIG_PATH" \
                        get deployment "$K8S_DEPLOYMENT" \
                        -n "$K8S_NAMESPACE"

                    echo "Dashboard deployment completed."
                '''
            }
        }

        stage('Validate IoT Bridge') {
            when {
                expression {
                    params.COMPONENT in ['bridge', 'both']
                }
            }
            steps {
                sh '''
                    set -eu

                    BRIDGE_DIR="azure-iot-dashboard-bridge/bridge"

                    test -f "$BRIDGE_DIR/consumer.py"
                    test -f "$BRIDGE_DIR/requirements.txt"
                    test -f "$BRIDGE_DIR/Dockerfile"

                    python3 -m py_compile "$BRIDGE_DIR/consumer.py"

                    echo "IoT bridge validation passed."
                '''
            }
        }

        stage('Build and Push IoT Bridge') {
            when {
                expression {
                    params.COMPONENT in ['bridge', 'both']
                }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_TOKEN'
                    )
                ]) {
                    sh '''
                        set -eu
                        set +x

                        BRIDGE_IMAGE="${DOCKER_USER}/azure-iot-dashboard-bridge"
                        IMAGE_TAG="${BRIDGE_IMAGE}:${BUILD_NUMBER}"

                        printf '%s' "$DOCKER_TOKEN" |
                            docker login \
                                --username "$DOCKER_USER" \
                                --password-stdin

                        trap 'docker logout >/dev/null 2>&1 || true' EXIT

                        docker build --pull \
                            --file azure-iot-dashboard-bridge/bridge/Dockerfile \
                            -t "$IMAGE_TAG" \
                            -t "${BRIDGE_IMAGE}:latest" \
                            azure-iot-dashboard-bridge/bridge

                        docker push "$IMAGE_TAG"
                        docker push "${BRIDGE_IMAGE}:latest"

                        echo "IoT bridge image pushed: $IMAGE_TAG"
                    '''
                }
            }
        }
    }

    post {
        always {
            sh '''
                if [ -d .venv-ci ]; then
                    rm -rf .venv-ci
                fi
            '''
            echo "Pipeline finished for COMPONENT=${params.COMPONENT}"
        }

        success {
            echo 'Selected pipeline stages completed successfully.'
        }

        failure {
            echo 'Pipeline failed. Check Console Output for the first failing stage.'
        }
    }
}
