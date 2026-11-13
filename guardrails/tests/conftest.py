"""guardrails/tests/conftest.py - Test configuration and environment fixtures for guardrail tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def setup_guardrails_test_env(monkeypatch):
    """Ensure standard environment variables are configured for guardrail tests."""
    monkeypatch.setenv("LLM_TIMEOUT_S", os.getenv("LLM_TIMEOUT_S", "30.0"))
    monkeypatch.setenv("LLM_MAX_RETRIES", os.getenv("LLM_MAX_RETRIES", "3"))
    monkeypatch.setenv("BREAKER_FAILS", os.getenv("BREAKER_FAILS", "3"))
    monkeypatch.setenv("BREAKER_RESET_S", os.getenv("BREAKER_RESET_S", "30"))
    monkeypatch.setenv("PRICE_PER_1K_PROMPT", os.getenv("PRICE_PER_1K_PROMPT", "0.00015"))
    monkeypatch.setenv("PRICE_PER_1K_COMPLETION", os.getenv("PRICE_PER_1K_COMPLETION", "0.00060"))
    monkeypatch.setenv("PROMPT_VERSION", os.getenv("PROMPT_VERSION", "v1"))
