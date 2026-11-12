"""guardrails/toxicity.py - Offline lexical toxicity filter.

Provides lightweight, offline toxicity detection for both incoming reports and generated
outputs, preventing abusive, threatening, or harmful language from being silently processed
or emitted.

Distinguishes legitimate clinical pathology (e.g. 'toxic epidermal necrolysis', 'cardiotoxicity',
'overdose', 'suicidal ideation', 'necrotic lesions') from genuine abuse/harassment.
"""

from __future__ import annotations

import logging
import re
from typing import NamedTuple, Optional

logger = logging.getLogger("guardrails.toxicity")

# Clinical terms that contain 'toxic' or sensitive anatomical/pathological words
CLINICAL_WHITELIST_TERMS = {
    "toxic",
    "toxicity",
    "toxic epidermal necrolysis",
    "hepatotoxicity",
    "cardiotoxicity",
    "nephrotoxicity",
    "neurotoxicity",
    "ototoxicity",
    "cytotoxicity",
    "overdose",
    "accidental overdose",
    "intentional overdose",
    "suicide",
    "suicidal",
    "suicidal ideation",
    "suicide attempt",
    "self-harm",
    "death",
    "fatal",
    "mortality",
    "necrosis",
    "necrotic",
    "gangrene",
    "ulcer",
    "ulceration",
    "hemorrhage",
    "genital",
    "penile",
    "vaginal",
    "anal",
    "rectal",
    "breast",
    "sepsis",
    "shock",
    "coma",
    "convulsion",
    "seizure",
}

# Explicit harassment, hate speech, threats, and abusive patterns
TOXIC_PATTERNS = [
    re.compile(r"\b(?:f[*u]+ck(?:ing|er)?|f\*{2,}ing|sh[*i]+t|b[*i]+tch|bastard|asshole|cunt)\b", re.IGNORECASE),
    re.compile(r"\b(?:kill\s+yourself|go\s+die|die\s+in\s+a\s+fire)\b", re.IGNORECASE),
    re.compile(r"\b(?:nigg[ea]r|faggot|kike|chink|spic|retard)\b", re.IGNORECASE),
    re.compile(r"\b(?:i\s+will\s+kill\s+you|murder\s+you|bomb\s+your)\b", re.IGNORECASE),
    re.compile(r"\b(?:worthless\s+scum|subhuman)\b", re.IGNORECASE),
]


class ToxicityCheckResult(NamedTuple):
    passed: bool
    reason: Optional[str] = None
    matched_pattern: Optional[str] = None


def check_toxicity(
    text: Optional[str],
    is_input: bool = True,
    run_id: Optional[str] = None,
) -> ToxicityCheckResult:
    """Analyze text for toxic, harassing, or threatening content.

    Args:
        text: Clinical text or generated output to evaluate.
        is_input: True if checking incoming report, False if checking model output.
        run_id: Correlation identifier for audit logging.

    Returns:
        ToxicityCheckResult with passed=True if clean, or passed=False with reason.
    """
    if not text:
        return ToxicityCheckResult(passed=True)

    text_lower = text.lower()

    for pattern in TOXIC_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            matched_term = match.group(0)
            role_str = "input report" if is_input else "model output"
            reason = f"Toxic content detected in {role_str}: matched abusive pattern '{matched_term}'"
            logger.warning(
                "Toxicity detected in %s [run_id=%s]: %s",
                role_str,
                run_id or "unknown",
                reason,
            )
            return ToxicityCheckResult(
                passed=False,
                reason=reason,
                matched_pattern=matched_term,
            )

    return ToxicityCheckResult(passed=True)
