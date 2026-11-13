"""shared/contracts.py - Frozen system interfaces.

This file defines the shared data models (Pydantic v2) and typing Protocols
agreed upon across all three team members (Member A: Platform, Member B: Agents,
Member C: Data & RAG).

GLOBAL RULE:
Frozen interfaces live in shared/contracts.py. Do not change them without team agreement.
shared/ is written by Member A only; Members B and C treat it as read-only.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable
from pydantic import BaseModel, ConfigDict, Field


class Passage(BaseModel):
    """A passage retrieved from the regulatory corpus or package insert."""

    model_config = ConfigDict(extra="ignore")

    id: str
    text: str
    source_doc: str
    page: int | None = None
    clause_id: str | None = None
    section: str | None = None
    score: float | None = None


class Citation(BaseModel):
    """Direct reference to a passage supporting a specific assessment claim."""

    model_config = ConfigDict(extra="ignore")

    passage_id: str
    quote: str


class ToolCall(BaseModel):
    """Audit record for a tool call made during graph execution."""

    step: int
    tool: str
    input: Any
    output_summary: str
    latency_ms: float
    ok: bool


class TraceStep(BaseModel):
    """Audit step in the agent execution trace with cost and token accounting."""

    step: int
    agent: str
    kind: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    detail: dict[str, Any] | str = Field(default_factory=dict)


class Seriousness(BaseModel):
    """Seriousness determination and supporting statutory criteria."""

    is_serious: bool
    criteria: list[str] = Field(default_factory=list)


class Expectedness(BaseModel):
    """Expectedness determination against the approved package insert."""

    is_listed: bool
    matched_term: str | None = None


class RunResult(BaseModel):
    """Final output contract returned by graph execution for a triage report."""

    run_id: str
    status: Literal["completed", "escalated", "failed"]
    routing: Literal["expedited", "periodic", "non_reportable"] | None = None
    routing_basis: str | None = None
    seriousness: Seriousness = Field(
        default_factory=lambda: Seriousness(is_serious=False, criteria=[])
    )
    expectedness: Expectedness = Field(
        default_factory=lambda: Expectedness(is_listed=False, matched_term=None)
    )
    citations: list[Citation] = Field(default_factory=list)
    escalation_reason: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)


@runtime_checkable
class Retriever(Protocol):
    """Protocol for vector and clause retrieval against the regulatory corpus."""

    def search(self, query: str, k: int = 5) -> list[Passage]:
        """Search corpus for top-k passages matching the query."""
        ...

    def get_clause(self, clause_id: str) -> Passage | None:
        """Lookup a specific regulatory clause by its exact identifier."""
        ...


@runtime_checkable
class GraphRunner(Protocol):
    """Protocol for executing the multi-agent triage graph."""

    def run_graph(self, report: dict[str, Any], run_id: str) -> RunResult:
        """Execute the multi-agent workflow for a validated adverse event report."""
        ...
