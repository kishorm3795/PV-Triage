"""api/main.py - FastAPI Intake Boundary, Schema Validation, and Quarantine Service.

Enforces strict input validation, quarantine of malformed requests, async job enqueuing
via Redis RQ, run status polling, Prometheus metrics, and service health checks.
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

from api.models import AdverseEventReport
from worker.tasks import process_triage_job

# Logging configuration with correlation ID support
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [correlation_id=%(correlation_id)s] %(message)s",
)
logger = logging.getLogger("api.main")

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


@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or f"req_{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    # Pass correlation_id in request state
    request.state.correlation_id = correlation_id

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

    # Check Redis
    try:
        r = get_redis_client()
        redis_healthy = bool(r.ping())
    except Exception as e:
        logger.warning(f"Healthcheck: Redis unreachable ({e})", extra={"correlation_id": "health"})

    # Check Stub LLM
    stub_base_url = os.getenv("LLM_BASE_URL", "http://stub-llm:8001")
    try:
        with urllib.request.urlopen(f"{stub_base_url}/health", timeout=1.0) as resp:
            stub_llm_healthy = (resp.status == 200)
    except Exception as e:
        # In early phase or local test, stub_llm might not be up yet if tested in isolation
        stub_llm_healthy = False

    is_overall_healthy = redis_healthy
    status_code = status.HTTP_200_OK if is_overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_overall_healthy else "unhealthy",
            "redis": redis_healthy,
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
      - If valid: enqueues RQ job, returns HTTP 202 with run_id immediately.
    """
    correlation_id = getattr(request.state, "correlation_id", f"req_{uuid.uuid4().hex[:8]}")
    extra = {"correlation_id": correlation_id}

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    r = get_redis_client()

    # Step 1: Validation
    try:
        report = AdverseEventReport.model_validate(body)
    except ValidationError as val_err:
        # Format field errors
        field_errors = []
        for err in val_err.errors():
            loc = [str(x) for x in err.get("loc", [])]
            field_errors.append({
                "loc": loc,
                "msg": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            })

        # Generate quarantine identifier
        quarantine_id = body.get("report_id") or f"quar_{uuid.uuid4().hex[:8]}"
        quarantine_record = {
            "quarantine_id": quarantine_id,
            "submitted_payload": body,
            "errors": field_errors,
            "quarantined_at": datetime.datetime.utcnow().isoformat(),
            "correlation_id": correlation_id,
        }

        # Store in Redis quarantine without touching the RQ queue!
        r.set(f"quarantine:{quarantine_id}", json.dumps(quarantine_record))
        r.lpush("quarantine:reports", quarantine_id)
        QUARANTINE_TOTAL.inc()

        logger.warning(
            "Report rejected and quarantined (%s): %d errors",
            quarantine_id,
            len(field_errors),
            extra=extra,
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
    report_dict = report.model_dump(mode="json")

    # Record initial state
    r.set(f"run:{run_id}:state", "queued")
    r.set(f"run:{run_id}:created_at", str(time.time()))
    r.set(f"run:{run_id}:report", json.dumps(report_dict))

    # Enqueue to Redis RQ
    q = Queue("runs", connection=r)
    job = q.enqueue(process_triage_job, run_id, report_dict, job_id=run_id)

    RUNS_TOTAL.labels(status="queued").inc()
    QUEUE_DEPTH.set(len(q))

    logger.info("Enqueued valid report %s (job_id=%s)", run_id, job.id, extra=extra)

    return {
        "run_id": run_id,
        "status": "queued",
        "message": "Report validated successfully and enqueued for triage assessment.",
    }


@app.get("/v1/runs/{run_id}")
def get_run_status(run_id: str):
    """Retrieve execution status and result for a triage run."""
    r = get_redis_client()

    state = r.get(f"run:{run_id}:state")
    if not state:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    result = None
    result_raw = r.get(f"run:{run_id}:result")
    if result_raw:
        try:
            result = json.loads(result_raw)
        except Exception:
            result = result_raw

    error = r.get(f"run:{run_id}:error")

    return {
        "run_id": run_id,
        "status": state,
        "result": result,
        "error": error,
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
