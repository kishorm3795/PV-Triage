# Operational Runbook: Critical Failure Recovery

This runbook documents confirmation diagnostics and recovery procedures for the two most critical operational failure modes in the PV-Triage platform.

---

## 1. Failure Mode 1: LLM Provider Outage / Circuit Breaker Open

### Symptom
- Client reports receiving delayed or degraded responses, or error alerts indicating LLM failure.
- Prometheus metric `circuit_breaker_state` changes from `0` (Closed) to `2` (Open).
- In Stub mode, `STUB_FAIL=true` triggers HTTP 500 responses from upstream provider.
- In Gemini mode, upstream network timeouts, rate limit exhaustion (HTTP 429), or 5xx server errors occur.

### Confirmation Diagnostics
Execute the following verification commands to inspect breaker state and upstream provider health:

1. **Check Circuit Breaker Prometheus Gauge:**
   ```bash
   curl -s http://localhost:8000/metrics | grep circuit_breaker_state
   ```
   - Value `0`: Closed (Normal operation).
   - Value `1`: Half-Open (Probing recovery).
   - Value `2`: Open (Traffic tripping breaker, shedding upstream calls).

2. **Probe Upstream Stub LLM Directly:**
   ```bash
   curl -s -i http://localhost:8001/health
   curl -s -X POST http://localhost:8001/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Test health check"}'
   ```
   - If HTTP 500 is returned with `"Simulated Stub LLM Failure (STUB_FAIL=true)"`, provider outage simulation is active.

3. **Check Worker Exception Logs:**
   ```bash
   docker logs pv-triage-worker-1 --tail 50 | grep -i "breaker\|llm"
   ```

### Recovery Procedure
1. **Disable Simulated Failure (if testing):**
   Ensure `STUB_FAIL=false` in `.env` or container environment:
   ```bash
   docker compose exec stub-llm sh -c "export STUB_FAIL=false"
   docker compose restart stub-llm
   ```
2. **Graceful Fallback Mode:**
   While breaker is open, the system invokes deterministic emergency fallbacks in `agents/run.py` and `llm/client.py`, ensuring unhandled exceptions are caught and escalated honestly rather than crashing jobs.
3. **Wait for Breaker Reset Window:**
   The circuit breaker automatically resets after `BREAKER_RESET_S=30` seconds into Half-Open state. Once consecutive successful probe calls succeed, the breaker transitions back to Closed (`circuit_breaker_state = 0`).

---

## 2. Failure Mode 2: Retrieval Index Missing or Stale

### Symptom
- `GET /health` on the API returns `HTTP 503 Service Unavailable` with `index_present: false`.
- Intake reports requiring semantic retrieval fail or escalate unexpectedly with empty citations.
- Prometheus metric `pv_index_chunk_count` drops to 0 or is absent.

### Confirmation Diagnostics
Execute the following diagnostic commands to verify index presence, timestamp, and metadata:

1. **Verify Index Metadata Presence:**
   ```bash
   cat data/chroma/index_meta.json
   ```
   - Must contain valid JSON with `build_time`, `embed_model`, `total_chunks`, and `source_docs`.

2. **Check API Health Dependency Endpoint:**
   ```bash
   curl -s http://localhost:8000/health
   ```
   Expected response:
   ```json
   {"status":"healthy","redis":true,"index_present":true,"index":true,"stub_llm":true,"version":"1.0.0"}
   ```
   If `index_present: false`, the API returns HTTP 503.

3. **Query Ingestion Prometheus Freshness Gauges:**
   ```bash
   curl -s http://localhost:8002/metrics | grep "pv_index"
   ```
   Verify `pv_index_build_timestamp_seconds` and `pv_index_chunk_count` (>700 chunks).

### Recovery Procedure
1. **Trigger Immediate Ingestion Rebuild:**
   Run the idempotent ingestion pipeline inside Docker Compose or the local environment:
   ```bash
   docker compose run --rm ingest python -m pipeline.ingest --force
   ```
   Or on local python runtime:
   ```bash
   python3 -m pipeline.ingest --force
   ```
2. **Verify Metadata Generation:**
   Check that `data/chroma/index_meta.json` was regenerated with updated timestamps:
   ```bash
   ls -la data/chroma/index_meta.json
   ```
3. **Restart API Service:**
   Once the index metadata is populated, reload the API container to restore 200 OK health status:
   ```bash
   docker compose restart api
   curl -s http://localhost:8000/health
   ```
