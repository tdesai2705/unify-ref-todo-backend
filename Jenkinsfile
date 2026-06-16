// CloudBees CI Pipeline - Todo Backend
// Build → Test (with Smart Tests) → Push Image → Update Helm Values → ArgoCD Auto-Deploys

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
    image: python:3.13-slim
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

        LAUNCHABLE_ORGANIZATION = 'tejas'
        LAUNCHABLE_WORKSPACE = 'tejas'
    }

    stages {
        stage('Setup') {
            steps {
                container('python') {
                    echo "Setting up workspace..."
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
                echo "Checking out code from branch: ${env.BRANCH_NAME}"
                checkout scm
                script {
                    env.GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                container('python') {
                    sh """
                        apt-get update && apt-get install -y --no-install-recommends default-jre-headless git
                        pip install --no-cache-dir -r requirements.txt
                        pip install smart-tests-cli==2.11.2
                    """
                }
            }
        }

        stage('Smart Tests - Record Build') {
            steps {
                container('python') {
                    withCredentials([string(credentialsId: 'SMART_TESTS_TOKEN', variable: 'SMART_TESTS_TOKEN')]) {
                        sh """
                            git config --global --add safe.directory ${WORKSPACE}
                            smart-tests verify || true
                            smart-tests record build \
                                --build ${BUILD_NUMBER} \
                                --source .
                        """
                    }
                }
            }
        }

        stage('Test') {
            steps {
                container('python') {
                    withCredentials([string(credentialsId: 'SMART_TESTS_TOKEN', variable: 'SMART_TESTS_TOKEN')]) {
                        sh """
                            mkdir -p test-results

                            PYTHONPATH=. pytest tests/ \
                                --junit-xml=test-results/results.xml \
                                --cov=app \
                                --cov-report=xml:test-results/coverage.xml \
                                -v || true

                            smart-tests record tests \
                                --build ${BUILD_NUMBER} \
                                --test-suite todo-backend-tests \
                                pytest test-results/results.xml
                        """
                    }
                }
            }
            post {
                always {
                    junit 'test-results/results.xml'
                }
            }
        }

        stage('Docker Build & Push') {
            steps {
                container('docker-cli') {
                    echo "Building and pushing Docker image..."
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

                                echo "Image pushed: ${IMAGE_NAME}:${IMAGE_TAG}"
                            """
                        }
                    }
                }
            }
        }

        stage('Update Infrastructure Repo') {
            steps {
                container('python') {
                    echo "Updating infrastructure repo with new image tag..."
                    script {
                        withCredentials([string(
                            credentialsId: 'github-pat',
                            variable: 'GITHUB_TOKEN'
                        )]) {
                            sh """
                                apt-get update && apt-get install -y git

                                git config --global user.email "ci@cloudbees.com"
                                git config --global user.name "CloudBees CI"

                                git clone https://\$GITHUB_TOKEN@github.com/tdesai2705/unify-ref-todo-infrastructure.git infra
                                cd infra

                                if [ "${env.BRANCH_NAME}" = "develop" ]; then
                                    ENV="dev"
                                elif [ "${env.BRANCH_NAME}" = "main" ]; then
                                    ENV="qa"
                                else
                                    ENV="dev"
                                fi

                                echo "Updating \${ENV} environment with image tag: ${IMAGE_TAG}"

                                sed -i "s|tag: .*|tag: ${IMAGE_TAG}|" helm/todo-app/envs/\${ENV}/backend-values.yaml

                                echo "Updated values file:"
                                cat helm/todo-app/envs/\${ENV}/backend-values.yaml

                                git add helm/todo-app/envs/\${ENV}/backend-values.yaml
                                git commit -m "Update backend image to ${IMAGE_TAG} [skip ci]" || echo "No changes to commit"

                                for i in 1 2 3 4 5; do
                                    git pull --rebase origin main && git push origin main && break
                                    echo "Push attempt \$i failed, retrying in 5s..."
                                    sleep 5
                                done

                                echo "Infrastructure repo updated. ArgoCD will sync automatically."
                            """
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Backend pipeline completed successfully!"
            echo "Build: ${BUILD_NUMBER} | Branch: ${env.BRANCH_NAME} | Image: ${IMAGE_NAME}:${IMAGE_TAG}"
        }
        failure {
            echo "Backend pipeline failed!"
        }
    }
}
