"""worker/tasks.py - Background task processing using Redis and RQ."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
import redis

# NOTE: When Member B merges, swap this single import:
# from agents.run import run_graph
from worker.placeholder import run_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [correlation_id=%(correlation_id)s] %(message)s",
)
logger = logging.getLogger("worker.tasks")


def get_redis_client() -> redis.Redis:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


def process_triage_job(run_id: str, report_data: dict[str, Any]) -> dict[str, Any]:
    """Execute triage graph for an adverse event report."""
    r = get_redis_client()
    extra = {"correlation_id": run_id}
    logger.info("Picking up job %s from queue", run_id, extra=extra)

    # Transition state to running
    r.set(f"run:{run_id}:state", "running")
    r.set(f"run:{run_id}:updated_at", str(time.time()))

    try:
        run_result = run_graph(report_data, run_id)
        result_dict = run_result.model_dump()

        # Persist result and terminal state
        r.set(f"run:{run_id}:result", json.dumps(result_dict))
        r.set(f"run:{run_id}:state", run_result.status)
        r.set(f"run:{run_id}:updated_at", str(time.time()))

        if run_result.trace:
            r.set(
                f"run:{run_id}:trace",
                json.dumps([t.model_dump() for t in run_result.trace]),
            )

        logger.info(
            "Triage run %s finished successfully with status %s",
            run_id,
            run_result.status,
            extra=extra,
        )
        return result_dict
    except Exception as exc:
        logger.exception("Triage job %s failed: %s", run_id, exc, extra=extra)
        r.set(f"run:{run_id}:state", "failed")
        r.set(f"run:{run_id}:error", str(exc))
        r.set(f"run:{run_id}:updated_at", str(time.time()))
        raise
