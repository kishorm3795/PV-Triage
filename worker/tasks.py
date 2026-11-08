"""worker/tasks.py - Background task processing using Redis, RQ, OpenTelemetry, and Prometheus."""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from typing import Any
import redis
from rq import Queue
from rq.timeouts import JobTimeoutException

from agents.run import run_graph
from api.logging_setup import set_correlation_id
from shared.contracts import Expectedness, RunResult, Seriousness
from shared.metrics import (
    ESCALATIONS_TOTAL,
    QUEUE_DEPTH,
    RUN_ERRORS_TOTAL,
    RUNS_BY_STATUS_TOTAL,
    RUNS_THROUGHPUT_TOTAL,
    WORKER_TASK_DURATION,
    record_run_e2e_latency,
)
from shared.telemetry import build_and_export_run_trace

logger = logging.getLogger("worker.tasks")


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
        error_type = "timeout"
    else:
        error_msg = f"Job failed: {exc_value}"
        error_type = "worker_exception"

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

        # Export trace and record telemetry
        start_epoch = time.time() - 1.0
        finish_epoch = time.time()
        build_and_export_run_trace(run_id, failed_res, start_epoch, finish_epoch, redis_client=r)
        record_run_e2e_latency(r, run_id, "failed", finish_time_epoch=finish_epoch)

        RUNS_BY_STATUS_TOTAL.labels(status="failed").inc()
        RUN_ERRORS_TOTAL.labels(error_type=error_type).inc()
    except Exception as e:
        logger.exception("Failed to record failure in Redis for job %s: %s", run_id, e)


def rq_exception_handler(job, exc_type, exc_value, traceback) -> bool:
    """RQ custom exception handler attached to Worker instance."""
    handle_job_failure(job, None, exc_type, exc_value, traceback)
    return True  # Proceed to RQ default exception handling


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
    RUNS_BY_STATUS_TOTAL.labels(status="running").inc()
    try:
        QUEUE_DEPTH.set(len(Queue("runs", connection=r)))
    except Exception:
        pass

    try:
        run_result = run_graph(report_data, run_id)
        finish_time = time.time()
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
            ESCALATIONS_TOTAL.labels(
                reason=run_result.escalation_reason or "escalated_to_human"
            ).inc()
        elif final_status == "failed":
            r.set(f"run:{run_id}:failed_at", finish_iso)
            r.set(f"run:{run_id}:error", run_result.escalation_reason or "Graph execution failed")
            r.lpush("failed:runs", run_id)
            RUN_ERRORS_TOTAL.labels(error_type="graph_failed").inc()

        if run_result.trace:
            r.set(
                f"run:{run_id}:trace",
                json.dumps([t.model_dump() for t in run_result.trace]),
            )
            for step in run_result.trace:
                logger.info(
                    "Agent step %d [%s:%s] completed (tokens=%d cost=$%.6f latency=%.1fms)",
                    step.step,
                    step.agent,
                    step.kind,
                    step.prompt_tokens + step.completion_tokens,
                    step.cost_usd,
                    step.latency_ms,
                    extra={"agent_step": step.step, "agent": step.agent, "kind": step.kind},
                )

        # Worker Hook: Build child spans per agent step and tool call, export to Jaeger and persist trace
        build_and_export_run_trace(
            run_id=run_id,
            run_result=run_result,
            start_time_epoch=start_time,
            finish_time_epoch=finish_time,
            redis_client=r,
        )

        duration = finish_time - start_time
        record_run_e2e_latency(r, run_id, final_status, finish_time_epoch=finish_time)
        RUNS_BY_STATUS_TOTAL.labels(status=final_status).inc()
        RUNS_THROUGHPUT_TOTAL.labels(status=final_status).inc()
        WORKER_TASK_DURATION.observe(duration)

        # Cache completed result for subsequent identical reports (Phase 6 cost control)
        if final_status == "completed":
            report_hash = r.get(f"run:{run_id}:report_hash")
            if report_hash:
                cache_ttl = int(os.getenv("REPORT_CACHE_TTL_S", "86400"))
                r.set(f"cache:report:{report_hash}", json.dumps(result_dict), ex=cache_ttl)
                logger.info("Cached completed triage result for hash %s (TTL=%ds)", report_hash, cache_ttl)

        try:
            QUEUE_DEPTH.set(len(Queue("runs", connection=r)))
        except Exception:
            pass

        logger.info(
            "Triage run %s finished with status %s in %.2fs",
            run_id,
            final_status,
            duration,
            extra={"status": final_status, "duration_s": duration},
        )
        return result_dict

    except Exception as exc:
        finish_time = time.time()
        duration = finish_time - start_time
        fail_iso = _get_utc_now_iso()
        error_reason = f"Worker exception: {str(exc)}"

        RUNS_BY_STATUS_TOTAL.labels(status="failed").inc()
        RUN_ERRORS_TOTAL.labels(error_type="worker_exception").inc()
        WORKER_TASK_DURATION.observe(duration)

        logger.exception(
            "Triage job %s failed with exception: %s",
            run_id,
            exc,
            extra={"error": str(exc), "duration_s": duration},
        )

        r.set(f"run:{run_id}:state", "failed")
        r.set(f"run:{run_id}:error", error_reason)
        r.set(f"run:{run_id}:failed_at", fail_iso)
        r.set(f"run:{run_id}:finished_at", fail_iso)
        r.set(f"run:{run_id}:updated_at", fail_iso)
        r.lpush("failed:runs", run_id)

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

        build_and_export_run_trace(
            run_id=run_id,
            run_result=failed_result,
            start_time_epoch=start_time,
            finish_time_epoch=finish_time,
            redis_client=r,
        )
        record_run_e2e_latency(r, run_id, "failed", finish_time_epoch=finish_time)
        raise
