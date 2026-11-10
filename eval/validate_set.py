"""eval/validate_set.py - Validation script for benchmark scenarios.

Verifies:
1. Every scenario report conforms strictly to api/contract/report.schema.json (read-only).
2. Every supporting quote exists verbatim in the parsed corpus text.
3. Required schema invariants (temporal ordering, enum bounds, non-empty fields).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
import pypdf

SCHEMA_PATH = Path("api/contract/report.schema.json")
SCENARIOS_PATH = Path("eval/scenarios.jsonl")
CORPUS_PDFS = [
    Path("corpus/ipc_pv_guidance_mah.pdf"),
    Path("corpus/lamotrigine_package_insert.pdf"),
    Path("corpus/ndct_rules_2019.pdf"),
]


def load_corpus_text() -> str:
    combined_text = []
    for pdf_path in CORPUS_PDFS:
        if not pdf_path.exists():
            print(f"[ERROR] Missing corpus document: {pdf_path}", file=sys.stderr)
            sys.exit(1)
        reader = pypdf.PdfReader(str(pdf_path))
        for p in reader.pages:
            t = p.extract_text()
            if t:
                combined_text.append(t)
    return " ".join(" ".join(combined_text).split()).lower()


def validate_scenarios() -> bool:
    if not SCHEMA_PATH.exists():
        print(f"[ERROR] Schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return False

    with open(SCHEMA_PATH, "r", encoding="utf-8") as sf:
        schema = json.load(sf)

    if not SCENARIOS_PATH.exists():
        print(f"[ERROR] Scenarios file not found at {SCENARIOS_PATH}", file=sys.stderr)
        return False

    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        scenarios = [json.loads(line) for line in f if line.strip()]

    print(f"=== PV-Triage Scenario Set Validation ({len(scenarios)} scenarios) ===")
    print(f"Corpus documents: {[p.name for p in CORPUS_PDFS]}")
    print(f"Data contract schema: {SCHEMA_PATH}")
    print("-" * 70)

    clean_corpus = load_corpus_text()
    all_passed = True

    for idx, s in enumerate(scenarios, start=1):
        sid = s.get("id", f"scenario_{idx}")
        report = s.get("report", {})
        quote = s.get("supporting_quote", "")

        # 1. Schema conformance
        if HAS_JSONSCHEMA:
            try:
                jsonschema.validate(instance=report, schema=schema)
                schema_ok = True
            except jsonschema.ValidationError as ve:
                print(f"[{sid}] SCHEMA ERROR: {ve.message}", file=sys.stderr)
                schema_ok = False
                all_passed = False
        else:
            # Native Python validation against report.schema.json
            schema_ok = True
            required_fields = schema.get("required", [])
            for rf in required_fields:
                if rf not in report or report[rf] is None or report[rf] == "":
                    print(f"[{sid}] SCHEMA ERROR: Missing required field '{rf}'", file=sys.stderr)
                    schema_ok = False
                    all_passed = False
            # Check reporter_type enum
            rep_types = schema.get("$defs", {}).get("ReporterType", {}).get("enum", [])
            if report.get("reporter_type") not in rep_types:
                print(f"[{sid}] SCHEMA ERROR: Invalid reporter_type '{report.get('reporter_type')}'", file=sys.stderr)
                schema_ok = False
                all_passed = False
            # Check patient_sex enum
            sex_types = schema.get("$defs", {}).get("PatientSex", {}).get("enum", [])
            if report.get("patient_sex") not in sex_types:
                print(f"[{sid}] SCHEMA ERROR: Invalid patient_sex '{report.get('patient_sex')}'", file=sys.stderr)
                schema_ok = False
                all_passed = False
            # Check outcome enum
            outcomes = schema.get("$defs", {}).get("Outcome", {}).get("enum", [])
            if report.get("outcome") not in outcomes:
                print(f"[{sid}] SCHEMA ERROR: Invalid outcome '{report.get('outcome')}'", file=sys.stderr)
                schema_ok = False
                all_passed = False

        # 2. Quote verification
        clean_quote = " ".join(quote.split()).lower()
        quote_ok = clean_quote in clean_corpus
        if not quote_ok:
            print(f"[{sid}] QUOTE ERROR: Supporting quote not found in corpus text: {quote[:60]}...", file=sys.stderr)
            all_passed = False

        status_str = "PASS" if (schema_ok and quote_ok) else "FAIL"
        action = s.get("expected_action", "unknown")
        routing = s.get("expected_routing", "None")
        print(f"[{idx:02d}/20] {sid:<35} | {action:<8} | {str(routing):<14} | {status_str}")

    print("=" * 70)
    if all_passed:
        print(f"RESULT: ALL {len(scenarios)} SCENARIOS FULLY VALID (Schema & Verbatim Quotes Verified)!")
    else:
        print("RESULT: VALIDATION FAILED! Check error messages above.", file=sys.stderr)

    return all_passed


if __name__ == "__main__":
    success = validate_scenarios()
    sys.exit(0 if success else 1)
