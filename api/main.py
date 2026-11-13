"""api/main.py - FastAPI Intake Boundary, Schema Validation, Quarantine, and Observability Service.

Enforces strict input validation, quarantine of malformed requests, async job enqueuing
via Redis RQ with timeouts, run status tracking with timestamps, failed jobs registry,
OpenTelemetry tracing to Jaeger, Prometheus metrics, and full trace reconstruction.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import sqlite3
import time
import urllib.request
import uuid
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
import redis
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from rq import Queue
from rq.registry import FailedJobRegistry

from api.logging_setup import get_correlation_id, set_correlation_id, setup_logging
from api.models import AdverseEventReport
from shared.metrics import (
    CIRCUIT_BREAKER_STATE,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    QUEUE_DEPTH,
    QUARANTINE_TOTAL,
    RATE_LIMIT_EXCEEDED_TOTAL,
    REPORT_CACHE_HITS_TOTAL,
    REPORT_CACHE_MISSES_TOTAL,
    RUN_ERRORS_TOTAL,
    RUNS_BY_STATUS_TOTAL,
)
from shared.telemetry import (
    extract_queries_from_tool_calls,
    extract_retrieved_passage_ids,
    flush_telemetry,
    init_tracer,
)
from worker.tasks import handle_job_failure, process_triage_job

# Initialize structured JSON logging
logger = setup_logging("api")

# Initialize OpenTelemetry tracer for API service
tracer = init_tracer("api")

app = FastAPI(
    title="PV-Triage Intake Service",
    version="1.0.0",
    description="Pharmacovigilance Adverse Event Intake, Triage, and Observability API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def resolve_redis_url(redis_url: str) -> str:
    """Resolve Redis URL, falling back from container hostname 'redis' to localhost on host test runs."""
    try:
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(redis_url)
        if parsed.hostname == "redis":
            try:
                socket.gethostbyname("redis")
            except (socket.gaierror, OSError):
                return redis_url.replace("redis://redis:", "redis://localhost:")
    except Exception:
        pass
    return redis_url


def get_redis_client() -> redis.Redis:
    raw_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_url = resolve_redis_url(raw_url)
    return redis.from_url(redis_url, decode_responses=True)


def get_queue() -> Queue:
    redis_conn = get_redis_client()
    return Queue("runs", connection=redis_conn)


def _get_utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _load_trace_from_sqlite(run_id: str) -> Optional[dict]:
    """Retrieve persisted trace from SQLite database."""
    candidate_paths = [
        os.getenv("TRACES_DB_PATH"),
        "/app/data/traces/traces.db",
        "/app/data/traces.db",
        os.path.join(os.getcwd(), "data", "traces.db"),
        "traces.db",
    ]
    for p in candidate_paths:
        if p and os.path.exists(p):
            try:
                conn = sqlite3.connect(p)
                cursor = conn.cursor()
                cursor.execute("SELECT payload FROM traces WHERE run_id = ?", (run_id,))
                row = cursor.fetchone()
                conn.close()
                if row and row[0]:
                    return json.loads(row[0])
            except Exception as e:
                logger.debug("SQLite lookup error in %s: %s", p, e)
    return None


@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or f"req_{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    endpoint = request.url.path

    # Pass correlation_id in request state and logging context
    request.state.correlation_id = correlation_id
    set_correlation_id(correlation_id)

    # OpenTelemetry HTTP request span
    span_name = f"http_{request.method.lower()} {endpoint}"
    start_ns = int(start_time * 1e9)

    response: Optional[Response] = None
    try:
        with tracer.start_as_current_span(
            span_name,
            start_time=start_ns,
            attributes={
                "http.method": request.method,
                "http.route": endpoint,
                "correlation_id": correlation_id,
            },
        ) as span:
            response = await call_next(request)
            duration = time.time() - start_time
            status_code = str(response.status_code)

            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("duration_s", duration)

            # Record Prometheus Metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, endpoint=endpoint, status=status_code
            ).inc()
            HTTP_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)

            if response.status_code >= 500:
                RUN_ERRORS_TOTAL.labels(error_type=f"http_{status_code}").inc()

            response.headers["X-Correlation-ID"] = correlation_id
            return response
    except Exception as exc:
        duration = time.time() - start_time
        HTTP_REQUESTS_TOTAL.labels(method=request.method, endpoint=endpoint, status="500").inc()
        HTTP_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        RUN_ERRORS_TOTAL.labels(error_type="http_500_exception").inc()
        raise exc
    finally:
        flush_telemetry("api")


@app.get("/health")
def health():
    """Health check for service orchestration and Docker Compose dependencies."""
    redis_healthy = False
    stub_llm_healthy = False
    index_present = False

    # 1. Check Redis
    try:
        r = get_redis_client()
        redis_healthy = bool(r.ping())
    except Exception as e:
        logger.warning("Healthcheck: Redis unreachable (%s)", e)

    # 2. Check Index Presence (index_meta.json)
    chroma_dir = os.getenv("CHROMA_DIR", "/app/data/chroma")
    meta_candidates = [
        os.path.join(chroma_dir, "index_meta.json"),
        os.path.join(os.getcwd(), "data", "chroma", "index_meta.json"),
        "index_meta.json",
    ]
    index_present = any(os.path.exists(p) for p in meta_candidates)

    # 3. Check Stub LLM
    stub_base_url = os.getenv("LLM_BASE_URL", "http://stub-llm:8001")
    try:
        with urllib.request.urlopen(f"{stub_base_url}/health", timeout=1.0) as resp:
            stub_llm_healthy = resp.status == 200
    except Exception:
        stub_llm_healthy = False

    is_overall_healthy = redis_healthy and index_present
    status_code = status.HTTP_200_OK if is_overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_overall_healthy else "unhealthy",
            "redis": redis_healthy,
            "index_present": index_present,
            "index": index_present,
            "stub_llm": stub_llm_healthy,
            "version": "1.0.0",
        },
    )


@app.get("/metrics")
def metrics():
    """Expose Prometheus scraping metrics."""
    try:
        q = get_queue()
        QUEUE_DEPTH.set(len(q))
    except Exception:
        pass
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


RATE_LIMIT_LUA = """
local key_tokens = KEYS[1]
local key_ts = KEYS[2]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local last_tokens = tonumber(redis.call('get', key_tokens))
local last_ts = tonumber(redis.call('get', key_ts))

if last_tokens == nil then
    last_tokens = capacity
    last_ts = now
else
    local elapsed = math.max(0, now - last_ts)
    last_tokens = math.min(capacity, last_tokens + elapsed * refill_rate)
    last_ts = now
end

if last_tokens >= cost then
    last_tokens = last_tokens - cost
    redis.call('set', key_tokens, last_tokens, 'EX', 120)
    redis.call('set', key_ts, last_ts, 'EX', 120)
    return {1, 0, math.floor(last_tokens)}
else
    local needed = cost - last_tokens
    local retry_after = math.ceil(needed / refill_rate)
    if retry_after < 1 then retry_after = 1 end
    redis.call('set', key_tokens, last_tokens, 'EX', 120)
    redis.call('set', key_ts, last_ts, 'EX', 120)
    return {0, retry_after, 0}
end
"""


def check_rate_limit(r: redis.Redis, client_id: str, limit_per_min: int) -> tuple[bool, int]:
    """Check Redis token bucket rate limit for client. Returns (allowed, retry_after_seconds)."""
    if limit_per_min <= 0:
        return True, 0
    now = time.time()
    refill_rate = limit_per_min / 60.0
    key_tokens = f"ratelimit:{client_id}:tokens"
    key_ts = f"ratelimit:{client_id}:ts"
    try:
        res = r.eval(RATE_LIMIT_LUA, 2, key_tokens, key_ts, limit_per_min, refill_rate, now, 1)
        allowed = bool(res[0] == 1)
        retry_after = int(res[1])
        return allowed, retry_after
    except Exception as e:
        logger.warning("Redis rate limit evaluation failed: %s; allowing request", e)
        return True, 0


def compute_report_hash(report: AdverseEventReport) -> str:
    """Compute deterministic SHA-256 hash of normalized adverse event report."""
    reporter_val = (
        report.reporter_type.value
        if hasattr(report.reporter_type, "value")
        else str(report.reporter_type)
    )
    patient_sex_val = (
        (
            report.patient_sex.value
            if hasattr(report.patient_sex, "value")
            else str(report.patient_sex)
        )
        if report.patient_sex
        else None
    )
    outcome_val = (
        (report.outcome.value if hasattr(report.outcome, "value") else str(report.outcome))
        if report.outcome
        else None
    )

    norm = {
        "reporter_type": str(reporter_val).lower().strip(),
        "patient_age": report.patient_age,
        "patient_sex": str(patient_sex_val).lower().strip() if patient_sex_val else None,
        "suspect_drug": report.suspect_drug.strip().lower(),
        "drug_start_date": report.drug_start_date.isoformat() if report.drug_start_date else None,
        "event_date": report.event_date.isoformat() if report.event_date else None,
        "reaction_description": " ".join(report.reaction_description.strip().lower().split()),
        "outcome": str(outcome_val).lower().strip() if outcome_val else None,
        "narrative": " ".join(report.narrative.strip().lower().split())
        if report.narrative
        else None,
    }
    canonical_json = json.dumps(norm, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


@app.post("/v1/reports", status_code=status.HTTP_202_ACCEPTED)
async def submit_report(request: Request):
    """
    Intake boundary for adverse event reports.
    1. Enforces per-client token bucket rate limiting (RATE_LIMIT_PER_MIN) returning 429.
    2. Validates report schema: malformed quarantined with HTTP 422.
    3. Normalizes valid report and checks whole-run cache: cache hit returns HTTP 202 completed immediately.
    4. Cache miss enqueues RQ job with RUN_TIMEOUT_S timeout.
    """
    r = get_redis_client()

    # Step 0: Rate Limiting
    client_id = (
        request.headers.get("X-Client-ID")
        or request.headers.get("client-id")
        or (request.client.host if request.client else "anonymous")
    )
    rate_limit_per_min = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
    allowed, retry_after = check_rate_limit(r, client_id, rate_limit_per_min)
    if not allowed:
        RATE_LIMIT_EXCEEDED_TOTAL.labels(client_id=client_id).inc()
        HTTP_REQUESTS_TOTAL.labels(method="POST", endpoint="/v1/reports", status="429").inc()
        logger.warning(
            "Rate limit exceeded for client '%s' (limit=%d/min). Retry-After=%ds",
            client_id,
            rate_limit_per_min,
            retry_after,
            extra={"client_id": client_id, "retry_after": retry_after},
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                "retry_after": retry_after,
                "client_id": client_id,
            },
            headers={"Retry-After": str(retry_after)},
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Step 1: Validation
    try:
        report = AdverseEventReport.model_validate(body)
    except ValidationError as val_err:
        field_errors = []
        for err in val_err.errors():
            loc = [str(x) for x in err.get("loc", [])]
            field_errors.append(
                {
                    "loc": loc,
                    "msg": err.get("msg", "Validation error"),
                    "type": err.get("type", "value_error"),
                }
            )

        quarantine_id = body.get("report_id") or f"quar_{uuid.uuid4().hex[:8]}"
        cid = getattr(request.state, "correlation_id", quarantine_id)
        quarantine_record = {
            "quarantine_id": quarantine_id,
            "submitted_payload": body,
            "errors": field_errors,
            "quarantined_at": _get_utc_now_iso(),
            "correlation_id": cid,
        }

        # Store in Redis quarantine without touching the RQ queue
        r.set(f"quarantine:{quarantine_id}", json.dumps(quarantine_record))
        r.lpush("quarantine:reports", quarantine_id)
        QUARANTINE_TOTAL.inc()

        logger.warning(
            "Report rejected and quarantined (%s): %d errors",
            quarantine_id,
            len(field_errors),
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": field_errors,
                "quarantined": True,
                "quarantine_id": quarantine_id,
            },
        )

    # Step 2: Valid report -> Enqueue RQ job
    run_id = report.report_id
    set_correlation_id(run_id)  # Unify correlation_id = run_id across log stream
    request.state.correlation_id = run_id

    report_dict = report.model_dump(mode="json")
    now_iso = _get_utc_now_iso()

    # Step 2a: Report Normalization & Whole-Run Cache Check
    report_hash = compute_report_hash(report)
    cached_result_json = r.get(f"cache:report:{report_hash}")
    if cached_result_json:
        try:
            cached_result = json.loads(cached_result_json)
            cached_result["run_id"] = run_id
            r.set(f"run:{run_id}:state", "completed")
            r.set(f"run:{run_id}:result", json.dumps(cached_result))
            r.set(f"run:{run_id}:created_at", now_iso)
            r.set(f"run:{run_id}:queued_at", now_iso)
            r.set(f"run:{run_id}:started_at", now_iso)
            r.set(f"run:{run_id}:finished_at", now_iso)
            r.set(f"run:{run_id}:updated_at", now_iso)
            r.set(f"run:{run_id}:cached", "true")
            r.set(f"run:{run_id}:report", json.dumps(report_dict))
            r.set(f"run:{run_id}:report_hash", report_hash)
            REPORT_CACHE_HITS_TOTAL.inc()
            RUNS_BY_STATUS_TOTAL.labels(status="completed").inc()
            logger.info(
                "Cache hit for report %s (hash=%s). Reusing cached triage result.",
                run_id,
                report_hash,
                extra={"run_id": run_id, "cache_hit": True, "report_hash": report_hash},
            )
            return {
                "run_id": run_id,
                "status": "completed",
                "created_at": now_iso,
                "cached": True,
                "message": "Report matched existing cached triage assessment.",
            }
        except Exception as e:
            logger.warning("Failed to deserialize cached result for %s: %s", run_id, e)

    # Step 2b: Cache Miss -> Enqueue to RQ
    REPORT_CACHE_MISSES_TOTAL.inc()
    r.set(f"run:{run_id}:report_hash", report_hash)
    r.set(f"run:{run_id}:state", "queued")
    r.set(f"run:{run_id}:created_at", now_iso)
    r.set(f"run:{run_id}:queued_at", now_iso)
    r.set(f"run:{run_id}:updated_at", now_iso)
    r.set(f"run:{run_id}:report", json.dumps(report_dict))

    # Configure RQ timeout from environment
    run_timeout_s = int(os.getenv("RUN_TIMEOUT_S", "60"))

    # Enqueue to Redis RQ with timeout and failure callback
    q = Queue("runs", connection=r)
    job = q.enqueue(
        process_triage_job,
        run_id,
        report_dict,
        job_id=run_id,
        job_timeout=run_timeout_s,
        on_failure=handle_job_failure,
    )

    RUNS_BY_STATUS_TOTAL.labels(status="queued").inc()
    QUEUE_DEPTH.set(len(q))

    logger.info(
        "Enqueued valid report %s into queue 'runs' (job_id=%s, timeout=%ds)",
        run_id,
        job.id,
        run_timeout_s,
    )

    return {
        "run_id": run_id,
        "status": "queued",
        "created_at": now_iso,
        "message": "Report validated successfully and enqueued for triage assessment.",
    }


def _extract_run_payload(r: redis.Redis, run_id: str) -> dict[str, Any]:
    """Helper to assemble full run details and timestamps from Redis."""
    state = r.get(f"run:{run_id}:state") or "unknown"
    created_at = r.get(f"run:{run_id}:created_at") or r.get(f"run:{run_id}:queued_at")
    queued_at = r.get(f"run:{run_id}:queued_at") or created_at
    started_at = r.get(f"run:{run_id}:started_at") or r.get(f"run:{run_id}:running_at")
    running_at = r.get(f"run:{run_id}:running_at") or started_at
    completed_at = r.get(f"run:{run_id}:completed_at")
    escalated_at = r.get(f"run:{run_id}:escalated_at")
    failed_at = r.get(f"run:{run_id}:failed_at")
    finished_at = r.get(f"run:{run_id}:finished_at") or completed_at or escalated_at or failed_at
    updated_at = r.get(f"run:{run_id}:updated_at") or finished_at or started_at or created_at

    result = None
    result_raw = r.get(f"run:{run_id}:result")
    if result_raw:
        try:
            result = json.loads(result_raw)
        except Exception:
            result = result_raw

    error = r.get(f"run:{run_id}:error")

    timestamps = {
        "created_at": created_at,
        "queued_at": queued_at,
        "started_at": started_at,
        "running_at": running_at,
        "completed_at": completed_at,
        "escalated_at": escalated_at,
        "failed_at": failed_at,
        "finished_at": finished_at,
        "updated_at": updated_at,
    }

    return {
        "run_id": run_id,
        "status": state,
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "updated_at": updated_at,
        "timestamps": timestamps,
        "result": result,
        "error": error,
    }


@app.get("/v1/runs/{run_id}")
def get_run_status(run_id: str):
    """Retrieve execution status, lifecycle timestamps, and assessment results for a run."""
    r = get_redis_client()

    state = r.get(f"run:{run_id}:state")
    if not state:
        # Check if job exists in RQ failed registry
        try:
            q = Queue("runs", connection=r)
            failed_registry = FailedJobRegistry(queue=q)
            if run_id in failed_registry.get_job_ids():
                state = "failed"
                r.set(f"run:{run_id}:state", "failed")
        except Exception:
            pass

    if not state:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return _extract_run_payload(r, run_id)


@app.get("/v1/runs/{run_id}/trace")
def get_run_trace(run_id: str):
    """Retrieve full execution trace for a run.

    Returns every tool call, query, retrieved passage ids, prompt versions,
    per-step latency, tokens and cost, and verification outcome.
    Survives worker restarts via Redis and SQLite persistence.
    """
    r = get_redis_client()

    # 1. Try Redis cached full trace
    try:
        full_trace_raw = r.get(f"run:{run_id}:trace_full")
        if full_trace_raw:
            return json.loads(full_trace_raw)
    except Exception as exc:
        logger.debug("Redis trace_full lookup failed for %s: %s", run_id, exc)

    # 2. Try SQLite persisted trace
    sqlite_doc = _load_trace_from_sqlite(run_id)
    if sqlite_doc:
        return sqlite_doc

    # 3. Check if run exists in Redis state
    state = r.get(f"run:{run_id}:state")
    if not state:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    payload = _extract_run_payload(r, run_id)
    result = payload.get("result") or {}

    # If run finished but trace_full was not stored, reconstruct from stored result
    if result and isinstance(result, dict):
        tool_calls = result.get("tool_calls", [])
        trace_steps = result.get("trace", [])
        citations = result.get("citations", [])
        prompt_versions = result.get("prompt_versions", {})

        queries = extract_queries_from_tool_calls(tool_calls)
        retrieved_ids = extract_retrieved_passage_ids(tool_calls, citations)

        step_latencies = [
            {
                "step": s.get("step"),
                "agent": s.get("agent"),
                "kind": s.get("kind"),
                "latency_ms": s.get("latency_ms", 0.0),
            }
            for s in trace_steps
        ]

        tokens_per_step = [
            {
                "step": s.get("step"),
                "agent": s.get("agent"),
                "kind": s.get("kind"),
                "prompt_tokens": s.get("prompt_tokens", 0),
                "completion_tokens": s.get("completion_tokens", 0),
                "cost_usd": s.get("cost_usd", 0.0),
                "latency_ms": s.get("latency_ms", 0.0),
            }
            for s in trace_steps
        ]
        total_p = sum(s["prompt_tokens"] for s in tokens_per_step)
        total_c = sum(s["completion_tokens"] for s in tokens_per_step)
        total_cost = sum(s["cost_usd"] for s in tokens_per_step)

        verification_outcome = {
            "passed": (state == "completed"),
            "errors": [],
            "escalation_reason": result.get("escalation_reason"),
            "verified_citations": len(citations),
        }
        for s in trace_steps:
            d = s.get("detail", {})
            if isinstance(d, dict):
                if "verification_passed" in d:
                    verification_outcome["passed"] = bool(d["verification_passed"])
                if "verification_errors" in d:
                    verification_outcome["errors"] = d["verification_errors"]
                if "verified_citations" in d:
                    verification_outcome["verified_citations"] = d["verified_citations"]

        return {
            "run_id": run_id,
            "correlation_id": run_id,
            "status": state,
            "routing": result.get("routing"),
            "routing_basis": result.get("routing_basis"),
            "seriousness": result.get("seriousness", {}),
            "expectedness": result.get("expectedness", {}),
            "queries": queries,
            "retrieved_passage_ids": retrieved_ids,
            "prompt_versions": prompt_versions,
            "step_latencies": step_latencies,
            "tokens_and_cost": {
                "total_prompt_tokens": total_p,
                "total_completion_tokens": total_c,
                "total_tokens": total_p + total_c,
                "total_cost_usd": round(total_cost, 6),
                "per_step": tokens_per_step,
            },
            "verification_outcome": verification_outcome,
            "citations": citations,
            "tool_calls": tool_calls,
            "trace": trace_steps,
            "timestamps": payload.get("timestamps", {}),
        }

    # Run is queued or running and has no final result yet
    return {
        "run_id": run_id,
        "correlation_id": run_id,
        "status": state,
        "message": f"Run '{run_id}' is in state '{state}'. Trace details will be populated upon completion.",
        "queries": [],
        "retrieved_passage_ids": [],
        "prompt_versions": {},
        "step_latencies": [],
        "tokens_and_cost": {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "per_step": [],
        },
        "verification_outcome": {
            "passed": False,
            "errors": [],
            "escalation_reason": None,
            "verified_citations": 0,
        },
        "citations": [],
        "tool_calls": [],
        "trace": [],
        "timestamps": payload.get("timestamps", {}),
    }


@app.get("/v1/failed-jobs")
@app.get("/v1/runs/failed")
def list_failed_jobs(limit: int = 50):
    """List failed and timed-out jobs stored in the failed registry."""
    r = get_redis_client()
    failed_ids = set()

    # 1. From Redis failed runs list
    try:
        recorded = r.lrange("failed:runs", 0, limit)
        for rid in recorded:
            if rid:
                failed_ids.add(rid)
    except Exception as exc:
        logger.warning("Error fetching failed:runs from Redis: %s", exc)

    # 2. From RQ FailedJobRegistry
    try:
        q = Queue("runs", connection=r)
        registry = FailedJobRegistry(queue=q)
        for jid in registry.get_job_ids():
            failed_ids.add(jid)
    except Exception as exc:
        logger.warning("Error inspecting FailedJobRegistry: %s", exc)

    jobs = []
    for fid in list(failed_ids)[:limit]:
        job_data = _extract_run_payload(r, fid)
        jobs.append(job_data)

    return {
        "failed_jobs_count": len(jobs),
        "failed_jobs": jobs,
    }


@app.get("/v1/quarantine")
def list_quarantine():
    """List recent quarantined reports for inspection."""
    r = get_redis_client()
    ids = r.lrange("quarantine:reports", 0, 50)
    records = []
    for qid in ids:
        raw = r.get(f"quarantine:{qid}")
        if raw:
            try:
                records.append(json.loads(raw))
            except Exception:
                records.append({"quarantine_id": qid, "raw": raw})
    return {"quarantined_count": len(ids), "records": records}


class FeedbackRequest(BaseModel):
    """Payload for human evaluator feedback."""

    satisfactory: Optional[bool] = None
    rating: Optional[str] = None  # backwards compat: "thumbs_up" | "thumbs_down"
    reason: Optional[str] = None


FeedbackRequest.model_rebuild()


@app.post("/v1/runs/{run_id}/feedback")
async def record_feedback(run_id: str, feedback: FeedbackRequest):
    """Record qualified person feedback on a triage recommendation."""
    r = get_redis_client()
    state = r.get(f"run:{run_id}:state")
    if not state:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    is_sat = True
    if feedback.satisfactory is not None:
        is_sat = bool(feedback.satisfactory)
    elif feedback.rating is not None:
        is_sat = feedback.rating.lower() == "thumbs_up"

    rating_str = feedback.rating or ("thumbs_up" if is_sat else "thumbs_down")
    record = {
        "run_id": run_id,
        "satisfactory": is_sat,
        "rating": rating_str,
        "reason": feedback.reason,
        "recorded_at": _get_utc_now_iso(),
    }
    r.set(f"run:{run_id}:feedback", json.dumps(record))
    r.lpush("runs:feedback", json.dumps(record))
    logger.info("Feedback recorded for run %s: satisfactory=%s", run_id, is_sat)
    return {
        "status": "recorded",
        "run_id": run_id,
        "satisfactory": is_sat,
        "rating": rating_str,
        "reason": feedback.reason,
    }


@app.get("/v1/feedback/summary")
async def get_feedback_summary():
    """Retrieve statistical aggregate of human evaluator feedback."""
    r = get_redis_client()
    raw_items = r.lrange("runs:feedback", 0, -1)
    items = []
    sat_count = 0
    unsat_count = 0
    for item in raw_items:
        try:
            rec = json.loads(item)
            items.append(rec)
            if rec.get("satisfactory") is True:
                sat_count += 1
            elif rec.get("satisfactory") is False:
                unsat_count += 1
        except Exception:
            pass
    total = len(items)
    rate = (sat_count / total) if total > 0 else 0.0
    return {
        "total_feedback": total,
        "satisfactory_count": sat_count,
        "unsatisfactory_count": unsat_count,
        "satisfaction_rate": round(rate, 4),
        "recent_feedback": items[:50],
    }


# Mount the single-page clinical web client at "/"
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.isdir(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
