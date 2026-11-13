"""agents/state.py - LangGraph Agent State definition.

Maintains complete execution context across assessor and verifier nodes,
including report payload, retrieved passages, tool call audit log, trace steps,
prompt versions, retry accounting, and intermediate/final decisions.
"""

from __future__ import annotations

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
    seriousness: Seriousness
    expectedness: Expectedness
    citations: List[Citation]
    escalation_reason: Optional[str]
    verification_passed: bool
    verification_errors: List[str]
