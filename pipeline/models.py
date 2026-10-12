"""pipeline/models.py - Passage dataclass matching shared/contracts.py.

This module provides the Passage dataclass representation for ingestion
and retrieval pipelines, perfectly conforming to the frozen contract
defined in shared/contracts.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
from shared.contracts import Passage as ContractPassage


@dataclass
class Passage:
    """Passage dataclass matching shared/contracts.py."""

    id: str
    text: str
    source_doc: str
    page: Optional[int] = None
    clause_id: Optional[str] = None
    section: Optional[str] = None
    score: Optional[float] = None

    def to_contract(self) -> ContractPassage:
        """Convert to the frozen Pydantic Passage model from shared/contracts.py."""
        return ContractPassage(
            id=self.id,
            text=self.text,
            source_doc=self.source_doc,
            page=self.page,
            clause_id=self.clause_id,
            section=self.section,
            score=self.score,
        )

    @classmethod
    def from_contract(cls, passage: ContractPassage) -> Passage:
        """Construct from a shared/contracts.py Pydantic Passage model."""
        return cls(
            id=passage.id,
            text=passage.text,
            source_doc=passage.source_doc,
            page=passage.page,
            clause_id=passage.clause_id,
            section=passage.section,
            score=passage.score,
        )

    def model_dump(self) -> Dict[str, Any]:
        """Dictionary dump for compatibility with Pydantic v2 interface."""
        return asdict(self)
