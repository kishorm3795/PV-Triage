"""guardrails/toxicity.py - Heuristic toxicity and profanity filter.

Provides an input and output safety filter for gratuitous toxicity, hate speech,
harassment, and abusive profanity while strictly preserving legitimate clinical terminology
(e.g., genital, colorectal, blood, necrotic, death, overdose, suicide attempts in AE narratives).

LIMITATIONS & BOUNDARIES:
- Heuristic dictionary/regex based: targets high-confidence abusive profanity and personal insults.
- Does not replace deep semantic moderation models (e.g., Perspective API / Llama Guard),
  which are intentionally excluded to maintain offline deterministic operation inside Docker.
- Deliberately allows anatomical, pathological, and psychiatric terms necessary for
  accurate adverse drug event documentation.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger("guardrails.toxicity")

# High-confidence toxic phrases and slurs that have zero legitimate clinical usage
TOXIC_PATTERNS = [
    re.compile(r"(?i)\b(kill\s+yourself|go\s+die|die\s+in\s+a\s+fire)\b"),
    re.compile(r"(?i)\b(fuck\s+(off|you|this)|piece\s+of\s+shit|asshole|bastard|bitch)\b"),
    re.compile(r"(?i)\b(motherfucker|cunt|nigger|faggot|retard)\b"),
]


def check_toxicity(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Check text for toxic content, harassment, or abusive profanity.

    Returns:
        (is_toxic, reason)
    """
    if not text or not isinstance(text, str):
        return False, None

    normalized = " ".join(text.split())

    for regex in TOXIC_PATTERNS:
        match = regex.search(normalized)
        if match:
            trigger = match.group(0)
            reason = f"toxic or abusive language detected ('{trigger}')"
            logger.warning("Toxicity filter triggered: %s", reason)
            return True, reason

    return False, None
