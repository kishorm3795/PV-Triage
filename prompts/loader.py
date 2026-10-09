"""prompts/loader.py - Versioned prompt file loader.

Selects prompt versions based on the PROMPT_VERSION environment variable or
explicit version arguments. Returns the prompt text and the active version tag.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(agent_name: str, version: str | None = None) -> Tuple[str, str]:
    """Load the versioned prompt markdown file for a given agent.

    Args:
        agent_name: Subfolder name corresponding to the agent (e.g., 'assessor', 'verifier').
        version: Explicit version tag (e.g., 'v1'). If None, reads PROMPT_VERSION from env (defaults to 'v1').

    Returns:
        Tuple of (prompt_text, resolved_version).

    Raises:
        FileNotFoundError: If the specified agent or version file does not exist.
    """
    resolved_version = (version or os.getenv("PROMPT_VERSION", "v1")).strip()
    prompt_file = PROMPTS_DIR / agent_name / f"{resolved_version}.md"

    if not prompt_file.exists():
        # Check if fallback v1 exists
        fallback_file = PROMPTS_DIR / agent_name / "v1.md"
        if fallback_file.exists():
            text = fallback_file.read_text(encoding="utf-8")
            return text, "v1"
        raise FileNotFoundError(
            f"Prompt file not found for agent '{agent_name}' with version '{resolved_version}' "
            f"at {prompt_file}"
        )

    text = prompt_file.read_text(encoding="utf-8")
    return text, resolved_version
