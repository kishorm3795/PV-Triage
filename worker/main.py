"""worker/main.py - Worker service entry point.

Listens to the 'runs' queue in Redis and processes triage jobs asynchronously.
Scalable across multiple container instances without fixed host ports.
"""

from __future__ import annotations

import os
import sys
import time
import redis
from rq import Queue, Worker


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"[worker] Starting RQ worker, connecting to {redis_url}...", flush=True)

    # Wait for redis connection with retry
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
