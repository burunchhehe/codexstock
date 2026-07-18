from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .custom_indicators import CustomIndicatorRegistry
from .indicators import calculate


OPERATORS = {"<", "<=", ">", ">=", "=="}


def validate_multitimeframe_rules(rules: dict[str, Any]) -> list[str]:
    errors = []
    contexts, execution = rules.get("contexts"), str(rules.get("execution_context") or "")
    if not isinstance(contexts, dict) or not 2 <= len(contexts) <= 8:
        return ["multi_timeframe contexts must contain 2..8 aliases"]
    for alias, context in contexts.items():
        if not str(alias).replace("_", "").isalnum() or not isinstance(context, dict) or set(context) != {"timeframe"}:
            errors.append(f"invalid timeframe context: {alias}")
            continue
        try: _duration(str(context["timeframe"]))
        except ValueError as exc: errors.append(str(exc))
    if execution not in contexts: errors.append("execution_context must reference a declared context")
    for side in ("entry", "exit"):
        group = rules.get(side)
        if not isinstance(group, dict) or set(group) != {"all"} or not isinstance(group.get("all"), list) or not group["all"]:
            errors.append(f"multi_timeframe.{side} must be a non-empty all group"); continue
        if len(group["all"]) > 30: errors.append(f"multi_timeframe.{side} exceeds 30 conditions")
        for index, condition in enumerate(group["all"]):
            if not isinstance(condition, dict) or set(condition) != {"left", "operator", "right"} or condition.get("operator") not in OPERATORS:
                errors.append(f"multi_timeframe.{side}[{index}] is invalid"); continue
            for operand in (condition["left"], condition["right"]):
                errors.extend(_validate_operand(operand, contexts))
    return errors


def evaluate_multitimeframe(
    rules: dict[str, Any], rows_by_context: dict[str, list[dict[str, Any]]],
    custom_registry: CustomIndicatorRegistry | None = None,
) -> dict[str, Any]:
    errors = validate_multitimeframe_rules(rules)
    if errors: raise ValueError("; ".join(errors))
    contexts, execution = rules["contexts"], rules["execution_context"]
    if set(rows_by_context) != set(contexts): raise ValueError("rows_by_context must exactly match declared contexts")
    timelines = {}
    for alias, context in contexts.items():
        rows = rows_by_context[alias]
        if not rows: raise ValueError(f"context {alias} has no rows")
        duration = _duration(context["timeframe"])
        timestamps = [_timestamp(row) for row in rows]
        if any(left >= right for left, right in zip(timestamps, timestamps[1:])): raise ValueError(f"context {alias} timestamps are not strictly increasing")
        available = [_timestamp_value(row.get("available_at")) if row.get("available_at") else timestamp + duration for row, timestamp in zip(rows, timestamps)]
        timelines[alias] = {"rows": rows, "timestamps": timestamps, "available": available, "timeframe": context["timeframe"]}
    base = timelines[execution]
    evaluation_times = base["available"]
    aligned_indexes = {alias: _align(timeline["available"], evaluation_times) for alias, timeline in timelines.items()}
    cache: dict[str, list[float | None]] = {}

    def operand_series(operand: Any) -> list[float | None]:
        if isinstance(operand, (int, float)): return [float(operand)] * len(evaluation_times)
        alias = str(operand.get("timeframe") or execution)
        source = timelines[alias]
        key = repr(operand)
        if key not in cache:
            if "field" in operand:
                raw = [float(row[operand["field"]]) for row in source["rows"]]
            elif "custom_indicator" in operand:
                if custom_registry is None: raise ValueError("custom indicator registry is required")
                result = custom_registry.calculate(str(operand["custom_indicator"]), str(operand["version"]), source["rows"])
                raw = result["outputs"][str(operand.get("output") or "value")]
            else:
                result = calculate(str(operand["indicator"]), source["rows"], dict(operand.get("parameters") or {}), str(operand.get("profile") or "STANDARD"))
                raw = result["outputs"][str(operand.get("output") or "value")]
            cache[key] = [None if index is None else raw[index] for index in aligned_indexes[alias]]
        return cache[key]

    def signals(side: str) -> list[bool]:
        compiled = [(operand_series(row["left"]), row["operator"], operand_series(row["right"])) for row in rules[side]["all"]]
        return [all(_compare(left[index], op, right[index]) for left, op, right in compiled) for index in range(len(evaluation_times))]

    entry, exit_values = signals("entry"), signals("exit")
    violations = 0
    for alias, indexes in aligned_indexes.items():
        for base_index, source_index in enumerate(indexes):
            if source_index is not None and timelines[alias]["available"][source_index] > evaluation_times[base_index]: violations += 1
    return {
        "execution_context": execution, "execution_timeframe": base["timeframe"],
        "rows": base["rows"], "entry_signals": entry, "exit_signals": exit_values,
        "entry_signal_count": sum(entry), "exit_signal_count": sum(exit_values),
        "alignment": {alias: {"timeframe": timelines[alias]["timeframe"], "source_rows": len(timelines[alias]["rows"]), "unavailable_prefix_rows": sum(index is None for index in indexes)} for alias, indexes in aligned_indexes.items()},
        "future_information_violations": violations, "higher_timeframe_close_required": True,
    }


def _validate_operand(value: Any, contexts: dict[str, Any]) -> list[str]:
    if isinstance(value, (int, float)): return []
    if not isinstance(value, dict): return ["operand must be numeric or an object"]
    alias = str(value.get("timeframe") or "")
    if alias and alias not in contexts: return [f"unknown timeframe alias: {alias}"]
    common = {"timeframe"}
    if "field" in value:
        return [] if not set(value) - (common | {"field"}) and value["field"] in {"open", "high", "low", "close", "volume"} else ["invalid timeframe field operand"]
    if "custom_indicator" in value:
        required = {"custom_indicator", "version"}
        return [] if required.issubset(value) and not set(value) - (common | required | {"output"}) else ["invalid custom indicator operand"]
    return [] if "indicator" in value and not set(value) - (common | {"indicator", "parameters", "output", "profile"}) else ["invalid built-in indicator operand"]


def _align(source_available: list[datetime], targets: list[datetime]) -> list[int | None]:
    output, cursor = [], -1
    for target in targets:
        while cursor + 1 < len(source_available) and source_available[cursor + 1] <= target: cursor += 1
        output.append(cursor if cursor >= 0 else None)
    return output


def _duration(value: str) -> timedelta:
    if value == "1d": return timedelta(days=1)
    if value.endswith("m") and value[:-1].isdigit() and int(value[:-1]) in {1, 3, 5, 10, 15, 30, 60}: return timedelta(minutes=int(value[:-1]))
    raise ValueError(f"unsupported timeframe: {value}")


def _timestamp(row: dict[str, Any]) -> datetime:
    return _timestamp_value(row.get("timestamp") or row.get("date"))


def _timestamp_value(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _compare(left: float | None, operator: str, right: float | None) -> bool:
    if left is None or right is None: return False
    return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right, "==": left == right}[operator]
