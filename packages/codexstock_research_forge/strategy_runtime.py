from __future__ import annotations

from typing import Any

from .indicators import calculate
from .execution import simulate_long_only


OPERATORS = {"<", "<=", ">", ">=", "=="}


def validate_indicator_rules(rules: dict[str, Any]) -> list[str]:
    errors = []
    for side in ("entry", "exit"):
        group = rules.get(side)
        if not isinstance(group, dict) or set(group) != {"all"} or not isinstance(group.get("all"), list) or not group["all"]:
            errors.append(f"indicator_rules.{side} must be a non-empty all array")
            continue
        if len(group["all"]) > 20:
            errors.append(f"indicator_rules.{side} exceeds 20 conditions")
        for index, condition in enumerate(group["all"]):
            if not isinstance(condition, dict) or set(condition) != {"left", "operator", "right"}:
                errors.append(f"indicator_rules.{side}[{index}] has invalid keys")
                continue
            if condition["operator"] not in OPERATORS:
                errors.append(f"indicator_rules.{side}[{index}] has unsupported operator")
            for operand_name in ("left", "right"):
                errors.extend(_validate_operand(condition[operand_name], f"{side}[{index}].{operand_name}"))
    return errors


def indicator_signals(rows: list[dict[str, Any]], rules: dict[str, Any]) -> tuple[list[bool], list[bool]]:
    profile = str(rules.get("profile") or "STANDARD")
    cache: dict[str, list[float | None]] = {}

    def series(operand: Any) -> list[float | None]:
        if isinstance(operand, (int, float)):
            return [float(operand)] * len(rows)
        if "field" in operand:
            field = str(operand["field"])
            return [float(row[field]) for row in rows]
        key = repr((operand, profile))
        if key not in cache:
            result = calculate(
                str(operand["indicator"]), rows, dict(operand.get("parameters") or {}), profile
            )
            output = str(operand.get("output") or "value")
            values = result["outputs"].get(output)
            if not isinstance(values, list):
                raise ValueError(f"indicator output does not exist: {output}")
            cache[key] = values
        return cache[key]

    def group(name: str) -> list[bool]:
        conditions = rules[name]["all"]
        compiled = [(series(item["left"]), item["operator"], series(item["right"])) for item in conditions]
        output = []
        for index in range(len(rows)):
            output.append(all(_compare(left[index], operator, right[index]) for left, operator, right in compiled))
        return output

    return group("entry"), group("exit")


def run_signals_next_open(
    rows: list[dict[str, Any]], entry: list[bool], exit: list[bool], model: dict[str, Any]
) -> dict[str, Any]:
    result = simulate_long_only(rows, entry, exit, model)
    result.update({"entry_signal_count": sum(entry), "exit_signal_count": sum(exit)})
    return result


def _validate_operand(value: Any, label: str) -> list[str]:
    if isinstance(value, (int, float)):
        return []
    if not isinstance(value, dict):
        return [f"{label} must be a number or operand object"]
    if set(value) == {"field"}:
        return [] if value["field"] in {"open", "high", "low", "close", "volume"} else [f"{label} has unsupported field"]
    allowed = {"indicator", "parameters", "output"}
    if "indicator" not in value or set(value) - allowed:
        return [f"{label} has invalid indicator operand keys"]
    if not isinstance(value.get("parameters", {}), dict):
        return [f"{label}.parameters must be an object"]
    return []


def _compare(left: float | None, operator: str, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return {
        "<": left < right,
        "<=": left <= right,
        ">": left > right,
        ">=": left >= right,
        "==": left == right,
    }[operator]
