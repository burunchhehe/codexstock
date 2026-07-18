from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .indicators import INDICATORS, calculate as calculate_builtin


OPS = {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "MIN", "MAX", "ABS", "NEGATE", "LAG"}


class CustomIndicatorRegistry:
    """Persistent, non-executable indicator formulas with mandatory golden and prefix-stability checks."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def register(self, definition: dict[str, Any]) -> dict[str, Any]:
        normalized = self._validate_definition(definition)
        verification = self._verify(normalized)
        if not verification["passed"]:
            raise ValueError("custom indicator verification failed: " + "; ".join(verification["errors"]))
        canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        payload = {"schema_version": 1, "definition": normalized, "content_hash": f"sha256:{digest}", "verification": verification, "enabled": True}
        path = self.root / f"{normalized['name']}__{normalized['version']}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("content_hash") != payload["content_hash"]:
                raise ValueError("custom indicator name/version is immutable")
            return self._summary(existing)
        self._atomic(path, payload)
        return self._summary(payload)

    def calculate(self, name: str, version: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        payload = self.get(name, version)
        outputs = {key: self._evaluate(expression, rows) for key, expression in payload["definition"]["outputs"].items()}
        canonical = json.dumps(outputs, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return {"name": payload["definition"]["name"], "version": payload["definition"]["version"], "row_count": len(rows), "outputs": outputs, "definition_hash": payload["content_hash"], "result_hash": f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"}

    def get(self, name: str, version: str) -> dict[str, Any]:
        safe_name, safe_version = str(name).upper(), str(version)
        if not safe_name.replace("_", "").isalnum() or not safe_version.replace(".", "").replace("-", "").isalnum():
            raise ValueError("invalid custom indicator identity")
        path = self.root / f"{safe_name}__{safe_version}.json"
        if not path.is_file(): raise ValueError("custom indicator not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self) -> dict[str, Any]:
        rows = [self._summary(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.root.glob("*.json"))]
        return {"ok": True, "count": len(rows), "indicators": rows}

    def _verify(self, definition: dict[str, Any]) -> dict[str, Any]:
        errors, cases = [], []
        for index, case in enumerate(definition["golden_tests"]):
            rows, expected = case["rows"], case["expected_last"]
            first = {key: self._evaluate(expr, rows) for key, expr in definition["outputs"].items()}
            second = {key: self._evaluate(expr, rows) for key, expr in definition["outputs"].items()}
            if first != second: errors.append(f"case {index} is non-deterministic")
            tolerance = float(case.get("tolerance") or 1e-9)
            for output, expected_value in expected.items():
                series = first.get(output)
                actual = next((value for value in reversed(series or []) if value is not None), None)
                if actual is None or abs(float(actual) - float(expected_value)) > tolerance:
                    errors.append(f"case {index} output {output} differs from golden value")
            # A value at t must be identical when later rows do not exist.
            for end in range(1, len(rows) + 1):
                for output, expression in definition["outputs"].items():
                    prefix = self._evaluate(expression, rows[:end])[-1]
                    full = first[output][end - 1]
                    if prefix != full: errors.append(f"case {index} output {output} uses future data at index {end - 1}")
            cases.append({"case": index, "rows": len(rows), "expected_outputs": sorted(expected)})
        return {"passed": not errors, "errors": errors[:50], "golden_case_count": len(cases), "prefix_stability_checked": True, "determinism_checked": True, "cases": cases}

    def _evaluate(self, expression: dict[str, Any], rows: list[dict[str, Any]]) -> list[float | None]:
        if "constant" in expression: return [float(expression["constant"])] * len(rows)
        if "field" in expression:
            return [float(row[expression["field"]]) for row in rows]
        if "indicator" in expression:
            result = calculate_builtin(expression["indicator"], rows, expression.get("parameters") or {}, expression.get("profile") or "STANDARD")
            return list(result["outputs"][expression.get("output") or "value"])
        op, args = expression["op"], expression["args"]
        values = [self._evaluate(arg, rows) for arg in args]
        if op == "LAG":
            periods = int(expression.get("periods") or 1)
            return [None] * periods + values[0][:-periods] if periods < len(rows) else [None] * len(rows)
        output = []
        for index in range(len(rows)):
            operands = [series[index] for series in values]
            if any(value is None for value in operands): output.append(None); continue
            a = float(operands[0]); b = float(operands[1]) if len(operands) > 1 else None
            if op == "ADD": value = a + float(b)
            elif op == "SUBTRACT": value = a - float(b)
            elif op == "MULTIPLY": value = a * float(b)
            elif op == "DIVIDE": value = None if b == 0 else a / float(b)
            elif op == "MIN": value = min(a, float(b))
            elif op == "MAX": value = max(a, float(b))
            elif op == "ABS": value = abs(a)
            else: value = -a
            output.append(value if value is None or math.isfinite(value) else None)
        return output

    def _validate_definition(self, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) - {"name", "version", "description", "outputs", "golden_tests"}:
            raise ValueError("custom indicator definition has invalid keys")
        name, version = str(value.get("name") or "").upper(), str(value.get("version") or "")
        if name in INDICATORS or not name.replace("_", "").isalnum() or not version.replace(".", "").replace("-", "").isalnum():
            raise ValueError("custom indicator requires a unique alphanumeric name and version")
        outputs, tests = value.get("outputs"), value.get("golden_tests")
        if not isinstance(outputs, dict) or not 1 <= len(outputs) <= 8 or not isinstance(tests, list) or not tests:
            raise ValueError("custom indicator requires outputs and golden_tests")
        nodes = [0]
        for output, expression in outputs.items():
            if not str(output).replace("_", "").isalnum(): raise ValueError("invalid custom output name")
            self._validate_expression(expression, 0, nodes)
        for case in tests:
            if not isinstance(case, dict) or not isinstance(case.get("rows"), list) or not 2 <= len(case["rows"]) <= 500 or not isinstance(case.get("expected_last"), dict):
                raise ValueError("invalid custom indicator golden test")
        return {"name": name, "version": version, "description": str(value.get("description") or ""), "outputs": outputs, "golden_tests": tests}

    def _validate_expression(self, value: Any, depth: int, nodes: list[int]) -> None:
        nodes[0] += 1
        if depth > 10 or nodes[0] > 100 or not isinstance(value, dict): raise ValueError("custom expression is too complex or invalid")
        if set(value) == {"constant"}:
            if not math.isfinite(float(value["constant"])): raise ValueError("constant must be finite")
            return
        if set(value) == {"field"}:
            if value["field"] not in {"open", "high", "low", "close", "volume"}: raise ValueError("unsupported custom field")
            return
        if "indicator" in value:
            if set(value) - {"indicator", "parameters", "output", "profile"} or str(value["indicator"]).upper() not in INDICATORS: raise ValueError("invalid built-in indicator reference")
            return
        if set(value) - {"op", "args", "periods"} or value.get("op") not in OPS or not isinstance(value.get("args"), list): raise ValueError("invalid custom operation")
        arity = 1 if value["op"] in {"ABS", "NEGATE", "LAG"} else 2
        if len(value["args"]) != arity: raise ValueError("invalid custom operation arity")
        if value["op"] == "LAG" and not 1 <= int(value.get("periods") or 1) <= 500: raise ValueError("invalid lag")
        for arg in value["args"]: self._validate_expression(arg, depth + 1, nodes)

    @staticmethod
    def _summary(payload: dict[str, Any]) -> dict[str, Any]:
        definition = payload["definition"]
        return {"name": definition["name"], "version": definition["version"], "description": definition["description"], "outputs": sorted(definition["outputs"]), "content_hash": payload["content_hash"], "verification": payload["verification"], "enabled": payload["enabled"]}

    @staticmethod
    def _atomic(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
