"""llm/client.py - Provider-agnostic LLM client abstraction.

Supports 'stub' and 'gemini' providers selected strictly via the LLM_PROVIDER
environment variable. No endpoints, keys, or models are hardcoded.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field
import requests


class LLMResponse(BaseModel):
    """Normalized response returned by all LLM providers."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class LLMClient:
    """Unified LLM client dispatching to configured provider."""

    def __init__(
        self,
        provider: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "stub")).lower().strip()
        default_timeout = float(os.getenv("LLM_TIMEOUT", os.getenv("RUN_TIMEOUT_S", "30.0")))
        self.default_timeout = timeout if timeout is not None else default_timeout

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using the active LLM provider.

        Args:
            prompt: User/task prompt text.
            system: Optional system instruction prompt.
            timeout: Optional call timeout in seconds.
            **kwargs: Extra provider-specific parameters (e.g., temperature, max_tokens).

        Returns:
            LLMResponse containing text, prompt_tokens, completion_tokens, latency_ms, model.
        """
        call_timeout = timeout if timeout is not None else self.default_timeout

        if self.provider == "stub":
            return self._generate_stub(prompt, system, call_timeout, **kwargs)
        elif self.provider == "gemini":
            return self._generate_gemini(prompt, system, call_timeout, **kwargs)
        else:
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. Must be 'stub' or 'gemini'."
            )

    def _generate_stub(
        self,
        prompt: str,
        system: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the deterministic Stub LLM service over HTTP."""
        base_url = os.getenv("LLM_BASE_URL", "http://stub-llm:8001").rstrip("/")
        endpoint = f"{base_url}/generate"

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "system": system,
            "model": kwargs.get("model", "stub-llm"),
        }
        for k, v in kwargs.items():
            if k not in payload:
                payload[k] = v

        start_time = time.perf_counter()
        try:
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            # If default container hostname 'stub-llm' fails on local host, try localhost:8001
            if "stub-llm" in base_url and os.getenv("LLM_BASE_URL") is None:
                try:
                    fallback_endpoint = "http://localhost:8001/generate"
                    resp = requests.post(fallback_endpoint, json=payload, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException:
                    raise RuntimeError(f"Stub LLM request failed: {exc}") from exc
            else:
                raise RuntimeError(f"Stub LLM request failed: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return LLMResponse(
            text=data.get("text", ""),
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            latency_ms=float(data.get("latency_ms", elapsed_ms)),
            model=str(data.get("model", "stub-llm")),
        )

    def _generate_gemini(
        self,
        prompt: str,
        system: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the Google Gemini API using env-configured credentials and model."""
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable is required for Gemini provider.")

        model = os.getenv("LLM_MODEL", "").strip() or kwargs.get("model", "gemini-1.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        contents: list[Dict[str, Any]] = [{"parts": [{"text": prompt}]}]
        body: Dict[str, Any] = {"contents": contents}

        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}

        gen_config: Dict[str, Any] = {}
        if "temperature" in kwargs:
            gen_config["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs or "max_output_tokens" in kwargs:
            gen_config["maxOutputTokens"] = kwargs.get("max_tokens") or kwargs.get("max_output_tokens")
        if gen_config:
            body["generationConfig"] = gen_config

        start_time = time.perf_counter()
        try:
            resp = requests.post(url, json=body, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini API request failed: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                text = parts[0].get("text", "")

        usage = data.get("usageMetadata", {})
        prompt_tokens = int(usage.get("promptTokenCount", 0))
        completion_tokens = int(usage.get("candidatesTokenCount", 0))

        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=elapsed_ms,
            model=model,
        )
