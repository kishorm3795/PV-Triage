"""llm/tests/test_resilience.py - Unit tests for circuit breaker and resilience."""

import time
import pytest
import requests
from llm.resilience import (
    BreakerState,
    CircuitBreaker,
    CircuitBreakerOpenError,
    LLMUnavailableError,
    execute_with_resilience,
)


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout_s=0.2)
    assert cb.state == BreakerState.CLOSED
    assert cb.is_allowed() is True

    # 1 failure
    cb.record_failure(ValueError("err 1"))
    assert cb.state == BreakerState.CLOSED
    assert cb.consecutive_failures == 1

    # 2 failures -> trips to OPEN
    cb.record_failure(ValueError("err 2"))
    assert cb.state == BreakerState.OPEN
    assert cb.is_allowed() is False

    # Wait for cooldown to expire
    time.sleep(0.25)
    assert cb.state == BreakerState.HALF_OPEN
    assert cb.is_allowed() is True

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == BreakerState.CLOSED
    assert cb.consecutive_failures == 0


def test_execute_with_resilience_trips_breaker():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout_s=1.0)

    def failing_call():
        raise requests.ConnectionError("Service unavailable")

    with pytest.raises(LLMUnavailableError):
        execute_with_resilience(failing_call, breaker=cb, max_retries=0)

    assert cb.consecutive_failures == 1

    with pytest.raises(LLMUnavailableError):
        execute_with_resilience(failing_call, breaker=cb, max_retries=0)

    assert cb.consecutive_failures == 2
    assert cb.state == BreakerState.OPEN

    # Next call should be immediately rejected with CircuitBreakerOpenError without invoking failing_call
    with pytest.raises(CircuitBreakerOpenError):
        execute_with_resilience(failing_call, breaker=cb, max_retries=0)
