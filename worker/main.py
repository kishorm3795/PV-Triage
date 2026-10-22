"""worker/main.py - Worker service entry point.

Listens to the 'runs' queue in Redis and processes triage jobs asynchronously.
Exposes Prometheus metrics endpoint on port 8002.
Scalable across multiple container instances without fixed host ports.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import redis
from rq import Queue, Worker

from api.logging_setup import setup_logging
from worker.tasks import rq_exception_handler

# Worker Prometheus Metrics
WORKER_JOBS_TOTAL = Counter(
    "worker_jobs_total",
    "Total triage jobs processed by worker instances",
    ["status"],
)
WORKER_JOB_DURATION = Histogram(
    "worker_job_duration_seconds",
    "Duration of triage graph execution in worker",
)
WORKER_ACTIVE_GAUGE = Gauge(
    "worker_active",
    "Worker heartbeat / liveness indicator",
)

logger = setup_logging("worker")


def main() -> None:
    # 1. Start Prometheus HTTP metrics exporter
    metrics_port = int(os.getenv("METRICS_PORT", "8002"))
    try:
        start_http_server(metrics_port)
        logger.info("Prometheus metrics exporter started on port %d", metrics_port)
    except Exception as exc:
        logger.warning("Prometheus metrics exporter could not bind port %d: %s", metrics_port, exc)

    WORKER_ACTIVE_GAUGE.set(1)

    # 2. Redis Connection with retry
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    logger.info("Starting RQ worker, connecting to %s...", redis_url)

    retries = 15
    conn = None
    while retries > 0:
        try:
            conn = redis.from_url(redis_url)
            conn.ping()
            logger.info("Connected to Redis successfully.")
            break
        except Exception as e:
            logger.warning("Redis not ready (%s), waiting 2s...", e)
            time.sleep(2)
            retries -= 1

    if conn is None:
        logger.error("Could not connect to Redis. Exiting.")
        sys.exit(1)

    queue = Queue("runs", connection=conn)
    worker = Worker(
        [queue],
        connection=conn,
        exception_handlers=[rq_exception_handler],
    )
    logger.info("RQ Worker initialized with timeout & failure handlers. Listening on queue 'runs'...")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
