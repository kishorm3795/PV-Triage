"""api/main.py - FastAPI Intake Boundary, Schema Validation, and Quarantine Service.

Enforces strict input validation, quarantine of malformed requests, async job enqueuing
via Redis RQ with timeouts, run status tracking with timestamps, failed jobs registry,
Prometheus metrics, and service health checks.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
import urllib.request
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import redis
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from rq import Queue
from rq.registry import FailedJobRegistry

from api.logging_setup import get_correlation_id, set_correlation_id, setup_logging
from api.models import AdverseEventReport
from worker.tasks import handle_job_failure, process_triage_job

# Initialize structured JSON logging
logger = setup_logging("api")

app = FastAPI(
    title="PV-Triage Intake Service",
    version="1.0.0",
    description="Pharmacovigilance Adverse Event Intake and Triage API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics Definitions
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
)
RUNS_TOTAL = Counter(
    "pv_runs_total",
    "Total triage runs submitted",
    ["status"],
)
QUARANTINE_TOTAL = Counter(
    "pv_quarantine_total",
    "Total malformed reports quarantined",
)
QUEUE_DEPTH = Gauge(
    "pv_queue_depth",
    "Current number of pending runs in Redis queue",
)


def get_redis_client() -> redis.Redis:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


def get_queue() -> Queue:
    redis_conn = get_redis_client()
    return Queue("runs", connection=redis_conn)


def _get_utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or f"req_{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    # Pass correlation_id in request state and logging context
    request.state.correlation_id = correlation_id
    set_correlation_id(correlation_id)

    response = await call_next(request)
    duration = time.time() - start_time

    endpoint = request.url.path
    status_code = str(response.status_code)

    HTTP_REQUESTS_TOTAL.labels(
        method=request.method, endpoint=endpoint, status=status_code
    ).inc()
    HTTP_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)

    response.headers["X-Correlation-ID"] = correlation_id
    return response


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
            stub_llm_healthy = (resp.status == 200)
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


@app.post("/v1/reports", status_code=status.HTTP_202_ACCEPTED)
async def submit_report(request: Request):
    """
    Intake boundary for adverse event reports.
    Validates FIRST:
      - If invalid: quarantined in Redis with field-level errors, returns HTTP 422, enqueues NOTHING.
      - If valid: enqueues RQ job with RUN_TIMEOUT_S timeout, returns HTTP 202 with run_id immediately.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    r = get_redis_client()

    # Step 1: Validation
    try:
        report = AdverseEventReport.model_validate(body)
    except ValidationError as val_err:
        field_errors = []
        for err in val_err.errors():
            loc = [str(x) for x in err.get("loc", [])]
            field_errors.append({
                "loc": loc,
                "msg": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            })

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

    # Record initial queued state and timestamps
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

    RUNS_TOTAL.labels(status="queued").inc()
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
