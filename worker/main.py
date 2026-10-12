"""worker/main.py - Worker service entry point.

Listens to the 'runs' queue in Redis and processes triage jobs asynchronously.
Exposes Prometheus metrics endpoint on port 8002.
Scalable across multiple container instances without fixed host ports.
"""

from __future__ import annotations

import os
import sys
import time
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import redis
from rq import Queue, Worker

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


def main() -> None:
    # 1. Start Prometheus HTTP metrics exporter
    metrics_port = int(os.getenv("METRICS_PORT", "8002"))
    try:
        start_http_server(metrics_port)
        print(f"[worker] Prometheus metrics exporter started on port {metrics_port}", flush=True)
    except Exception as exc:
        print(f"[worker] Notice: Prometheus metrics exporter could not bind port {metrics_port}: {exc}", flush=True)

    WORKER_ACTIVE_GAUGE.set(1)

    # 2. Redis Connection with retry
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"[worker] Starting RQ worker, connecting to {redis_url}...", flush=True)

    retries = 15
    conn = None
    while retries > 0:
        try:
            conn = redis.from_url(redis_url)
            conn.ping()
            print("[worker] Connected to Redis successfully.", flush=True)
            break
        except Exception as e:
            print(f"[worker] Redis not ready ({e}), waiting 2s...", flush=True)
            time.sleep(2)
            retries -= 1

    if conn is None:
        print("[worker] Could not connect to Redis. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)

    queue = Queue("runs", connection=conn)
    worker = Worker([queue], connection=conn)
    print("[worker] RQ Worker initialized. Listening on queue 'runs'...", flush=True)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
