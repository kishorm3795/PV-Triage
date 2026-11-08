#!/usr/bin/env bash
# ==============================================================================
# scripts/clean_clone_test.sh - Phase 2 Clean-Clone Verification Script
#
# Clones the repository into an isolated temporary folder, spins up services via
# Docker Compose, verifies Prometheus targets (api & worker UP), submits a valid
# report, polls for end-to-end completion, and tears down cleanly.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d -t pv_clean_clone_XXXXXX)"
TARGET_DIR="${TMP_DIR}/PV-Triage"

echo "======================================================================"
echo " PV-Triage Clean-Clone Verification"
echo " Repo Source: ${REPO_DIR}"
echo " Temp Directory: ${TMP_DIR}"
echo "======================================================================"

cleanup() {
    echo ""
    echo "[clean-clone] Cleaning up temporary containers and volume..."
    if [ -d "${TARGET_DIR}" ]; then
        cd "${TARGET_DIR}"
        docker compose down -v --remove-orphans || true
    fi
    rm -rf "${TMP_DIR}"
    echo "[clean-clone] Cleanup finished."
}
trap cleanup EXIT

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")"
echo "[clean-clone] Cloning fresh copy of branch ${CURRENT_BRANCH}..."
git clone --branch "${CURRENT_BRANCH}" "file://${REPO_DIR}" "${TARGET_DIR}"

cd "${TARGET_DIR}"

echo "[clean-clone] Copying .env.example to .env..."
cp .env.example .env

echo "[clean-clone] Starting Docker Compose services (build + up)..."
docker compose up -d --build

echo "[clean-clone] Waiting for /health dependency checks (redis, index_present, stub_llm)..."
MAX_RETRIES=40
RETRIES=0
HEALTHY=false

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
        STATUS_OUTPUT=$(curl -s http://localhost:8000/health)
        echo "[clean-clone] Health check response: ${STATUS_OUTPUT}"
        HEALTHY=true
        break
    fi
    echo "[clean-clone] Waiting for API to be healthy... ($((RETRIES + 1))/$MAX_RETRIES)"
    sleep 2
    RETRIES=$((RETRIES + 1))
done

if [ "$HEALTHY" != "true" ]; then
    echo "[clean-clone] ERROR: API healthcheck did not become healthy in time!"
    docker compose logs
    exit 1
fi

echo "[clean-clone] Waiting for Prometheus scrape cycle and verifying targets are UP..."
TARGETS_UP=false
TARGETS_JSON=""

for i in {1..20}; do
    TARGETS_JSON=$(curl -s http://localhost:9090/api/v1/targets || echo "{}")
    API_UP=$(python3 -c "import json; data=json.loads('''${TARGETS_JSON}'''); print(any(t.get('labels',{}).get('job')=='api' and t.get('health')=='up' for t in data.get('data',{}).get('activeTargets',[])))" 2>/dev/null || echo "False")
    WORKER_UP=$(python3 -c "import json; data=json.loads('''${TARGETS_JSON}'''); print(any(t.get('labels',{}).get('job')=='worker' and t.get('health')=='up' for t in data.get('data',{}).get('activeTargets',[])))" 2>/dev/null || echo "False")
    if [ "$API_UP" = "True" ] && [ "$WORKER_UP" = "True" ]; then
        TARGETS_UP=true
        break
    fi
    echo "[clean-clone] Waiting for targets to enter UP status... ($i/20)"
    sleep 2
done

echo "[clean-clone] Prometheus Targets Status (targets UP: ${TARGETS_UP}):"
python3 -c "
import sys, json
try:
    data = json.loads('''${TARGETS_JSON}''')
    active = data.get('data', {}).get('activeTargets', [])
    for t in active:
        job = t.get('labels', {}).get('job')
        health = t.get('health')
        scrape_url = t.get('scrapeUrl')
        print(f'  - Job: {job:<12} | Health: {health:<6} | Scrape URL: {scrape_url}')
except Exception as e:
    print('Error parsing targets:', e)
"

if [ "$TARGETS_UP" != "true" ]; then
    echo "[clean-clone] ERROR: Not all Prometheus targets reached UP state!"
    exit 1
fi

echo "[clean-clone] Submitting Section 4.1 reference case report to POST /v1/reports..."
SUBMIT_PAYLOAD='{
  "report_id": "rep_ref_clean_001",
  "reporter_type": "physician",
  "patient_age": 42,
  "patient_sex": "female",
  "suspect_drug": "Lamotrigine",
  "drug_start_date": "2026-09-01",
  "event_date": "2026-09-15",
  "reaction_description": "Severe skin peeling with epidermal detachment and mucocutaneous lesions requiring inpatient ICU hospitalization",
  "outcome": "not_recovered",
  "narrative": "The patient'\''s skin started peeling badly a week after starting Lamotrigine, and she was admitted to hospital."
}'

SUBMIT_RESP=$(curl -s -X POST http://localhost:8000/v1/reports \
    -H "Content-Type: application/json" \
    -d "$SUBMIT_PAYLOAD")

echo "[clean-clone] Submit response: ${SUBMIT_RESP}"

RUN_ID=$(python3 -c "import json; print(json.loads('''${SUBMIT_RESP}''').get('run_id', ''))")

if [ -z "$RUN_ID" ]; then
    echo "[clean-clone] ERROR: No run_id returned!"
    exit 1
fi

echo "[clean-clone] Polling GET /v1/runs/${RUN_ID} until completion..."
POLL_RETRIES=30
POLL_COUNT=0
RUN_DONE=false

while [ $POLL_COUNT -lt $POLL_RETRIES ]; do
    RUN_DATA=$(curl -s http://localhost:8000/v1/runs/${RUN_ID})
    STATUS=$(python3 -c "import json; print(json.loads('''${RUN_DATA}''').get('status', ''))")
    echo "[clean-clone] Run ${RUN_ID} status: ${STATUS} ($((POLL_COUNT + 1))/$POLL_RETRIES)"
    if [ "$STATUS" = "completed" ]; then
        echo "[clean-clone] SUCCESS: Run finished with status: ${STATUS}"
        echo "[clean-clone] Final Run Payload:"
        python3 -m json.tool <<< "$RUN_DATA"

        echo "[clean-clone] Verifying ground truth reference case assertions..."
        python3 -c "
import json, sys
data = json.loads('''${RUN_DATA}''')
assert data.get('status') == 'completed', f'Status must be completed, got {data.get(\"status\")}'
assert data.get('routing') == 'expedited', f'Routing must be expedited, got {data.get(\"routing\")}'
assert data.get('seriousness', {}).get('is_serious') is True, 'Seriousness must be is_serious=True'
citations = data.get('citations', [])
assert len(citations) > 0, 'Citations list must not be empty'
print(f'  [PASS] Status: {data.get(\"status\")}')
print(f'  [PASS] Routing: {data.get(\"routing\")}')
print(f'  [PASS] Seriousness: is_serious={data.get(\"seriousness\", {}).get(\"is_serious\")}')
print(f'  [PASS] Citations: {len(citations)} verified citations')
"
        RUN_DONE=true
        break
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "escalated" ]; then
        echo "[clean-clone] Run failed or escalated unexpectedly: ${RUN_DATA}"
        exit 1
    fi
    sleep 2
    POLL_COUNT=$((POLL_COUNT + 1))
done

if [ "$RUN_DONE" != "true" ]; then
    echo "[clean-clone] ERROR: Run did not reach terminal state within timeout!"
    docker compose logs
    exit 1
fi

echo "======================================================================"
echo " PV-Triage Clean-Clone Verification PASSED End-to-End!"
echo "======================================================================"
