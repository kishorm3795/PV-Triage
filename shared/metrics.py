"""shared/metrics.py - Centralized Prometheus metrics definitions.

Defines all Prometheus metrics required for complete system observability across
API boundary, async job queue, and worker execution:
  1. request latency histogram (http_request_duration_seconds)
  2. end-to-end run latency (submit -> final) (pv_run_e2e_duration_seconds)
  3. error rate (pv_run_errors_total, http_requests_total)
  4. throughput (pv_runs_throughput_total)
  5. queue depth (pv_queue_depth)
  6. runs by status (pv_runs_by_status_total)
  7. escalations (pv_escalations_total)
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger("shared.metrics")

# 1. HTTP Request Latency Histogram
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds partitioned by endpoint",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# 2. End-to-End Run Latency (submit -> final status)
RUN_E2E_DURATION = Histogram(
    "pv_run_e2e_duration_seconds",
    "End-to-end run latency from submission/enqueued time to terminal status in seconds",
    ["status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0],
)

# 3. Error Rate Accounting
RUN_ERRORS_TOTAL = Counter(
    "pv_run_errors_total",
    "Total run errors and failures partitioned by error type",
    ["error_type"],
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received partitioned by method, endpoint, and status",
    ["method", "endpoint", "status"],
)

# 4. Throughput
RUNS_THROUGHPUT_TOTAL = Counter(
    "pv_runs_throughput_total",
    "Total runs processed to terminal state for throughput rate calculation",
    ["status"],
)

# 5. Queue Depth Gauge
QUEUE_DEPTH = Gauge(
    "pv_queue_depth",
    "Current number of pending triage runs in Redis queue",
)

# 6. Runs by Status
RUNS_BY_STATUS_TOTAL = Counter(
    "pv_runs_by_status_total",
    "Total triage runs partitioned by lifecycle status",
    ["status"],
)

# 7. Escalations
ESCALATIONS_TOTAL = Counter(
    "pv_escalations_total",
    "Total runs escalated to human review partitioned by reason category",
    ["reason"],
)

# Additional Worker Task Metrics
WORKER_TASK_DURATION = Histogram(
    "worker_task_duration_seconds",
    "Worker execution duration in seconds for triage graph",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

QUARANTINE_TOTAL = Counter(
    "pv_quarantine_total",
    "Total malformed reports quarantined by the intake boundary",
)

# Phase 6: Cost controls, caching, rate limiting, and circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state: 0=Closed, 1=Half-Open, 2=Open",
)
CIRCUIT_BREAKER_STATE.set(0)  # Default: Closed

REPORT_CACHE_HITS_TOTAL = Counter(
    "pv_report_cache_hits_total",
    "Total intake requests served from whole-run report cache",
)

REPORT_CACHE_MISSES_TOTAL = Counter(
    "pv_report_cache_misses_total",
    "Total intake requests missing report cache and sent to worker queue",
)

RATE_LIMIT_EXCEEDED_TOTAL = Counter(
    "pv_rate_limit_exceeded_total",
    "Total intake requests rejected with HTTP 429 rate limit exceeded",
    ["client_id"],
)


def record_run_e2e_latency(
    redis_client,
    run_id: str,
    final_status: str,
    finish_time_epoch: Optional[float] = None,
) -> Optional[float]:
    """Calculate and observe end-to-end latency from submit/queued time to final state.

    Args:
        redis_client: Redis connection client.
        run_id: Unique run identifier.
        final_status: Final execution status ('completed', 'escalated', 'failed').
        finish_time_epoch: Optional finish epoch timestamp. Defaults to now.

    Returns:
        Observed latency in seconds, or None if queued_at timestamp was unavailable.
    """
    if finish_time_epoch is None:
        finish_time_epoch = datetime.datetime.now(datetime.timezone.utc).timestamp()

    try:
        queued_iso = redis_client.get(f"run:{run_id}:queued_at") or redis_client.get(
            f"run:{run_id}:created_at"
        )
        if not queued_iso:
            return None

        # Parse ISO timestamp
        queued_dt = datetime.datetime.fromisoformat(queued_iso)
        queued_epoch = queued_dt.timestamp()
        e2e_seconds = max(0.0, finish_time_epoch - queued_epoch)

        RUN_E2E_DURATION.labels(status=final_status).observe(e2e_seconds)
        return e2e_seconds
    except Exception as exc:
        logger.debug("Could not record e2e latency for %s: %s", run_id, exc)
        return None
