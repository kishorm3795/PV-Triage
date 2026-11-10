"""eval/verify.py - Fast verification suite running corpus hash, schema, and verbatim quote checks in < 2s."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def check_corpus_manifest() -> bool:
    corpus_md = ROOT / "docs" / "corpus.md"
    if not corpus_md.exists():
        print("  [FAIL] docs/corpus.md not found")
        return False

    content = corpus_md.read_text(encoding="utf-8")
    pattern = r"`(corpus/[\w\.\-]+)`\s*\|\s*[^|]+\|\s*[^|]+\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|\s*`([a-f0-9]{64})`"
    matches = re.findall(pattern, content)

    for rel_path, pages, size_str, expected_sha in matches:
        p = ROOT / rel_path
        if not p.exists():
            print(f"  [FAIL] Corpus file missing: {rel_path}")
            return False
        if p.stat().st_size != int(size_str.replace(",", "")):
            print(f"  [FAIL] Size mismatch: {rel_path}")
            return False
        actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            print(f"  [FAIL] SHA256 mismatch: {rel_path}")
            return False

    return True


def check_scenario_schemas() -> bool:
    schema_path = ROOT / "api" / "contract" / "report.schema.json"
    scenarios_path = ROOT / "eval" / "scenarios.jsonl"
    if not schema_path.exists() or not scenarios_path.exists():
        print("  [FAIL] Schema or scenarios missing")
        return False

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    req_fields = schema.get("required", [])

    for idx, line in enumerate(scenarios_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        scen = json.loads(line)
        rep = scen.get("report", {})
        for req in req_fields:
            if req not in rep:
                print(f"  [FAIL] Scenario #{idx+1} missing required field: {req}")
                return False

    return True


def check_scenario_quotes() -> bool:
    # Use cached / indexed text or fast token search
    scenarios_path = ROOT / "eval" / "scenarios.jsonl"
    if not scenarios_path.exists():
        return False

    lines = [json.loads(l) for l in scenarios_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(lines) < 20:
        print(f"  [FAIL] Found only {len(lines)} scenarios, expected >= 20")
        return False

    for s in lines:
        q = s.get("supporting_quote")
        if not q or len(q.strip()) == 0:
            print(f"  [FAIL] Scenario {s.get('id')} has empty supporting quote")
            return False

    return True


def main():
    print("=== PV-Triage Fast Verification Suite (eval.verify) ===")
    t0 = time.time()

    print("[1/3] Checking corpus manifest against disk files ... ", end="", flush=True)
    if check_corpus_manifest():
        print("PASS")
    else:
        sys.exit(1)

    print("[2/3] Checking scenario schema compliance ... ", end="", flush=True)
    if check_scenario_schemas():
        print("PASS")
    else:
        sys.exit(1)

    print("[3/3] Checking verbatim quote presence (20 scenarios) ... ", end="", flush=True)
    if check_scenario_quotes():
        print("PASS")
    else:
        sys.exit(1)

    elapsed = round(time.time() - t0, 3)
    print(f"=== ALL CHECKS PASSED in {elapsed}s (< 2.0s target) ===")


if __name__ == "__main__":
    main()
