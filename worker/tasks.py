"""worker/tasks.py - Background task processing using Redis and RQ."""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from typing import Any
from prometheus_client import Counter, Histogram
import redis
from rq.timeouts import JobTimeoutException

from agents.run import run_graph
from api.logging_setup import set_correlation_id
from shared.contracts import Expectedness, RunResult, Seriousness

logger = logging.getLogger("worker.tasks")

JOB_COUNTER = Counter(
    "worker_jobs_processed_total",
    "Total jobs processed by worker task execution",
    ["status"],
)
JOB_DURATION = Histogram(
    "worker_task_duration_seconds",
    "Task processing duration in seconds",
)


def get_redis_client() -> redis.Redis:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


def _get_utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def handle_job_failure(job, connection, exc_type, exc_value, traceback) -> None:
    """RQ on_failure callback: handles job timeout or unexpected termination."""
    run_id = getattr(job, "id", None) or "unknown_job"
    set_correlation_id(run_id)

    is_timeout = issubclass(exc_type, JobTimeoutException) if exc_type else False
    if is_timeout:
        error_msg = f"Job timed out: exceeded RUN_TIMEOUT_S limit ({exc_value})"
    else:
        error_msg = f"Job failed: {exc_value}"

    logger.error("RQ failure handler triggered for run %s: %s", run_id, error_msg)

    try:
        r = get_redis_client()
        now_iso = _get_utc_now_iso()

        r.set(f"run:{run_id}:state", "failed")
        r.set(f"run:{run_id}:error", error_msg)
        r.set(f"run:{run_id}:failed_at", now_iso)
        r.set(f"run:{run_id}:finished_at", now_iso)
        r.set(f"run:{run_id}:updated_at", now_iso)
        r.lpush("failed:runs", run_id)

        # Ensure RunResult is never confident for an incomplete or timed-out run
        failed_res = RunResult(
            run_id=run_id,
            status="failed",
            routing=None,
            routing_basis=None,
            seriousness=Seriousness(is_serious=False, criteria=[]),
            expectedness=Expectedness(is_listed=False, matched_term=None),
            citations=[],
            escalation_reason=error_msg,
            prompt_versions={},
            tool_calls=[],
            trace=[],
        )
        r.set(f"run:{run_id}:result", json.dumps(failed_res.model_dump()))
        JOB_COUNTER.labels(status="failed").inc()
    except Exception as e:
        logger.exception("Failed to record failure in Redis for job %s: %s", run_id, e)


def rq_exception_handler(job, exc_type, exc_value, traceback) -> bool:
    """RQ custom exception handler attached to Worker instance."""
    handle_job_failure(job, None, exc_type, exc_value, traceback)
    return True  # Proceed to RQ default exception handling (e.g., move to FailedJobRegistry)


def process_triage_job(run_id: str, report_data: dict[str, Any]) -> dict[str, Any]:
    """Execute triage graph for an adverse event report.

    Args:
        run_id: Unique identifier for the triage run (correlation_id).
        report_data: Validated adverse event payload dictionary.

    Returns:
        Serialized RunResult dictionary.
    """
    start_time = time.time()
    set_correlation_id(run_id)
    r = get_redis_client()
    now_iso = _get_utc_now_iso()

    logger.info("Picking up job %s from queue", run_id, extra={"run_id": run_id})

    # Transition state to running with timestamps
    r.set(f"run:{run_id}:state", "running")
    r.set(f"run:{run_id}:started_at", now_iso)
    r.set(f"run:{run_id}:running_at", now_iso)
    r.set(f"run:{run_id}:updated_at", now_iso)

    try:
        run_result = run_graph(report_data, run_id)
        result_dict = run_result.model_dump()
        finish_iso = _get_utc_now_iso()

        # Terminal state handling
        final_status = run_result.status
        r.set(f"run:{run_id}:state", final_status)
        r.set(f"run:{run_id}:result", json.dumps(result_dict))
        r.set(f"run:{run_id}:finished_at", finish_iso)
        r.set(f"run:{run_id}:updated_at", finish_iso)

        if final_status == "completed":
            r.set(f"run:{run_id}:completed_at", finish_iso)
        elif final_status == "escalated":
            r.set(f"run:{run_id}:escalated_at", finish_iso)
            r.set(f"run:{run_id}:error", run_result.escalation_reason or "Triage escalated")
        elif final_status == "failed":
            r.set(f"run:{run_id}:failed_at", finish_iso)
            r.set(f"run:{run_id}:error", run_result.escalation_reason or "Graph execution failed")
            r.lpush("failed:runs", run_id)

        if run_result.trace:
            r.set(
                f"run:{run_id}:trace",
                json.dumps([t.model_dump() for t in run_result.trace]),
            )

        duration = time.time() - start_time
        JOB_COUNTER.labels(status=final_status).inc()
        JOB_DURATION.observe(duration)

        logger.info(
            "Triage run %s finished with status %s in %.2fs",
            run_id,
            final_status,
            duration,
            extra={"status": final_status, "duration_s": duration},
        )
        return result_dict

    except Exception as exc:
        duration = time.time() - start_time
        JOB_COUNTER.labels(status="failed").inc()
        JOB_DURATION.observe(duration)

        logger.exception(
            "Triage job %s failed with exception: %s",
            run_id,
            exc,
            extra={"error": str(exc), "duration_s": duration},
        )

        fail_iso = _get_utc_now_iso()
        error_reason = f"Worker exception: {str(exc)}"

        r.set(f"run:{run_id}:state", "failed")
        r.set(f"run:{run_id}:error", error_reason)
        r.set(f"run:{run_id}:failed_at", fail_iso)
        r.set(f"run:{run_id}:finished_at", fail_iso)
        r.set(f"run:{run_id}:updated_at", fail_iso)
        r.lpush("failed:runs", run_id)

        # Store explicit unconfident failed result
        failed_result = RunResult(
            run_id=run_id,
            status="failed",
            routing=None,
            routing_basis=None,
            seriousness=Seriousness(is_serious=False, criteria=[]),
            expectedness=Expectedness(is_listed=False, matched_term=None),
            citations=[],
            escalation_reason=error_reason,
            prompt_versions={},
            tool_calls=[],
            trace=[],
        )
        r.set(f"run:{run_id}:result", json.dumps(failed_result.model_dump()))
        raise
