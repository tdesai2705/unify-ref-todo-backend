// ─────────────────────────────────────────────────────────────────────────────
// CloudBees CI Pipeline — Todo Backend
// Reference Architecture: Feature Flags + Predictive Test Selection (PTS)
//
// Pipeline stages:
//   1. Checkout          — clone repo, capture git context
//   2. Install Deps      — pip + smart-tests-cli (includes Java for PTS)
//   3. Record Build      — register this build with CloudBees Unify
//   4. Test              — observation OR subsetting based on SMART_TESTS_OBSERVATION
//   5. Docker Build+Push — image tagged as <branch>-<build> → Docker Hub
//   6. Infra Update      — bump image tag in infra repo → ArgoCD auto-syncs QA
//
// Feature flag + PTS interaction:
//   - Flags are CBCI parameters → passed as env vars to pytest
//   - Each flag has a dedicated test class in test_feature_flags.py
//   - After 20+ observation runs, PTS maps each flag's code path to its tests
//   - A commit touching only one flag → PTS selects ~5 tests, not all 35
//
// Observation vs Subsetting:
//   SMART_TESTS_OBSERVATION = true  → run all tests, build the model
//   SMART_TESTS_OBSERVATION = false → PTS selects minimum tests at 90% confidence
//
// See DEMO_GUIDE.md for SE walkthrough. See README.md for architecture details.
// ─────────────────────────────────────────────────────────────────────────────

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
    command: [sleep]
    args: [99d]
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
    command: [sleep]
    args: [99d]
    env:
    - name: DOCKER_HOST
      value: tcp://localhost:2375
  volumes:
  - name: docker-socket
    emptyDir: {}
"""
        }
    }

    // ── Feature flag parameters ─────────────────────────────────
    // Toggle each flag per-build from the CBCI UI (Build with Parameters)
    parameters {
        booleanParam(name: 'FEATURE_ENHANCED_STATS',    defaultValue: false, description: 'Stats endpoint: adds overdue_count + by_category')
        booleanParam(name: 'FEATURE_DUE_DATE_WARNINGS', defaultValue: false, description: 'Todo responses: adds overdue + days_until_due fields')
        booleanParam(name: 'FEATURE_BULK_OPERATIONS',   defaultValue: false, description: 'Enables POST /todos/bulk-complete endpoint')
        booleanParam(name: 'SMART_TESTS_OBSERVATION',   defaultValue: false, description: 'Observation mode (ON for first 20+ runs, then turn OFF)')
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10', daysToKeepStr: '30'))
    }

    environment {
        APP_NAME        = 'todo-backend'
        DOCKER_REGISTRY = 'docker.io'
        DOCKER_REPO     = 'tejasdesai27'
        IMAGE_NAME      = "${DOCKER_REPO}/${APP_NAME}"
        IMAGE_TAG       = "${env.BRANCH_NAME?.replaceAll('/', '-')}-${BUILD_NUMBER}"
        INFRA_REPO      = 'https://github.com/tdesai2705/unify-ref-todo-infrastructure.git'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                }
                echo "Branch: ${env.BRANCH_NAME} | Commit: ${env.GIT_COMMIT_SHORT} | Build: ${BUILD_NUMBER}"
            }
        }

        stage('Install Dependencies') {
            steps {
                container('python') {
                    sh '''
                        apt-get update -qq
                        apt-get install -y --no-install-recommends default-jre-headless git curl
                        pip install --no-cache-dir -r requirements.txt
                        pip install --no-cache-dir "smart-tests-cli~=2.0"
                        smart-tests --version
                    '''
                }
            }
        }

        stage('Smart Tests — Record Build') {
            steps {
                container('python') {
                    withCredentials([string(credentialsId: 'SMART_TESTS_TOKEN', variable: 'SMART_TESTS_TOKEN')]) {
                        sh '''
                            git config --global --add safe.directory ${WORKSPACE}
                            smart-tests verify || true
                            smart-tests record build \
                                --build ${BUILD_TAG} \
                                --source .
                        '''
                    }
                }
            }
        }

        stage('Test') {
            steps {
                container('python') {
                    withCredentials([string(credentialsId: 'SMART_TESTS_TOKEN', variable: 'SMART_TESTS_TOKEN')]) {
                        script {
                            def obsFlag = params.SMART_TESTS_OBSERVATION ? '--observation' : ''
                            def featureEnv = """
                                FEATURE_ENHANCED_STATS=${params.FEATURE_ENHANCED_STATS}
                                FEATURE_DUE_DATE_WARNINGS=${params.FEATURE_DUE_DATE_WARNINGS}
                                FEATURE_BULK_OPERATIONS=${params.FEATURE_BULK_OPERATIONS}
                            """.trim()

                            sh """
                                mkdir -p test-results

                                # Step 1: Create Smart Tests session
                                smart-tests record session \\
                                    --build ${BUILD_TAG} \\
                                    --test-suite todo-backend-tests \\
                                    ${obsFlag} \\
                                    > session.txt

                                echo "Session: \$(cat session.txt)"
                                echo "Observation mode: ${params.SMART_TESTS_OBSERVATION}"
                                echo "Feature flags: enhanced_stats=${params.FEATURE_ENHANCED_STATS} due_date=${params.FEATURE_DUE_DATE_WARNINGS} bulk=${params.FEATURE_BULK_OPERATIONS}"

                                # Step 2a: Observation — run all tests
                                if [ "${params.SMART_TESTS_OBSERVATION}" = "true" ]; then
                                    FEATURE_ENHANCED_STATS=${params.FEATURE_ENHANCED_STATS} \\
                                    FEATURE_DUE_DATE_WARNINGS=${params.FEATURE_DUE_DATE_WARNINGS} \\
                                    FEATURE_BULK_OPERATIONS=${params.FEATURE_BULK_OPERATIONS} \\
                                    PYTHONPATH=. pytest tests/ \\
                                        --junitxml=test-results/results.xml \\
                                        -v

                                # Step 2b: Subset — PTS selects which tests to run
                                else
                                    PYTHONPATH=. pytest tests/ --collect-only -q \\
                                        | grep '::' \\
                                        | smart-tests subset pytest \\
                                            --session @session.txt \\
                                            --confidence 90% \\
                                            > subset.txt

                                    echo "Smart Tests selected \$(wc -l < subset.txt) of 35 tests:"
                                    cat subset.txt

                                    FEATURE_ENHANCED_STATS=${params.FEATURE_ENHANCED_STATS} \\
                                    FEATURE_DUE_DATE_WARNINGS=${params.FEATURE_DUE_DATE_WARNINGS} \\
                                    FEATURE_BULK_OPERATIONS=${params.FEATURE_BULK_OPERATIONS} \\
                                    PYTHONPATH=. pytest tests/ \\
                                        --junitxml=test-results/results.xml \\
                                        -v \\
                                        \$(cat subset.txt)
                                fi
                            """
                        }
                    }
                }
            }
            post {
                always {
                    container('python') {
                        withCredentials([string(credentialsId: 'SMART_TESTS_TOKEN', variable: 'SMART_TESTS_TOKEN')]) {
                            sh '''
                                smart-tests record tests pytest \
                                    --session @session.txt \
                                    test-results/results.xml
                            '''
                        }
                    }
                    junit 'test-results/results.xml'
                }
            }
        }

        stage('Docker Build & Push') {
            steps {
                container('docker-cli') {
                    withCredentials([usernamePassword(
                        credentialsId: 'dockerhub-credentials',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh """
                            echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin ${DOCKER_REGISTRY}
                            docker build --platform linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .
                            docker push ${IMAGE_NAME}:${IMAGE_TAG}
                            docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest
                            docker push ${IMAGE_NAME}:latest
                        """
                    }
                }
            }
        }

        stage('Update Infrastructure → ArgoCD Sync') {
            steps {
                container('python') {
                    withCredentials([string(credentialsId: 'github-pat', variable: 'GITHUB_TOKEN')]) {
                        sh """
                            git config --global user.email "ci@cloudbees.com"
                            git config --global user.name "CloudBees CI"

                            git clone https://\$GITHUB_TOKEN@github.com/tdesai2705/unify-ref-todo-infrastructure.git infra
                            cd infra

                            ENV=\$([ "${env.BRANCH_NAME}" = "main" ] && echo "qa" || echo "dev")
                            echo "Deploying to: \$ENV | Image: ${IMAGE_TAG}"

                            sed -i "s|tag: .*|tag: ${IMAGE_TAG}|" helm/todo-app/envs/\${ENV}/backend-values.yaml
                            cat helm/todo-app/envs/\${ENV}/backend-values.yaml

                            git add .
                            git commit -m "ci: update backend to ${IMAGE_TAG} [skip ci]" || echo "No changes"

                            for i in 1 2 3; do
                                git pull --rebase origin main && git push origin main && break
                                sleep 5
                            done

                            echo "ArgoCD will auto-sync within 3 minutes."
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline done | Build: ${BUILD_NUMBER} | Image: ${IMAGE_NAME}:${IMAGE_TAG}"
        }
        failure {
            echo "❌ Pipeline failed at build ${BUILD_NUMBER}"
        }
    }
}
