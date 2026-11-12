"""guardrails/output.py - Output guardrail enforcing regulatory recommendation boundaries.

Blocks any model output or draft claiming a final regulatory action (e.g., "submitted",
"filed", "approved for filing", "I have reported", "report has been sent").

Outputs must strictly read as recommendations for a qualified person (e.g. "recommended routing:").
On detection: ends the run "escalated" with a clear reason and prevents output text release.
Never silently rewrites the text.
"""

from __future__ import annotations

import logging
import re
from typing import NamedTuple, Optional

logger = logging.getLogger("guardrails.output")

# Patterns indicating inappropriate claims of final regulatory submission or filing
REGULATORY_ACTION_BLOCK_PATTERNS = [
    re.compile(r"\b(?:have|has|is|was|were)\s+(?:been\s+)?submitted\b", re.IGNORECASE),
    re.compile(r"\b(?:have|has|is|was|were)\s+(?:been\s+)?filed\b", re.IGNORECASE),
    re.compile(r"\b(?:have|has|is|was|were)\s+(?:been\s+)?reported\b", re.IGNORECASE),
    re.compile(r"\b(?:have|has|is|was|were)\s+(?:been\s+)?sent\b", re.IGNORECASE),
    re.compile(r"\bi\s+have\s+(?:submitted|filed|reported|sent)\b", re.IGNORECASE),
    re.compile(r"\bwe\s+have\s+(?:submitted|filed|reported|sent)\b", re.IGNORECASE),
    re.compile(r"\bapproved\s+for\s+filing\b", re.IGNORECASE),
    re.compile(r"\breport\s+has\s+been\s+sent\b", re.IGNORECASE),
    re.compile(r"\breport\s+(?:is|was)\s+(?:submitted|filed|reported)\b", re.IGNORECASE),
    re.compile(r"\bfiling\s+complete(?:d)?\b", re.IGNORECASE),
    re.compile(r"\bsubmission\s+complete(?:d)?\b", re.IGNORECASE),
    re.compile(r"\bsubmitted\s+to\s+(?:the\s+)?(?:cdsco|fda|regulatory|authorities|national|moh)\b", re.IGNORECASE),
    re.compile(r"\bfiled\s+with\s+(?:the\s+)?(?:cdsco|fda|regulatory|authorities|national|moh)\b", re.IGNORECASE),
    re.compile(r"\breport\s+(?:is|has\s+been)\s+transmitted\b", re.IGNORECASE),
]


class OutputGuardrailResult(NamedTuple):
    passed: bool
    reason: Optional[str] = None
    matched_phrase: Optional[str] = None


def check_output_guardrail(
    text: Optional[str],
    run_id: Optional[str] = None,
) -> OutputGuardrailResult:
    """Validate that agent output does not claim final regulatory filing/submission.

    Args:
        text: Generated assessment narrative or routing basis string.
        run_id: Unique correlation identifier for audit logging.

    Returns:
        OutputGuardrailResult with passed=True if compliant, or passed=False with audit reason.
    """
    if not text:
        return OutputGuardrailResult(passed=True)

    for pattern in REGULATORY_ACTION_BLOCK_PATTERNS:
        match = pattern.search(text)
        if match:
            matched_phrase = match.group(0)
            reason = (
                f"Output guardrail blocked: text claims a final regulatory action "
                f"('{matched_phrase}'). System must only provide recommendations for a qualified person."
            )
            logger.warning(
                "Output guardrail violation [run_id=%s]: %s",
                run_id or "unknown",
                reason,
            )
            return OutputGuardrailResult(
                passed=False,
                reason=reason,
                matched_phrase=matched_phrase,
            )

    return OutputGuardrailResult(passed=True)
