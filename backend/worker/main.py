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
from prometheus_client import Gauge, start_http_server
import redis
from rq import Queue, SimpleWorker

from api.logging_setup import setup_logging
from shared.metrics import QUEUE_DEPTH
from worker.tasks import rq_exception_handler

logger = setup_logging("worker")

WORKER_ACTIVE_GAUGE = Gauge(
    "worker_active",
    "Worker heartbeat / liveness indicator",
)


def main() -> None:
    # 1. Start Prometheus HTTP metrics exporter on port 8002
    metrics_port = int(os.getenv("METRICS_PORT", "8002"))
    try:
        start_http_server(metrics_port)
        logger.info("Prometheus metrics exporter started on port %d", metrics_port)
    except Exception as exc:
        logger.warning("Prometheus metrics exporter could not bind port %d: %s", metrics_port, exc)

    WORKER_ACTIVE_GAUGE.set(1)

    # 2. Redis Connection with retry
    raw_redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        import socket
        from urllib.parse import urlparse
        parsed = urlparse(raw_redis_url)
        if parsed.hostname == "redis":
            try:
                socket.gethostbyname("redis")
                redis_url = raw_redis_url
            except (socket.gaierror, OSError):
                redis_url = raw_redis_url.replace("redis://redis:", "redis://localhost:")
        else:
            redis_url = raw_redis_url
    except Exception:
        redis_url = raw_redis_url
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
    try:
        QUEUE_DEPTH.set(len(queue))
    except Exception:
        pass

    worker = SimpleWorker(
        [queue],
        connection=conn,
        exception_handlers=[rq_exception_handler],
    )
    logger.info("RQ Worker initialized with timeout & failure handlers. Listening on queue 'runs'...")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
