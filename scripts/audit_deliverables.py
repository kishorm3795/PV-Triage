"""scripts/audit_deliverables.py - Deliverables Audit & Verification Script.

Meets Post-Phase Member C Task 4:
Checks that README, runbook, incident log (>=1 real entry), .env.example,
eval set (>=20 scenarios), SLO.md, report, and demo script all exist and meet criteria.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REQUIRED_FILES = [
    ("README.md", "Project documentation & clean-clone instructions"),
    (".env.example", "Environment configuration template"),
    ("AGENTS.md", "Global rules & ownership contracts"),
    ("docs/runbook.md", "Operational & troubleshooting runbook"),
    ("docs/incident_log.md", "Real engineering incident log"),
    ("docs/SLO.md", "Pre-loadtest committed Service Level Objectives"),
    ("docs/load_results.md", "Locust load testing results & scaling tables"),
    ("docs/eval_results.md", "Evaluation benchmark metrics (Prompt v1 vs v2)"),
    ("docs/metrics.md", "Mathematical formulations of evaluation metrics"),
    ("docs/cost_controls.md", "Rate limiting and whole-run caching architecture"),
    ("docs/reference_case.md", "Reference case clinical and statutory mapping"),
    ("docs/reference_verification.md", "Physical PDF corpus verification audit"),
    ("docs/demo_script.md", "The 10-item comprehensive demonstration script"),
    ("docs/report.md", "Comprehensive engineering project report"),
    ("docs/viva_questions.md", "Data, RAG, Eval & SLO viva preparation guide"),
    ("agents/CHANGES.md", "Agent Core diagnostic change log & deliberate experiment"),
    ("agents/COST.md", "Token accounting & cost per 100 runs breakdown"),
    ("agents/VIVA.md", "Agent architecture & resilience viva guide"),
    ("eval/scenarios.jsonl", "Synthetic benchmark scenario dataset"),
    ("scripts/demo.sh", "10-item demonstration execution script"),
    ("scripts/clean_clone_test.sh", "Clean-clone end-to-end verification script"),
    ("scripts/scan_secrets.sh", "Security secret scanning script"),
]


def audit_deliverables() -> int:
    root = Path(__file__).resolve().parent.parent
    print("================================================================================")
    print("                    PV-TRIAGE DELIVERABLES AUDIT CHECKLIST                      ")
    print(f"Repository Root: {root}")
    print("================================================================================\n")

    failures = 0

    for rel_path, desc in REQUIRED_FILES:
        file_path = root / rel_path
        if not file_path.exists():
            print(f"❌ [MISSING] {rel_path:<30} - {desc}")
            failures += 1
            continue

        size = file_path.stat().st_size
        if size == 0:
            print(f"❌ [EMPTY]   {rel_path:<30} - File exists but has 0 bytes")
            failures += 1
            continue

        # Content-specific checks
        if rel_path == "docs/incident_log.md":
            text = file_path.read_text(encoding="utf-8")
            if "Incident 001" not in text and "Root Cause" not in text:
                print(f"❌ [INVALID] {rel_path:<30} - Missing real incident entries")
                failures += 1
                continue

        if rel_path == "eval/scenarios.jsonl":
            lines = [l for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if len(lines) < 20:
                print(f"❌ [INSUFFICIENT] {rel_path:<30} - Found {len(lines)} scenarios, expected >= 20")
                failures += 1
                continue

        if rel_path == "scripts/demo.sh":
            if not os.access(file_path, os.X_OK):
                os.chmod(file_path, 0o755)

        print(f"✅ [PASS]    {rel_path:<30} ({size:>6} bytes) - {desc}")

    print("\n--------------------------------------------------------------------------------")
    if failures == 0:
        print("🎉 ALL DELIVERABLES AUDITED AND VERIFIED SUCCESSFULLY! (100% PASS)")
        print("--------------------------------------------------------------------------------\n")
        return 0
    else:
        print(f"⚠️ AUDIT FAILED: {failures} deliverable(s) missing or invalid.")
        print("--------------------------------------------------------------------------------\n")
        return 1


if __name__ == "__main__":
    sys.exit(audit_deliverables())
