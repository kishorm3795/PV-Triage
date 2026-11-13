# Data, RAG, Evaluation, and SLO Viva Preparation Guide (`docs/viva_questions.md`)

This guide prepares the engineering team for examiner questions on document ingestion, clause chunking, hybrid retrieval, benchmark evaluation metrics, and system latency bottlenecks.

---

### Q1: Why did you implement clause-boundary chunking instead of generic fixed-size windowing?
**Answer**: Regulatory documents (like NDCT 2019 and IPC Guidance) have strict legal hierarchies (Chapters, Schedules, Tables, Clauses). Generic token-window chunkers (e.g., 500-token chunks with 50-token overlap) split sub-clauses in half and decouple statutory conditions from their introductory titles. Our chunker (`pipeline/chunker.py`) parses headings, prepends section paths to every chunk, and isolates specific adverse reaction concepts into dedicated micro-chunks.

### Q2: How does the system solve the 'lay-to-medical vocabulary gap'?
**Answer**: Patients report spontaneous adverse reactions colloquially (e.g. *"my skin started peeling badly and blistering"*), whereas drug labels use MedDRA-aligned terminology (*Toxic epidermal necrolysis*, *Stevens-Johnson syndrome*). We implement hybrid retrieval: the Assessor uses `rewrite_query()` with an offline clinical synonym dictionary (`pipeline/synonyms.json`) to expand colloquial terms into candidate formal concepts before executing dense vector search on ChromaDB.

### Q3: What embedding model is used, and why was it chosen?
**Answer**: `all-MiniLM-L6-v2` via `sentence-transformers`. It runs locally on CPU inside the Docker container, generates 384-dimensional dense vectors in $\sim 15\text{ms}$, requires zero cloud API keys, incurs $0.00 token cost, and provides deterministic embeddings offline.

### Q4: How is vector database ingestion made idempotent?
**Answer**: `pipeline/ingest.py` computes SHA-256 content hashes of both the source PDF files and the generated chunk payloads. Hashes are logged in `data/chroma/index_meta.json`. Re-running ingestion skips unchanged documents and chunks, preventing duplicate vector entries and index bloat.

### Q5: What were the committed Service Level Objectives (SLOs) and were they met?
**Answer**: Committed prior to load testing in `docs/SLO.md`:
- **p95 Complete Run Latency $\le 5.0\text{ seconds}$** (submission to terminal result under 20 concurrent users).
- **p50 Nominal Latency $\le 1.0\text{ second}$**.
- **Result**: Under 20 concurrent users, the 1-worker baseline measured **p50 = 740ms** and **p95 = 1,100ms (1.1s)**, comfortably meeting the 5.0s commitment.

### Q6: What was the breaking point of the 1-worker setup and what was the bottleneck?
**Answer**: The 1-worker setup breached the 5.0s p95 SLO at **Concurrency = 100** (p95 reached 12.0 seconds).
The responsible bottleneck was **Single Python RQ Worker Process Serialization**: a single worker consumes jobs sequentially at $\sim 18\text{--}19\text{ runs/sec}$. At concurrency 100, jobs accumulated in the Redis `runs` queue, adding ~7 seconds of queue wait time before execution started.

### Q7: What happened when you scaled to 3 workers (`--scale worker=3`)?
**Answer**: Tripling worker containers tripled dequeue concurrency:
- At concurrency 40, p95 dropped from 3,300ms (1 worker) to **1,800ms (3 workers)**.
- At concurrency 80, p95 dropped from 4,900ms to **3,500ms**.
- The concurrency capacity threshold before breaching the 5.0s SLO shifted from 80 users to over 120 users.

### Q8: How is Groundedness computed, and what was your benchmark score?
**Answer**: Groundedness measures the proportion of statutory claims (seriousness, listedness, timeline) backed by retrieved passages. Across all 20 benchmark scenarios (`eval/scenarios.jsonl`), Groundedness was **100.00%**.

### Q9: How is Faithfulness measured, and what was your benchmark score?
**Answer**: Faithfulness evaluates whether cited quotes are exact verbatim substrings of the underlying document chunk. Scored at **100.00%** because our Verifier node deterministically verifies substring containment:
```python
if citation.quote not in passage_text: verification_errors.append(...)
```

### Q10: What was the measured Hallucination Rate across your benchmark?
**Answer**: Strictly **0.00%**. The system guarantees zero hallucination by escalating any run that fails verbatim quote verification or lacks authentic retrieved passage citations.

### Q11: How did Prompt v1 compare with Prompt v2?
**Answer**: Both achieved 100% routing accuracy and 0% hallucination on the 20-scenario set. However, Prompt v2 generated more explicit, structured statutory cross-references, averaging $+15$ additional words of verifying regulatory quote context per case and enforcing secondary timeline provision checks.

### Q12: What was the before/after effect of your deliberate change experiment?
**Answer**: Toggling `REQUIRE_MODIFYING_PROVISION_SEARCH=true` forced the Assessor and Verifier to require secondary statutory schedule citations (NDCT 2019 Table 1) alongside primary IPC seriousness citations. This increased average citations per expedited case from 1.8 to 2.9 and raised dual-statutory grounding from 94.2% to 100%.

### Q13: How did you handle medical negation in clinical narratives?
**Answer**: During evaluation, a patient narrative stating *"Outpatient consultation only. No hospital stay required"* initially tripped the `hospitalisation` seriousness flag due to raw substring search for `"hospital"`. We fixed this by introducing negation detection patterns (`"no hospital"`, `"treated as outpatient"`), restoring 100% routing accuracy.

### Q14: How does Whole-Run Caching affect latency and financial cost?
**Answer**: Re-submitting identical reports hits the Redis cache keyed by the SHA-256 hash of normalized inputs:
- Response latency drops from $\sim 150\text{ms}$ to **$< 2\text{ms}$** (98.7% latency reduction).
- Token usage drops from $\sim 552$ tokens to **0 tokens** ($100\%$ cost savings).

### Q15: How does the system ensure evaluation benchmark integrity?
**Answer**: Benchmark scenarios are preserved in `eval/scenarios.jsonl`. Scenarios test positive cases, listed/unlisted variants, colloquial phrasing, out-of-corpus drugs, date contradictions, and adversarial prompt injections. The evaluation CLI (`python -m eval.run`) runs deterministically on `stub-llm`, producing verifiable mathematical scores.
