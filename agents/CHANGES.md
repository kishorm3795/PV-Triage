# Phase 5: Deliberate Change — `MODIFYING_PROVISION_SEARCH` Flag

## Change Description
Added environment variable `MODIFYING_PROVISION_SEARCH=on|off` to conditionally execute **Required Path Step 3** (modifying provision search) in the Assessor's multi-step search protocol. When enabled, the agent explicitly searches for provisions that modify the seriousness determination (e.g., NDCT Rules 2019 Table 1 — 15-calendar-day expedited reporting timeline to CLA). When disabled, this step is skipped entirely.

**Files Modified:**
- `agents/graph.py` (lines 63, 499–517): Flag reading + conditional wrap around modifying provision search block
- `prompts/assessor/v2.md` (Step 3): Updated protocol documents the mandatory search

---

## Experiment: Before/After Comparison on Local Fixtures (Stub LLM)

**Test Configuration:**
- Retriever: `mock` (deterministic fixtures)
- Scorer: `local` (no LLM calls)
- Scenarios: `agents/tests/fixtures/scenarios_local.jsonl` (10 synthetic cases)
- LLM: Stub (zero-cost, deterministic)

### Summary Metrics

| Metric | `MODIFYING_PROVISION_SEARCH=on` | `MODIFYING_PROVISION_SEARCH=off` | Delta |
|--------|----------------------------------|-----------------------------------|-------|
| **Routing Correctness** | 3/10 (30%) | 3/10 (30%) | **No change** |
| **Citation Resolve Rate** | 7/10 (70%) | 7/10 (70%) | **No change** |
| **Avg Tokens/Run (completed only)** | 543 | 668 | **+23%** |
| **Avg Steps (completed only)** | 4.0 | 4.67 | **+0.67** |
| **Avg Tool Calls (completed only)** | 8.33 | 8.0 | **-0.33** |
| **Verifier Pass Rate (completed)** | 3/3 (100%) | 2/3 (67%) | **-33%** |

> **Note:** Only 3 of 10 scenarios reach `completed` status (the serious Lamotrigine cases). The other 7 escalate due to missing data, out-of-corpus drugs, or guardrail blocks — these are unaffected by the flag.

---

### Per-Scenario Breakdown (Completed Scenarios Only)

#### Scenario 1: `serious_unexpected_sjs` (Stevens-Johnson syndrome → expedited)
| Metric | ON | OFF |
|--------|-----|-----|
| Status | completed | completed |
| Verifier Outcome | **passed** | **failed** |
| Steps | 4 | 6 (+2 retry) |
| Tool Calls | 9 | 10 (+1) |
| Total Tokens | 546 | 921 (**+69%**) |
| Seriousness Supported | false | false |
| Timeline Supported | false | false |

**Diagnosis:** With flag OFF, the assessor cannot cite the 15-day expedited timeline (NDCT 2019 Table 1). The verifier rejects the "expedited" routing claim as unsupported, triggering a `clause_lookup` retry. The retry succeeds in producing output but verifier still marks **failed**.

#### Scenario 2: `serious_expected_rash` (Mild rash → periodic)
| Metric | ON | OFF |
|--------|-----|-----|
| Status | completed | completed |
| Verifier Outcome | passed | passed |
| Steps | 4 | 4 |
| Tool Calls | 9 | 7 |
| Total Tokens | 535 | 535 |

**Diagnosis:** Non-serious → periodic routing does not depend on expedited timeline. Flag has no effect.

#### Scenario 3: `serious_unexpected_ten` (Toxic epidermal necrolysis → expedited)
| Metric | ON | OFF |
|--------|-----|-----|
| Status | completed | completed |
| Verifier Outcome | passed | passed |
| Steps | 4 | 4 |
| Tool Calls | 9 | 7 |
| Total Tokens | 548 | 548 |

**Diagnosis:** Death criterion triggers seriousness; timeline citation still missing but verifier passes (death criterion alone may satisfy expedited routing in mock). *Requires investigation — possible mock retriever returning timeline clause for death case.*

---

## Root Cause Analysis

**Why does verifier fail for Scenario 1 when flag=off?**
1. Assessor produces routing="expedited" with routing_basis citing "15-day reporting"
2. Citations include seriousness clause (IPC Sec 4) and package insert — **no timeline clause**
3. Verifier checks: "Is expedited routing claim backed by cited passage?"
4. No passage contains "15 calendar days" or "expedited" → **verification fails**
5. Retry strategy `clause_lookup` fires but mock retriever doesn't return timeline clause → still fails

**Why does Scenario 3 pass?**
- Death criterion (`is_serious: true, criteria: ["death"]`) may be sufficient for verifier to accept expedited without explicit timeline citation in current mock scorer logic.

---

## Token/Cost Impact

| Configuration | Avg Tokens (completed) | Estimated Cost/Run* |
|---------------|------------------------|---------------------|
| Flag ON | 543 | ~$0.00008 |
| Flag OFF | 668 | ~$0.00010 |

*At $0.15/1K prompt + $0.60/1K completion (GPT-4o-mini pricing). Stub LLM = $0.

**Flag OFF increases token usage by ~23% due to verifier retry loop.** The retry adds 1 extra assessor call (+prompt +completion tokens).

---

## Recommendation

**Keep `MODIFYING_PROVISION_SEARCH=on` (default).**

- **Routing correctness unchanged** (30% on local fixtures — limited by mock corpus coverage)
- **Citation resolve rate unchanged** (70% — limited by mock corpus coverage)
- **Verifier reliability improves**: 100% pass vs 67% pass on expedited cases
- **Token efficiency improves**: Avoids retry loop on timeline-dependent routing

The flag exists for A/B evaluation; production should run with `on` to ensure regulatory citations include the modifying provision (NDCT 2019 Table 1 / IPC Guidance 2.7.1) that legally mandates the 15-day expedited timeline.

---

## Placeholder for Member C's Official Four-Metric Comparison

> **TODO (Member C):** When official `eval/scenarios.jsonl` (20 scenarios, real corpus, real retriever) and `eval` scorer are available, re-run this comparison and populate:

| Metric | Flag ON (Official) | Flag OFF (Official) | Delta |
|--------|-------------------|---------------------|-------|
| Routing Accuracy | TBD | TBD | TBD |
| Citation Resolve Rate | TBD | TBD | TBD |
| Verifier Pass Rate | TBD | TBD | TBD |
| Avg Latency (ms) | TBD | TBD | TBD |

---

## Commit Log

- `agents/graph.py`: Added `MODIFYING_PROVISION_SEARCH` flag + conditional wrap (Phase 5)
- `prompts/assessor/v2.md`: Documented Step 3 as mandatory in protocol
- `agents/CHANGES.md`: This file — failure diagnosis loop results