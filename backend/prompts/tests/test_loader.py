"""prompts/tests/test_loader.py - Unit tests for versioned prompt loader."""

import os
import pytest
from prompts.loader import load_prompt


def test_load_assessor_v1():
    """Test loading assessor v1 prompt."""
    text, version = load_prompt("assessor", version="v1")
    assert version == "v1"
    assert "Pharmacovigilance" in text
    assert "Assessor" in text
    assert "NDCT" in text


def test_load_verifier_v1():
    """Test loading verifier v1 prompt."""
    text, version = load_prompt("verifier", version="v1")
    assert version == "v1"
    assert "Verifier" in text
    assert "Verification Checklist" in text


def test_load_prompt_env_var(monkeypatch):
    """Test loading prompt with PROMPT_VERSION env var."""
    monkeypatch.setenv("PROMPT_VERSION", "v1")
    text, version = load_prompt("assessor")
    assert version == "v1"
    assert len(text) > 0


def test_missing_prompt_agent_raises():
    """Test that requesting a non-existent agent raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_prompt("non_existent_agent", version="v999")
