"""agents/tools.py - Agent tool definitions and MockRetriever implementation.

Provides the standard tool interfaces:
  - search_corpus(query, k) -> list[Passage]
  - get_clause(clause_id) -> Passage | None
  - get_request_fields(run_id, report) -> dict
  - rewrite_query(lay_text) -> list[str]
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from shared.contracts import Passage, Retriever


class MockRetriever:
    """Deterministic in-memory Mock Retriever implementing the Retriever protocol."""

    def __init__(self) -> None:
        self.passages: Dict[str, Passage] = {
            "ndct-2019-second-sched-table1": Passage(
                id="ndct-2019-second-sched-table1",
                clause_id="ndct-2019-second-sched-table1",
                source_doc="New Drugs and Clinical Trials Rules 2019",
                page=218,
                section="Second Schedule, Table 1, Clause 4(3)",
                text=(
                    "Any serious unexpected adverse event shall be reported by the sponsor "
                    "or marketing authorisation holder to the Central Licencing Authority "
                    "within fifteen calendar days of receipt of the information."
                ),
                score=0.95,
            ),
            "ipc-pv-guidance-sec4-seriousness": Passage(
                id="ipc-pv-guidance-sec4-seriousness",
                clause_id="ipc-pv-guidance-sec4-seriousness",
                source_doc="IPC Pharmacovigilance Guidance Document for MAHs",
                page=14,
                section="Section 4.1: Seriousness Criteria",
                text=(
                    "A serious adverse event (SAE) or reaction is any untoward medical occurrence that "
                    "at any dose results in death, inpatient hospitalisation or prolongation of existing "
                    "hospitalisation, persistent or significant disability or incapacity, or is a "
                    "congenital anomaly or birth defect, or is life-threatening."
                ),
                score=0.92,
            ),
            "lamotrigine-pi-sec4-8-undesirable": Passage(
                id="lamotrigine-pi-sec4-8-undesirable",
                clause_id="lamotrigine-pi-sec4-8-undesirable",
                source_doc="Lamotrigine Package Insert",
                page=6,
                section="Section 4.8: Undesirable Effects",
                text=(
                    "Adverse reactions reported during clinical trials and post-marketing surveillance: "
                    "Skin and subcutaneous tissue disorders: Very common: skin rash; Rare: Stevens-Johnson "
                    "syndrome (SJS); Very rare: Toxic epidermal necrolysis (TEN). Severe cutaneous adverse "
                    "reactions require immediate discontinuation."
                ),
                score=0.88,
            ),
            "ipc-pv-guidance-sec5-expectedness": Passage(
                id="ipc-pv-guidance-sec5-expectedness",
                clause_id="ipc-pv-guidance-sec5-expectedness",
                source_doc="IPC Pharmacovigilance Guidance Document for MAHs",
                page=18,
                section="Section 5.2: Expectedness Assessment",
                text=(
                    "An adverse reaction is considered unexpected if its nature, severity, specificity, "
                    "or outcome is not consistent with the reference safety information or approved package insert."
                ),
                score=0.85,
            ),
        }

    def search(self, query: str, k: int = 5) -> List[Passage]:
        """Search mock corpus for relevant passages."""
        query_terms = set(query.lower().split())
        scored_passages: List[tuple[float, Passage]] = []

        for p in self.passages.values():
            text_terms = set(p.text.lower().split())
            section_terms = set((p.section or "").lower().split())
            doc_terms = set(p.source_doc.lower().split())

            all_terms = text_terms | section_terms | doc_terms
            matched = query_terms.intersection(all_terms)
            overlap_score = len(matched) / (len(query_terms) + 1e-5)
            final_score = (p.score or 0.8) * (1.0 + overlap_score)
            scored_passages.append((final_score, p))

        scored_passages.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored_passages[:k]]

    def get_clause(self, clause_id: str) -> Optional[Passage]:
        """Retrieve passage by exact clause identifier."""
        return self.passages.get(clause_id)


_DEFAULT_MOCK_RETRIEVER = MockRetriever()


def get_default_retriever() -> Retriever:
    """Return the active retriever instance."""
    return _DEFAULT_MOCK_RETRIEVER


def search_corpus(
    query: str,
    k: int = 5,
    retriever: Optional[Retriever] = None,
) -> List[Passage]:
    """Execute corpus search query against the configured retriever.

    Args:
        query: Natural language or medical search query.
        k: Maximum number of passages to return.
        retriever: Optional custom retriever instance conforming to Retriever protocol.

    Returns:
        List of Passage models.
    """
    active_retriever = retriever or get_default_retriever()
    return active_retriever.search(query, k=k)


def get_clause(
    clause_id: str,
    retriever: Optional[Retriever] = None,
) -> Optional[Passage]:
    """Lookup a specific statutory clause or package insert section by ID.

    Args:
        clause_id: Exact passage or clause ID.
        retriever: Optional custom retriever instance.

    Returns:
        Passage model if found, else None.
    """
    active_retriever = retriever or get_default_retriever()
    return active_retriever.get_clause(clause_id)


def get_request_fields(
    run_id: str,
    report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract and return report fields for the specified run.

    Args:
        run_id: Identifier of the active run.
        report: Dictionary representing the adverse event report payload.

    Returns:
        Dictionary of key report fields.
    """
    if not report:
        return {"run_id": run_id}

    return {
        "run_id": run_id,
        "report_id": report.get("report_id", run_id),
        "suspect_drug": report.get("suspect_drug"),
        "patient_age": report.get("patient_age"),
        "patient_sex": report.get("patient_sex"),
        "reporter_type": report.get("reporter_type"),
        "drug_start_date": str(report.get("drug_start_date", "")),
        "event_date": str(report.get("event_date", "")),
        "reaction_description": report.get("reaction_description"),
        "outcome": report.get("outcome"),
        "narrative": report.get("narrative"),
    }


def rewrite_query(lay_text: str) -> List[str]:
    """Rewrite layperson symptom terms into candidate medical / MedDRA terminology.

    Args:
        lay_text: Free-text symptom or reaction description.

    Returns:
        List of candidate medical search terms.
    """
    lay_lower = lay_text.lower()
    candidates = []

    # Deterministic mapping for common PV reactions
    if "peeling" in lay_lower or "blister" in lay_lower or "skin" in lay_lower:
        candidates.extend([
            "Toxic epidermal necrolysis",
            "Stevens-Johnson syndrome",
            "Severe cutaneous adverse reactions",
            "Erythema multiforme",
        ])
    if "rash" in lay_lower or "hives" in lay_lower:
        candidates.extend(["Urticaria", "Maculopapular rash", "Drug eruption"])
    if "liver" in lay_lower or "jaundice" in lay_lower or "yellow" in lay_lower:
        candidates.extend(["Drug-induced liver injury", "Hepatotoxicity", "Jaundice"])
    if "bleed" in lay_lower or "hemorrhage" in lay_lower:
        candidates.extend(["Gastrointestinal hemorrhage", "Coagulopathy", "Bleeding"])

    if not candidates:
        candidates.append(lay_text.strip())

    return candidates
