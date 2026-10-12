"""pipeline/models.py - Pipeline data models matching shared/contracts.py.

Frozen interface conformance:
Shared data model Passage defined in shared/contracts.py.
Member C owns pipeline/ and ensures models conform to shared contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from shared.contracts import Passage

__all__ = ["Passage"]
