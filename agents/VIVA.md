# Agent Core & LLMOps Viva Voce Preparation Guide (`agents/VIVA.md`)

This guide prepares the engineering team for viva examination questions focused on the agent architecture, multi-agent state machines, verification integrity, resilience, and LLMOps design choices.

---

### Q1: Why use two distinct agents (Assessor and Verifier) instead of a single prompt or chain?
**Answer**: A single agent generating both assessment and verification exhibits cognitive self-bias: LLMs tend to rationalize their own hallucinations. Decoupling into an **Assessor** (which explores hypotheses and synthesizes draft recommendations) and an **independent Verifier** (which has a separate state view, separate prompt, and audits claims adversarially against deterministic substring checks) establishes true checks and balances.

### Q2: Exactly what does the Verifier agent check before approving a run?
**Answer**: The Verifier performs three mandatory adversarial audits in `verifier_node`:
1. **Passage Retrieval Authenticity**: Confirms that every cited `passage_id` was genuinely retrieved in this run's `tool_log`.
2. **Verbatim Quote Integrity**: Confirms that the cited `quote` is a 100% exact verbatim substring of the retrieved document chunk.
3. **Statutory Claim Entailment**: Verifies that cited statutory clauses actually support the asserted claims (e.g. confirming hospitalization keywords in the cited seriousness passage, and 15-day provisions in expedited routing).

### Q3: What happens when an external tool invocation fails or times out?
**Answer**: All tools are wrapped by `wrap_tools()` in `agents/tools.py`. If a tool times out or raises an exception, the wrapper records `ok: false` and the error message in `tool_log`. If `MAX_TOOL_CALLS` is breached, a `ToolCallLimitExceeded` exception escalates the run with the exact bound named in `escalation_reason`. The system never suppresses tool failures.

### Q4: How do the hard execution loop bounds work, and where are they enforced?
**Answer**: Execution bounds are governed by `_check_bounds()` at every node entry in `agents/graph.py`:
- `MAX_STEPS` (default: 15): Caps graph state transitions.
- `MAX_TOOL_CALLS` (default: 20): Prevents runaway retrieval loops.
- `RUN_TIMEOUT_S` (default: 30s): Enforces real-time wall-clock budgets.
Exceeding any bound immediately terminates the graph with status `escalated` and logs the elapsed metric.

### Q5: What are the three states of the LLM Circuit Breaker and how do transitions occur?
**Answer**: Implemented in `llm/resilience.py`:
- **CLOSED (0)**: Normal healthy operation.
- **OPEN (2)**: Tripped when consecutive failures reach `BREAKER_FAILS=3`. Calls are rejected immediately ($< 0.1\text{ms}$) without network overhead, escalating with `"LLM unavailable"`.
- **HALF-OPEN (1)**: Entered automatically after `BREAKER_RESET_S=30` seconds cooldown in OPEN. Allows a single trial request. Success resets to CLOSED; failure re-trips to OPEN.

### Q6: Why is an unverified or incomplete run never returned as a confident answer?
**Answer**: Mandated by Global Rule 6: In pharmaceutical pharmacovigilance, an ungrounded or fabricated regulatory deadline can result in legal non-compliance, regulatory audits, and patient risk. If verification fails or any component crashes, the status is set to `escalated` or `failed` with `routing: null`.

### Q7: What is the failure behavior difference between an Assessor crash and a Verifier crash?
**Answer**:
- If the **Assessor crashes**: Status is set to **`failed`** (the draft assessment could not be produced).
- If the **Verifier crashes**: Status is set to **`escalated`** (safety protocol requires escalating the draft for qualified human review rather than treating the crash as an unhandled defect).

### Q8: What architectural design alternatives were considered and rejected?
**Answer**:
1. **Single Autonomous ReAct Agent**: Rejected because dynamic tool loops without an adversarial verifier frequently hallucinated non-existent regulatory sub-clauses.
2. **Fixed-Window Chunker**: Rejected because splitting documents strictly by token counts split statutory clauses across boundaries, severing clause headings from text.
3. **Automated Regulatory Submission**: Rejected because statutory frameworks strictly require human QPPV responsibility.

### Q9: How is lay-to-medical vocabulary expansion handled deterministically?
**Answer**: Colloquial descriptions (e.g. *"skin peeling badly"*) cannot be matched directly against product inserts that use technical medical terms. The Assessor invokes `rewrite_query()`, which uses an offline synonym dictionary (`pipeline/synonyms.json`) to expand colloquial phrases into formal MedDRA-aligned concepts (`Toxic epidermal necrolysis`, `Stevens-Johnson syndrome`) before querying ChromaDB.

### Q10: How are adversarial prompt injections detected and prevented?
**Answer**: In `guardrails/injection.py`:
1. Every free-text field (`reaction_description`, `narrative`, etc.) is inspected with high-precision regexes detecting instruction overrides, role hijacks, and tool smuggling.
2. User input is wrapped in boundary isolation delimiters (`<<<USER_CLINICAL_DATA>>>`) instructing the downstream LLM to treat content strictly as inert clinical data.
3. Any detected injection escalates immediately with reason `"possible prompt injection"`.

### Q11: How does the system prevent false positives on clinical terms like 'ignore' or 'system'?
**Answer**: In `guardrails/injection.py`, regex patterns require adversarial verb-object combinations (e.g. `ignore previous instructions` or `system override`). Benign phrases such as *"patient advised to ignore mild dizziness"* or *"nervous system reaction"* do not match these patterns.

### Q12: How is prompt versioning tracked across runs?
**Answer**: Prompt markdown files are organized by version in `prompts/assessor/` and `prompts/verifier/`. The loader records the active version string in `RunResult.prompt_versions` (e.g., `{"assessor": "v1", "verifier": "v1"}`), enabling exact historical prompt reconstruction for every run.

### Q13: What was the purpose and outcome of the Phase 5 deliberate change experiment?
**Answer**: Controlled by `REQUIRE_MODIFYING_PROVISION_SEARCH`. It tests enforcing secondary statutory modifying clauses (NDCT 2019 Table 1 15-day timeline) in addition to primary IPC seriousness clauses. When enabled, groundedness and dual-statutory coverage reached 100%, demonstrating controllable agent behavior via environment configuration.

### Q14: How does Whole-Run Caching work and why is it essential for multi-step agents?
**Answer**: Implemented in `api/main.py` via Redis. A canonical SHA-256 hash is computed over normalized report fields. On an identical report submission, the cached completed `RunResult` is returned in $< 2\text{ms}$ with zero queue latency, zero CPU vector compute, and zero token expenditure.

### Q15: How does the Verifier handle multiple search retries before escalating?
**Answer**: If verification checks fail on the initial pass, the Verifier does not immediately escalate. It loops back to the Assessor with specific diagnostic feedback (`verifier_feedback`) and switches search strategy (e.g. to direct clause lookup). The loop allows up to **2 retries**. If verification still fails after 2 retries, the run is escalated with full error history.
