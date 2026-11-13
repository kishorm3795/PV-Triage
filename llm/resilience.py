"""llm/resilience.py - Resilience, timeout, retry with backoff, and circuit breaker.

Implements:
1. Model timeout configured strictly from environment (no hardcoded defaults in code paths).
2. Bounded retry with exponential backoff and jitter for retryable errors (timeouts, HTTP 5xx),
   strictly never retrying 4xx client errors.
3. Circuit breaker (closed, open, half-open) with BREAKER_FAILS and BREAKER_RESET_S from env.
   Injectable clock and sleep_fn for instantaneous, deterministic unit tests.
4. Fallback: breaker open -> run ends 'escalated' with reason 'LLM unavailable'.
5. Prometheus gauge 'llm_breaker_state' (0=closed, 1=half_open, 2=open).
6. Token cost calculation adhering to PRICE_PER_1K_PROMPT and PRICE_PER_1K_COMPLETION.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple
import requests

from prometheus_client import REGISTRY, Gauge

logger = logging.getLogger("llm.resilience")

# Define Prometheus gauge for LLM circuit breaker state
# 0 = closed, 1 = half_open, 2 = open
try:
    llm_breaker_state = Gauge(
        "llm_breaker_state",
        "LLM Circuit Breaker State: 0=closed, 1=half_open, 2=open",
    )
except ValueError:
    llm_breaker_state = REGISTRY._names_to_collectors.get("llm_breaker_state")  # type: ignore

# Initialize gauge to closed (0)
if llm_breaker_state is not None:
    try:
        llm_breaker_state.set(0)
    except Exception:
        pass


class CircuitBreakerOpenError(RuntimeError):
    """Raised when an LLM call is attempted while the circuit breaker is OPEN."""

    pass


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM service is completely unavailable or exhausted."""

    pass


def get_llm_timeout() -> float:
    """Retrieve model timeout strictly from environment (no hardcoded default allowed)."""
    raw = os.getenv("LLM_TIMEOUT_S")
    if raw is None or not raw.strip():
        raise ValueError(
            "LLM_TIMEOUT_S environment variable must be set (no hardcoded default allowed in code paths)."
        )
    return float(raw.strip())


def get_max_attempts() -> int:
    """Retrieve maximum retry attempts from environment (no hardcoded default)."""
    raw = os.getenv("LLM_MAX_ATTEMPTS") or os.getenv("LLM_MAX_RETRIES")
    if raw is None or not raw.strip():
        raise ValueError("LLM_MAX_ATTEMPTS or LLM_MAX_RETRIES environment variable must be set.")
    return int(raw.strip())


def get_breaker_fails() -> int:
    """Retrieve failure threshold from environment (no hardcoded default)."""
    raw = os.getenv("BREAKER_FAILS")
    if raw is None or not raw.strip():
        raise ValueError("BREAKER_FAILS environment variable must be set.")
    return int(raw.strip())


def get_breaker_reset_s() -> float:
    """Retrieve breaker reset cooldown from environment (no hardcoded default)."""
    raw = os.getenv("BREAKER_RESET_S")
    if raw is None or not raw.strip():
        raise ValueError("BREAKER_RESET_S environment variable must be set.")
    return float(raw.strip())


def compute_token_cost(
    prompt_tokens: int,
    completion_tokens: int,
) -> Tuple[float, Optional[str]]:
    """Calculate USD cost from tokens. If prices are unset or empty, cost is 0.0 with flag 'price not set'."""
    prompt_price_raw = os.getenv("PRICE_PER_1K_PROMPT", "").strip()
    comp_price_raw = os.getenv("PRICE_PER_1K_COMPLETION", "").strip()

    if not prompt_price_raw or not comp_price_raw:
        return 0.0, "price not set"

    try:
        price_prompt = float(prompt_price_raw)
        price_comp = float(comp_price_raw)
        cost = (prompt_tokens / 1000.0 * price_prompt) + (completion_tokens / 1000.0 * price_comp)
        return cost, None
    except ValueError:
        return 0.0, "price not set"


def is_retryable_error(exc: Exception) -> bool:
    """Determine whether an error is transient and eligible for bounded retry.

    Retryable:
      - Network timeouts (requests.Timeout)
      - Connection errors (requests.ConnectionError)
      - HTTP 5xx Server Errors (requests.HTTPError with status >= 500)
    Non-retryable:
      - HTTP 4xx Client Errors (requests.HTTPError with 400 <= status < 500)
      - ValueErrors, KeyErrors, TypeErrors
    """
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True

    if isinstance(exc, requests.HTTPError):
        if exc.response is not None:
            status_code = exc.response.status_code
            if 400 <= status_code < 500:
                return False
            if status_code >= 500:
                return True

    if isinstance(exc, RuntimeError) and "500" in str(exc):
        return True

    return False


class CircuitBreaker:
    """Circuit breaker with closed, open, and half-open states."""

    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"

    def __init__(
        self,
        fails_threshold: Optional[int] = None,
        reset_s: Optional[float] = None,
        clock: Optional[Callable[[], float]] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ):
        self._fails_threshold = fails_threshold
        self._reset_s = reset_s
        self.clock = clock or time.time
        self.sleep_fn = sleep_fn or time.sleep

        self.state = self.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.total_calls = 0
        self._update_gauge()

    @property
    def fails_threshold(self) -> int:
        return self._fails_threshold if self._fails_threshold is not None else get_breaker_fails()

    @property
    def reset_s(self) -> float:
        return self._reset_s if self._reset_s is not None else get_breaker_reset_s()

    def _update_gauge(self) -> None:
        if llm_breaker_state is not None:
            try:
                val = 0 if self.state == self.CLOSED else (1 if self.state == self.HALF_OPEN else 2)
                llm_breaker_state.set(val)
            except Exception:
                pass

    def get_state(self) -> str:
        """Inspect current state and evaluate reset timeout transition to half-open."""
        if self.state == self.OPEN:
            elapsed = self.clock() - self.last_failure_time
            if elapsed >= self.reset_s:
                logger.info(
                    "Circuit breaker cooldown passed (%.2fs >= %.2fs). Transitioning to HALF_OPEN",
                    elapsed,
                    self.reset_s,
                )
                self.state = self.HALF_OPEN
                self._update_gauge()
        return self.state

    def record_success(self) -> None:
        """Record successful invocation."""
        if self.state in (self.HALF_OPEN, self.OPEN):
            logger.info(
                "Circuit breaker trial call succeeded. Transitioning from %s to CLOSED", self.state
            )
        self.state = self.CLOSED
        self.consecutive_failures = 0
        self._update_gauge()

    def record_failure(self) -> None:
        """Record failed invocation and check if threshold reached."""
        self.consecutive_failures += 1
        self.last_failure_time = self.clock()
        if self.state == self.HALF_OPEN:
            logger.warning(
                "Circuit breaker trial call failed in HALF_OPEN. Transitioning back to OPEN."
            )
            self.state = self.OPEN
            self._update_gauge()
        elif self.state == self.CLOSED and self.consecutive_failures >= self.fails_threshold:
            logger.warning(
                "Circuit breaker tripped after %d consecutive failures. Transitioning from CLOSED to OPEN.",
                self.consecutive_failures,
            )
            self.state = self.OPEN
            self._update_gauge()

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self.state = self.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.total_calls = 0
        self._update_gauge()

    def execute_with_resilience(
        self,
        call_fn: Callable[..., Any],
        *args: Any,
        max_attempts: Optional[int] = None,
        base_backoff_s: float = 0.05,
        max_backoff_s: float = 1.0,
        jitter_s: float = 0.02,
        **kwargs: Any,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Execute callable with circuit breaking, bounded retry, exponential backoff, and jitter.

        Returns:
            Tuple of (result, audit_metadata)
        """
        current_state = self.get_state()
        if current_state == self.OPEN:
            raise CircuitBreakerOpenError(
                f"LLM unavailable: circuit breaker is OPEN (tripped after {self.consecutive_failures} failures)."
            )

        attempts_limit = max_attempts if max_attempts is not None else get_max_attempts()
        retries_done = 0
        last_exc: Optional[Exception] = None

        for attempt in range(1, attempts_limit + 1):
            self.total_calls += 1
            try:
                result = call_fn(*args, **kwargs)
                self.record_success()
                audit = {
                    "attempt": attempt,
                    "retries": retries_done,
                    "breaker_state": self.state,
                }
                return result, audit
            except Exception as exc:
                last_exc = exc
                if not is_retryable_error(exc):
                    logger.warning(
                        "Non-retryable error encountered: %s. Aborting retries immediately.", exc
                    )
                    self.record_failure()
                    raise exc

                if attempt >= attempts_limit:
                    logger.warning(
                        "Exhausted all %d attempts on retryable error: %s", attempts_limit, exc
                    )
                    self.record_failure()
                    raise exc

                retries_done += 1
                backoff = min(
                    max_backoff_s, base_backoff_s * (2 ** (attempt - 1))
                ) + random.uniform(0, jitter_s)
                logger.info(
                    "Retryable error '%s' on attempt %d/%d. Backing off for %.3fs.",
                    exc,
                    attempt,
                    attempts_limit,
                    backoff,
                )
                self.sleep_fn(backoff)

        if last_exc is not None:
            self.record_failure()
            raise last_exc
        raise LLMUnavailableError("LLM call failed with no attempts made.")


# Global singleton instance for application-wide breaker state
_GLOBAL_BREAKER: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Retrieve or initialize the global CircuitBreaker singleton."""
    global _GLOBAL_BREAKER
    if _GLOBAL_BREAKER is None:
        _GLOBAL_BREAKER = CircuitBreaker()
    return _GLOBAL_BREAKER


def reset_circuit_breaker() -> None:
    """Reset global circuit breaker (primarily used in test suites)."""
    global _GLOBAL_BREAKER
    if _GLOBAL_BREAKER is not None:
        _GLOBAL_BREAKER.reset()
    else:
        _GLOBAL_BREAKER = CircuitBreaker()
