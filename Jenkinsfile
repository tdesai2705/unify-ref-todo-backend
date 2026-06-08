// CloudBees CI Pipeline - Todo Backend
// Build → Test → Push Image → Update Helm Values → ArgoCD Auto-Deploys

pipeline {
    agent {
        kubernetes {
            yaml """
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agents
  containers:
  - name: python
    image: python:3.11-slim
    command:
    - sleep
    args:
    - 99d
  - name: docker
    image: docker:24-dind
    securityContext:
      privileged: true
    args:
    - --host=tcp://0.0.0.0:2375
    - --tls=false
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
    volumeMounts:
    - name: docker-socket
      mountPath: /var/run
  - name: docker-cli
    image: docker:24-cli
    command:
    - sleep
    args:
    - 99d
    env:
    - name: DOCKER_HOST
      value: tcp://localhost:2375
  volumes:
  - name: docker-socket
    emptyDir: {}
"""
        }
    }

    options {
        buildDiscarder(logRotator(
            numToKeepStr: '10',
            artifactNumToKeepStr: '5',
            daysToKeepStr: '30'
        ))
    }

    environment {
        APP_NAME = 'todo-backend'
        DOCKER_REGISTRY = 'docker.io'
        DOCKER_REPO = 'tejasdesai27'
        IMAGE_NAME = "${DOCKER_REPO}/${APP_NAME}"

        BRANCH_NAME_CLEAN = "${env.BRANCH_NAME.replaceAll('/', '-')}"
        IMAGE_TAG = "${BRANCH_NAME_CLEAN}-${BUILD_NUMBER}"

        INFRA_REPO = 'https://github.com/tdesai2705/unify-ref-todo-infrastructure.git'
    }

    stages {
        stage('Setup') {
            steps {
                container('python') {
                    echo "🔧 Setting up workspace..."
                    sh """
                        echo "Build: ${BUILD_NUMBER}"
                        echo "Branch: ${BRANCH_NAME}"
                        echo "Image Tag: ${IMAGE_TAG}"
                    """
                }
            }
        }

        stage('Checkout') {
            steps {
                echo "🔄 Checking out code from branch: ${env.BRANCH_NAME}"
                checkout scm

                script {
                    env.GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                }
            }
        }

        stage('Test') {
            steps {
                container('python') {
                    echo "🧪 Installing dependencies and running tests..."
                    sh """
                        pip install --no-cache-dir -r requirements.txt
                        echo "Tests would run here - pytest etc."
                    """
                }
            }
        }

        stage('Docker Build & Push') {
            steps {
                container('docker-cli') {
                    echo "🐳 Building and pushing Docker image..."
                    script {
                        withCredentials([usernamePassword(
                            credentialsId: 'dockerhub-credentials',
                            usernameVariable: 'DOCKER_USER',
                            passwordVariable: 'DOCKER_PASS'
                        )]) {
                            sh """
                                echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin ${DOCKER_REGISTRY}

                                docker build --platform linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .
                                docker push ${IMAGE_NAME}:${IMAGE_TAG}

                                docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:${BRANCH_NAME_CLEAN}-latest
                                docker push ${IMAGE_NAME}:${BRANCH_NAME_CLEAN}-latest

                                echo "✅ Image pushed: ${IMAGE_NAME}:${IMAGE_TAG}"
                            """
                        }
                    }
                }
            }
        }

        stage('Update Infrastructure Repo') {
            steps {
                container('python') {
                    echo "📝 Updating infrastructure repo with new image tag..."
                    script {
                        withCredentials([secretFile(
                            credentialsId: 'github-ssh-key',
                            variable: 'SSH_KEY'
                        )]) {
                            sh """
                                # Install git and openssh
                                apt-get update && apt-get install -y git openssh-client

                                # Configure git
                                git config --global user.email "ci@cloudbees.com"
                                git config --global user.name "CloudBees CI"

                                # Set up SSH
                                mkdir -p ~/.ssh
                                chmod 700 ~/.ssh
                                cp \$SSH_KEY ~/.ssh/id_ed25519
                                chmod 600 ~/.ssh/id_ed25519
                                cat ~/.ssh/id_ed25519

                                ssh-keyscan github.com >> ~/.ssh/known_hosts

                                # Clone infrastructure repo via SSH
                                git clone git@github.com:tdesai2705/unify-ref-todo-infrastructure.git infra
                                cd infra

                                # Determine environment based on branch
                                if [ "${env.BRANCH_NAME}" = "develop" ]; then
                                    ENV="dev"
                                elif [ "${env.BRANCH_NAME}" = "main" ]; then
                                    ENV="qa"
                                else
                                    ENV="dev"
                                fi

                                echo "Updating \${ENV} environment with image tag: ${IMAGE_TAG}"

                                # Update backend image tag in values file
                                sed -i "s|tag: .*|tag: ${IMAGE_TAG}|" kubernetes/\${ENV}/backend-values.yaml

                                echo "Updated values file:"
                                cat kubernetes/\${ENV}/backend-values.yaml

                                # Commit and push
                                git add kubernetes/\${ENV}/backend-values.yaml
                                git commit -m "Update backend image to ${IMAGE_TAG} [skip ci]" || echo "No changes to commit"
                                git push origin main

                                echo "✅ Infrastructure repo updated. ArgoCD will sync automatically."
                            """
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "✅ Backend pipeline completed successfully!"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "📦 Build: ${BUILD_NUMBER}"
            echo "🌿 Branch: ${env.BRANCH_NAME}"
            echo "🐳 Image: ${IMAGE_NAME}:${IMAGE_TAG}"
            echo "🔄 ArgoCD will auto-deploy to ${env.BRANCH_NAME == 'develop' ? 'dev' : 'qa'} environment"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        }
        failure {
            echo "❌ Backend pipeline failed!"
        }
    }
}
