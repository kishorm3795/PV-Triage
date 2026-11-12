# BLOCKED_ON_C.md — Dependency Ledger for Member B (Agents)

**Branch:** `b/agents`  
**Owner:** Member B (Agent Core & LLMOps)  
**Phase:** Phase 4–6 (Safety, Resilience, Observability + Prompt Variants + Cost/Sampling/Guardrail Tuning)  
**Last Updated:** 2026-11-12

---

## Ledger Format

| Item | What I Did Instead (B-owned Fallback) | What Is Still Needed from C | How to Switch Over (Exact Env Change or Command) |
| :--- | :--- | :--- | :--- |

---

## Phase 4 Items

| Item | What I Did Instead (B-owned Fallback) | What Is Still Needed from C | How to Switch Over |
| :--- | :--- | :--- | :--- |
| **Retrieval Adapter (Real Index)** | Built `MockRetriever` in `agents/tools.py` with deterministic fixtures. `RETRIEVER=mock` works fully for all graph runs, tests, and batch evaluation. | Member C's real Chroma vector index, `RealRetriever` implementing `Retriever` protocol, persisted corpus chunks with clause_id mapping. | Set `RETRIEVER=real` (requires C's `pipeline/` and `corpus/` work to be complete and indexed). |
| **Evaluation Dataset (20 Scenarios)** | Created `agents/tests/fixtures/scenarios_local.jsonl` with 10 synthetic reports covering serious/unexpected, serious/expected, non-serious, out-of-corpus drug, unclear timing, and injection/toxicity edge cases. Each has expected routing, seriousness, expectedness, and required citation passage_ids (mock passages only). | Member C's official `eval/scenarios.jsonl` with 20 scenarios, real corpus passage_ids, and human-verified ground truth. | Place C's file at `eval/scenarios.jsonl` (read-only for B). Batch runner defaults to it if exists, else falls back to local fixtures. |
| **Scorers (Groundedness, Citation Resolve)** | Implemented `LocalScorer` in `agents/scoring.py` (protocol `Scorer`). Deterministic: checks citation passage_id exists in retrieved passages, quote is substring of passage text, claim count supported. `SCORER=local` works fully. | Member C's `EvalScorer` with LLM-as-judge groundedness, semantic equivalence, and regulatory compliance metrics. | Set `SCORER=eval` (imports C's scorers with try/except; falls back to local with logged warning on ImportError). |
| **Batch Runner Integration** | `agents/batch.py` accepts `--prompt-version`, `--set`, outputs timestamped JSON to `agents/out/`. Works with local fixtures and mock retriever. | C's eval harness integration for official reporting, CI pipeline hook. | No code change needed; batch runner auto-detects C's eval set at `eval/scenarios.jsonl`. |

---

## Status Summary

- **All Phase 4 tasks complete on mock/local data.**
- No items marked "done" — all marked "done on mock" per dependency rule.
- Guardrails, resilience, cost tracking, and trace detail format fully implemented and tested.
- Mermaid diagram and failure table in `agents/TOPOLOGY.md` updated to include input/output guardrails.
- Ready for Phase 5 (prompt variants, failure fixes, deliberate change).

---

## Phase 5 Items (Complete)

| Item | B-owned Implementation | C Dependency |
| :--- | :--- | :--- |
| **Prompt Version A/B** | `PROMPT_VERSION=v1|v2` env var in `prompts/loader.py` + graph node | None — uses same mock retriever |
| **Deliberate Change Flag** | `MODIFYING_PROVISION_SEARCH=on|off` in `agents/graph.py` wraps Step 3 | None — mock retriever compatible |
| **Failure Diagnosis Loop** | Ran batch on local fixtures; documented in `agents/CHANGES.md` | C's official eval set for 4-metric comparison |
| **CHANGES.md** | Created with before/after comparison (stub LLM) | Placeholder for C's official results |

---

## Phase 6 Items (Complete — B-only, No C Dependencies)

| Item | Implementation | Files |
| :--- | :--- | :--- |
| **Cost Report** | `agents/COST.md` — cost per 100 runs from batch trace tokens, formula, prices from env, per-agent/tool breakdown, largest cost driver identified (Assessor = 68%), stub LLM disclaimer | `agents/COST.md` |
| **Live Sampling** | `agents/sampling.py` — background job sampling ~10% of completed runs (SAMPLE_RATE), dual RunSource adapters (TraceStoreRunSource + BatchOutputRunSource fallback), SQLite storage (SAMPLE_DB), CLI for table/CSV export | `agents/sampling.py`, `agents/out/sampling.db` |
| **Guardrail FP Review** | `agents/tests/fixtures/clinical_narratives.jsonl` (15 clinical narratives), measured 0% false positive rate, 100% true positive preserved, documented in `guardrails/README.md` | `agents/tests/fixtures/clinical_narratives.jsonl`, `guardrails/README.md` |

---

## Phase 5+ Anticipated Dependencies

| Item | Anticipated B-owned Fallback | Needed from C |
| :--- | :--- | :--- |
| **Real Retrieval for Batch Eval** | `RETRIEVER=mock` continues to work; local fixtures provide deterministic results. | C's real index for official eval runs. |
| **Official Scorer Metrics** | `SCORER=local` provides citation resolve + claim support. | C's LLM-judge scorers for groundedness, regulatory compliance. |
| **Prompt Version Comparison** | `agents/batch.py --prompt-version v1|v2` works with local fixtures. | C's eval set for official 4-metric comparison. |
| **Trace Store Adapter** | `BatchOutputRunSource` reads `agents/out/*.json` (fallback). | Member A's trace store HTTP endpoint (`TRACE_STORE_URL`). |