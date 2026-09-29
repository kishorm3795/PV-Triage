# PV-Triage: Pharmacovigilance Adverse Event Intake & Triage Service

> **UE24AM342AA5 — ML System Design & AgentOps | Mini Project 14 (Level 3)**  
> An automated, production-grade multi-agent pharmacovigilance system designed to ingest adverse event reports, ground assessments against regulatory corpora, and route cases to expedited, periodic, or non-reportable triage streams with cited evidence.

---

## 📖 About the Project

Pharmaceutical organizations must systematically evaluate adverse drug reaction (ADR) reports received from clinicians, patients, and literature. Regulatory authorities mandate reporting within strict timelines based on two primary dimensions:
1. **Seriousness**: Determining if the reaction resulted in death, inpatient hospitalization, disability, or congenital anomaly.
2. **Expectedness**: Determining whether the reaction is listed within approved drug product information (package inserts).

The combination of seriousness and expectedness dictates the statutory reporting pathway (**expedited reporting** within fixed calendar days vs. **periodic safety update reporting**).

### Core Principles
- **Recommends Only**: The system acts strictly as decision support for a Qualified Person for Pharmacovigilance (QPPV). It never submits a regulatory filing autonomously.
- **Evidence or Silence**: Every claim must be grounded in and cite verbatim text retrieved from approved regulatory documents during that specific run. An unverified answer is never returned.
- **Fail-Safe & Escalation**: When drug names fall outside the corpus, timing is ambiguous, or medical terms cannot be matched with confidence, the system escalates directly to a human specialist.
- **Production Architecture**: Built as an asynchronous, containerized service with request validation, queuing, scalable workers, circuit breakers, and end-to-end observability.

---

## 👥 3-Member Work Division

The system boundaries are partitioned cleanly across three members to allow parallel development without merge conflicts:

| Member | Focus Area | Owned Modules & Folders | Key Responsibilities |
| :--- | :--- | :--- | :--- |
| **Member A** | **Platform & Infrastructure** | `api/`, `worker/`, `stub_llm/`, `infra/`, `loadtest/`, `shared/`, `scripts/` | FastAPI REST intake boundary, schema validation & quarantine, Redis task queue, worker lifecycle, stub LLM service, Docker Compose, monitoring (Prometheus & Jaeger), Locust load testing, and the clinical web client. |
| **Member B** | **Agent Core & LLMOps** | `agents/`, `llm/`, `prompts/`, `guardrails/` | LangGraph multi-agent architecture (Assessor & Verifier agents), prompt versioning, agent tools (query rewriting, clause lookup), security guardrails (prompt injection & toxicity defense), and circuit breakers for LLM resilience. |
| **Member C** | **Data, RAG & Evaluation** | `pipeline/`, `corpus/`, `eval/`, `docs/` | Regulatory corpus processing (NDCT Rules 2019, IPC guidelines, package inserts), idempotent RAG chunking & Chroma vector storage, bridging lay-to-medical terms, 20-scenario eval benchmark (groundedness, faithfulness, hallucination scoring), and runbook/incident tracking. |

---

## 🗺️ Project Phases Overview

Each phase represents a milestone where all three team members deliver cohesive components that integrate at defined sync points:

### **Phase 1: Skeleton, Corpus & LLM Interface**
* **Goal**: Establish the base runnable skeleton so `docker compose up` serves end-to-end requests with mock implementations.
* **What We Do**:
  * **Member A**: Creates `docker-compose.yml` (API, worker, Redis, stub LLM), establishes input validation and quarantine in FastAPI, and provisions the async queue.
  * **Member B**: Builds the LLM client abstraction (supporting stub and Gemini), versioned prompt loaders, and an initial LangGraph agent skeleton with mock tools.
  * **Member C**: Verifies text layers for regulatory PDFs, documents corpus metadata, extracts exact reference case passages, and establishes the reference benchmark.

### **Phase 2: Ingestion Pipeline & Hybrid Retrieval**
* **Goal**: Replace mock retrieval with a real, idempotent vector indexing and search pipeline.
* **What We Do**:
  * **Member A**: Adds Prometheus and Jaeger services to Docker Compose, configures a one-shot ingestion container, and connects service health checks.
  * **Member B**: Implements the query rewriter tool (converting colloquial patient descriptions to medical terms) and connects agents to the real retrieval adapter.
  * **Member C**: Builds the document ingestion CLI (page-aware parsing, clause-boundary chunking, sentence-transformers embeddings, and Chroma index generation).

### **Phase 3: Multi-Agent Reasoning & Self-Verification**
* **Goal**: Implement the two-agent reasoning and verification loop; successfully pass the complex reference case.
* **What We Do**:
  * **Member A**: Integrates the real LangGraph graph into Redis RQ workers, manages job failure states, and formats structured JSON logs with correlation IDs.
  * **Member B**: Implements the **Assessor** (plans tool calls, drafts recommendations with citations) and **Verifier** (checks citation existence and claim groundness; requests retries or triggers escalation on failure).
  * **Member C**: Tunes retrieval recall (addressing lay-vs-medical vocabulary mismatches) and constructs the first 10 scenarios in the evaluation benchmark.

### **Phase 4: Safety, Resilience & Observability**
* **Goal**: Ensure the system fails safely under malicious input, service outages, and high latency.
* **What We Do**:
  * **Member A**: Instruments OpenTelemetry spans across agent steps and tool calls, exposes Prometheus metrics, and implements the `/trace` reconstruction endpoint.
  * **Member B**: Adds prompt injection defense, output filtering (preventing unauthorized final determinations), and circuit breaker fallbacks.
  * **Member C**: Completes the full 20-scenario evaluation suite, creates automated validation checks, and establishes the incident log and runbook.

### **Phase 5: Evaluation & Load Testing**
* **Goal**: Execute load testing against predefined SLOs and measure agent evaluation metrics.
* **What We Do**:
  * **Member A**: Commits the p95 latency Service Level Objective (SLO), executes Locust load tests on 1 vs. 3 workers, and identifies system bottlenecks.
  * **Member B**: Introduces prompt variant `v2`, tests deliberate system modifications, and conducts comparative ablation analyses.
  * **Member C**: Executes automated evaluation runs measuring Groundedness, Context Relevance, Faithfulness, and Hallucination rates before and after system modifications.

### **Phase 6: Web Client, Cost Optimization & Final Polish**
* **Goal**: Finalize system integration, package documentation, and prepare for live demonstration.
* **What We Do**:
  * **Member A**: Deploys the clinical-grade single-page web client (`api/web/`), configures per-client rate limiting, and implements response caching in Redis.
  * **Member B**: Generates per-step token cost accounting, analyzes cost drivers, and conducts soak tests.
  * **Member C**: Audits all repository deliverables, finalizes the demonstration script, and verifies all citation claims against original regulatory texts.

---

## 🏗️ Architecture Overview

```
                      ┌───────────────────────────────────────────────┐
                      │                 Client Layer                  │
                      │         (Web Client / REST API / curl)        │
                      └───────────────────────┬───────────────────────┘
                                              │ POST /v1/reports
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │                 FastAPI (api)                 │
                      │   - Pydantic Validation & Ingestion Boundary  │
                      │   - Rate Limiting & Response Cache            │
                      │   - Quarantine for Malformed Requests         │
                      └──────────────┬─────────────────▲──────────────┘
                        Enqueue Job  │                 │ Poll Status
                                     ▼                 │
                      ┌────────────────────────────────┴──────────────┐
                      │              Redis (Queue & State)            │
                      │        RQ Jobs | Run States | Cache           │
                      └───────────────────────┬───────────────────────┘
                                              │ Worker picks job
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │             LangGraph Worker Node             │
                      │                                               │
                      │   [Input Guardrails (Injection / Toxicity)]   │
                      │                       │                       │
                      │                       ▼                       │
                      │             ┌───────────────────┐             │
                      │             │  Assessor Agent   │◄────────┐   │
                      │             │  (Plan & Draft)   │         │   │
                      │             └─────────┬─────────┘         │   │
                      │                       │ Draft             │   │
                      │                       ▼                   │   │
                      │             ┌───────────────────┐         │   │
                      │             │  Verifier Agent   │──Retry──┘   │
                      │             │(Citation Verify)  │  (Max 2)    │
                      │             └─────────┬─────────┘             │
                      │                       │ Pass / Escalate       │
                      │                       ▼                       │
                      │         [Output Filter & Result Store]        │
                      └───────────────┬───────────────┬───────────────┘
                                      │               │
                     Tools & Retrieval│               │ Metrics & Traces
                                      ▼               ▼
                      ┌──────────────────────┐ ┌──────────────────────┐
                      │   Chroma DB Vector   │ │ Observability Stack  │
                      │  - Sentence Embed    │ │ - Prometheus Metrics │
                      │  - Regulatory Corpus │ │ - Jaeger Traces      │
                      │  - Package Inserts   │ │ - Grafana Dashboard  │
                      └──────────────────────┘ └──────────────────────┘
```

---

## 🛠️ Tech Stack

- **Agent Reasoning**: LangGraph, LangChain
- **Backend & Serving**: FastAPI, Pydantic v2, Python 3.11
- **Task Queue & Caching**: Redis, RQ (Redis Queue)
- **Vector Retrieval**: Chroma DB, `sentence-transformers` (`all-MiniLM-L6-v2`)
- **LLM Support**: Google Gemini API / Local Stub LLM (for deterministic load testing)
- **Observability**: OpenTelemetry, Prometheus, Jaeger, Grafana
- **Testing & Benchmarking**: Pytest, Locust, TruLens / LLM evaluation harness
- **Deployment**: Docker, Docker Compose

---

## 🚀 Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/kishorm3795/PV-Triage.git
cd PV-Triage

# Copy the sample environment file
cp .env.example .env
```

### 3. Launch Services
```bash
docker compose up -d --build
```

### 4. Ingest Regulatory Corpus
```bash
docker compose run --rm ingest
```

### 5. Submit an Adverse Event Report
```bash
curl -X POST http://localhost:8000/v1/reports \
  -H "Content-Type: application/json" \
  -d '{
    "report_id": "REP-2026-001",
    "reporter_type": "physician",
    "patient_age": 45,
    "patient_sex": "male",
    "suspect_drug": "Phenytoin",
    "drug_start_date": "2026-01-05",
    "event_date": "2026-01-12",
    "reaction_description": "Patient developed severe skin detachment and erosions on mucous membranes, admitted to intensive care.",
    "outcome": "hospitalized"
  }'
```
