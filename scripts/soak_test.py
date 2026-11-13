"""scripts/soak_test.py - Soak Testing Script (Post-Phase Member B Task 1).

Executes 50 consecutive triage runs on the stub with mixed scenarios from
eval/scenarios.jsonl. Reports completed, escalated, and failed counts, and asserts
that ZERO runs returned a confident answer without passing verification.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

_backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from agents.run import run_graph
from shared.contracts import RunResult


def run_soak_test(num_runs: int = 50) -> int:
    scenarios_path = Path("eval/scenarios.jsonl")
    if not scenarios_path.exists():
        print("ERROR: eval/scenarios.jsonl not found!", file=sys.stderr)
        return 1

    with scenarios_path.open("r", encoding="utf-8") as f:
        scenarios = [json.loads(line) for line in f if line.strip()]

    print("================================================================================")
    print(f"                      PV-TRIAGE STABILITY SOAK TEST ({num_runs} RUNS)                   ")
    print(f"Scenarios Pool: {len(scenarios)} unique clinical and edge cases")
    print("================================================================================\n")

    counts = {"completed": 0, "escalated": 0, "failed": 0}
    unverified_confident_answers = 0
    t0 = time.perf_counter()

    for i in range(1, num_runs + 1):
        scen = random.choice(scenarios)
        report = scen["report"]
        run_id = f"soak_{i:03d}_{scen['scenario_id'].lower()}"

        res: RunResult = run_graph(report, run_id=run_id)
        status = res.status
        counts[status] = counts.get(status, 0) + 1

        # Global Rule 6: An unverified or incomplete run must never be returned as a confident answer
        if status == "completed":
            # Check citations
            if not res.citations or len(res.citations) == 0:
                unverified_confident_answers += 1
                print(f"[{i:03d}/{num_runs:03d}] VIOLATION: Run {run_id} completed without citations!")
            elif res.routing is None:
                unverified_confident_answers += 1
                print(f"[{i:03d}/{num_runs:03d}] VIOLATION: Run {run_id} completed without routing!")

        if i % 10 == 0 or i == num_runs:
            print(f"Progress: [{i:02d}/{num_runs}] | Completed: {counts['completed']} | Escalated: {counts['escalated']} | Failed: {counts['failed']}")

    elapsed = time.perf_counter() - t0
    avg_latency_ms = (elapsed / num_runs) * 1000.0

    print("\n--------------------------------------------------------------------------------")
    print("SOAK TEST RESULTS SUMMARY:")
    print("--------------------------------------------------------------------------------")
    print(f"  Total Runs Executed             : {num_runs}")
    print(f"  Completed Runs (Verified)       : {counts['completed']} ({counts['completed']/num_runs*100:.1f}%)")
    print(f"  Escalated Runs (Safe Rejections): {counts['escalated']} ({counts['escalated']/num_runs*100:.1f}%)")
    print(f"  Failed Runs                     : {counts['failed']} ({counts['failed']/num_runs*100:.1f}%)")
    print(f"  Unverified Confident Answers    : {unverified_confident_answers} (TARGET: MUST BE 0)")
    print(f"  Total Elapsed Time              : {elapsed:.2f}s (Avg: {avg_latency_ms:.1f}ms per run)")
    print("--------------------------------------------------------------------------------\n")

    if unverified_confident_answers > 0:
        print("❌ CRITICAL DEFECT: Unverified confident answers detected!", file=sys.stderr)
        return 1

    print("🎉 SOAK TEST PASSED: Zero unverified confident answers across 50 runs!")
    return 0


if __name__ == "__main__":
    sys.exit(run_soak_test(50))
