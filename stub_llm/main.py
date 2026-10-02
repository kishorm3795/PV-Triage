"""stub_llm/main.py - Deterministic Stub LLM service for testing and load testing.

Returns fixed JSON responses after STUB_DELAY_MS latency.
Returns HTTP 500 error when STUB_FAIL=true to simulate upstream provider outages.
"""

from __future__ import annotations

import os
import time
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Stub LLM Service", version="1.0.0")


class GenerateRequest(BaseModel):
    prompt: str | None = None
    system: str | None = None
    messages: list[dict[str, Any]] | None = None
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """Health check for Docker Compose dependencies."""
    return {"status": "healthy", "service": "stub-llm"}


@app.api_route("/generate", methods=["GET", "POST"])
@app.api_route("/v1/chat/completions", methods=["POST"])
@app.api_route("/v1/generate", methods=["POST"])
@app.api_route("/", methods=["POST"])
async def generate(request: Request) -> JSONResponse:
    """Simulate LLM generation with configurable latency and failure modes."""
    stub_fail = (
        os.getenv("STUB_FAIL", "false").lower() == "true"
        or request.query_params.get("stub_fail", "").lower() == "true"
    )
    delay_ms = int(os.getenv("STUB_DELAY_MS", "50"))

    if stub_fail:
        raise HTTPException(
            status_code=500,
            detail="Simulated Stub LLM Failure (STUB_FAIL=true)",
        )

    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    response_payload = {
        "text": (
            "The patient experienced severe skin peeling and blistering 7 days after starting "
            "the suspect drug, resulting in inpatient hospitalization. Under NDCT Rules 2019 "
            "and IPC Pharmacovigilance Guidance for MAHs, inpatient hospitalization satisfies "
            "statutory seriousness criteria. The adverse reaction is not listed in the package "
            "insert, constituting a serious unexpected adverse reaction requiring expedited reporting."
        ),
        "prompt_tokens": 150,
        "completion_tokens": 62,
        "latency_ms": float(delay_ms),
        "model": "stub-llm",
    }
    return JSONResponse(content=response_payload)
