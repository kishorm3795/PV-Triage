"""agents/run.py - Main entry point executing the triage graph.

Implements the GraphRunner protocol from shared/contracts.py:
  run_graph(report: dict, run_id: str) -> RunResult
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict
from agents.graph import create_triage_graph
from agents.state import AgentState
from agents.tools import register_run_report
from shared.contracts import (
    Expectedness,
    RunResult,
    Seriousness,
)

logger = logging.getLogger("agents.run")

_COMPILED_GRAPH = None


def get_graph():
    """Lazy initialize and cache the compiled LangGraph workflow."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = create_triage_graph()
    return _COMPILED_GRAPH


def reset_graph():
    """Reset cached graph (useful for test environments)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def run_graph(report: Dict[str, Any], run_id: str) -> RunResult:
    """Execute the multi-agent pharmacovigilance triage workflow.

    Args:
        report: Raw or validated adverse event report dictionary.
        run_id: Unique identifier for the triage execution run.

    Returns:
        RunResult meeting the shared/contracts.py specification.
    """
    register_run_report(run_id, report)

    initial_state: AgentState = {
        "run_id": run_id,
        "report": report,
        "retrieved_passages": [],
        "tool_log": [],
        "trace": [],
        "step_count": 0,
        "prompt_versions": {},
        "run_start_time": time.perf_counter(),
        "retry_count": 0,
        "search_strategy": "initial",
        "verifier_feedback": None,
        "force_invalid_citation": bool(report.get("force_invalid_citation", False)),
        "status": "running",
        "routing": None,
        "routing_basis": None,
        "seriousness": Seriousness(is_serious=False, criteria=[]),
        "expectedness": Expectedness(is_listed=False, matched_term=None),
        "citations": [],
        "escalation_reason": None,
        "verification_passed": False,
        "verification_errors": [],
    }

    try:
        graph = get_graph()
        final_state = graph.invoke(initial_state)

        result = RunResult(
            run_id=run_id,
            status=final_state.get("status", "completed"),
            routing=final_state.get("routing"),
            routing_basis=final_state.get("routing_basis"),
            seriousness=final_state.get(
                "seriousness", Seriousness(is_serious=False, criteria=[])
            ),
            expectedness=final_state.get(
                "expectedness", Expectedness(is_listed=False, matched_term=None)
            ),
            citations=final_state.get("citations", []),
            escalation_reason=final_state.get("escalation_reason"),
            prompt_versions=final_state.get("prompt_versions", {}),
            tool_calls=final_state.get("tool_log", []),
            trace=final_state.get("trace", []),
        )

        # Enforce Pydantic validation
        return RunResult.model_validate(result.model_dump())

    except Exception as exc:
        logger.exception("Agent execution failed for run %s: %s", run_id, exc)
        err_msg = str(exc)
        is_verifier = "verifier" in err_msg.lower() or "verifier" in repr(exc).lower()
        failed_status: Any = "escalated" if is_verifier else "failed"
        reason = (
            f"Verifier crashed: {err_msg}. Escalating per safety protocol (Global Rule 6)."
            if is_verifier
            else f"Execution error: {err_msg}"
        )
        failed_result = RunResult(
            run_id=run_id,
            status=failed_status,
            routing=None,
            routing_basis=None,
            seriousness=Seriousness(is_serious=False, criteria=[]),
            expectedness=Expectedness(is_listed=False, matched_term=None),
            citations=[],
            escalation_reason=reason,
            prompt_versions=initial_state.get("prompt_versions", {}),
            tool_calls=initial_state.get("tool_log", []),
            trace=initial_state.get("trace", []),
        )
        return RunResult.model_validate(failed_result.model_dump())
