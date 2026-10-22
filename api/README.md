# API Intake Gateway & Triage Service (`api/`)

**Owner:** Member A (Platform & Infrastructure)  
**Branch:** `a/platform`  
**Conforming Data Contracts:** [`shared/contracts.py`](file:///Users/pavankishorm/Documents/My%20Projects/PV-Triage/shared/contracts.py)

---

## 1. Architectural Overview & The Async + Queue Rationale

### Why Asynchronous Processing + Queue (Redis RQ)?

A central architectural mandate of the PV-Triage platform is that the intake gateway (`POST /v1/reports`) validates the report schema and immediately returns an asynchronous response (**HTTP 202 Accepted**) containing a deterministic `run_id`, while delegating graph execution to background Redis RQ workers.

#### The Problem with Synchronous Execution
1. **Multi-Agent Execution Latency:** A complete pharmacovigilance triage run is not a simple database lookup; it executes a multi-agent LangGraph workflow:
   - MedDRA / candidate term query expansion (`rewrite_query`)
   - Dense vector retrieval and clause lookup from ChromaDB (`search_corpus`, `get_clause`)
   - Multi-turn LLM reasoning and statutory drafting in the **Assessor Node**
   - Quote verification, passage provenance audit, and claim validation in the **Verifier Node**
   Under real-world LLM inference and retrieval, this workflow takes **tens of seconds** (typically 15 to 45 seconds).
2. **Reverse Proxy and Gateway Timeouts:** Standard API gateways, cloud load balancers (AWS ALB, GCP Cloud Load Balancing), and reverse proxies (Nginx, Cloudflare) enforce strict client timeout limits (commonly 30 or 60 seconds). Synchronous execution risks random `504 Gateway Timeout` errors under traffic fluctuations.
3. **Thread Pool & ASGI Starvation:** Synchronous blocking in FastAPI/Uvicorn worker threads rapidly depletes socket connections, crashing API responsiveness and causing cascading denial-of-service under even modest concurrent loads.
4. **Zero Backpressure or Durability:** If an un-queued service restarts or crashes mid-request, all in-flight assessments are permanently lost without retry or audit trails.

#### The Async + Redis RQ Solution
- **Decoupled Intake:** The API boundary validates statutory report schemas (`AdverseEventReport`), quaranitines malformed records without queuing, and enqueues valid payloads into Redis in **< 15 milliseconds**.
- **Resilient Backpressure:** Inbound traffic bursts buffer safely in Redis without saturating memory or worker compute.
- **Horizontal Scalability:** Worker containers scale horizontally without modifying code or API endpoints:
  ```bash
  docker compose up -d --scale worker=3
  ```
- **Guaranteed Timeout Enforcement:** Every job is bound by `RUN_TIMEOUT_S`. Jobs that exceed this deadline or encounter fatal exceptions land in the failed jobs registry (`/v1/failed-jobs`), preventing hanging processes and ensuring that unverified answers are never returned.

---

## 2. Run Lifecycle & State Machine

Every adverse event run moves through a deterministic state machine with full UTC ISO 8601 timestamp tracking:

```
[ POST /v1/reports ]
        │
        ├─► [ Invalid Schema ] ──► Quarantined in Redis (HTTP 422)
        │
        └─► [ Valid Report ] ──► Enqueued in Redis RQ (HTTP 202)
                                        │
                                        ▼ (state: "queued")
                              [ RQ Worker Picks Up ]
                                        │
                                        ▼ (state: "running")
                         [ LangGraph Multi-Agent Engine ]
                                        │
                ┌───────────────────────┼───────────────────────┐
                ▼                       ▼                       ▼
       [ Verification Passed ]    [ Escalated ]         [ Worker Crash / Timeout ]
                │                       │                       │
                ▼                       ▼                       ▼
       (state: "completed")    (state: "escalated")     (state: "failed")
```

### Supported Statuses
| Status | Description | Terminal? | Timestamps Captured |
| :--- | :--- | :--- | :--- |
| `queued` | Validated and placed onto the Redis `runs` queue. | No | `created_at`, `queued_at`, `updated_at` |
| `running` | Picked up by an active RQ worker; triage graph executing. | No | `started_at`, `running_at`, `updated_at` |
| `completed` | Triage completed and verified by the Verifier agent. | **Yes** | `completed_at`, `finished_at`, `updated_at` |
| `escalated` | Verifier detected ambiguity, out-of-corpus drug, or citation discrepancy. | **Yes** | `escalated_at`, `finished_at`, `updated_at` |
| `failed` | Worker exception, timeout (`RUN_TIMEOUT_S`), or system error. | **Yes** | `failed_at`, `finished_at`, `updated_at` |

---

## 3. Structured JSON Logging & Correlation Tracing

All API services and worker tasks use structured JSON logging ([`api/logging_setup.py`](file:///Users/pavankishorm/Documents/My%20Projects/PV-Triage/api/logging_setup.py)):
- Every log entry is emitted as a single-line JSON string containing:
  `timestamp`, `level`, `service`, `logger`, `correlation_id`, `message`, and contextual metrics.
- The `correlation_id` is set to `run_id` upon intake and propagates through the RQ job payload into the worker thread via Python `contextvars`.
- Any operator can filter logs across the entire cluster using:
  ```bash
  docker compose logs | grep '"correlation_id": "rep_ref_lamotrigine_001"'
  ```

---

## 4. API Endpoints Reference

### 1. `POST /v1/reports`
- **Request Body:** Validated against [`api/models.py:AdverseEventReport`](file:///Users/pavankishorm/Documents/My%20Projects/PV-Triage/api/models.py).
- **Responses:**
  - `HTTP 202 Accepted`: Enqueued successfully. Returns `{"run_id": "...", "status": "queued"}`.
  - `HTTP 422 Unprocessable Entity`: Schema failure. Quarantined in Redis without enqueuing.

### 2. `GET /v1/runs/{run_id}`
- Returns status, lifecycle timestamps (`timestamps` dict and top-level fields), assessment result, and error details.

### 3. `GET /v1/failed-jobs` (or `GET /v1/runs/failed`)
- Lists all failed or timed-out triage runs from both Redis `failed:runs` and RQ's `FailedJobRegistry`.

### 4. `GET /v1/quarantine`
- Returns recent quarantined payloads with field-level validation errors.

### 5. `GET /health`
- Verifies Redis connectivity, Stub LLM liveness, and Chroma index metadata presence.

### 6. `GET /metrics`
- Prometheus scrape endpoint exposing intake rate, queue depth, run outcomes, and processing latencies.
