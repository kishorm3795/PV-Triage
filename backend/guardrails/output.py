"""guardrails/output.py - Regulatory non-delegation output filter.

Blocks any agent output that asserts an authoritative or final regulatory submission
or legal decision (e.g., 'submitted to CLA', 'approved for filing', 'I have reported').

Under statutory mandates (IPC, CDSCO, US FDA, EMA), the automated AI system
only RECOMMENDS triage routing and statutory deadlines; a qualified human expert
(Qualified Person for Pharmacovigilance / QPPV) makes all official filing decisions.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger("guardrails.output")

# Forbidden assertions of autonomous legal submission or execution
NON_DELEGATION_PATTERNS = [
    re.compile(r"(?i)\b(i\s+have\s+submitted|has\s+been\s+submitted\s+to\s+regulatory|submitted\s+to\s+cdsco|submitted\s+to\s+cla)\b"),
    re.compile(r"(?i)\b(approved\s+for\s+filing|official\s+submission\s+complete|filing\s+is\s+finalized)\b"),
    re.compile(r"(?i)\b(i\s+have\s+reported|report\s+has\s+been\s+filed|formally\s+submitted)\b"),
    re.compile(r"(?i)\b(binding\s+regulatory\s+ruling|statutory\s+judgment\s+rendered)\b"),
]


def check_regulatory_output(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Inspect output text to ensure it adheres to regulatory non-delegation rules.

    Returns:
        (violates_non_delegation, reason)
    """
    if not text or not isinstance(text, str):
        return False, None

    for regex in NON_DELEGATION_PATTERNS:
        match = regex.search(text)
        if match:
            violation = match.group(0)
            reason = (
                f"Non-delegation safety violation: output asserts final submission or filing ('{violation}'). "
                f"The system may only produce recommendations for human QPPV review."
            )
            logger.error("Regulatory output guardrail tripped: %s", reason)
            return True, reason

    return False, None


def sanitize_or_frame_recommendation(text: str) -> str:
    """Ensure output explicitly frames findings as a decision-support recommendation."""
    if "recommend" not in text.lower():
        return f"Recommendation for Qualified Person review: {text}"
    return text
