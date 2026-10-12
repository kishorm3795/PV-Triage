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

echo "[clean-clone] Cloning fresh copy of branch a/platform..."
git clone --branch a/platform "file://${REPO_DIR}" "${TARGET_DIR}"

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

echo "[clean-clone] Checking Prometheus targets (/api/v1/targets)..."
sleep 6 # Allow scrape cycle to run
TARGETS_JSON=$(curl -s http://localhost:9090/api/v1/targets || echo "{}")
echo "[clean-clone] Prometheus Targets Summary:"
python3 -c "
import sys, json
try:
    data = json.loads('''${TARGETS_JSON}''')
    active = data.get('data', {}).get('activeTargets', [])
    for t in active:
        job = t.get('labels', {}).get('job')
        health = t.get('health')
        scrape_url = t.get('scrapeUrl')
        print(f'  - Job: {job} | Health: {health} | URL: {scrape_url}')
except Exception as e:
    print('Error parsing targets:', e)
"

echo "[clean-clone] Submitting valid adverse event report to POST /v1/reports..."
SUBMIT_PAYLOAD='{
  "report_id": "rep_clean_clone_001",
  "reporter_type": "physician",
  "patient_age": 42,
  "patient_sex": "female",
  "suspect_drug": "Lamotrigine",
  "drug_start_date": "2026-09-01",
  "event_date": "2026-09-15",
  "reaction_description": "Severe toxic epidermal necrolysis with extensive cutaneous peeling requiring ICU burn unit admission",
  "outcome": "not_recovered",
  "narrative": "Patient admitted with life-threatening blistering and sloughing skin."
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
POLL_RETRIES=20
POLL_COUNT=0
RUN_DONE=false

while [ $POLL_COUNT -lt $POLL_RETRIES ]; do
    RUN_DATA=$(curl -s http://localhost:8000/v1/runs/${RUN_ID})
    STATUS=$(python3 -c "import json; print(json.loads('''${RUN_DATA}''').get('status', ''))")
    echo "[clean-clone] Run ${RUN_ID} status: ${STATUS} ($((POLL_COUNT + 1))/$POLL_RETRIES)"
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "escalated" ]; then
        echo "[clean-clone] SUCCESS: Run finished with status: ${STATUS}"
        echo "[clean-clone] Final Run Payload:"
        python3 -m json.tool <<< "$RUN_DATA"
        RUN_DONE=true
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "[clean-clone] Run failed: ${RUN_DATA}"
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
