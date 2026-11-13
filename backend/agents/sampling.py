"""agents/sampling.py - Live Quality Sampling for Triage Runs (Phase 6 Member B).

Selects approximately 10% of completed production triage runs, evaluates them
using the evaluation scorers (Groundedness, Faithfulness, Citation Veracity),
and stores timestamped score records in Redis and SQLite for continuous quality charting.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import random
import sqlite3
import time
from typing import Any, Dict, Optional

from shared.contracts import RunResult

logger = logging.getLogger("agents.sampling")

DEFAULT_SAMPLE_RATE = float(os.getenv("LIVE_SAMPLE_RATE", "0.10"))
SAMPLING_DB_PATH = os.getenv("SAMPLING_DB_PATH", "data/sampling.db")


def init_sampling_sqlite(db_path: str = SAMPLING_DB_PATH) -> None:
    """Initialize SQLite database for persisting live quality scores."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quality_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE,
            timestamp TEXT,
            status TEXT,
            routing TEXT,
            groundedness REAL,
            faithfulness REAL,
            hallucination INTEGER,
            citations_count INTEGER,
            latency_ms REAL,
            raw_payload TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def score_completed_run(run_result: RunResult) -> Dict[str, Any]:
    """Score a completed triage run across core quality dimensions."""
    citations = run_result.citations
    hallucination = False
    verbatim_citations = 0

    if citations:
        for cit in citations:
            if not cit.passage_id or not cit.quote or "unsupported" in cit.passage_id:
                hallucination = True
            else:
                verbatim_citations += 1
    elif run_result.status == "completed" and run_result.routing in ("expedited", "periodic"):
        hallucination = True

    faithfulness = (verbatim_citations / len(citations)) if citations else (1.0 if run_result.status == "escalated" else 0.0)
    if hallucination:
        faithfulness = 0.0

    claims_supported = 0
    total_claims = 3
    if run_result.seriousness and len(citations) >= 1:
        claims_supported += 1
    if run_result.expectedness is not None:
        claims_supported += 1
    if run_result.routing in ("expedited", "periodic"):
        claims_supported += 1
    groundedness = claims_supported / total_claims if run_result.status == "completed" else 1.0

    # Calculate total latency from tool calls
    total_latency_ms = sum(tc.latency_ms for tc in run_result.tool_calls)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "run_id": run_result.run_id,
        "timestamp": now_iso,
        "status": run_result.status,
        "routing": run_result.routing,
        "groundedness": round(groundedness, 4),
        "faithfulness": round(faithfulness, 4),
        "hallucination": 1 if hallucination else 0,
        "citations_count": len(citations),
        "latency_ms": round(total_latency_ms, 2),
    }


def maybe_sample_run(
    run_result: RunResult,
    sample_rate: float = DEFAULT_SAMPLE_RATE,
    redis_client: Optional[Any] = None,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """Probabilistically evaluate a run (~10% sample) and persist the score record."""
    if not force and random.random() >= sample_rate:
        return None

    score_record = score_completed_run(run_result)
    logger.info(
        "Quality sample recorded for run %s: Groundedness=%.2f, Faithfulness=%.2f, Hallucination=%d",
        run_result.run_id,
        score_record["groundedness"],
        score_record["faithfulness"],
        score_record["hallucination"],
    )

    # 1. Store in Redis list for quick API consumption
    if redis_client is not None:
        try:
            payload_str = json.dumps(score_record)
            redis_client.lpush("sampling:scores", payload_str)
            redis_client.ltrim("sampling:scores", 0, 500)
        except Exception as exc:
            logger.debug("Redis sampling storage failed: %s", exc)

    # 2. Persist in SQLite
    try:
        init_sampling_sqlite()
        conn = sqlite3.connect(SAMPLING_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO quality_samples (
                run_id, timestamp, status, routing, groundedness,
                faithfulness, hallucination, citations_count, latency_ms, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score_record["run_id"],
                score_record["timestamp"],
                score_record["status"],
                score_record["routing"],
                score_record["groundedness"],
                score_record["faithfulness"],
                score_record["hallucination"],
                score_record["citations_count"],
                score_record["latency_ms"],
                json.dumps(score_record),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug("SQLite sampling persistence error: %s", exc)

    return score_record


def get_sampling_summary(limit: int = 50) -> Dict[str, Any]:
    """Retrieve quality sampling aggregate stats and recent sample rows."""
    try:
        init_sampling_sqlite()
        conn = sqlite3.connect(SAMPLING_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT raw_payload FROM quality_samples ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        samples = [json.loads(r[0]) for r in rows if r and r[0]]
        if not samples:
            return {"total_samples": 0, "avg_groundedness": 0.0, "avg_faithfulness": 0.0, "hallucination_rate": 0.0, "samples": []}

        avg_g = sum(s["groundedness"] for s in samples) / len(samples)
        avg_f = sum(s["faithfulness"] for s in samples) / len(samples)
        hall_rate = sum(s["hallucination"] for s in samples) / len(samples)

        return {
            "total_samples": len(samples),
            "avg_groundedness": round(avg_g, 4),
            "avg_faithfulness": round(avg_f, 4),
            "hallucination_rate": round(hall_rate, 4),
            "samples": samples,
        }
    except Exception as exc:
        logger.warning("Failed to retrieve sampling summary: %s", exc)
        return {"total_samples": 0, "error": str(exc), "samples": []}
