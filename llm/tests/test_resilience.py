"""llm/tests/test_resilience.py - Unit tests for timeout, bounded retry, and circuit breaker."""

from unittest.mock import MagicMock
import pytest
import requests

from llm.client import LLMClient
from llm.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    LLMUnavailableError,
    compute_token_cost,
    get_llm_timeout,
    get_max_attempts,
    is_retryable_error,
    llm_breaker_state,
)


def test_timeout_from_env_no_hardcoded_default(monkeypatch):
    """Task 4a: Timeout must be loaded from env; missing env raises ValueError (no hardcoded default)."""
    monkeypatch.setenv("LLM_TIMEOUT_S", "14.5")
    assert get_llm_timeout() == 14.5

    monkeypatch.delenv("LLM_TIMEOUT_S", raising=False)
    with pytest.raises(ValueError) as exc:
        get_llm_timeout()
    assert "LLM_TIMEOUT_S environment variable must be set" in str(exc.value)


def test_retry_only_retryable_errors():
    """Task 4b: Retry only timeouts and 5xx; never retry 4xx errors."""
    # 1. Timeouts are retryable
    assert is_retryable_error(requests.Timeout("Connection timed out")) is True

    # 2. ConnectionErrors are retryable
    assert is_retryable_error(requests.ConnectionError("Connection refused")) is True

    # 3. HTTP 500 / 502 / 503 are retryable
    resp_500 = requests.Response()
    resp_500.status_code = 500
    assert (
        is_retryable_error(requests.HTTPError("Internal Server Error", response=resp_500)) is True
    )

    resp_503 = requests.Response()
    resp_503.status_code = 503
    assert is_retryable_error(requests.HTTPError("Service Unavailable", response=resp_503)) is True

    # 4. HTTP 400 / 401 / 403 / 404 / 422 are NEVER retryable
    for code in [400, 401, 403, 404, 422]:
        resp_4xx = requests.Response()
        resp_4xx.status_code = code
        assert (
            is_retryable_error(requests.HTTPError(f"Client Error {code}", response=resp_4xx))
            is False
        )

    # 5. ValueErrors / non-network errors are not retryable
    assert is_retryable_error(ValueError("Invalid syntax")) is False


def test_retry_non_retryable_4xx_aborts_immediately():
    """Verify that 4xx HTTP error is not retried even when attempts remain."""
    call_count = 0
    sleeps = []

    def mock_call():
        nonlocal call_count
        call_count += 1
        resp = requests.Response()
        resp.status_code = 401
        raise requests.HTTPError("401 Unauthorized", response=resp)

    breaker = CircuitBreaker(
        fails_threshold=3,
        reset_s=30.0,
        clock=lambda: 100.0,
        sleep_fn=sleeps.append,
    )

    with pytest.raises(requests.HTTPError):
        breaker.execute_with_resilience(mock_call, max_attempts=3)

    # Must abort on first attempt with 0 sleeps
    assert call_count == 1
    assert len(sleeps) == 0


def test_retry_backoff_and_jitter():
    """Verify bounded exponential backoff with jitter on retryable 500 errors."""
    call_count = 0
    sleep_durations = []

    def mock_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            resp = requests.Response()
            resp.status_code = 503
            raise requests.HTTPError("503 Service Unavailable", response=resp)
        return "success"

    breaker = CircuitBreaker(
        fails_threshold=5,
        reset_s=30.0,
        clock=lambda: 100.0,
        sleep_fn=sleep_durations.append,
    )

    res, audit = breaker.execute_with_resilience(
        mock_call,
        max_attempts=3,
        base_backoff_s=0.1,
        jitter_s=0.01,
    )

    assert res == "success"
    assert audit["attempt"] == 3
    assert audit["retries"] == 2
    assert len(sleep_durations) == 2
    # Verify exponential backoff: sleep 1 ~ 0.1s, sleep 2 ~ 0.2s
    assert 0.1 <= sleep_durations[0] <= 0.12
    assert 0.2 <= sleep_durations[1] <= 0.22


def test_circuit_breaker_state_transitions_with_fake_clock():
    """Task 4c & 4e: Test CLOSED -> OPEN -> HALF_OPEN -> CLOSED with fake clock and gauge updates."""
    current_time = 1000.0

    def fake_clock():
        return current_time

    breaker = CircuitBreaker(
        fails_threshold=2,
        reset_s=15.0,
        clock=fake_clock,
        sleep_fn=lambda s: None,
    )

    # 1. Initial State: CLOSED (gauge = 0)
    assert breaker.get_state() == CircuitBreaker.CLOSED
    assert llm_breaker_state._value.get() == 0

    # 2. Failure 1: Still CLOSED
    breaker.record_failure()
    assert breaker.get_state() == CircuitBreaker.CLOSED
    assert breaker.consecutive_failures == 1
    assert llm_breaker_state._value.get() == 0

    # 3. Failure 2: Reaches threshold -> Trips to OPEN (gauge = 2)
    breaker.record_failure()
    assert breaker.get_state() == CircuitBreaker.OPEN
    assert llm_breaker_state._value.get() == 2

    # 4. Attempt call while OPEN and cooldown not met -> Blocks with CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        breaker.execute_with_resilience(lambda: "never_called")

    # 5. Advance clock past reset cooldown (15s) -> Transitions to HALF_OPEN (gauge = 1)
    current_time += 16.0
    assert breaker.get_state() == CircuitBreaker.HALF_OPEN
    assert llm_breaker_state._value.get() == 1

    # 6. Trial call succeeds -> Transitions back to CLOSED (gauge = 0)
    result, audit = breaker.execute_with_resilience(lambda: "trial_ok", max_attempts=1)
    assert result == "trial_ok"
    assert breaker.get_state() == CircuitBreaker.CLOSED
    assert breaker.consecutive_failures == 0
    assert llm_breaker_state._value.get() == 0


def test_circuit_breaker_half_open_failure_reopens():
    """Verify that failure during HALF_OPEN trial reopens the circuit breaker."""
    current_time = 500.0
    breaker = CircuitBreaker(
        fails_threshold=1,
        reset_s=10.0,
        clock=lambda: current_time,
        sleep_fn=lambda s: None,
    )

    # Trip to OPEN
    breaker.record_failure()
    assert breaker.get_state() == CircuitBreaker.OPEN

    # Advance time to half-open
    current_time += 12.0
    assert breaker.get_state() == CircuitBreaker.HALF_OPEN
    assert llm_breaker_state._value.get() == 1

    # Trial call fails
    breaker.record_failure()
    assert breaker.get_state() == CircuitBreaker.OPEN
    assert llm_breaker_state._value.get() == 2


def test_cost_tracking_with_prices_and_unconfigured_flag(monkeypatch):
    """Task 5: Token cost calculation; flag 'price not set' if prices empty."""
    # 1. Configured prices
    monkeypatch.setenv("PRICE_PER_1K_PROMPT", "0.00015")
    monkeypatch.setenv("PRICE_PER_1K_COMPLETION", "0.00060")
    cost, flag = compute_token_cost(1000, 2000)
    assert flag is None
    assert abs(cost - (0.00015 + 0.00120)) < 1e-6

    # 2. Empty prices -> cost 0.0 and flag 'price not set'
    monkeypatch.setenv("PRICE_PER_1K_PROMPT", "")
    monkeypatch.setenv("PRICE_PER_1K_COMPLETION", "")
    cost_empty, flag_empty = compute_token_cost(500, 500)
    assert cost_empty == 0.0
    assert flag_empty == "price not set"
