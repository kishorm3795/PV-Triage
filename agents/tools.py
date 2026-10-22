"""agents/tools.py - Agent tool definitions with Retriever protocol support.

Provides the standard tool interfaces:
  - search_corpus(query, k=5, retriever=None) -> list[Passage]
  - get_clause(clause_id, retriever=None) -> Passage | None
  - get_request_fields(run_id, report=None) -> dict
  - rewrite_query(lay_text) -> list[str]

Tool execution is wrapped with logging, timeout, and call count enforcement.
Use `wrap_tools(tool_log)` to get versions that log to a specific tool_log.
"""

from __future__ import annotations

import concurrent.futures
import inspect
import json
import logging
import os
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar
from shared.contracts import Passage, Retriever, ToolCall

logger = logging.getLogger("agents.tools")

# ========================================================================
# Retriever Implementations
# ========================================================================


class MockRetriever:
    """Deterministic in-memory Mock Retriever implementing the Retriever protocol."""

    def __init__(self) -> None:
        self.passages: Dict[str, Passage] = {
            "ndct-2019-second-sched-table1": Passage(
                id="ndct-2019-second-sched-table1",
                clause_id="ndct-2019-second-sched-table1",
                source_doc="New Drugs and Clinical Trials Rules 2019",
                page=218,
                section="Second Schedule, Table 1, Clause 4(3)",
                text=(
                    "Any serious unexpected adverse event shall be reported by the sponsor "
                    "or marketing authorisation holder to the Central Licencing Authority "
                    "within fifteen calendar days of receipt of the information."
                ),
                score=0.95,
            ),
            "ipc-pv-guidance-sec4-seriousness": Passage(
                id="ipc-pv-guidance-sec4-seriousness",
                clause_id="ipc-pv-guidance-sec4-seriousness",
                source_doc="IPC Pharmacovigilance Guidance Document for MAHs",
                page=14,
                section="Section 4.1: Seriousness Criteria",
                text=(
                    "A serious adverse event (SAE) or reaction is any untoward medical occurrence that "
                    "at any dose results in death, inpatient hospitalisation or prolongation of existing "
                    "hospitalisation, persistent or significant disability or incapacity, or is a "
                    "congenital anomaly or birth defect, or is life-threatening."
                ),
                score=0.92,
            ),
            "lamotrigine-pi-sec4-8-undesirable": Passage(
                id="lamotrigine-pi-sec4-8-undesirable",
                clause_id="lamotrigine-pi-sec4-8-undesirable",
                source_doc="Lamotrigine Package Insert",
                page=6,
                section="Section 4.8: Undesirable Effects",
                text=(
                    "Adverse reactions reported during clinical trials and post-marketing surveillance: "
                    "Skin and subcutaneous tissue disorders: Very common: skin rash; Rare: Stevens-Johnson "
                    "syndrome (SJS); Very rare: Toxic epidermal necrolysis (TEN). Severe cutaneous adverse "
                    "reactions require immediate discontinuation."
                ),
                score=0.88,
            ),
            "ipc-pv-guidance-sec5-expectedness": Passage(
                id="ipc-pv-guidance-sec5-expectedness",
                clause_id="ipc-pv-guidance-sec5-expectedness",
                source_doc="IPC Pharmacovigilance Guidance Document for MAHs",
                page=18,
                section="Section 5.2: Expectedness Assessment",
                text=(
                    "An adverse reaction is considered unexpected if its nature, severity, specificity, "
                    "or outcome is not consistent with the reference safety information or approved package insert."
                ),
                score=0.85,
            ),
        }

    def search(self, query: str, k: int = 5) -> List[Passage]:
        """Search mock corpus for relevant passages."""
        query_terms = set(query.lower().split())
        scored_passages: List[tuple[float, Passage]] = []

        for p in self.passages.values():
            text_terms = set(p.text.lower().split())
            section_terms = set((p.section or "").lower().split())
            doc_terms = set(p.source_doc.lower().split())

            all_terms = text_terms | section_terms | doc_terms
            matched = query_terms.intersection(all_terms)
            overlap_score = len(matched) / (len(query_terms) + 1e-5)
            final_score = (p.score or 0.8) * (1.0 + overlap_score)
            scored_passages.append((final_score, p))

        scored_passages.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored_passages[:k]]

    def get_clause(self, clause_id: str) -> Optional[Passage]:
        """Retrieve passage by exact clause identifier."""
        return self.passages.get(clause_id)


def _convert_to_contract_passage(obj: Any) -> Passage:
    """Normalize arbitrary passage representation into shared.contracts.Passage."""
    if isinstance(obj, Passage):
        return obj
    if hasattr(obj, "to_contract") and callable(obj.to_contract):
        return obj.to_contract()
    if isinstance(obj, dict):
        return Passage(**obj)
    if hasattr(obj, "__dict__"):
        return Passage(
            id=getattr(obj, "id", ""),
            text=getattr(obj, "text", ""),
            source_doc=getattr(obj, "source_doc", ""),
            page=getattr(obj, "page", None),
            clause_id=getattr(obj, "clause_id", None),
            section=getattr(obj, "section", None),
            score=getattr(obj, "score", None),
        )
    return Passage.model_validate(obj)


class RealRetrieverAdapter:
    """Adapter wrapping Member C's pipeline retrieval behind the Retriever protocol.

    Dynamically discovers and adapts Member C's retrieval implementation from pipeline.retrieval.
    Raises NotImplementedError with clear guidance if Member C's retriever is unavailable.
    """

    def __init__(self, retrieval_module_path: str = "pipeline.retrieval") -> None:
        self._retrieval_module_path = retrieval_module_path
        self._retriever: Any = None
        self._import_error: Optional[str] = None

    def _get_retriever(self) -> Any:
        """Lazily import and instantiate Member C's retriever."""
        if self._retriever is not None:
            return self._retriever

        try:
            import importlib
            mod = importlib.import_module(self._retrieval_module_path)

            # Discover candidate class or factory
            candidate = (
                getattr(mod, "ChromaRetriever", None)
                or getattr(mod, "Retriever", None)
                or getattr(mod, "get_retriever", None)
                or getattr(mod, "retriever", None)
            )

            if candidate is None:
                raise ImportError(
                    f"Module '{self._retrieval_module_path}' does not export ChromaRetriever, "
                    f"Retriever, or get_retriever."
                )

            if isinstance(candidate, type):
                self._retriever = candidate()
            elif callable(candidate):
                self._retriever = candidate()
            else:
                self._retriever = candidate

            return self._retriever

        except Exception as exc:
            self._import_error = str(exc)
            raise NotImplementedError(
                f"RealRetrieverAdapter: Member C's retrieval module not available ({exc}). "
                f"Ensure '{self._retrieval_module_path}' exists and implements search() and get_clause(), "
                f"or set RETRIEVER=mock."
            ) from exc

    def search(self, query: str, k: int = 5) -> List[Passage]:
        """Search corpus using Member C's retrieval implementation."""
        retriever = self._get_retriever()
        results = retriever.search(query, k=k)
        if results is None:
            return []
        return [_convert_to_contract_passage(p) for p in results]

    def get_clause(self, clause_id: str) -> Optional[Passage]:
        """Lookup specific clause using Member C's retrieval implementation."""
        retriever = self._get_retriever()
        result = retriever.get_clause(clause_id)
        if result is None:
            return None
        return _convert_to_contract_passage(result)


# ========================================================================
# Retriever Factory (env-driven)
# ========================================================================

_CACHED_RETRIEVER: Optional[Retriever] = None
_CACHED_RETRIEVER_MODE: Optional[str] = None


def get_default_retriever() -> Retriever:
    """Return the active retriever instance based on RETRIEVER environment variable.

    RETRIEVER=mock  -> MockRetriever (default, deterministic, no external deps)
    RETRIEVER=real  -> RealRetrieverAdapter (imports Member C's pipeline retrieval)

    Automatically re-creates instance if RETRIEVER environment variable changes.
    """
    global _CACHED_RETRIEVER, _CACHED_RETRIEVER_MODE

    current_mode = os.getenv("RETRIEVER", "mock").lower().strip()
    if _CACHED_RETRIEVER is not None and _CACHED_RETRIEVER_MODE == current_mode:
        return _CACHED_RETRIEVER

    if current_mode == "real":
        _CACHED_RETRIEVER = RealRetrieverAdapter()
    else:
        _CACHED_RETRIEVER = MockRetriever()

    _CACHED_RETRIEVER_MODE = current_mode
    return _CACHED_RETRIEVER


def reset_retriever() -> None:
    """Reset the cached retriever instance (useful for testing)."""
    global _CACHED_RETRIEVER, _CACHED_RETRIEVER_MODE
    _CACHED_RETRIEVER = None
    _CACHED_RETRIEVER_MODE = None


# ========================================================================
# Active Run Reports Registry (for get_request_fields)
# ========================================================================

_RUN_REPORTS: Dict[str, Dict[str, Any]] = {}


def register_run_report(run_id: str, report: Dict[str, Any]) -> None:
    """Register report fields in memory for a given run_id."""
    _RUN_REPORTS[run_id] = dict(report)


def unregister_run_report(run_id: str) -> None:
    """Remove report from registry for a given run_id."""
    _RUN_REPORTS.pop(run_id, None)


def clear_run_reports() -> None:
    """Clear all registered run reports."""
    _RUN_REPORTS.clear()


# ========================================================================
# Tool Wrapper: Logging, Timeout, Call Count Enforcement
# ========================================================================

MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "20"))
TOOL_TIMEOUT_S = float(os.getenv("TOOL_TIMEOUT_S", "10.0"))

T = TypeVar("T")


class ToolCallLimitExceeded(Exception):
    """Raised when MAX_TOOL_CALLS is exceeded."""
    pass


class ToolTimeoutError(Exception):
    """Raised when a tool call exceeds TOOL_TIMEOUT_S."""
    pass


class ToolError(Exception):
    """Generic tool execution error."""
    pass


def _summarize_input(func: Callable[..., Any], args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Create a clean dict of tool input arguments using function signature."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        summary = {}
        for k, v in bound.arguments.items():
            if k == "retriever":
                continue  # omit internal retriever dependency from tool call input summary
            if isinstance(v, (str, int, float, bool, type(None))):
                summary[k] = v
            elif isinstance(v, dict):
                summary[k] = {sk: str(sv)[:50] for sk, sv in list(v.items())[:5]}
            else:
                summary[k] = str(v)[:80]
        return summary
    except Exception:
        return {"args": [str(a)[:50] for a in args], "kwargs": {k: str(v)[:50] for k, v in kwargs.items()}}


def _summarize_output(result: Any) -> str:
    """Create a clean, human-readable summary of tool output for audit logging."""
    if result is None:
        return "None"
    if isinstance(result, list):
        if not result:
            return "Empty list []"
        first = result[0]
        if isinstance(first, Passage):
            ids = [p.id for p in result]
            return f"Retrieved {len(result)} passages: {ids}"
        if isinstance(first, str):
            return f"Rewrote to {len(result)} terms: {result}"
        return f"List[{len(result)} items]"
    if isinstance(result, Passage):
        return f"Passage(id='{result.id}', clause='{result.clause_id}', source='{result.source_doc}')"
    if isinstance(result, dict):
        keys = list(result.keys())
        return f"Dict[{len(keys)} fields: {', '.join(keys[:6])}]"
    return str(result)[:200]


def make_tool_wrapper(
    tool_name: str,
    tool_log: List[ToolCall],
    max_calls: int = MAX_TOOL_CALLS,
    timeout_s: float = TOOL_TIMEOUT_S,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create a decorator that wraps a tool function with logging, timeout, and call count enforcement.

    Enforces:
      1. MAX_TOOL_CALLS: Logs failure and raises ToolCallLimitExceeded if reached.
      2. Per-call timeout: Executes within timeout_s or raises ToolTimeoutError.
      3. Complete audit logging: Records EVERY call (step, tool, input, output_summary, latency_ms, ok).
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            step = len(tool_log) + 1
            input_summary = _summarize_input(func, args, kwargs)

            # Check call count limit before execution
            if len(tool_log) >= max_calls:
                err_msg = (
                    f"Tool call limit exceeded: {len(tool_log)}/{max_calls} "
                    f"(MAX_TOOL_CALLS={max_calls})."
                )
                tool_log.append(
                    ToolCall(
                        step=step,
                        tool=tool_name,
                        input=input_summary,
                        output_summary=f"ERROR: {err_msg}",
                        latency_ms=0.0,
                        ok=False,
                    )
                )
                raise ToolCallLimitExceeded(err_msg)

            start_time = time.perf_counter()
            ok = True
            output_summary = ""
            result: Any = None

            # Execute with per-call timeout
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    try:
                        result = future.result(timeout=timeout_s)
                    except concurrent.futures.TimeoutError as exc:
                        raise ToolTimeoutError(
                            f"Tool '{tool_name}' timed out after {timeout_s}s"
                        ) from exc

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                # Secondary post-execution timeout safety check
                if latency_ms > (timeout_s * 1000.0 + 50.0):
                    raise ToolTimeoutError(
                        f"Tool '{tool_name}' latency ({latency_ms:.1f}ms) exceeded timeout ({timeout_s}s)"
                    )

                output_summary = _summarize_output(result)
                return result  # type: ignore

            except ToolTimeoutError as t_err:
                ok = False
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                output_summary = f"ERROR: {t_err}"
                raise

            except Exception as exc:
                ok = False
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                output_summary = f"ERROR: {exc}"
                raise

            finally:
                tool_log.append(
                    ToolCall(
                        step=step,
                        tool=tool_name,
                        input=input_summary,
                        output_summary=output_summary,
                        latency_ms=latency_ms,
                        ok=ok,
                    )
                )

        return wrapper
    return decorator


# ========================================================================
# Core Tool Implementations
# ========================================================================

def _search_corpus_core(
    query: str,
    k: int = 5,
    retriever: Optional[Retriever] = None,
) -> List[Passage]:
    """Execute corpus search query against the configured retriever.

    Args:
        query: Clinical search query.
        k: Maximum number of passages to retrieve.
        retriever: Optional explicit retriever instance (defaults to get_default_retriever()).

    Returns:
        List of matching Passage objects.
    """
    active_retriever = retriever or get_default_retriever()
    return active_retriever.search(query, k=k)


def _get_clause_core(
    clause_id: str,
    retriever: Optional[Retriever] = None,
) -> Optional[Passage]:
    """Lookup specific regulatory clause by exact clause identifier.

    Args:
        clause_id: Unique clause identifier (e.g., 'ndct-2019-second-sched-table1').
        retriever: Optional explicit retriever instance (defaults to get_default_retriever()).

    Returns:
        Passage matching the clause identifier, or None.
    """
    active_retriever = retriever or get_default_retriever()
    return active_retriever.get_clause(clause_id)


def _get_request_fields_core(
    run_id: str,
    report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract and return standardized report fields for the run.

    Checks:
      1. Directly passed `report` dict
      2. In-memory `_RUN_REPORTS` registry
      3. Redis `run:{run_id}:report` key if available

    Args:
        run_id: Triage run identifier.
        report: Optional report payload dictionary.

    Returns:
        Dictionary of standardized report fields.
    """
    target_report: Optional[Dict[str, Any]] = report

    if target_report is None:
        # Check in-memory run registry
        target_report = _RUN_REPORTS.get(run_id)

    if target_report is None:
        # Check Redis if reachable
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            r = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.2)
            raw = r.get(f"run:{run_id}:report")
            if raw:
                target_report = json.loads(raw)
        except Exception:
            pass

    if not target_report:
        return {"run_id": run_id}

    return {
        "run_id": run_id,
        "report_id": target_report.get("report_id", run_id),
        "suspect_drug": target_report.get("suspect_drug"),
        "patient_age": target_report.get("patient_age"),
        "patient_sex": target_report.get("patient_sex"),
        "reporter_type": target_report.get("reporter_type"),
        "drug_start_date": str(target_report.get("drug_start_date", "")),
        "event_date": str(target_report.get("event_date", "")),
        "reaction_description": target_report.get("reaction_description"),
        "outcome": target_report.get("outcome"),
        "narrative": target_report.get("narrative"),
    }


# Comprehensive deterministic fallback dictionary for lay-to-medical terms
_FALLBACK_REWRITE_MAP: Dict[str, List[str]] = {
    "peeling": [
        "Toxic epidermal necrolysis",
        "Stevens-Johnson syndrome",
        "Severe cutaneous adverse reactions",
        "Erythema multiforme",
        "Bullous dermatitis",
    ],
    "blister": [
        "Bullous dermatitis",
        "Stevens-Johnson syndrome",
        "Toxic epidermal necrolysis",
        "Bullous pemphigoid",
        "Dermatitis herpetiformis",
    ],
    "skin": [
        "Drug eruption",
        "Maculopapular rash",
        "Exanthem",
        "Cutaneous adverse reaction",
        "Dermatitis",
    ],
    "rash": [
        "Urticaria",
        "Maculopapular rash",
        "Drug eruption",
        "Generalized exanthem",
        "Angioedema",
    ],
    "hives": [
        "Urticaria",
        "Angioedema",
        "Allergic urticaria",
        "Physical urticaria",
        "Drug-induced urticaria",
    ],
    "liver": [
        "Drug-induced liver injury",
        "Hepatotoxicity",
        "Cholestatic liver injury",
        "Hepatic failure",
        "Transaminitis",
    ],
    "jaundice": [
        "Jaundice",
        "Cholestatic jaundice",
        "Hepatocellular jaundice",
        "Drug-induced liver injury",
        "Obstructive jaundice",
    ],
    "yellow": [
        "Jaundice",
        "Hyperbilirubinemia",
        "Cholestasis",
        "Hepatocellular injury",
        "Gilbert syndrome",
    ],
    "bleed": [
        "Gastrointestinal hemorrhage",
        "Upper GI bleed",
        "Coagulopathy",
        "Hemorrhage",
        "Bleeding diathesis",
    ],
    "hemorrhage": [
        "Gastrointestinal hemorrhage",
        "Intracranial hemorrhage",
        "Hemorrhage",
        "Coagulopathy",
        "Disseminated intravascular coagulation",
    ],
    "fever": [
        "Pyrexia",
        "Drug-induced fever",
        "Hyperthermia",
        "Febrile neutropenia",
        "Systemic inflammatory response",
    ],
    "seizure": [
        "Convulsion",
        "Epileptic seizure",
        "Status epilepticus",
        "Partial seizure",
        "Generalized tonic-clonic seizure",
    ],
    "convulsion": [
        "Convulsion",
        "Epileptic seizure",
        "Tonic-clonic convulsion",
        "Myoclonus",
    ],
    "dizziness": [
        "Vertigo",
        "Presyncope",
        "Syncope",
        "Dizziness postural",
    ],
    "nausea": [
        "Nausea",
        "Vomiting",
        "Dyspepsia",
        "Gastrointestinal upset",
    ],
    "vomit": [
        "Vomiting",
        "Emesis",
        "Hematemesis",
        "Gastrointestinal disorder",
    ],
    "breath": [
        "Dyspnea",
        "Respiratory distress",
        "Bronchospasm",
        "Asthma aggravated",
    ],
    "kidney": [
        "Acute kidney injury",
        "Renal impairment",
        "Nephrotoxicity",
        "Tubulointerstitial nephritis",
    ],
    "renal": [
        "Acute kidney injury",
        "Renal failure",
        "Nephrotoxicity",
        "Proteinuria",
    ],
    "swelling": [
        "Angioedema",
        "Peripheral edema",
        "Facial edema",
        "Anaphylaxis",
    ],
    "heart": [
        "Myocardial infarction",
        "Arrhythmia",
        "Cardiac failure",
        "QT prolongation",
    ],
}


def _strip_markdown_code_blocks(text: str) -> str:
    """Strip markdown code fence blocks like ```json ... ``` from text."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _rewrite_query_llm(lay_text: str) -> Optional[List[str]]:
    """Attempt LLM-based rewrite using prompts/rewrite/v1.md prompt."""
    try:
        provider = os.getenv("LLM_PROVIDER", "stub").lower().strip()
        if provider == "stub":
            # Stub LLM returns narrative text, not medical term lists; use deterministic fallback
            return None

        from llm.client import LLMClient
        from prompts.loader import load_prompt

        prompt_text, _ = load_prompt("rewrite")
        llm = LLMClient()
        llm_resp = llm.generate(prompt=lay_text, system=prompt_text, timeout=10.0)

        cleaned_text = _strip_markdown_code_blocks(llm_resp.text)
        terms = json.loads(cleaned_text)

        if isinstance(terms, list) and 3 <= len(terms) <= 5 and all(isinstance(t, str) for t in terms):
            return terms

    except Exception as exc:
        logger.debug("LLM query rewrite fallback triggered: %s", exc)

    return None


def _rewrite_query_fallback(lay_text: str) -> List[str]:
    """Deterministic fallback rewrite using keyword matching with concept interleaving."""
    lay_lower = lay_text.lower()
    matched_lists: List[List[str]] = []

    for keyword, terms in _FALLBACK_REWRITE_MAP.items():
        if keyword in lay_lower:
            matched_lists.append(terms)

    # Interleave terms across all matched concepts so multiple clinical concerns are represented
    seen = set()
    unique_candidates: List[str] = []
    max_depth = max((len(l) for l in matched_lists), default=0)

    for depth in range(max_depth):
        for term_list in matched_lists:
            if depth < len(term_list):
                term = term_list[depth]
                if term not in seen:
                    seen.add(term)
                    unique_candidates.append(term)
                    if len(unique_candidates) == 5:
                        break
        if len(unique_candidates) == 5:
            break

    # Pad with generic clinical terms if fewer than 3 terms found
    generic_terms = [
        "Adverse drug reaction",
        "Drug hypersensitivity",
        "Medication adverse reaction",
        "Pharmacovigilance signal",
        "Drug safety event",
    ]

    for term in generic_terms:
        if len(unique_candidates) >= 3:
            break
        if term not in seen:
            seen.add(term)
            unique_candidates.append(term)

    if len(unique_candidates) > 5:
        unique_candidates = unique_candidates[:5]

    if not unique_candidates:
        stripped = lay_text.strip()
        unique_candidates = [
            stripped or "Adverse drug reaction",
            "Drug hypersensitivity",
            "Medication adverse reaction",
        ]

    return unique_candidates


def _rewrite_query_core(lay_text: str) -> List[str]:
    """Core implementation of lay-to-medical query rewrite."""
    llm_terms = _rewrite_query_llm(lay_text)
    if llm_terms:
        return llm_terms
    return _rewrite_query_fallback(lay_text)


# ========================================================================
# Tool Factory & Namespace
# ========================================================================

class Tools:
    """Namespace holding tool functions wrapped for a specific tool_log."""

    def __init__(
        self,
        tool_log: List[ToolCall],
        max_calls: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        self._tool_log = tool_log
        self._max_calls = max_calls if max_calls is not None else int(os.getenv("MAX_TOOL_CALLS", "20"))
        self._timeout_s = timeout_s if timeout_s is not None else float(os.getenv("TOOL_TIMEOUT_S", "10.0"))
        self._wrap_tools()

    def _wrap_tools(self) -> None:
        """Create wrapped versions of all tools bound to this tool_log."""
        self.search_corpus = make_tool_wrapper(
            "search_corpus", self._tool_log, max_calls=self._max_calls, timeout_s=self._timeout_s
        )(_search_corpus_core)

        self.get_clause = make_tool_wrapper(
            "get_clause", self._tool_log, max_calls=self._max_calls, timeout_s=self._timeout_s
        )(_get_clause_core)

        self.get_request_fields = make_tool_wrapper(
            "get_request_fields", self._tool_log, max_calls=self._max_calls, timeout_s=self._timeout_s
        )(_get_request_fields_core)

        self.rewrite_query = make_tool_wrapper(
            "rewrite_query", self._tool_log, max_calls=self._max_calls, timeout_s=self._timeout_s
        )(_rewrite_query_core)


def wrap_tools(
    tool_log: List[ToolCall],
    max_calls: Optional[int] = None,
    timeout_s: Optional[float] = None,
) -> Tools:
    """Create a Tools namespace with all tools wrapped to log to the given tool_log.

    Args:
        tool_log: The list to append ToolCall audit records to (typically state["tool_log"]).
        max_calls: Maximum allowed tool calls before ToolCallLimitExceeded is raised. Defaults to MAX_TOOL_CALLS env var.
        timeout_s: Per-call execution timeout in seconds. Defaults to TOOL_TIMEOUT_S env var.

    Returns:
        Tools instance with search_corpus, get_clause, get_request_fields, rewrite_query methods.
    """
    resolved_max_calls = max_calls if max_calls is not None else int(os.getenv("MAX_TOOL_CALLS", "20"))
    resolved_timeout_s = timeout_s if timeout_s is not None else float(os.getenv("TOOL_TIMEOUT_S", "10.0"))
    return Tools(tool_log, max_calls=resolved_max_calls, timeout_s=resolved_timeout_s)


# ========================================================================
# Standalone / Unwrapped Tool Functions (backward compatibility & testing)
# ========================================================================

search_corpus = _search_corpus_core
get_clause = _get_clause_core
get_request_fields = _get_request_fields_core
rewrite_query = _rewrite_query_core
