"""loadtest/run_benchmarks.py - Automated benchmark runner for PV-Triage load testing.

Runs Locust headless across specified concurrency levels, collects exact metrics
from the generated CSVs for '[E2E] Complete Run (Submission to Result)', and
evaluates against the declared SLO (p95 <= 5000 ms).
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import time
from typing import Any, Dict, List

SLO_P95_MS = 5000.0  # 5.0 seconds declared in docs/SLO.md
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def parse_locust_csv(csv_prefix: str) -> Dict[str, Any]:
    """Parse the generated _stats.csv file for E2E and overall metrics."""
    stats_file = f"{csv_prefix}_stats.csv"
    if not os.path.exists(stats_file):
        raise FileNotFoundError(f"Missing Locust stats CSV: {stats_file}")

    e2e_row = None
    agg_row = None

    with open(stats_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "")
            req_type = row.get("Type", "")
            if "[E2E]" in name or req_type == "E2E":
                e2e_row = row
            if name == "Aggregated" or not req_type and name == "Aggregated":
                agg_row = row

    if not e2e_row:
        # Fallback to aggregated if custom metric missing
        e2e_row = agg_row

    if not e2e_row:
        return {}

    def _clean_float(val: Any, default: float = 0.0) -> float:
        if val in ("N/A", "", None):
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    req_count = int(_clean_float(e2e_row.get("Request Count", 0)))
    fail_count = int(_clean_float(e2e_row.get("Failure Count", 0)))
    rps = _clean_float(e2e_row.get("Requests/s", 0.0))
    p50_ms = _clean_float(e2e_row.get("50%", e2e_row.get("Median Response Time", 0.0)))
    p95_ms = _clean_float(e2e_row.get("95%", 0.0))
    avg_ms = _clean_float(e2e_row.get("Average Response Time", 0.0))
    max_ms = _clean_float(e2e_row.get("Max Response Time", 0.0))

    slo_met = (p95_ms <= SLO_P95_MS) and (fail_count == 0)

    return {
        "requests": req_count,
        "failures": fail_count,
        "rps": round(rps, 2),
        "p50_ms": round(p50_ms, 1),
        "p95_ms": round(p95_ms, 1),
        "avg_ms": round(avg_ms, 1),
        "max_ms": round(max_ms, 1),
        "slo_met": "MET" if slo_met else "NOT MET",
    }


def run_benchmark(
    concurrency: int,
    spawn_rate: int,
    duration_s: int,
    csv_prefix: str,
    host: str = "http://localhost:8000",
) -> Dict[str, Any]:
    """Execute a single headless Locust benchmark run."""
    cmd = [
        "locust",
        "-f",
        os.path.join(os.path.dirname(__file__), "locustfile.py"),
        "--headless",
        "-u",
        str(concurrency),
        "-r",
        str(spawn_rate),
        "-t",
        f"{duration_s}s",
        "--host",
        host,
        "--csv",
        csv_prefix,
        "--only-summary",
    ]
    print(f"\n>>> Running Locust: Concurrency={concurrency}, SpawnRate={spawn_rate}, Duration={duration_s}s...")
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0
    print(f"    Completed in {elapsed:.1f}s (exit_code={res.returncode})")

    metrics = parse_locust_csv(csv_prefix)
    metrics["concurrency"] = concurrency
    metrics["duration_s"] = duration_s
    return metrics


def run_suite(worker_count: int, test_matrix: List[Dict[str, int]]) -> List[Dict[str, Any]]:
    """Run a ladder of benchmarks for a specific worker configuration."""
    results = []
    for test in test_matrix:
        c = test["c"]
        r = test.get("r", c)
        d = test.get("d", 25)
        prefix = os.path.join(RESULTS_DIR, f"run_w{worker_count}_c{c}")
        data = run_benchmark(concurrency=c, spawn_rate=r, duration_s=d, csv_prefix=prefix)
        data["workers"] = worker_count
        results.append(data)
        time.sleep(2)  # Cooldown between runs
    return results


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)
    # Default 1-worker test ladder
    matrix_1w = [
        {"c": 1, "r": 1, "d": 20},
        {"c": 5, "r": 5, "d": 20},
        {"c": 10, "r": 10, "d": 25},
        {"c": 20, "r": 10, "d": 25},
        {"c": 30, "r": 15, "d": 30},
    ]
    print("Starting 1-worker benchmark ladder...")
    res_1w = run_suite(1, matrix_1w)
    print("\n--- 1 Worker Results ---")
    print(json.dumps(res_1w, indent=2))
