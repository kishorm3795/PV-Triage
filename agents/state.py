"""agents/state.py - LangGraph Agent State definition and Trace detail formatting.

Maintains complete execution context across assessor and verifier nodes,
including report payload, retrieved passages, tool call audit log, trace steps,
prompt versions, retry accounting, and intermediate/final decisions.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict

from shared.contracts import (
    Citation,
    Expectedness,
    Passage,
    Seriousness,
    ToolCall,
    TraceStep,
)


class AgentState(TypedDict, total=False):
    """Execution state schema for the LangGraph triage workflow."""

    run_id: str
    report: Dict[str, Any]
    retrieved_passages: List[Passage]
    tool_log: List[ToolCall]
    trace: List[TraceStep]
    step_count: int
    prompt_versions: Dict[str, str]

    # Execution bounds and control flow
    run_start_time: float
    retry_count: int
    search_strategy: str
    verifier_feedback: Optional[str]
    force_invalid_citation: bool

    # Assessment determinations
    status: Literal["completed", "escalated", "failed"]
    routing: Optional[Literal["expedited", "periodic", "non_reportable"]]
    routing_basis: Optional[str]
    assessment_text: Optional[str]
    seriousness: Seriousness
    expectedness: Expectedness
    citations: List[Citation]
    escalation_reason: Optional[str]
    verification_passed: bool
    verification_errors: List[str]


def make_trace_detail(
    prompt_version: str = "v1",
    tool: Optional[str] = None,
    query: Optional[str] = None,
    passage_ids: Optional[List[str]] = None,
    guardrail_name: str = "none",
    guardrail_result: str = "pass",
    guardrail_reason: Optional[str] = None,
    llm_attempt: int = 1,
    llm_retries: int = 0,
    breaker_state: Optional[str] = None,
    model: str = "stub-llm",
    verification_ok: Optional[bool] = None,
    verification_failed_checks: Optional[List[str]] = None,
    cost_flag: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Format TraceStep.detail adhering to Member A's agreed schema."""
    if breaker_state is None:
        try:
            from llm.resilience import get_circuit_breaker
            breaker_state = get_circuit_breaker().get_state()
        except Exception:
            breaker_state = "closed"

    detail: Dict[str, Any] = {
        "prompt_version": prompt_version,
        "tool": tool,
        "query": query,
        "passage_ids": passage_ids or [],
        "guardrail": {
            "name": guardrail_name,
            "result": guardrail_result,
            "reason": guardrail_reason,
        },
        "llm": {
            "attempt": llm_attempt,
            "retries": llm_retries,
            "breaker_state": breaker_state,
            "model": model,
        },
        "verification": (
            {
                "ok": verification_ok,
                "failed_checks": verification_failed_checks or [],
            }
            if verification_ok is not None
            else None
        ),
    }
    if cost_flag:
        detail["cost_flag"] = cost_flag
    detail.update(extra)
    return detail
