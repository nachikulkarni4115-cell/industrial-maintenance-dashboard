pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        IMAGE_NAME = 'nachiket1/industrial-maintenance-dashboard'
        K8S_NAMESPACE = 'capstone'
        K8S_DEPLOYMENT = 'maintenance-dashboard'
        K8S_CONTAINER = 'maintenance-dashboard'
        KUBECONFIG_PATH = '/var/lib/jenkins/kubeconfig'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Validate dashboard') {
            steps {
                sh '''
                    set -eu
                    test -f app/__init__.py
                    test -f app/templates/base.html
                    test -f app/templates/dashboard.html
                    test -f app/static/css/dashboard.css
                    test -f app/static/js/dashboard-live.js
                    test ! -f Jenkinsfile.dashboard
                    python3 -m compileall -q app wsgi.py
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

        stage('Deploy dashboard to Kubernetes') {
            steps {
                sh '''
                    set -eu
                    test -r "$KUBECONFIG_PATH"
                    kubectl --kubeconfig="$KUBECONFIG_PATH" get deployment "$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE"
                    kubectl --kubeconfig="$KUBECONFIG_PATH" set image "deployment/$K8S_DEPLOYMENT" "$K8S_CONTAINER=${IMAGE_NAME}:${BUILD_NUMBER}" -n "$K8S_NAMESPACE"
                    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout status "deployment/$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE" --timeout=180s
                    kubectl --kubeconfig="$KUBECONFIG_PATH" get deployment "$K8S_DEPLOYMENT" -n "$K8S_NAMESPACE"
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -rf .venv-ci || true'
        }
        success {
            echo 'SUCCESS: Dashboard tests, image publishing, and Kubernetes deployment completed.'
        }
        failure {
            echo 'FAILED: Check the first failing stage in the console log.'
        }
    }
}