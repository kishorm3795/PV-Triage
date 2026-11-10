"""eval/test_scenario_schema.py - Test that all scenarios satisfy report.schema.json."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


def validate_json_schema(data: dict, schema: dict) -> list[str]:
    """Lightweight recursive schema validator enforcing type, required, enum, and extra forbidden."""
    errors = []
    req_fields = schema.get("required", [])
    for field in req_fields:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        for k in data:
            if k not in properties:
                errors.append(f"Extra forbidden field: '{k}'")

    for k, v in data.items():
        if k in properties:
            prop_schema = properties[k]
            expected_type = prop_schema.get("type")
            if expected_type == "string" and not isinstance(v, str):
                errors.append(f"Field '{k}' must be string, got {type(v).__name__}")
            elif expected_type == "integer" and not (isinstance(v, int) and not isinstance(v, bool)):
                errors.append(f"Field '{k}' must be integer, got {type(v).__name__}")
            elif expected_type == "array" and not isinstance(v, list):
                errors.append(f"Field '{k}' must be array, got {type(v).__name__}")
            elif expected_type == "object" and isinstance(v, dict):
                errors.extend(validate_json_schema(v, prop_schema))

            if "enum" in prop_schema and v not in prop_schema["enum"]:
                errors.append(f"Field '{k}' value '{v}' not in allowed enum: {prop_schema['enum']}")

    return errors


class TestScenarioSchema(unittest.TestCase):
    """Ensure any scenario in eval/scenarios.jsonl satisfies api/contract/report.schema.json."""

    def test_all_scenarios_comply_with_schema(self):
        schema_path = ROOT / "api" / "contract" / "report.schema.json"
        self.assertTrue(schema_path.exists(), "api/contract/report.schema.json must exist")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        scenarios_path = ROOT / "eval" / "scenarios.jsonl"
        self.assertTrue(scenarios_path.exists(), "eval/scenarios.jsonl must exist")

        lines = [line.strip() for line in scenarios_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 20, "Must have at least 20 scenarios")

        for idx, line in enumerate(lines, 1):
            scen = json.loads(line)
            report = scen.get("report")
            self.assertIsNotNone(report, f"Scenario #{idx} missing 'report' object")
            errors = validate_json_schema(report, schema)
            self.assertEqual(len(errors), 0, f"Scenario #{idx} ({scen.get('id')}) failed schema: {errors}")


if __name__ == "__main__":
    unittest.main()
