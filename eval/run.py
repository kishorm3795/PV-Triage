"""eval/run.py - CLI evaluation harness for PV-Triage multi-agent workflows.

Usage:
    python -m eval.run --prompt-version v1 [--set eval/scenarios.jsonl] [--direct] [--force-invalid]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from eval.metrics import evaluate_run
from pipeline.retrieval import get_retriever, search

logger = logging.getLogger("eval.run")


def run_scenario_direct(
    scenario: Dict[str, Any],
    run_id: str,
    prompt_version: str,
    force_invalid: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute scenario directly in-process via agents.run.run_graph."""
    os.environ["PROMPT_VERSION"] = prompt_version
    os.environ["RETRIEVER"] = "real"

    from agents.run import reset_graph, run_graph

    reset_graph()

    report = dict(scenario["report"])
    if force_invalid:
        report["force_invalid_citation"] = True

    result = run_graph(report, run_id)
    result_dict = result.model_dump()

    # Extract retrieved passages from tool calls or direct search
    retrieved_passages: List[Dict[str, Any]] = []
    seen_ids = set()

    for tc in result.tool_calls:
        if tc.tool in ("search_corpus", "get_clause"):
            # Query tool retriever directly for matching text
            q = tc.input.get("query") if isinstance(tc.input, dict) else None
            cid = tc.input.get("clause_id") if isinstance(tc.input, dict) else None
            if q:
                passages = search(q, k=5)
                for p in passages:
                    if p.id not in seen_ids:
                        retrieved_passages.append(p.model_dump() if hasattr(p, "model_dump") else p.__dict__)
                        seen_ids.add(p.id)
            elif cid:
                retriever = get_retriever()
                p = retriever.get_clause(cid)
                if p and p.id not in seen_ids:
                    retrieved_passages.append(p.model_dump() if hasattr(p, "model_dump") else p.__dict__)
                    seen_ids.add(p.id)

    return result_dict, retrieved_passages


def run_scenario_api(
    scenario: Dict[str, Any],
    api_url: str,
    prompt_version: str,
    force_invalid: bool = False,
    timeout_s: float = 30.0,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute scenario via HTTP API -> queue -> worker -> graph."""
    import requests

    report = dict(scenario["report"])
    if force_invalid:
        report["force_invalid_citation"] = True

    headers = {
        "Content-Type": "application/json",
        "X-Client-ID": f"eval-harness-{int(time.time())}",
    }

    # Submit report to intake boundary
    resp = requests.post(f"{api_url}/v1/reports", json=report, headers=headers, timeout=10)
    if resp.status_code not in (200, 202):
        return {
            "status": "failed",
            "routing": None,
            "citations": [],
            "escalation_reason": f"API intake returned HTTP {resp.status_code}: {resp.text}",
        }, []

    run_id = report.get("report_id")

    # Poll run status until completed / escalated / timeout
    start_time = time.time()
    result_dict: Dict[str, Any] = {}
    while time.time() - start_time < timeout_s:
        run_resp = requests.get(f"{api_url}/v1/runs/{run_id}", headers=headers, timeout=5)
        if run_resp.status_code == 200:
            data = run_resp.json()
            run_status = data.get("status")
            if run_status in ("completed", "escalated", "failed"):
                result_dict = data.get("result") or data
                break
        time.sleep(0.5)

    if not result_dict:
        return {
            "status": "failed",
            "routing": None,
            "citations": [],
            "escalation_reason": f"Run {run_id} timed out after {timeout_s}s in worker queue",
        }, []

    # Query trace for retrieved passage metadata
    retrieved_passages: List[Dict[str, Any]] = []
    seen_ids = set()
    try:
        trace_resp = requests.get(f"{api_url}/v1/runs/{run_id}/trace", headers=headers, timeout=5)
        if trace_resp.status_code == 200:
            trace_data = trace_resp.json()
            tool_calls = trace_data.get("tool_calls", [])
            for tc in tool_calls:
                if tc.get("tool") in ("search_corpus", "get_clause"):
                    inp = tc.get("input", {})
                    q = inp.get("query")
                    cid = inp.get("clause_id")
                    if q:
                        passages = search(q, k=5)
                        for p in passages:
                            if p.id not in seen_ids:
                                retrieved_passages.append(p.model_dump() if hasattr(p, "model_dump") else p.__dict__)
                                seen_ids.add(p.id)
                    elif cid:
                        p = get_retriever().get_clause(cid)
                        if p and p.id not in seen_ids:
                            retrieved_passages.append(p.model_dump() if hasattr(p, "model_dump") else p.__dict__)
                            seen_ids.add(p.id)
    except Exception as exc:
        logger.debug("Failed querying trace for %s: %s", run_id, exc)

    return result_dict, retrieved_passages


def main():
    parser = argparse.ArgumentParser(description="PV-Triage Evaluation Harness")
    parser.add_argument("--prompt-version", default="v1", help="Prompt version tag to evaluate (e.g. v1, v2)")
    parser.add_argument("--set", default="eval/scenarios.jsonl", help="Path to scenario JSONL dataset")
    parser.add_argument("--direct", action="store_true", help="Execute in-process direct graph call instead of API")
    parser.add_argument("--force-invalid", action="store_true", help="Enable B's deliberate change: force invalid citations")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base URL of live API")
    parser.add_argument("--out", default=None, help="Output JSON path")
    args = parser.parse_args()

    scenarios_path = Path(args.set)
    if not scenarios_path.exists():
        print(f"Error: Scenarios file not found at {scenarios_path}", file=sys.stderr)
        sys.exit(1)

    scenarios: List[Dict[str, Any]] = []
    with open(scenarios_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                scenarios.append(json.loads(line))

    llm_provider = os.getenv("LLM_PROVIDER", "stub")
    mode_str = "direct (in-process run_graph)" if args.direct else f"full-stack API ({args.api_url})"
    print(f"======================================================================")
    print(f"PV-Triage Benchmark Evaluation")
    print(f"Dataset:        {args.set} ({len(scenarios)} scenarios)")
    print(f"Prompt Version: {args.prompt_version}")
    print(f"Execution Mode: {mode_str}")
    print(f"LLM Provider:   {llm_provider}")
    print(f"Deliberate Hook:{'FORCE_INVALID_CITATION=True' if args.force_invalid else 'None (Normal)'}")
    print(f"======================================================================")

    results: List[Dict[str, Any]] = []
    start_time = time.time()

    for idx, scen in enumerate(scenarios, 1):
        scen_id = scen.get("id", f"scen_{idx}")
        run_id = f"eval_{args.prompt_version}_{scen_id}_{int(time.time())}"
        print(f"[{idx:02d}/{len(scenarios):02d}] Evaluating {scen_id:<38} ... ", end="", flush=True)

        scen_start = time.time()
        if args.direct:
            run_result, retrieved = run_scenario_direct(scen, run_id, args.prompt_version, args.force_invalid)
        else:
            run_result, retrieved = run_scenario_api(scen, args.api_url, args.prompt_version, args.force_invalid)
        latency = round(time.time() - scen_start, 3)

        eval_metric = evaluate_run(scen, run_result, retrieved)
        eval_metric["latency_s"] = latency
        results.append(eval_metric)

        status_flag = "PASS" if eval_metric["passed"] else "FAIL"
        print(f"[{status_flag}] ({latency}s)")

    total_time = round(time.time() - start_time, 2)

    # Compute aggregate metrics
    answered_runs = [r for r in results if r["expected_action"] == "answer"]
    escalated_runs = [r for r in results if r["expected_action"] == "escalate"]

    avg_groundedness = round(sum(r["groundedness"] for r in results) / len(results), 4)
    avg_context_rel = round(sum(r["context_relevance"] for r in results) / len(results), 4)
    avg_faithfulness = round(sum(r["faithfulness"] for r in results) / len(results), 4)
    hallucination_rate = round(sum(r["hallucination"] for r in results) / len(results), 4)

    routing_acc = (
        round(sum(1 for r in answered_runs if r["routing_match"]) / len(answered_runs), 4)
        if answered_runs
        else 1.0
    )
    escalate_rate = (
        round(sum(1 for r in escalated_runs if r["escalation_match"]) / len(escalated_runs), 4)
        if escalated_runs
        else 1.0
    )

    passed_count = sum(1 for r in results if r["passed"])

    print("\n" + "=" * 70)
    print(f"EVALUATION SUMMARY: {passed_count}/{len(results)} Scenarios Passed ({passed_count/len(results)*100:.1f}%)")
    print("=" * 70)
    print(f"  * Groundedness:           {avg_groundedness * 100:6.2f}% (claims supported by retrieved text)")
    print(f"  * Context Relevance:      {avg_context_rel * 100:6.2f}% (semantic alignment of passages)")
    print(f"  * Faithfulness:           {avg_faithfulness * 100:6.2f}% (verbatim citation agreement)")
    print(f"  * Hallucination Rate:     {hallucination_rate * 100:6.2f}% (unsupported or fabricated citations)")
    print(f"  * Routing Accuracy:       {routing_acc * 100:6.2f}% (on answerable scenarios)")
    print(f"  * Correct-Escalation Rate:{escalate_rate * 100:6.2f}% (on out-of-scope / unsafe scenarios)")
    print(f"  * Total Evaluation Time:  {total_time}s")
    print("=" * 70)

    # List failures if any
    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"\nPer-Scenario Failures ({len(failures)} total):")
        for f in failures:
            print(f"  - [{f['scenario_id']}]: expected {f['expected_action']}/{f['expected_routing']}, "
                  f"got {f['actual_status']}/{f['actual_routing']} (Reason: {f.get('escalation_reason')})")
    else:
        print("\nAll 20 scenarios passed perfectly with zero regressions!")

    # Output artifact
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path("eval/out")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = Path(args.out) if args.out else out_dir / f"eval_{args.prompt_version}_{timestamp}.json"

    out_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": args.prompt_version,
        "llm_provider": llm_provider,
        "direct_mode": args.direct,
        "force_invalid": args.force_invalid,
        "total_scenarios": len(results),
        "passed_count": passed_count,
        "total_time_seconds": total_time,
        "metrics": {
            "groundedness": avg_groundedness,
            "context_relevance": avg_context_rel,
            "faithfulness": avg_faithfulness,
            "hallucination_rate": hallucination_rate,
            "routing_accuracy": routing_acc,
            "correct_escalation_rate": escalate_rate,
        },
        "per_scenario": results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2)

    print(f"\nArtifact saved: {out_file}\n")


if __name__ == "__main__":
    main()
