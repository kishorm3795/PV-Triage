# Chunking Strategy for PV-Triage Corpus

## Overview

This document describes the chunking strategy used in the PV-Triage corpus ingestion pipeline to address the **lay-vs-medical vocabulary gap** — the fundamental challenge that adverse event reporters use colloquial language (e.g., "skin started peeling badly") while regulatory documents use formal medical terminology (e.g., "toxic epidermal necrolysis", "Stevens-Johnson syndrome").

## The Vocabulary Gap Problem

| Lay Reporter Phrase | Medical Terminology in Corpus |
|---------------------|------------------------------|
| "skin started peeling badly" | Toxic epidermal necrolysis (TEN) |
| "skin peeling" | Stevens-Johnson syndrome (SJS) |
| "bad rash" | Exfoliative dermatitis |
| "blistering" | Vesiculobullous rash |
| "admitted to hospital" | Hospitalization / inpatient hospitalisation |

The exact colloquial phrase **"skin peeling" does not appear anywhere** in the Lamotrigine package insert. A naive semantic search on lay language would miss the critical regulatory passages.

## Chunking Strategy

### 1. Clause-Boundary Chunks

Documents are split at **regulatory clause boundaries** rather than arbitrary character counts:

- **Boxed Warning** sections (e.g., "WARNING: SERIOUS SKIN RASHES")
- **Numbered sections** (e.g., "Section 5.1: Warnings and Precautions")
- **Numbered clauses** (e.g., "2.5.3.6 Seriousness of the reaction")
- **Chapter/Appendix** boundaries

**Why**: Regulatory reasoning operates at the clause level. Keeping clauses intact preserves the legal/regulatory context needed for accurate triage.

### 2. Heading Prepended to Each Chunk

Every chunk has its **section and clause heading prepended**:

```
Section 5.1: Warnings and Precautions - Serious Skin Rashes | 2.5.3.6 Seriousness of the reaction

Among the rashes leading to hospitalization were Stevens-Johnson syndrome, toxic epidermal necrolysis...
```

**Why**: 
- Enables retrieval to match on section context ("Section 5.1", "Boxed Warning")
- Provides grounding for LLM to cite specific regulatory provisions
- Helps bridge vocabulary gap: "Section 5.1" + "hospitalization" retrieves even without "skin peeling"

### 3. Adverse Reaction Term Chunks (Package Insert Specific)

For the **Lamotrigine package insert**, we create **dedicated chunks for each listed adverse reaction term**:

```
Adverse Reaction Term: Stevens-Johnson syndrome
Source: lamotrigine_package_insert.pdf, Page: 32
Listed in package insert under adverse reactions.
Related terms: toxic epidermal necrolysis, exfoliative dermatitis, vesiculobullous rash...
```

**Why**: 
- Creates direct vector representations of medical terms
- When user queries "skin peeling", embedding similarity matches "exfoliative dermatitis" term chunk
- Enables **synonym expansion at retrieval time** without query rewriting
- Each term chunk acts as a "bridge" between lay and medical vocabulary

### 4. Content Hash for Idempotency

Each chunk gets a **SHA-256 content hash** (truncated to 16 chars):

```
chunk_id = "lamotrigine_package_insert.pdf::32::0042::a1b2c3d4e5f67890"
```

**Why**: 
- Unchanged chunks are skipped on re-ingestion (idempotent)
- `--reembed <doc>` only re-processes one document
- `--force` bypasses hash check for full rebuild

## Chunk Metadata

Every chunk carries:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier with source, page, index, hash |
| `text` | Full chunk text with prepended headings |
| `source_doc` | Originating PDF filename |
| `page` | Page number (1-indexed) |
| `clause_id` | Specific clause identifier (e.g., "2.5.3.6") |
| `section` | Section heading (e.g., "Section 5.1: Warnings...") |
| `content_hash` | SHA-256 of text for change detection |

## Retrieval Implications

### For "skin started peeling badly" Query

1. Query embedding → searches vector space
2. Matches **adverse reaction term chunks** (TEN, SJS, exfoliative dermatitis)
3. Matches **clause chunks** containing "hospitalization" + "serious skin rashes"
4. Returns passages with **both medical terms and regulatory context**

### For Medical Term Query ("toxic epidermal necrolysis")

1. Direct match on term chunks and clause chunks
2. High similarity scores due to exact terminology overlap
3. Returns same regulatory passages with full context

## Configuration

- **Max chunk size**: 2000 characters (configurable)
- **Overlap**: 200 characters between chunks
- **Embedding model**: `all-MiniLM-L6-v2` (from `EMBED_MODEL` env var)
- **Vector store**: ChromaDB at `CHROMA_DIR` (default `./data/chroma`)

## Validation

Run ingestion twice — second run should skip unchanged chunks:

```bash
python -m pipeline ingest
python -m pipeline ingest  # Should show "Skipped (unchanged)" for all docs
```

Force re-embed single document:

```bash
python -m pipeline ingest --reembed lamotrigine_package_insert.pdf
```

Full rebuild:

```bash
python -m pipeline ingest --force
```