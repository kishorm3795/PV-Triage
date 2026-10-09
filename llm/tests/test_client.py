"""llm/tests/test_client.py - Unit tests for LLM client abstraction."""

import os
from unittest.mock import MagicMock, patch
import pytest
import requests

from llm.client import LLMClient, LLMResponse


def test_llm_response_access():
    """Test that LLMResponse supports both attribute and item access."""
    resp = LLMResponse(
        text="Test completion",
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=45.0,
        model="stub-llm",
    )
    assert resp.text == "Test completion"
    assert resp["text"] == "Test completion"
    assert resp["prompt_tokens"] == 10
    assert resp.get("model") == "stub-llm"
    assert resp.get("non_existent", "default") == "default"


def test_default_provider_from_env(monkeypatch):
    """Test that LLMClient reads provider from LLM_PROVIDER env."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    client = LLMClient()
    assert client.provider == "stub"


def test_unsupported_provider():
    """Test that unsupported provider raises ValueError."""
    client = LLMClient(provider="unsupported_provider")
    with pytest.raises(ValueError) as exc:
        client.generate("Hello")
    assert "Unsupported LLM_PROVIDER" in str(exc.value)


def test_stub_provider_success(monkeypatch):
    """Test successful generation with stub provider."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-stub:8001")

    client = LLMClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "Stubbed assessment text",
        "prompt_tokens": 120,
        "completion_tokens": 40,
        "latency_ms": 25.0,
        "model": "stub-llm",
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = client.generate(prompt="Analyze this case", system="You are PV assessor")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://fake-stub:8001/generate"
        assert call_args[1]["json"]["prompt"] == "Analyze this case"
        assert call_args[1]["json"]["system"] == "You are PV assessor"

        assert res.text == "Stubbed assessment text"
        assert res.prompt_tokens == 120
        assert res.completion_tokens == 40
        assert res.latency_ms == 25.0
        assert res.model == "stub-llm"


def test_stub_provider_failure(monkeypatch):
    """Test stub provider network/HTTP failure handling."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("LLM_BASE_URL", "http://fake-stub:8001")

    client = LLMClient()

    with patch("requests.post", side_effect=requests.RequestException("Connection refused")):
        with pytest.raises(RuntimeError) as exc:
            client.generate(prompt="Test")
        assert "Stub LLM request failed" in str(exc.value)


def test_gemini_missing_api_key(monkeypatch):
    """Test that gemini provider raises ValueError if LLM_API_KEY is unset."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    client = LLMClient()
    with pytest.raises(ValueError) as exc:
        client.generate(prompt="Test")
    assert "LLM_API_KEY environment variable is required" in str(exc.value)


def test_gemini_provider_success(monkeypatch):
    """Test successful generation with gemini provider."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "test_gemini_key")
    monkeypatch.setenv("LLM_MODEL", "gemini-1.5-pro")

    client = LLMClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Gemini generated triage assessment"}]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 85,
            "candidatesTokenCount": 35,
        },
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = client.generate(
            prompt="Evaluate adverse event",
            system="System prompt",
            temperature=0.2,
        )

        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "key=test_gemini_key" in url
        assert "gemini-1.5-pro" in url
        body = mock_post.call_args[1]["json"]
        assert body["contents"][0]["parts"][0]["text"] == "Evaluate adverse event"
        assert body["system_instruction"]["parts"][0]["text"] == "System prompt"

        assert res.text == "Gemini generated triage assessment"
        assert res.prompt_tokens == 85
        assert res.completion_tokens == 35
        assert res.model == "gemini-1.5-pro"


def test_timeout_override(monkeypatch):
    """Test that timeout parameter is passed down to requests.post."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    client = LLMClient(timeout=10.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "ok", "prompt_tokens": 1, "completion_tokens": 1}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client.generate("test prompt", timeout=5.0)
        assert mock_post.call_args[1]["timeout"] == 5.0
