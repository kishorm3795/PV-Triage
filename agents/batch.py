"""agents/batch.py - Batch evaluation runner for prompt version comparison.

Usage:
    python -m agents.batch --prompt-version v1 --set eval/scenarios.jsonl
    python -m agents.batch --prompt-version v2 --set agents/tests/fixtures/scenarios_local.jsonl

Outputs timestamped JSON results to agents/out/ (gitignored) with per-scenario details
and a summary table printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.run import run_graph, reset_graph
from agents.scoring import get_scorer, reset_scorer
from agents.tools import get_default_retriever, reset_retriever
from llm.resilience import reset_circuit_breaker
from shared.contracts import RunResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("agents.batch")

# Default fixtures path (B-owned fallback)
DEFAULT_FIXTURES_PATH = "agents/tests/fixtures/scenarios_local.jsonl"
# Official eval set path (C-owned, read-only)
OFFICIAL_EVAL_PATH = "eval/scenarios.jsonl"


def load_scenarios(path: str) -> List[Dict[str, Any]]:
    """Load scenarios from JSONL file."""
    scenarios = []
    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                scenario = json.loads(line)
                scenarios.append(scenario)
            except json.JSONDecodeError as e:
                logger.warning("Skipping invalid JSON on line %d: %s", line_num, e)
    return scenarios


def run_batch(
    scenarios: List[Dict[str, Any]],
    prompt_version: str,
    retriever_mode: str,
    scorer_mode: str,
) -> List[Dict[str, Any]]:
    """Run batch evaluation on scenarios."""
    results = []

    # Set environment for prompt version
    os.environ["PROMPT_VERSION"] = prompt_version
    os.environ["RETRIEVER"] = retriever_mode
    os.environ["SCORER"] = scorer_mode

    # Reset stateful components
    reset_graph()
    reset_circuit_breaker()
    reset_retriever()
    reset_scorer()

    scorer = get_scorer()
    retriever = get_default_retriever()

    for idx, scenario in enumerate(scenarios):
        run_id = f"batch_{prompt_version}_{retriever_mode}_{idx:04d}"

        # Extract report (exclude expected fields)
        report = {
            k: v
            for k, v in scenario.items()
            if k
            not in [
                "expected_routing",
                "expected_seriousness",
                "expected_expectedness",
                "expected_citations",
                "scenario_id",
            ]
        }

        if not report.get("report_id"):
            report["report_id"] = f"batch_{idx:04d}"

        logger.info("Running scenario %d/%d: %s", idx + 1, len(scenarios), run_id)

        # Run graph
        start_time = time.perf_counter()
        result = run_graph(report, run_id)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Get retrieved passages from tool calls
        retrieved_passages = []
        for tool_call in result.tool_calls:
            if tool_call.tool in ("search_corpus", "get_clause") and tool_call.ok:
                # Tool calls don't store passage objects directly, so we re-fetch
                # In a real scenario, we'd track retrieved passages in state
                pass

        # For scoring, we need the passages that were actually retrieved
        # Since tool calls only have summaries, we simulate by re-running retrieval
        # on the queries used (best effort for mock retriever)
        # In practice, the assessor_node stores retrieved_passages in state
        # but that's not in RunResult. We'll use a heuristic.

        # Score the result
        score = scorer.score(result, [])  # Pass empty for now; LocalScorer handles gracefully

        # Determine routing correctness if expected provided
        routing_correct = None
        if "expected_routing" in scenario:
            routing_correct = result.routing == scenario["expected_routing"]

        # Determine routing correctness if expected provided
        routing_correct = None
        if "expected_routing" in scenario:
            routing_correct = result.routing == scenario["expected_routing"]

        # Citation resolve rate (from score)
        citations_resolved = score.get("citation_resolve", False)

        # Verifier outcome (infer from trace)
        verifier_outcome = "skipped"
        for ts in result.trace:
            if ts.agent == "verifier" and isinstance(ts.detail, dict):
                verification = ts.detail.get("verification")
                if verification is not None:
                    verifier_outcome = "passed" if verification.get("ok") else "failed"
                    break

        result_dict = {
            "run_id": run_id,
            "scenario_id": scenario.get("scenario_id", f"scenario_{idx}"),
            "status": result.status,
            "routing": result.routing,
            "routing_basis": result.routing_basis,
            "seriousness": {
                "is_serious": result.seriousness.is_serious,
                "criteria": result.seriousness.criteria,
            },
            "expectedness": {
                "is_listed": result.expectedness.is_listed,
                "matched_term": result.expectedness.matched_term,
            },
            "citations_resolved": citations_resolved,
            "citations_count": len(result.citations),
            "verifier_outcome": verifier_outcome,
            "escalation_reason": result.escalation_reason,
            "steps": len(result.trace),
            "tool_calls": len(result.tool_calls),
            "total_tokens": sum(
                ts.prompt_tokens + ts.completion_tokens for ts in result.trace
            ),
            "prompt_tokens": sum(ts.prompt_tokens for ts in result.trace),
            "completion_tokens": sum(ts.completion_tokens for ts in result.trace),
            "cost_usd": sum(ts.cost_usd for ts in result.trace),
            "prompt_versions": result.prompt_versions,
            "elapsed_ms": elapsed_ms,
            "score": score,
            "routing_correct": routing_correct,
        }

        results.append(result_dict)

    return results


def print_summary(results: List[Dict[str, Any]], prompt_version: str) -> None:
    """Print a summary table of batch results."""
    print(f"\n{'='*100}")
    print(f"BATCH EVALUATION SUMMARY — PROMPT VERSION: {prompt_version}")
    print(f"{'='*100}")

    total = len(results)
    completed = sum(1 for r in results if r["status"] == "completed")
    escalated = sum(1 for r in results if r["status"] == "escalated")
    failed = sum(1 for r in results if r["status"] == "failed")

    routing_correct_count = sum(
        1 for r in results if r.get("routing_correct") is True
    )
    routing_total = sum(1 for r in results if r.get("routing_correct") is not None)

    citations_resolved_count = sum(
        1 for r in results if r.get("citations_resolved") is True
    )
    citations_total = sum(
        1 for r in results if r.get("citations_resolved") is not None
    )

    avg_tokens = (
        sum(r.get("total_tokens", 0) for r in results) / total if total > 0 else 0
    )
    avg_cost = sum(r.get("cost_usd", 0) for r in results) / total if total > 0 else 0
    avg_elapsed = (
        sum(r.get("elapsed_ms", 0) for r in results) / total if total > 0 else 0
    )

    print(f"Total Scenarios:     {total}")
    print(f"  Completed:         {completed}")
    print(f"  Escalated:         {escalated}")
    print(f"  Failed:            {failed}")
    print(f"")
    if routing_total > 0:
        print(
            f"Routing Correct:     {routing_correct_count}/{routing_total} ({routing_correct_count/routing_total*100:.1f}%)"
        )
    if citations_total > 0:
        print(
            f"Citations Resolved:  {citations_resolved_count}/{citations_total} ({citations_resolved_count/citations_total*100:.1f}%)"
        )
    print(f"Avg Tokens/Run:      {avg_tokens:.0f}")
    print(f"Avg Cost/Run:        ${avg_cost:.6f}")
    print(f"Avg Latency:         {avg_elapsed:.0f} ms")
    print(f"")

    # Per-scenario table
    print(
        f"{'#':>3}  {'Scenario ID':<30}  {'Status':<10}  {'Routing':<12}  {'Correct':<7}  {'Cites OK':<7}  {'Cost':<10}  {'Time':<8}"
    )
    print("-" * 100)
    for idx, r in enumerate(results):
        status = r["status"]
        routing = r["routing"] or "N/A"
        correct = "✓" if r.get("routing_correct") else ("✗" if r.get("routing_correct") is False else "?")
        cites = "✓" if r.get("citations_resolved") else ("✗" if r.get("citations_resolved") is False else "?")
        cost = f"${r.get('cost_usd', 0):.6f}"
        elapsed = f"{r.get('elapsed_ms', 0):.0f}ms"
        scenario_id = r.get("scenario_id", f"sc_{idx}")[:30]
        print(
            f"{idx+1:>3}  {scenario_id:<30}  {status:<10}  {routing:<12}  {correct:<7}  {cites:<7}  {cost:<10}  {elapsed:<8}"
        )

    print(f"{'='*100}\n")


def save_results(
    results: List[Dict[str, Any]], prompt_version: str, retriever_mode: str, scorer_mode: str
) -> Path:
    """Save results to timestamped JSON file in agents/out/."""
    out_dir = Path("agents/out")
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_{prompt_version}_{retriever_mode}_{scorer_mode}_{timestamp}.json"
    filepath = out_dir / filename

    output = {
        "metadata": {
            "prompt_version": prompt_version,
            "retriever_mode": retriever_mode,
            "scorer_mode": scorer_mode,
            "timestamp": timestamp,
            "total_scenarios": len(results),
        },
        "results": results,
    }

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("Results saved to %s", filepath)
    return filepath


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch evaluation runner for PV-Triage agent prompt versions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agents.batch --prompt-version v1
  python -m agents.batch --prompt-version v2 --set eval/scenarios.jsonl
  python -m agents.batch --prompt-version v1 --set agents/tests/fixtures/scenarios_local.jsonl --retriever real --scorer eval

Environment:
  LLM_TIMEOUT_S, LLM_MAX_ATTEMPTS, BREAKER_FAILS, BREAKER_RESET_S - LLM resilience config
  RETRIEVER=mock|real - Retrieval backend (default: mock)
  SCORER=local|eval - Scoring backend (default: local)
  PRICE_PER_1K_PROMPT, PRICE_PER_1K_COMPLETION - Cost calculation prices
        """,
    )

    parser.add_argument(
        "--prompt-version",
        required=True,
        choices=["v1", "v2"],
        help="Prompt version to evaluate (v1 or v2)",
    )
    parser.add_argument(
        "--set",
        dest="scenarios_path",
        default=None,
        help=f"Path to scenarios JSONL (default: {OFFICIAL_EVAL_PATH} if exists, else {DEFAULT_FIXTURES_PATH})",
    )
    parser.add_argument(
        "--retriever",
        choices=["mock", "real"],
        default=None,
        help="Retriever mode (default: from RETRIEVER env var or mock)",
    )
    parser.add_argument(
        "--scorer",
        choices=["local", "eval"],
        default=None,
        help="Scorer mode (default: from SCORER env var or local)",
    )
    parser.add_argument(
        "--output",
        help="Custom output file path (default: agents/out/batch_<version>_<timestamp>.json)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress summary table output",
    )

    args = parser.parse_args()

    # Determine scenarios path
    if args.scenarios_path:
        scenarios_path = args.scenarios_path
    elif Path(OFFICIAL_EVAL_PATH).exists():
        scenarios_path = OFFICIAL_EVAL_PATH
        logger.info("Using official eval set: %s", OFFICIAL_EVAL_PATH)
    else:
        scenarios_path = DEFAULT_FIXTURES_PATH
        logger.info("Using local fixtures: %s", DEFAULT_FIXTURES_PATH)

    if not Path(scenarios_path).exists():
        logger.error("Scenarios file not found: %s", scenarios_path)
        return 1

    # Load scenarios
    scenarios = load_scenarios(scenarios_path)
    if not scenarios:
        logger.error("No scenarios loaded from %s", scenarios_path)
        return 1

    logger.info("Loaded %d scenarios from %s", len(scenarios), scenarios_path)

    # Determine retriever and scorer modes
    retriever_mode = args.retriever or os.getenv("RETRIEVER", "mock")
    scorer_mode = args.scorer or os.getenv("SCORER", "local")

    logger.info(
        "Configuration: prompt_version=%s, retriever=%s, scorer=%s",
        args.prompt_version,
        retriever_mode,
        scorer_mode,
    )

    # Run batch
    try:
        results = run_batch(scenarios, args.prompt_version, retriever_mode, scorer_mode)
    except Exception as exc:
        logger.exception("Batch evaluation failed: %s", exc)
        return 1

    # Print summary
    if not args.quiet:
        print_summary(results, args.prompt_version)

    # Save results
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(
                {
                    "metadata": {
                        "prompt_version": args.prompt_version,
                        "retriever_mode": retriever_mode,
                        "scorer_mode": scorer_mode,
                        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                        "total_scenarios": len(results),
                    },
                    "results": results,
                },
                f,
                indent=2,
                default=str,
            )
        logger.info("Results saved to %s", out_path)
    else:
        save_results(results, args.prompt_version, retriever_mode, scorer_mode)

    return 0


if __name__ == "__main__":
    sys.exit(main())