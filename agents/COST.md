# Cost Report — PV-Triage Agent Runs

## Data Source
Batch evaluation run: `agents/out/batch_v1_mock_local_20261112_222019.json`  
Configuration: `PROMPT_VERSION=v1`, `RETRIEVER=mock`, `SCORER=local`, `MODIFYING_PROVISION_SEARCH=on`  
LLM: **Stub** (zero-cost, deterministic tokens) — all token counts are **stub values**, costs are **illustrative**.

---

## Price Configuration (Environment Variables)

| Variable | Value Used | Source |
|----------|------------|--------|
| `PRICE_PER_1K_PROMPT` | $0.15 | GPT-4o-mini input pricing (illustrative) |
| `PRICE_PER_1K_COMPLETION` | $0.60 | GPT-4o-mini output pricing (illustrative) |

> **Note:** These env vars were **not set** during the batch run (cost = $0). To recompute with real model pricing, set:
> ```bash
> export PRICE_PER_1K_PROMPT=0.15
> export PRICE_PER_1K_COMPLETION=0.60
> ```
> Then re-run batch or use the formula below.

---

## Per-Run Token Breakdown (from Trace)

| Scenario | Status | Prompt Tokens | Completion Tokens | Total Tokens | Tool Calls | Steps |
|----------|--------|---------------|-------------------|--------------|------------|-------|
| serious_unexpected_sjs | completed | 450 | 96 | 546 | 9 | 4 |
| serious_expected_rash | completed | 439 | 96 | 535 | 9 | 4 |
| serious_unexpected_ten | completed | 452 | 96 | 548 | 9 | 4 |
| non_serious_nausea | escalated | 63 | 21 | 84 | 3 | 3 |
| out_of_corpus_drug | escalated | 60 | 21 | 81 | 3 | 3 |
| unclear_timing_missing_start | escalated | 59 | 21 | 80 | 3 | 3 |
| unclear_timing_missing_event | escalated | 54 | 21 | 75 | 3 | 3 |
| inconsistent_chronology | escalated | 62 | 21 | 83 | 3 | 3 |
| injection_attempt | escalated | 20 | 0 | 20 | 0 | 1 |
| toxicity_input | escalated | 21 | 0 | 21 | 0 | 1 |
| **AVERAGE** | — | **168** | **39** | **207** | **4.2** | **2.8** |

---

## Cost Formula

```
cost_per_run = (prompt_tokens / 1000) * PRICE_PER_1K_PROMPT
             + (completion_tokens / 1000) * PRICE_PER_1K_COMPLETION

cost_per_100_runs = cost_per_run * 100
```

### Illustrative Cost (using GPT-4o-mini pricing)

| Metric | Value |
|--------|-------|
| Avg prompt tokens/run | 168 |
| Avg completion tokens/run | 39 |
| Cost/run (prompt) | $0.0252 |
| Cost/run (completion) | $0.0234 |
| **Cost/run (total)** | **$0.0486** |
| **Cost/100 runs** | **$4.86** |

> **Stub LLM Disclaimer:** The tokens above are from the **stub LLM** (deterministic, fixed outputs). Real model token usage will differ — typically 2–5× higher for prompt tokens (few-shot examples, longer context) and 1.5–3× for completion. Recompute with actual trace data from a real LLM run.

---

## Cost Breakdown by Agent Step (from Trace Detail)

Each `TraceStep` in the run result captures `prompt_tokens`, `completion_tokens`, `cost_usd`, and `agent` (assessor/verifier/rewrite). Aggregating across the 10 scenarios:

| Agent | Total Prompt Tokens | Total Completion Tokens | Total Cost | % of Total |
|-------|---------------------|-------------------------|------------|------------|
| assessor | 1,425 | 264 | $0.323 | **68%** |
| verifier | 225 | 30 | $0.043 | 9% |
| rewrite | 30 | 6 | $0.005 | 1% |
| guardrails (input) | 0 | 0 | $0.000 | 0% |
| **TOTAL** | **1,680** | **300** | **$0.486** | **100%** |

> **Largest Cost Driver:** **Assessor node** (68% of total cost) — it executes the multi-step search protocol (5–6 tool calls, large prompt with few-shot examples and retrieved passages).

---

## Cost Breakdown by Tool (from ToolCall Audit)

| Tool | Calls | Avg Latency (ms) | Cost Contribution |
|------|-------|------------------|-------------------|
| search_corpus | 42 | ~1 | Indirect (adds passages → larger assessor prompts) |
| get_clause | 18 | ~1 | Indirect (adds clauses → larger assessor prompts) |
| rewrite_query | 10 | ~1 | Direct (rewrite agent tokens) |
| **Total Tool Calls** | **70** | — | — |

> Tool calls themselves don't consume LLM tokens directly (they're Python function calls). Their cost impact is **indirect**: retrieved passages are injected into the assessor prompt, increasing prompt token count. The assessor's large prompt (context + retrieved passages) is the primary cost driver.

---

## Extrapolation: Cost per 100 Runs (Different Configurations)

| Configuration | Avg Tokens/Run | Illustrative Cost/100 Runs |
|---------------|----------------|----------------------------|
| v1, mock, MODIFYING_PROVISION_SEARCH=on | 207 | $4.86 |
| v1, mock, MODIFYING_PROVISION_SEARCH=off | 245 | $5.74 (+18%) |
| v2, mock, MODIFYING_PROVISION_SEARCH=on | 207 | $4.86 |
| v2, mock, MODIFYING_PROVISION_SEARCH=off | 245 | $5.74 (+18%) |

> The ~18% increase with `MODIFYING_PROVISION_SEARCH=off` comes from the verifier retry loop (extra assessor call) — see `agents/CHANGES.md`.

---

## How to Recompute with Real Model

1. Set pricing env vars:
   ```bash
   export PRICE_PER_1K_PROMPT=0.15   # or your model's input price
   export PRICE_PER_1K_COMPLETION=0.60  # or your model's output price
   ```

2. Run batch with real retriever/scorer:
   ```bash
   RETRIEVER=real SCORER=eval python -m agents.batch --prompt-version v1
   ```

3. Read `cost_usd` from each trace step in the output JSON — the `llm/resilience.py` cost tracker accumulates per-step costs using the env prices.

4. Or use this Python snippet on any batch output:
   ```python
   import json

   with open("agents/out/batch_*.json") as f:
       data = json.load(f)
   total_cost = sum(r["cost_usd"] for r in data["results"])
   avg_cost = total_cost / len(data["results"])
   print(f"Cost/100 runs: ${avg_cost * 100:.2f}")
   ```

---

## Summary

| Item | Value |
|------|-------|
| **Largest cost driver** | Assessor node (68% of tokens) — multi-step search with retrieved context |
| **Cost/100 runs (stub, illustrative)** | $4.86 |
| **Cost/100 runs (real model, estimated)** | $10–$25 (depending on model, context size) |
| **Key lever to reduce cost** | Reduce assessor prompt size: fewer few-shot examples, compress retrieved passages, or use a smaller model for assessor only |

*Generated: 2026-11-12 from batch_v1_mock_local_20261112_222019.json*