# AGENTS.md

GLOBAL RULES (paste verbatim into AGENTS.md)
- Python 3.11. Docker Compose is the only way the system runs. Default to the STUB LLM.
- Never invent regulatory clauses, deadlines or package-insert text. The system may cite only
 text retrieved from ./corpus. When writing tests or docs, read the real PDFs and quote them.
- Synthetic data only. Never real patient data.
- No credentials, endpoints or model identifiers in the repo. All config via environment.
- The system only RECOMMENDS. It never submits a regulatory report. A qualified person decides.
- An unverified or incomplete run must never be returned as a confident answer.
- Edit only the folders you own. If you need a change elsewhere, tell the owner in your report.
- Frozen interfaces live in shared/contracts.py. Do not change them without team agreement.
- Work in small steps. Run what you build. Show proof (commands + output). Commit to your
 branch. Then STOP and wait for "go".

---

## Folder Ownership & Responsibilities

| Member | Active Branch | Owned Modules & Folders | Permissions & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Member A** | `a/platform` | `api/`, `worker/`, `stub_llm/`, `infra/`, `loadtest/`, `shared/`, `scripts/` | **Platform & Infrastructure**: FastAPI REST API, Redis RQ workers, Stub LLM service, Docker Compose, monitoring (Prometheus & Jaeger), Locust load testing, web client, shared contracts and setup scripts. `shared/` is written by A only; B and C treat it as read-only. |
| **Member B** | `b/agents` | `agents/`, `llm/`, `prompts/`, `guardrails/` | **Agent Core & LLMOps**: LangGraph multi-agent architecture (Assessor & Verifier), versioned prompt management, LLM abstraction layer, guardrails (prompt injection & toxicity defense), and circuit breakers. |
| **Member C** | `c/data` | `pipeline/`, `corpus/`, `eval/`, `docs/` | **Data, RAG & Evaluation**: Regulatory corpus processing, idempotent RAG chunking and Chroma vector storage, retrieval adapters, 20-scenario eval benchmark, and project documentation/runbooks. |

---

## Frozen-Interface Summary (`shared/contracts.py`)

All shared data models use Pydantic v2. The contracts and protocols are frozen across team members:

### Data Models
- **`Passage`**: `(id: str, text: str, source_doc: str, page: int | None, clause_id: str | None, section: str | None, score: float | None)`  
  Represents a chunk or clause retrieved from the corpus or package insert.
- **`Citation`**: `(passage_id: str, quote: str)`  
  A verbatim reference to a retrieved passage backing a specific claim.
- **`ToolCall`**: `(step: int, tool: str, input: Any, output_summary: str, latency_ms: float, ok: bool)`  
  Audit record for every tool executed during graph execution.
- **`TraceStep`**: `(step: int, agent: str, kind: str, latency_ms: float, prompt_tokens: int, completion_tokens: int, cost_usd: float, detail: dict | str)`  
  Step-level audit record capturing latency, tokens, cost, and decision details.
- **`Seriousness`**: `(is_serious: bool, criteria: list[str])`  
  Seriousness assessment and matched statutory criteria (e.g., hospitalisation, death).
- **`Expectedness`**: `(is_listed: bool, matched_term: str | None)`  
  Expectedness assessment against the approved package insert.
- **`RunResult`**: `(run_id: str, status: completed|escalated|failed, routing: expedited|periodic|non_reportable|None, routing_basis: str | None, seriousness: Seriousness, expectedness: Expectedness, citations: list[Citation], escalation_reason: str | None, prompt_versions: dict[str, str], tool_calls: list[ToolCall], trace: list[TraceStep])`  
  Final response payload emitted by the triage workflow.

### Protocols
- **`Retriever (typing.Protocol)`**:
  - `search(query: str, k: int = 5) -> list[Passage]`
  - `get_clause(clause_id: str) -> Passage | None`
- **`GraphRunner (typing.Protocol)`**:
  - `run_graph(report: dict, run_id: str) -> RunResult`
