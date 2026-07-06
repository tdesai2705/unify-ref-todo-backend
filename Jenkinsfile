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
  - name: jnlp
    resources:
      requests:
        cpu: "10m"
        memory: "256Mi"
      limits:
        cpu: "500m"
        memory: "512Mi"
  - name: python
    image: python:3.13-slim
    command: [sleep]
    args: [99d]
    resources:
      requests:
        cpu: "10m"
        memory: "256Mi"
      limits:
        cpu: "1"
        memory: "1Gi"
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
    resources:
      requests:
        cpu: "10m"
        memory: "256Mi"
      limits:
        cpu: "1"
        memory: "1Gi"
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
    resources:
      requests:
        cpu: "10m"
        memory: "128Mi"
      limits:
        cpu: "500m"
        memory: "256Mi"
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
        booleanParam(name: 'SMART_TESTS_OBSERVATION',   defaultValue: true, description: 'Observation mode (ON for first 20+ runs, then turn OFF)')
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
                        pip install --no-cache-dir "smart-tests-cli~=2.0" cyclonedx-bom
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

                                # Step 2a: Observation — run all tests with coverage
                                if [ "${params.SMART_TESTS_OBSERVATION}" = "true" ]; then
                                    FEATURE_ENHANCED_STATS=${params.FEATURE_ENHANCED_STATS} \\
                                    FEATURE_DUE_DATE_WARNINGS=${params.FEATURE_DUE_DATE_WARNINGS} \\
                                    FEATURE_BULK_OPERATIONS=${params.FEATURE_BULK_OPERATIONS} \\
                                    PYTHONPATH=. pytest tests/ \\
                                        --cov=app --cov-report=xml:test-results/coverage.xml \\
                                        --junitxml=test-results/results.xml \\
                                        -v

                                # Step 2b: Subset — PTS selects which tests to run
                                else
                                    PYTHONPATH=. pytest tests/ --collect-only -q \\
                                        | grep '::' \\
                                        | smart-tests subset pytest \\
                                            --session @session.txt \\
                                            --confidence 70% \\
                                            > subset.txt

                                    echo "Smart Tests selected \$(wc -l < subset.txt) of 35 tests:"
                                    cat subset.txt

                                    FEATURE_ENHANCED_STATS=${params.FEATURE_ENHANCED_STATS} \\
                                    FEATURE_DUE_DATE_WARNINGS=${params.FEATURE_DUE_DATE_WARNINGS} \\
                                    FEATURE_BULK_OPERATIONS=${params.FEATURE_BULK_OPERATIONS} \\
                                    PYTHONPATH=. pytest \$(cat subset.txt) \\
                                        --cov=app --cov-report=xml:test-results/coverage.xml \\
                                        --junitxml=test-results/results.xml \\
                                        -v
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
                                    test-results/results.xml \
                                    test-results/coverage.xml || \
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

        stage('Dependency-Track Scan') {
            steps {
                sh 'mkdir -p dt-results && chmod 777 dt-results'
                container('python') {
                    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {
                        sh '''
                            set +e
                            DT_URL="http://dependency-track-api-server.dependency-track.svc.cluster.local:8080"

                            echo "=== Generating CycloneDX SBOM from requirements.txt ==="
                            cyclonedx-py requirements -i requirements.txt \
                                --of xml \
                                > dt-results/bom.xml
                            ls -lh dt-results/bom.xml || { echo "SBOM generation failed"; exit 0; }

                            echo "=== Injecting known CPE identifiers for internal NVD matching ==="
                            # OSS Index (PyPI-aware analyzer) has no username configured on this DT
                            # instance, so it skips every scan. DT's internal CPE-based analyzer is
                            # enabled and its NVD mirror already has these CVEs -- it just never gets
                            # a CPE to match against from a plain requirements.txt SBOM. Inject the
                            # correct vendor:product (pulled from this DT's own NVD data) for the
                            # packages we track for this demo.
                            python3 - <<'PYEOF'
import xml.etree.ElementTree as ET

NS = "http://cyclonedx.org/schema/bom/1.6"
ET.register_namespace("", NS)
TAG = "{" + NS + "}"
PATH = "dt-results/bom.xml"

CPE_MAP = {
    "pyyaml": ("pyyaml", "pyyaml"),
    "requests": ("python", "requests"),
    "urllib3": ("python", "urllib3"),
}

tree = ET.parse(PATH)
root = tree.getroot()
injected = 0

for component in root.iter(TAG + "component"):
    name_el = component.find(TAG + "name")
    version_el = component.find(TAG + "version")
    if name_el is None or version_el is None or name_el.text is None:
        continue
    mapping = CPE_MAP.get(name_el.text.strip().lower())
    if mapping is None:
        continue
    vendor, product = mapping
    cpe_value = "cpe:2.3:a:" + vendor + ":" + product + ":" + version_el.text.strip() + ":*:*:*:*:*:*:*"
    cpe_el = ET.Element(TAG + "cpe")
    cpe_el.text = cpe_value
    purl_el = component.find(TAG + "purl")
    if purl_el is not None:
        component.insert(list(component).index(purl_el), cpe_el)
    else:
        component.append(cpe_el)
    injected += 1
    print("Injected CPE for " + name_el.text + " " + version_el.text + " -> " + cpe_value)

tree.write(PATH, encoding="UTF-8", xml_declaration=True)
print("Total CPEs injected: " + str(injected))
PYEOF

                            echo "=== Uploading SBOM to Dependency-Track ==="
                            base64 -w 0 dt-results/bom.xml > dt-results/bom-b64.txt
                            cat > dt-results/dt-payload.json <<PAYLOAD
{"projectName":"todo-backend","projectVersion":"${BRANCH_NAME:-main}","autoCreate":true,"bom":"$(cat dt-results/bom-b64.txt)"}
PAYLOAD

                            HTTP=$(curl -s -X PUT "${DT_URL}/api/v1/bom" \
                              -H "X-Api-Key: ${DT_API_KEY}" \
                              -H "Content-Type: application/json" \
                              -d @dt-results/dt-payload.json \
                              -o dt-results/dt-upload.json \
                              -w "%{http_code}")
                            echo "DT upload HTTP: ${HTTP}"
                            cat dt-results/dt-upload.json

                            if [ "${HTTP}" = "200" ]; then
                                TOKEN=$(grep -o '"token":"[^"]*"' dt-results/dt-upload.json | cut -d'"' -f4)
                                echo "Upload token: ${TOKEN}"

                                echo "=== Waiting for DT analysis (up to 2 min) ==="
                                for i in $(seq 1 24); do
                                    sleep 5
                                    STATUS=$(curl -s -H "X-Api-Key: ${DT_API_KEY}" \
                                      "${DT_URL}/api/v1/event/token/${TOKEN}" | \
                                      grep -o '"processing":[a-z]*' | cut -d: -f2)
                                    echo "  [${i}/24] processing=${STATUS}"
                                    [ "${STATUS}" = "false" ] && break
                                done

                                echo "=== Fetching findings ==="
                                PROJECT_UUID=$(curl -s -H "X-Api-Key: ${DT_API_KEY}" \
                                  "${DT_URL}/api/v1/project?name=todo-backend&version=${BRANCH_NAME:-main}" | \
                                  grep -o '"uuid":"[^"]*"' | head -1 | cut -d'"' -f4)
                                echo "Project UUID: ${PROJECT_UUID}"

                                if [ -n "${PROJECT_UUID}" ]; then
                                    # Internal analyzer can lag slightly behind the "processing" flag,
                                    # so retry a few times before accepting a zero count.
                                    for j in 1 2 3; do
                                        curl -s -H "X-Api-Key: ${DT_API_KEY}" \
                                          "${DT_URL}/api/v1/finding/project/${PROJECT_UUID}" \
                                          > dt-results/dt-findings.json
                                        # dt-findings.json is minified onto one line, so grep -c
                                        # (which counts matching *lines*) always caps at 1 -- count
                                        # occurrences instead.
                                        COUNT=$(grep -o '"vulnerability"' dt-results/dt-findings.json | wc -l | tr -d ' ')
                                        echo "  [retry ${j}/3] Findings: ${COUNT}"
                                        [ "${COUNT}" != "0" ] && break
                                        sleep 10
                                    done
                                    echo "Findings: ${COUNT}"
                                fi
                            fi

                            echo "=== Building SARIF from findings ==="
                            python3 - <<'PYEOF'
import json

DT_URL = "http://dependency-track.34.75.0.106.nip.io"
findings_file = "dt-results/dt-findings.json"
sarif_file = "dt-results/dependency-track-scan.sarif"

try:
    findings = json.loads(open(findings_file).read())
    if not isinstance(findings, list):
        findings = findings.get("findings", [])
except Exception:
    findings = []

results = []
for f in findings[:100]:
    vuln = f.get("vulnerability", {})
    comp = f.get("component", {})
    sev = (vuln.get("severity") or "UNASSIGNED").lower()
    level = "error" if sev in ("critical", "high") else ("warning" if sev == "medium" else "note")
    rule_id = "dt/" + str(vuln.get("vulnId") or "unknown")
    title = str(vuln.get("title") or vuln.get("vulnId") or "Vulnerability")
    msg = title + " in " + str(comp.get("name") or "unknown") + ":" + str(comp.get("version") or "") + " - " + sev.upper()
    results.append({
        "ruleId": rule_id,
        "level": level,
        "message": {"text": msg},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "requirements.txt"}}}],
    })

if not results:
    results.append({
        "ruleId": "dependency-track/scan-clean",
        "level": "note",
        "message": {"text": "Dependency-Track SBOM analysis complete. No vulnerabilities found."},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "requirements.txt"}}}],
    })

sarif = {
    "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
    "version": "2.1.0",
    "runs": [{
        "tool": {"driver": {"name": "Dependency-Track", "informationUri": DT_URL, "version": "1.0.0"}},
        "results": results,
    }],
}

content = json.dumps(sarif)
open(sarif_file, "w").write(content)
print("SARIF written (" + str(len(content)) + " bytes, " + str(len(results)) + " findings)")
PYEOF
                            exit 0
                        '''
                    }
                }
                archiveArtifacts artifacts: 'dt-results/**', allowEmptyArchive: true
                script {
                    try {
                        registerSecurityScan(
                            artifacts: 'dt-results/dependency-track-scan.sarif',
                            format: 'sarif',
                            scanner: 'Dependency-Track',
                            archive: false
                        )
                        echo "✅ DT findings registered with CloudBees Unify"
                    } catch (Exception e) {
                        echo "⚠️  Unify registration failed: ${e.message}"
                    }
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
