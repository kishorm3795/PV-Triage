"""api/logging_setup.py - Structured JSON logging with correlation ID tracing.

Provides unified single-line JSON logging across API, RQ jobs, and background workers.
Automatically extracts correlation_id from contextvars or log record attributes.
"""

from __future__ import annotations

from contextvars import ContextVar
import datetime
import json
import logging
import sys
from typing import Any, Optional

# Context variable preserving correlation_id across async and sync call frames
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: Optional[str]) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Retrieve the current correlation ID, if set."""
    return _correlation_id_ctx.get()


class JSONFormatter(logging.Formatter):
    """Outputs single-line JSON formatted log records for observability aggregation."""

    def __init__(self, service: str = "pv-triage"):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        # Resolve correlation_id: explicit record attribute -> ContextVar -> 'none'
        cid = getattr(record, "correlation_id", None) or get_correlation_id() or "none"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        log_data: dict[str, Any] = {
            "timestamp": now,
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "correlation_id": cid,
            "message": record.getMessage(),
        }

        # Format exception traceback if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Append any extra fields passed in logger calls
        reserved_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "correlation_id", "service", "taskName",
        }
        for k, v in record.__dict__.items():
            if k not in reserved_attrs and not k.startswith("_"):
                try:
                    # Validate JSON serializability
                    json.dumps(v)
                    log_data[k] = v
                except (TypeError, OverflowError):
                    log_data[k] = str(v)

        return json.dumps(log_data)


def setup_logging(service: str = "pv-triage", level: str = "INFO") -> logging.Logger:
    """Configure root logger with JSONFormatter on standard output."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)

    # Replace existing handlers
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(JSONFormatter(service=service))
    root.addHandler(stream_handler)

    # Suppress verbose third-party logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return logging.getLogger(service)
