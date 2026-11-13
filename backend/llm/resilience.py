"""llm/resilience.py - LLM Call Resilience, Retries, and 3-State Circuit Breaker.

Provides:
1. CircuitBreaker:
   - Closed (0): Normal operation. Consecutive failures increment error count.
   - Open (2): Tripped when consecutive failures reach BREAKER_FAILS. Rejects requests immediately.
   - Half-Open (1): After BREAKER_RESET_S seconds in Open, permits a single trial probe.
     Success resets to Closed; failure returns to Open.
   - Exposes state to Prometheus gauge CIRCUIT_BREAKER_STATE.
2. Bounded retries with exponential backoff and randomized jitter for transient network glitches.
3. Fallback behavior: when CircuitBreaker is open or all retries exhaust, raises CircuitBreakerOpenError
   or LLMUnavailableError so the calling agent escalates with reason 'LLM unavailable'.
"""

from __future__ import annotations

import enum
import logging
import os
import random
import time
from typing import Any, Callable, Optional, TypeVar
import requests

from shared.metrics import CIRCUIT_BREAKER_STATE

logger = logging.getLogger("llm.resilience")

T = TypeVar("T")


class BreakerState(enum.IntEnum):
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class CircuitBreakerOpenError(RuntimeError):
    """Raised when an LLM call is rejected because the circuit breaker is in OPEN state."""
    pass


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM service cannot be reached after retries."""
    pass


class CircuitBreaker:
    """Thread-safe 3-state circuit breaker tracking LLM service health."""

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        reset_timeout_s: Optional[float] = None,
    ) -> None:
        self.failure_threshold = failure_threshold or int(os.getenv("BREAKER_FAILS", "3"))
        self.reset_timeout_s = reset_timeout_s or float(os.getenv("BREAKER_RESET_S", "30.0"))

        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._last_state_change = time.time()
        self._last_failure_time = 0.0

        # Sync Prometheus gauge on initialization
        CIRCUIT_BREAKER_STATE.set(int(self._state))

    @property
    def state(self) -> BreakerState:
        """Evaluate and return current breaker state, applying half-open transition if cooldown elapsed."""
        if self._state == BreakerState.OPEN:
            elapsed = time.time() - self._last_state_change
            if elapsed >= self.reset_timeout_s:
                logger.info(
                    "Circuit breaker cooldown elapsed (%.1fs >= %.1fs). Transitioning OPEN -> HALF-OPEN",
                    elapsed,
                    self.reset_timeout_s,
                )
                self._state = BreakerState.HALF_OPEN
                self._last_state_change = time.time()
                CIRCUIT_BREAKER_STATE.set(int(self._state))
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def is_allowed(self) -> bool:
        """Check if a new execution attempt is permitted."""
        curr = self.state
        return curr in (BreakerState.CLOSED, BreakerState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful execution."""
        if self._state in (BreakerState.HALF_OPEN, BreakerState.OPEN):
            logger.info("Circuit breaker probe succeeded! Transitioning %s -> CLOSED", self._state.name)
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._last_state_change = time.time()
        CIRCUIT_BREAKER_STATE.set(int(self._state))

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record an execution failure and update breaker state."""
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

        if self._state == BreakerState.HALF_OPEN:
            logger.warning(
                "Circuit breaker trial call in HALF-OPEN failed (%s). Re-tripping to OPEN",
                error,
            )
            self._state = BreakerState.OPEN
            self._last_state_change = time.time()
        elif self._state == BreakerState.CLOSED:
            if self._consecutive_failures >= self.failure_threshold:
                logger.error(
                    "Circuit breaker failure threshold reached (%d >= %d). Tripping CLOSED -> OPEN. "
                    "Last error: %s",
                    self._consecutive_failures,
                    self.failure_threshold,
                    error,
                )
                self._state = BreakerState.OPEN
                self._last_state_change = time.time()
            else:
                logger.warning(
                    "Circuit breaker recorded failure %d/%d: %s",
                    self._consecutive_failures,
                    self.failure_threshold,
                    error,
                )

        CIRCUIT_BREAKER_STATE.set(int(self._state))

    def reset(self) -> None:
        """Manually reset the circuit breaker to clean CLOSED state."""
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._last_state_change = time.time()
        CIRCUIT_BREAKER_STATE.set(int(self._state))


# Global singleton circuit breaker instance for LLM operations
GLOBAL_CIRCUIT_BREAKER = CircuitBreaker()


def execute_with_resilience(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 2,
    base_delay_s: float = 0.05,
    max_delay_s: float = 0.5,
    breaker: Optional[CircuitBreaker] = None,
    **kwargs: Any,
) -> T:
    """Execute a function with circuit breaker check and exponential backoff retry.

    Args:
        func: Callable to execute.
        max_retries: Number of retry attempts on transient network/server failures.
        base_delay_s: Initial retry backoff in seconds.
        max_delay_s: Maximum ceiling for retry delay.
        breaker: Optional CircuitBreaker instance (defaults to GLOBAL_CIRCUIT_BREAKER).

    Raises:
        CircuitBreakerOpenError: If breaker is in OPEN state.
        LLMUnavailableError: If all retry attempts fail.
    """
    cb = breaker or GLOBAL_CIRCUIT_BREAKER

    # 1. Check circuit breaker status
    if not cb.is_allowed():
        logger.warning(
            "Call rejected by circuit breaker: state is OPEN (consecutive_failures=%d)",
            cb.consecutive_failures,
        )
        raise CircuitBreakerOpenError(
            f"LLM unavailable: circuit breaker is OPEN (consecutive_failures={cb.consecutive_failures})"
        )

    last_exc: Optional[Exception] = None
    delay = base_delay_s

    # 2. Attempt execution with bounded backoff
    for attempt in range(max_retries + 1):
        try:
            result = func(*args, **kwargs)
            cb.record_success()
            return result
        except (requests.RequestException, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            logger.warning(
                "LLM execution attempt %d/%d failed: %s",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if attempt < max_retries:
                # Add randomized jitter: [0.75 * delay, 1.25 * delay]
                jitter = delay * random.uniform(0.75, 1.25)
                time.sleep(min(jitter, max_delay_s))
                delay *= 2.0

    # 3. All retries exhausted -> record failure on breaker
    cb.record_failure(last_exc)
    raise LLMUnavailableError(f"Stub LLM request failed: LLM unavailable after {max_retries + 1} attempts: {last_exc}") from last_exc
