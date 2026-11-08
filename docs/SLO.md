# Service Level Objective (SLO): Complete Run Latency

## 1. Declared Target

| Metric | Target | Scope | Status |
| :--- | :--- | :--- | :--- |
| **p95 Complete Run Latency** | **≤ 5.0 seconds** | End-to-end: `POST /v1/reports` ingestion to terminal status (`completed` / `escalated` / `failed`) on `GET /v1/runs/{id}` | **Declared Prior to Load Testing** |
| **p50 Nominal Latency** | **≤ 1.0 second** | Uncontended / low-concurrency baseline | Declared Baseline |
| **Maximum Run Timeout** | **30.0 seconds** | Hard timeout cutoff via `RUN_TIMEOUT_S=30` | Enforced Circuit/Worker Bound |

> **Requirement Compliance (D6):** This target is declared and committed **prior** to executing any Locust load tests. Under no circumstances will this target be retroactively modified after observing load test results.

---

## 2. Justification Against Section 1 of the Brief

Section 1 of the project brief (*Mini Project 14 — Pharmacovigilance Adverse Event Intake and Triage Service*) defines the statutory operating context:
1. **Statutory Deadlines**: Adverse event reports arriving from clinicians, patients, and literature must be evaluated for seriousness and expectedness. Serious Unexpected Serious Adverse Reactions (SUSARs) require **expedited reporting** to the licensing authority (e.g., Central Drugs Standard Control Organisation under NDCT Rules 2019 Second Schedule Table 1) within **fifteen (15) calendar days** of receipt. Other events are scheduled for periodic safety update reports (PSURs).
2. **Zero Breach Tolerance**: Missing an expedited reporting deadline constitutes an adverse regulatory finding.
3. **Triage Latency vs. Statutory Envelope**: A p95 latency of **5.0 seconds** represents **0.00038%** of the 15-day (360-hour) regulatory envelope. The automated intake and triage system consumes a negligible fraction of the compliance window, reserving virtually the entire statutory period for medical review, case reconciliation, and formal regulatory dispatch.
4. **Promptness for the Qualified Person (QPPV)**: The automated triage service is a decision-support tool, not an autonomous regulatory submitter. A human safety officer (QPPV or safety evaluator) reviews each recommendation alongside its cited package-insert clauses during interactive intake sessions. To maintain an acceptable interactive operator experience and prevent case backlog accumulation during intake surges (e.g. literature batch ingests), the triage result must be available within seconds, well under the interactive threshold of 5.0 seconds.

---

## 3. Stub Delay Configuration

* **LLM Provider**: `LLM_PROVIDER=stub` (simulated deterministic inference service via `stub_llm`).
* **Configured Delay**: `STUB_DELAY_MS = 50` ms per generation request.
* **Model Step Latency**:
  * Assessor Agent: 1 generation call (`~50ms`).
  * Verifier Agent: 1 audit/generation call (`~50ms`).
  * Total LLM component time per run: **~100 ms**.
* **Rationale**: Eliminates external commercial API rate limits and network jitter, ensuring that load measurements reflect the true platform architecture (FastAPI, Redis RQ, Chroma vector search, and container concurrency).

---

## 4. Architectural Assumptions & System Boundaries

1. **Measurement Definition**:
   * Latency is **not** the 202 Accepted response from `POST /v1/reports` (which executes in `< 10ms`).
   * Latency is the **complete run elapsed time**:
     $$\text{Latency} = T_{\text{terminal}} - T_{\text{submission}}$$
     where $T_{\text{submission}}$ is the timestamp when the client initiates the `POST /v1/reports` request, and $T_{\text{terminal}}$ is the timestamp when polling `GET /v1/runs/{id}` returns `status \in {"completed", "escalated", "failed"}`.
2. **Pipeline Components Involved in Each Run**:
   * **API Ingestion**: Request receipt, Pydantic v2 schema & cross-field validation, Redis RQ enqueueing (`~5-15ms`).
   * **Queue & Dispatch**: Redis RQ job queue latency (contended during high concurrency).
   * **Worker Processing**:
     * Query rewriting & entity normalization.
     * Chroma vector retrieval with local sentence embedding (`all-MiniLM-L6-v2` on CPU) (`~30-80ms`).
     * Assessor LLM generation via `stub-llm` (`~50ms`).
     * Verifier clause retrieval & citation consistency check (`~10-20ms`).
     * OpenTelemetry span building and export to Jaeger (`~10-20ms`).
     * Redis state and trace persistence (`~5-10ms`).
3. **Nominal Single-Run Uncontended Baseline**:
   * Approximately **180 ms - 250 ms** end-to-end.
4. **Concurrency & Scaling Failure Hypotheses**:
   * With **1 worker container** (single-threaded RQ worker process), the system processes requests sequentially. At concurrency > 5-10, incoming requests will accumulate in the Redis queue (`runs`), causing queue wait time to increase linearly with concurrency.
   * We predict the 1-worker setup will meet the 5.0s p95 SLO at low-to-moderate concurrency (1 to ~10 concurrent users), but will breach the 5.0s SLO as concurrency rises to 15-20 users due to worker CPU/process serialization.
   * Scaling to **3 workers** (`docker compose up --scale worker=3`) should triple dequeue capacity, significantly reducing queue wait times and extending the concurrency threshold before SLO breach.
