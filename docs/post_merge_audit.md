# Post-Merge Audit Report: 15 Improvements (Member C)

**Date**: November 10, 2026  
**Branch**: `c/data`  
**Base Commit (Merged Main)**: `00cd4d9 Merge pull request #14 from kishorm3795/c/data`  
**Scope**: `pipeline/`, `corpus/`, `eval/`, `docs/` only. Strictly zero edits to Member A (`api/`, `worker/`, `stub_llm/`, `infra/`, `loadtest/`, `shared/`, `scripts/`) or Member B (`agents/`, `llm/`, `prompts/`, `guardrails/`).

---

## 1. Summary of 15 Post-Merge Commits

| # | Commit | Type | Description | Files Touched |
|---|--------|------|-------------|---------------|
| 1 | `f0fd4bc` | `docs` | Synchronized `docs/corpus.md` with disk files on `main` (exact SHA-256 hashes, byte sizes, page counts, CDSCO/FDA source URLs). | `docs/corpus.md` |
| 2 | `ba1f15d` | `test` | Added `eval/test_corpus_manifest_matches_disk.py` to assert disk files strictly match `docs/corpus.md`. | `eval/test_corpus_manifest_matches_disk.py` |
| 3 | `cc9c9e2` | `test` | Added `eval/test_contract_passage_compliance.py` asserting all chunker passages comply with `shared/contracts.py::Passage`. | `eval/test_contract_passage_compliance.py` |
| 4 | `fe7aec9` | `refactor` | Made `pipeline/retrieval.py` raise clean informative `FileNotFoundError`/`LookupError` on missing directories; added `eval/test_retrieval_errors.py`. | `pipeline/retrieval.py`, `eval/test_retrieval_errors.py` |
| 5 | `38cec7b` | `fix` | Expanded `pipeline/synonyms.json` covering lay terminology for angioedema, neutropenia, pancreatitis, and mucosal erosions. | `pipeline/synonyms.json` |
| 6 | `4552ac2` | `test` | Added `eval/test_synonym_expansion.py` asserting bi-directional query expansion for lay terminology. | `eval/test_synonym_expansion.py` |
| 7 | `a2a1e43` | `refactor` | Extracted citation resolution into modular `pipeline/citation.py` with standalone unit test `eval/test_citation.py`. | `pipeline/citation.py`, `eval/test_citation.py` |
| 8 | `3c49f7e` | `test` | Added `eval/test_scenario_schema.py` enforcing all 20 eval scenarios strictly validate against `api/contract/report.schema.json`. | `eval/test_scenario_schema.py` |
| 9 | `b80dd2e` | `test` | Added `eval/test_scenario_quotes_verbatim.py` checking verbatim quote existence in corpus PDFs with normalized whitespace. | `eval/test_scenario_quotes_verbatim.py` |
| 10 | `f2cba2e` | `docs` | Added `docs/retrieval_benchmarks.md` documenting measured Recall@1, 3, 5 across all 20 scenarios with multi-turn agent analysis. | `docs/retrieval_benchmarks.md` |
| 11 | `61ddfe3` | `chore` | Added fast verification CLI `python -m eval.verify` executing corpus, schema, and quote checks in < 2.0s (measured 0.012s). | `eval/verify.py` |
| 12 | `b683f95` | `docs` | Updated `docs/runbook.md` with zero-downtime corpus re-indexing procedure using atomic directory swap (`data/chroma_next`). | `docs/runbook.md` |
| 13 | `e1a9026` | `fix` | Handled edge cases in PDF chunker (`pipeline/chunker.py`) for blank/trailing pages and non-standard text blocks; added `eval/test_chunker_edge_cases.py`. | `pipeline/chunker.py`, `eval/test_chunker_edge_cases.py` |
| 14 | `50962a1` | `test` | Added `eval/test_pipeline_idempotence.py` asserting that re-ingesting corpus produces identical chunk counts and deterministic content hashes. | `eval/test_pipeline_idempotence.py` |
| 15 | (current) | `docs` | Added `docs/post_merge_audit.md` consolidating the audit record, git history, and test execution outputs. | `docs/post_merge_audit.md` |

---

## 2. Verification Suite Execution (`python -m eval.verify`)

```bash
$ python3 -m eval.verify
=== PV-Triage Fast Verification Suite (eval.verify) ===
[1/3] Checking corpus manifest against disk files ... PASS
[2/3] Checking scenario schema compliance ... PASS
[3/3] Checking verbatim quote presence (20 scenarios) ... PASS
=== ALL CHECKS PASSED in 0.012s (< 2.0s target) ===
```

---

## 3. Git Log (`git log --oneline -18`)

```text
<COMMIT_15> docs: add docs/post_merge_audit.md summarising all 15 post-merge improvements
50962a1 test: add test_pipeline_idempotence.py asserting identical chunk counts and metadata on re-ingest
e1a9026 fix: make pipeline/chunker.py handle edge cases in PDF extraction cleanly
b683f95 docs: update docs/runbook.md with exact zero-downtime corpus re-indexing procedure
61ddfe3 chore: add lightweight CLI check python -m eval.verify running fast checks in < 2s
f2cba2e docs: add docs/retrieval_benchmarks.md recording recall@1,3,5 on 20 scenarios
b80dd2e test: add test_scenario_quotes_verbatim.py ensuring all quotes exist verbatim in corpus
3c49f7e test: add test_scenario_schema.py ensuring all scenarios satisfy report.schema.json
a2a1e43 refactor: extract citation resolution into pipeline/citation.py with unit tests
4552ac2 test: add test_synonym_expansion.py asserting lay phrase mappings to clinical terms
38cec7b fix: improve lay-to-clinical synonym coverage for angioedema, neutropenia, pancreatitis, and mucosal erosions
fe7aec9 refactor: make pipeline/retrieval.py raise clean informative errors for missing Chroma directory
cc9c9e2 test: add test_contract_passage_compliance.py asserting Passage contract conformity
ba1f15d test: add test_corpus_manifest_matches_disk.py verifying docs/corpus.md files
f0fd4bc docs: sync docs/corpus.md with merged main
00cd4d9 (origin/main, origin/HEAD, main) Merge pull request #14 from kishorm3795/c/data
f36fdd3 (origin/c/data) docs(report): Phase 6 - complete runbook, incident log, verified README, report skeleton, and 10 demo items
31d493e feat(eval): Phase 5 - evaluation harness, RAG triad metrics, v1/v2 comparison, and deliberate change benchmark
```
