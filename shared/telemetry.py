"""shared/telemetry.py - OpenTelemetry instrumentation, Jaeger export, and trace persistence.

Provides unified OpenTelemetry tracing for API and background workers, exporting
to Jaeger via OTLP_ENDPOINT with root run spans and child spans for every agent step
and tool call. Persists structured trace records to Redis and SQLite for complete auditability.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from shared.contracts import RunResult

logger = logging.getLogger("shared.telemetry")

_TRACER_PROVIDERS: Dict[str, TracerProvider] = {}


def _get_utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolve_otlp_endpoint(endpoint: str) -> str:
    """Resolve endpoint, falling back from container hostname 'jaeger' to localhost on host test runs."""
    import socket

    parsed = urlparse(endpoint)
    host = parsed.hostname or endpoint
    try:
        socket.gethostbyname(host)
        return endpoint
    except (socket.gaierror, OSError):
        if host == "jaeger":
            return endpoint.replace("jaeger", "localhost")
        return endpoint


def init_tracer(service_name: str) -> trace.Tracer:
    """Initialize and configure OpenTelemetry tracer provider with OTLP export to Jaeger.

    Args:
        service_name: Name of the reporting service (e.g., 'api' or 'worker').

    Returns:
        Configured Tracer instance.
    """
    if service_name in _TRACER_PROVIDERS:
        return trace.get_tracer(service_name, tracer_provider=_TRACER_PROVIDERS[service_name])

    raw_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
    endpoint = resolve_otlp_endpoint(raw_endpoint)
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "telemetry.sdk.language": "python",
                "system": "pv-triage",
            }
        )
    )

    exporter = None
    try:
        # Determine whether endpoint uses HTTP or gRPC
        parsed = urlparse(endpoint)
        port = parsed.port
        if port == 4318 or "/v1/traces" in endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter as HTTPSpanExporter,
                )

                exporter = HTTPSpanExporter(endpoint=endpoint)
            except Exception as http_err:
                logger.warning(
                    "Failed to initialize OTLP HTTP exporter (%s), trying gRPC: %s",
                    endpoint,
                    http_err,
                )

        if exporter is None:
            # Default to gRPC exporter
            grpc_endpoint = endpoint
            if not parsed.scheme:
                grpc_endpoint = f"http://{endpoint}"
            exporter = GRPCSpanExporter(endpoint=grpc_endpoint, insecure=True)

        # BatchSpanProcessor provides non-blocking span capture with deterministic flush
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                max_queue_size=2048,
                schedule_delay_millis=100,
                max_export_batch_size=256,
                export_timeout_millis=1500,
            )
        )
        logger.info("OpenTelemetry exporter configured for %s targeting %s", service_name, endpoint)
    except Exception as exc:
        logger.warning(
            "Could not initialize OTLP exporter for %s at %s (%s). Tracing will run in-memory.",
            service_name,
            endpoint,
            exc,
        )

    _TRACER_PROVIDERS[service_name] = provider
    return trace.get_tracer(service_name, tracer_provider=provider)


def flush_telemetry(service_name: Optional[str] = None) -> None:
    """Flush pending spans to Jaeger collector."""
    if service_name and service_name in _TRACER_PROVIDERS:
        try:
            _TRACER_PROVIDERS[service_name].force_flush(timeout_millis=2000)
        except Exception as e:
            logger.debug("Telemetry flush failed for %s: %s", service_name, e)
    else:
        for name, provider in _TRACER_PROVIDERS.items():
            try:
                provider.force_flush(timeout_millis=2000)
            except Exception as e:
                logger.debug("Telemetry flush failed for %s: %s", name, e)


def extract_queries_from_tool_calls(tool_calls: List[Any]) -> List[str]:
    """Extract search and rewrite query strings executed during graph execution."""
    queries: List[str] = []
    for tc in tool_calls:
        tc_dict = tc if isinstance(tc, dict) else tc.model_dump()
        tool_name = tc_dict.get("tool", "")
        inp = tc_dict.get("input", {})
        if isinstance(inp, str):
            try:
                inp = json.loads(inp)
            except Exception:
                inp = {"raw": inp}

        if tool_name in ("search_regulatory_corpus", "search_corpus"):
            q = inp.get("query")
            if q and q not in queries:
                queries.append(str(q))
        elif tool_name == "rewrite_query":
            q = inp.get("lay_text") or inp.get("query")
            if q and q not in queries:
                queries.append(str(q))
        elif tool_name == "get_clause":
            cid = inp.get("clause_id")
            if cid and cid not in queries:
                queries.append(f"clause:{cid}")

    return queries


def extract_retrieved_passage_ids(tool_calls: List[Any], citations: List[Any]) -> List[str]:
    """Extract all passage identifiers retrieved across tool calls and citations."""
    passage_ids: List[str] = []

    def _add_id(pid: Optional[str]) -> None:
        if pid and pid not in passage_ids:
            passage_ids.append(str(pid))

    # 1. From citations
    for c in citations:
        c_dict = c if isinstance(c, dict) else c.model_dump()
        _add_id(c_dict.get("passage_id"))

    # 2. From tool calls
    for tc in tool_calls:
        tc_dict = tc if isinstance(tc, dict) else tc.model_dump()
        summary = tc_dict.get("output_summary", "")

        # Look for list of IDs in summary: ['CHROMA_...', 'PASSAGE_...']
        matches = re.findall(r"['\"]([A-Za-z0-9_\-]+(?:_[a-zA-Z0-9_\-]+)+)['\"]", summary)
        for m in matches:
            if m.startswith(("CHROMA_", "PASSAGE_", "REG_")):
                _add_id(m)

        # Look for single Passage(id='...')
        single_match = re.search(r"id=['\"]([^'\"]+)['\"]", summary)
        if single_match:
            _add_id(single_match.group(1))

    return passage_ids


def persist_trace_sqlite(trace_doc: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Persist structured trace record into SQLite database to survive worker restarts."""
    candidate_paths = [
        db_path,
        os.getenv("TRACES_DB_PATH"),
        "/app/data/traces/traces.db",
        "/app/data/traces.db",
        os.path.join(os.getcwd(), "data", "traces.db"),
    ]
    resolved_path = None
    for p in candidate_paths:
        if p:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
                resolved_path = p
                break
            except Exception:
                continue

    if not resolved_path:
        resolved_path = "traces.db"

    try:
        conn = sqlite3.connect(resolved_path)
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    run_id TEXT PRIMARY KEY,
                    correlation_id TEXT,
                    status TEXT,
                    payload TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO traces (run_id, correlation_id, status, payload, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    trace_doc["run_id"],
                    trace_doc.get("correlation_id", trace_doc["run_id"]),
                    trace_doc.get("status", "unknown"),
                    json.dumps(trace_doc),
                    _get_utc_now_iso(),
                ),
            )
        conn.close()
    except Exception as exc:
        logger.warning("Could not persist trace to SQLite (%s): %s", resolved_path, exc)


def build_and_export_run_trace(
    run_id: str,
    run_result: RunResult,
    start_time_epoch: float,
    finish_time_epoch: float,
    redis_client: Optional[Any] = None,
    sqlite_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Worker hook: Constructs one OpenTelemetry trace per run with child spans per agent step
    and tool call, exports to Jaeger via OTLP, and persists full trace records to Redis and SQLite.

    Args:
        run_id: Unique execution identifier (correlation_id).
        run_result: RunResult emitted by triage graph execution.
        start_time_epoch: Unix epoch start time of the run.
        finish_time_epoch: Unix epoch finish time of the run.
        redis_client: Optional Redis client instance for persistence.
        sqlite_path: Optional SQLite database file path.

    Returns:
        Consolidated structured trace document.
    """
    tracer = init_tracer("worker")

    result_dict = run_result.model_dump()
    tool_calls = result_dict.get("tool_calls", [])
    trace_steps = result_dict.get("trace", [])
    citations = result_dict.get("citations", [])
    prompt_versions = result_dict.get("prompt_versions", {})

    # Extract queries and retrieved passages
    queries = extract_queries_from_tool_calls(tool_calls)
    retrieved_passage_ids = extract_retrieved_passage_ids(tool_calls, citations)

    # Compute per-step latencies, tokens, and cost accounting
    step_latencies: List[Dict[str, Any]] = []
    tokens_per_step: List[Dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost_usd = 0.0

    for ts in trace_steps:
        lat = float(ts.get("latency_ms", 0.0))
        pt = int(ts.get("prompt_tokens", 0))
        ct = int(ts.get("completion_tokens", 0))
        cost = float(ts.get("cost_usd", 0.0))

        total_prompt_tokens += pt
        total_completion_tokens += ct
        total_cost_usd += cost

        step_latencies.append(
            {
                "step": ts.get("step"),
                "agent": ts.get("agent"),
                "kind": ts.get("kind"),
                "latency_ms": lat,
            }
        )
        tokens_per_step.append(
            {
                "step": ts.get("step"),
                "agent": ts.get("agent"),
                "kind": ts.get("kind"),
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "cost_usd": cost,
                "latency_ms": lat,
            }
        )

    # Verification outcome analysis
    verification_outcome: Dict[str, Any] = {
        "passed": (run_result.status == "completed"),
        "errors": [],
        "escalation_reason": run_result.escalation_reason,
        "verified_citations": len(citations),
    }

    for ts in trace_steps:
        detail = ts.get("detail", {})
        if isinstance(detail, dict):
            if "verification_passed" in detail:
                verification_outcome["passed"] = bool(detail["verification_passed"])
            if "verification_errors" in detail:
                verification_outcome["errors"] = detail["verification_errors"]
            if "verified_citations" in detail:
                verification_outcome["verified_citations"] = detail["verified_citations"]

    tokens_and_cost = {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "per_step": tokens_per_step,
    }

    # Assembled complete trace document
    trace_doc: Dict[str, Any] = {
        "run_id": run_id,
        "correlation_id": run_id,
        "status": run_result.status,
        "routing": run_result.routing,
        "routing_basis": run_result.routing_basis,
        "seriousness": run_result.seriousness.model_dump(),
        "expectedness": run_result.expectedness.model_dump(),
        "queries": queries,
        "retrieved_passage_ids": retrieved_passage_ids,
        "prompt_versions": prompt_versions,
        "step_latencies": step_latencies,
        "tokens_and_cost": tokens_and_cost,
        "verification_outcome": verification_outcome,
        "citations": citations,
        "tool_calls": tool_calls,
        "trace": trace_steps,
        "timestamps": {
            "started_at": datetime.datetime.fromtimestamp(
                start_time_epoch, tz=datetime.timezone.utc
            ).isoformat(),
            "finished_at": datetime.datetime.fromtimestamp(
                finish_time_epoch, tz=datetime.timezone.utc
            ).isoformat(),
            "duration_s": round(finish_time_epoch - start_time_epoch, 3),
        },
    }

    # -------------------------------------------------------------------------
    # OpenTelemetry Tracing to Jaeger
    # -------------------------------------------------------------------------
    root_start_ns = int(start_time_epoch * 1e9)
    root_end_ns = int(finish_time_epoch * 1e9)

    root_attrs = {
        "run_id": run_id,
        "correlation_id": run_id,
        "status": run_result.status,
        "routing": str(run_result.routing),
        "is_serious": run_result.seriousness.is_serious,
        "is_listed": run_result.expectedness.is_listed,
        "citations_count": len(citations),
        "tool_calls_count": len(tool_calls),
        "trace_steps_count": len(trace_steps),
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "total_cost_usd": total_cost_usd,
    }
    if run_result.escalation_reason:
        root_attrs["escalation_reason"] = run_result.escalation_reason

    try:
        with tracer.start_as_current_span(
            f"run:{run_id}",
            start_time=root_start_ns,
            attributes=root_attrs,
        ) as root_span:
            curr_offset_s = start_time_epoch

            # 1. Child spans for agent steps
            for step in trace_steps:
                lat_s = max(0.001, float(step.get("latency_ms", 1.0)) / 1000.0)
                step_start_ns = int(curr_offset_s * 1e9)
                step_end_ns = int((curr_offset_s + lat_s) * 1e9)
                curr_offset_s += lat_s

                step_num = step.get("step", 0)
                agent = step.get("agent", "unknown")
                kind = step.get("kind", "step")
                span_name = f"agent_step:{step_num}:{agent}:{kind}"

                step_attrs: Dict[str, Any] = {
                    "step": step_num,
                    "agent": agent,
                    "kind": kind,
                    "latency_ms": step.get("latency_ms", 0.0),
                    "prompt_tokens": step.get("prompt_tokens", 0),
                    "completion_tokens": step.get("completion_tokens", 0),
                    "cost_usd": step.get("cost_usd", 0.0),
                    "correlation_id": run_id,
                    "run_id": run_id,
                }
                detail = step.get("detail", {})
                if isinstance(detail, dict):
                    for dk, dv in detail.items():
                        if isinstance(dv, (str, int, float, bool)):
                            step_attrs[f"detail.{dk}"] = dv
                        else:
                            step_attrs[f"detail.{dk}"] = str(dv)[:120]

                with tracer.start_as_current_span(
                    span_name,
                    start_time=step_start_ns,
                    attributes=step_attrs,
                ) as step_span:
                    pass

            # 2. Child spans for tool calls
            for tool in tool_calls:
                lat_s = max(0.001, float(tool.get("latency_ms", 1.0)) / 1000.0)
                tool_start_ns = int(curr_offset_s * 1e9)
                tool_end_ns = int((curr_offset_s + lat_s) * 1e9)
                curr_offset_s += lat_s

                tool_num = tool.get("step", 0)
                tool_name = tool.get("tool", "tool")
                span_name = f"tool_call:{tool_num}:{tool_name}"

                inp_str = (
                    json.dumps(tool.get("input", {}))
                    if isinstance(tool.get("input"), dict)
                    else str(tool.get("input", ""))
                )
                tool_attrs = {
                    "step": tool_num,
                    "tool": tool_name,
                    "input": inp_str[:250],
                    "output_summary": str(tool.get("output_summary", ""))[:250],
                    "latency_ms": tool.get("latency_ms", 0.0),
                    "ok": bool(tool.get("ok", True)),
                    "correlation_id": run_id,
                    "run_id": run_id,
                }

                with tracer.start_as_current_span(
                    span_name,
                    start_time=tool_start_ns,
                    attributes=tool_attrs,
                ) as tool_span:
                    pass

        flush_telemetry("worker")
    except Exception as otel_exc:
        logger.warning("Error generating OpenTelemetry spans for run %s: %s", run_id, otel_exc)

    # -------------------------------------------------------------------------
    # Trace Persistence: Redis & SQLite
    # -------------------------------------------------------------------------
    if redis_client:
        try:
            redis_client.set(f"run:{run_id}:trace_full", json.dumps(trace_doc))
        except Exception as r_err:
            logger.warning("Failed to persist trace_full in Redis for run %s: %s", run_id, r_err)

    persist_trace_sqlite(trace_doc, db_path=sqlite_path)

    return trace_doc
