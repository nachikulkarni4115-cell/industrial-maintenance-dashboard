pipeline {
  agent any

  environment {
    // Configurable – change if you use a different Docker Hub repo
    DOCKER_IMAGE = "nachiket1/industrial-maintenance-dashboard"
    KUBECONFIG = "/var/lib/jenkins/kubeconfig"
    NAMESPACE = "capstone"
  }

  stages {
    stage("Checkout") {
      steps {
        checkout scm
      }
    }

    stage("Test") {
      steps {
        sh """
          python3 -m venv .venv || true
          . .venv/bin/activate
          pip install -q -r requirements.txt
          export FLASK_CONFIG=testing
          export PYTHONPATH=.
          pytest tests/ -v --tb=short
        """
      }
    }

    stage("Build Image") {
      steps {
        script {
          def tag = "${env.BUILD_NUMBER}"
          sh "docker build -t ${DOCKER_IMAGE}:${tag} -t ${DOCKER_IMAGE}:latest ."
          env.IMAGE_TAG = tag
        }
      }
    }

    stage("Push Image") {
      steps {
        withCredentials([usernamePassword(credentialsId: "dockerhub", usernameVariable: "DH_USER", passwordVariable: "DH_PASS")]) {
          sh """
            echo "\$DH_PASS" | docker login -u "\$DH_USER" --password-stdin
            docker push ${DOCKER_IMAGE}:${env.IMAGE_TAG}
            docker push ${DOCKER_IMAGE}:latest
          """
        }
      }
    }

    stage("Deploy Capstone Only") {
      steps {
        sh """
          export KUBECONFIG=${KUBECONFIG}
          # Update only the maintenance-dashboard deployment image
          kubectl -n ${NAMESPACE} set image deployment/maintenance-dashboard \
            maintenance-dashboard=${DOCKER_IMAGE}:${env.IMAGE_TAG}
          kubectl -n ${NAMESPACE} rollout status deployment/maintenance-dashboard --timeout=180s
        """
      }
    }

    stage("Health Check") {
      steps {
        sh """
          export KUBECONFIG=${KUBECONFIG}
          kubectl -n ${NAMESPACE} get pods -l app=maintenance-dashboard
          kubectl -n ${NAMESPACE} get svc maintenance-dashboard-service
        """
      }
    }
  }

  post {
    failure {
      echo "Pipeline failed. Capstone namespace only was targeted. Portfolio resources were not modified."
    }
    success {
      echo "Deployed ${DOCKER_IMAGE}:${env.IMAGE_TAG} to namespace ${NAMESPACE}"
    }
  }
}
