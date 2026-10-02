"""worker/placeholder.py - Phase 1 placeholder for GraphRunner.

This placeholder returns a fixed, schema-compliant RunResult until Member B
merges the real LangGraph agent implementation in b/agents.

Swap in worker/tasks.py with:
    from agents.run import run_graph
"""

from typing import Any
from shared.contracts import (
    Citation,
    Expectedness,
    RunResult,
    Seriousness,
    ToolCall,
    TraceStep,
)


def run_graph(report: dict[str, Any], run_id: str) -> RunResult:
    """Simulate graph execution and return a validated RunResult."""
    suspect_drug = report.get("suspect_drug", "Unknown Drug")
    reaction = report.get("reaction_description", "Adverse Event")

    return RunResult(
        run_id=run_id,
        status="completed",
        routing="expedited",
        routing_basis=(
            f"Expedited 15-day reporting recommended: suspect drug '{suspect_drug}' caused "
            f"reaction '{reaction}', which resulted in inpatient hospitalization and is "
            "not listed as expected in the approved package insert."
        ),
        seriousness=Seriousness(
            is_serious=True,
            criteria=["hospitalisation"],
        ),
        expectedness=Expectedness(
            is_listed=False,
            matched_term=None,
        ),
        citations=[
            Citation(
                passage_id="ndct-2019-second-sched-table1",
                quote=(
                    "Any serious unexpected adverse event shall be reported by the sponsor "
                    "or marketing authorisation holder to the Central Licencing Authority "
                    "within fifteen calendar days."
                ),
            ),
            Citation(
                passage_id="ipc-pv-guidance-sec4-seriousness",
                quote=(
                    "A serious adverse event (SAE) is any untoward medical occurrence that "
                    "results in death, inpatient hospitalisation or prolongation of existing "
                    "hospitalisation, persistent or significant disability, or congenital anomaly."
                ),
            ),
        ],
        escalation_reason=None,
        prompt_versions={
            "assessor": "v1-placeholder",
            "verifier": "v1-placeholder",
        },
        tool_calls=[
            ToolCall(
                step=1,
                tool="search_corpus",
                input={"query": f"{suspect_drug} {reaction}"},
                output_summary="Retrieved 3 passages from package insert and NDCT rules",
                latency_ms=18.5,
                ok=True,
            ),
            ToolCall(
                step=2,
                tool="get_clause",
                input={"clause_id": "ndct-2019-second-sched-table1"},
                output_summary="Retrieved clause on 15-day expedited reporting timeline",
                latency_ms=8.2,
                ok=True,
            ),
        ],
        trace=[
            TraceStep(
                step=1,
                agent="assessor",
                kind="tool_execution",
                latency_ms=26.7,
                prompt_tokens=180,
                completion_tokens=65,
                cost_usd=0.000066,
                detail={"action": "retrieved regulatory evidence", "status": "draft_created"},
            ),
            TraceStep(
                step=2,
                agent="verifier",
                kind="verification",
                latency_ms=12.1,
                prompt_tokens=90,
                completion_tokens=30,
                cost_usd=0.000031,
                detail={"verified_citations": 2, "outcome": "passed"},
            ),
        ],
    )
