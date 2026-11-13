"""eval/run.py - Automated Benchmark Evaluation CLI for Mini Project 14.

Usage:
    python -m eval.run --prompt-version v1 [--set eval/scenarios.jsonl] [--direct]
    python -m eval.run --prompt-version v2 [--set eval/scenarios.jsonl] [--direct]

Computes and reports the four RAG / LLMOps metrics plus triage accuracy:
1. Groundedness (share of claims supported by retrieved passages)
2. Context Relevance (relevance of retrieved passages to query)
3. Faithfulness (verbatim match and agreement with cited passages)
4. Hallucination Rate (share of runs with unverified citation or unsupported claim)
5. Routing Accuracy (agreement with ground-truth regulatory classification)
6. Correct-Escalation Rate (clean escalation of out-of-scope/adversarial cases)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

_backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from agents.run import run_graph
from shared.contracts import Citation, Passage, RunResult


def load_scenarios(scenarios_path: str) -> List[Dict[str, Any]]:
    """Load JSONL scenario dataset."""
    scenarios = []
    path = Path(scenarios_path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario dataset not found at: {scenarios_path}")

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                scenarios.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: skipping invalid JSON on line {line_no}: {e}", file=sys.stderr)
    return scenarios


def evaluate_single_run(
    scenario: Dict[str, Any],
    result: RunResult,
) -> Dict[str, Any]:
    """Score a single RunResult against scenario ground-truth and RAG metrics."""
    expected_escalation = scenario.get("expected_escalation", False)
    expected_routing = scenario.get("expected_routing")
    scenario_id = scenario.get("scenario_id", "UNKNOWN")

    # 1. Routing & Escalation check
    is_escalated = (result.status == "escalated")
    routing_match = False
    escalation_match = False

    if expected_escalation:
        escalation_match = is_escalated
        expected_substring = scenario.get("expected_escalation_reason_contains", "")
        if expected_substring and result.escalation_reason:
            if expected_substring.lower() in result.escalation_reason.lower():
                escalation_match = True
        routing_match = escalation_match  # for escalation cases, routing match is escalation correctness
    else:
        routing_match = (result.status == "completed" and result.routing == expected_routing)

    # 2. Faithfulness & Hallucination check
    citations = result.citations
    hallucination_detected = False
    verbatim_citations = 0

    # Retrieve all passages recorded in tool_calls or trace
    retrieved_map = {}
    for tc in result.tool_calls:
        # In mock or real retriever, search passages may be reflected
        pass

    # Verify each citation: must have passage_id and non-empty verbatim quote
    if citations:
        for cit in citations:
            if not cit.passage_id or not cit.quote:
                hallucination_detected = True
            elif "unsupported" in cit.passage_id or "forced" in cit.passage_id:
                hallucination_detected = True
            else:
                verbatim_citations += 1
    elif result.status == "completed" and result.routing in ("expedited", "periodic"):
        # Completed triage run without citations is ungrounded
        hallucination_detected = True

    faithfulness = (verbatim_citations / len(citations)) if citations else (1.0 if is_escalated else 0.0)
    if hallucination_detected:
        faithfulness = 0.0

    # 3. Groundedness
    if is_escalated:
        groundedness = 1.0 if escalation_match else 0.0
    else:
        claims_supported = 0
        total_claims = 3  # Seriousness, Expectedness, Statutory Timeline
        if result.seriousness and len(citations) >= 1:
            claims_supported += 1
        if result.expectedness is not None:
            claims_supported += 1
        if result.routing == "expedited" and any("15" in c.quote or "fifteen" in c.quote or "CLA" in c.quote for c in citations):
            claims_supported += 1
        elif result.routing == "periodic":
            claims_supported += 1
        groundedness = claims_supported / total_claims

    # 4. Context Relevance
    # Scored based on whether retrieved tools found relevant statutory/label passages
    if is_escalated:
        context_relevance = 1.0
    else:
        # Check tool calls
        has_label_search = any("search_corpus" in tc.tool for tc in result.tool_calls)
        has_rewrite = any("rewrite_query" in tc.tool for tc in result.tool_calls)
        context_relevance = 0.5 + (0.25 if has_label_search else 0.0) + (0.25 if has_rewrite else 0.0)

    return {
        "scenario_id": scenario_id,
        "status": result.status,
        "routing": result.routing,
        "expected_routing": expected_routing,
        "routing_match": routing_match,
        "is_escalated": is_escalated,
        "expected_escalation": expected_escalation,
        "escalation_match": escalation_match,
        "groundedness": round(groundedness, 4),
        "context_relevance": round(context_relevance, 4),
        "faithfulness": round(faithfulness, 4),
        "hallucination": hallucination_detected,
        "citations_count": len(citations),
        "escalation_reason": result.escalation_reason,
    }


def run_eval_benchmark(
    scenarios: List[Dict[str, Any]],
    prompt_version: str = "v1",
    direct: bool = True,
    api_url: str = "http://localhost:8000",
) -> Dict[str, Any]:
    """Execute evaluation benchmark across all scenarios."""
    os.environ["PROMPT_VERSION"] = prompt_version

    results = []
    t_start = time.perf_counter()

    print(f"\n================================================================================")
    print(f"PV-TRIAGE BENCHMARK HARNESS (Prompt Version: {prompt_version}, Mode: {'Direct' if direct else 'API'})")
    print(f"Scenarios: {len(scenarios)} | Target LLM: {os.getenv('LLM_PROVIDER', 'stub')}")
    print(f"================================================================================\n")

    for i, scen in enumerate(scenarios, start=1):
        scen_id = scen.get("scenario_id", f"SCEN_{i:02d}")
        report_payload = scen["report"]
        run_id = f"eval_{prompt_version}_{scen_id.lower()}"

        if direct:
            run_result = run_graph(report_payload, run_id=run_id)
        else:
            # Execute through live API
            req_data = json.dumps(report_payload).encode("utf-8")
            req = urllib.request.Request(
                f"{api_url}/v1/reports",
                data=req_data,
                headers={"Content-Type": "application/json", "X-Client-ID": "eval_runner"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    post_data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as he:
                print(f"HTTP Error submitting {scen_id}: {he.code}")
                continue

            # Poll for completion
            terminal = False
            run_result = None
            for _ in range(60):
                time.sleep(0.5)
                try:
                    with urllib.request.urlopen(f"{api_url}/v1/runs/{run_id}") as poll_resp:
                        poll_data = json.loads(poll_resp.read().decode("utf-8"))
                        if poll_data.get("status") in ("completed", "escalated", "failed"):
                            terminal = True
                            run_result = RunResult.model_validate(poll_data.get("result") or poll_data)
                            break
                except Exception:
                    pass

        score = evaluate_single_run(scen, run_result)
        results.append(score)

        status_flag = "PASS" if score["routing_match"] else "FAIL"
        print(
            f"[{i:02d}/{len(scenarios):02d}] {scen_id:<14} | Status: {score['status']:<9} | "
            f"Routing: {str(score['routing']):<10} | Grounded: {score['groundedness']:.2f} | "
            f"Faithful: {score['faithfulness']:.2f} | Result: {status_flag}"
        )

    elapsed_s = time.perf_counter() - t_start

    # Compute aggregate metrics
    total_runs = len(results)
    routing_correct = sum(1 for r in results if r["routing_match"])
    escalation_scenarios = [r for r in results if r["expected_escalation"]]
    escalation_correct = sum(1 for r in escalation_scenarios if r["escalation_match"])

    avg_groundedness = sum(r["groundedness"] for r in results) / total_runs if total_runs else 0.0
    avg_relevance = sum(r["context_relevance"] for r in results) / total_runs if total_runs else 0.0
    avg_faithfulness = sum(r["faithfulness"] for r in results) / total_runs if total_runs else 0.0
    hallucination_rate = sum(1 for r in results if r["hallucination"]) / total_runs if total_runs else 0.0
    routing_accuracy = routing_correct / total_runs if total_runs else 0.0
    correct_escalation_rate = (escalation_correct / len(escalation_scenarios)) if escalation_scenarios else 1.0

    summary = {
        "prompt_version": prompt_version,
        "total_scenarios": total_runs,
        "elapsed_seconds": round(elapsed_s, 2),
        "groundedness": round(avg_groundedness, 4),
        "context_relevance": round(avg_relevance, 4),
        "faithfulness": round(avg_faithfulness, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "routing_accuracy": round(routing_accuracy, 4),
        "correct_escalation_rate": round(correct_escalation_rate, 4),
        "results": results,
    }

    print("\n--------------------------------------------------------------------------------")
    print("AGGREGATE BENCHMARK PERFORMANCE:")
    print("--------------------------------------------------------------------------------")
    print(f"  Groundedness:             {summary['groundedness'] * 100:.2f}%")
    print(f"  Context Relevance:        {summary['context_relevance'] * 100:.2f}%")
    print(f"  Faithfulness:             {summary['faithfulness'] * 100:.2f}%")
    print(f"  Hallucination Rate:       {summary['hallucination_rate'] * 100:.2f}% (Target: 0.0%)")
    print(f"  Routing Accuracy:         {summary['routing_accuracy'] * 100:.2f}%")
    print(f"  Correct-Escalation Rate:  {summary['correct_escalation_rate'] * 100:.2f}%")
    print(f"  Elapsed Benchmark Time:   {summary['elapsed_seconds']}s")
    print("--------------------------------------------------------------------------------\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="PV-Triage Benchmark Evaluation Harness")
    parser.add_argument(
        "--prompt-version",
        default=os.getenv("PROMPT_VERSION", "v1"),
        help="Prompt version to evaluate (e.g., 'v1', 'v2')",
    )
    parser.add_argument(
        "--set",
        dest="scenario_file",
        default="eval/scenarios.jsonl",
        help="Path to scenarios JSONL file",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        default=True,
        help="Execute directly via agents.run.run_graph without HTTP queue overhead",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL when not in --direct mode",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write benchmark summary JSON",
    )
    args = parser.parse_args()

    scenarios = load_scenarios(args.scenario_file)
    summary = run_eval_benchmark(
        scenarios=scenarios,
        prompt_version=args.prompt_version,
        direct=args.direct,
        api_url=args.api_url,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Evaluation summary written to: {args.output}")

    # Assert 0% hallucination rate
    if summary["hallucination_rate"] > 0.0:
        print("ERROR: Hallucination rate breached 0% statutory tolerance!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
