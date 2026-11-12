"""llm/tests/conftest.py - Test configuration and environment fixtures for LLM tests."""

import os
import pytest
from llm.resilience import reset_circuit_breaker


@pytest.fixture(autouse=True)
def setup_llm_test_env(monkeypatch):
    """Ensure standard environment variables are configured for resilience tests and reset breaker."""
    monkeypatch.setenv("LLM_TIMEOUT_S", os.getenv("LLM_TIMEOUT_S", "30.0"))
    monkeypatch.setenv("LLM_MAX_RETRIES", os.getenv("LLM_MAX_RETRIES", "3"))
    monkeypatch.setenv("BREAKER_FAILS", os.getenv("BREAKER_FAILS", "3"))
    monkeypatch.setenv("BREAKER_RESET_S", os.getenv("BREAKER_RESET_S", "30"))
    monkeypatch.setenv("PRICE_PER_1K_PROMPT", os.getenv("PRICE_PER_1K_PROMPT", "0.00015"))
    monkeypatch.setenv("PRICE_PER_1K_COMPLETION", os.getenv("PRICE_PER_1K_COMPLETION", "0.00060"))

    reset_circuit_breaker()
    yield
    reset_circuit_breaker()
