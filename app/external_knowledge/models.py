from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from .schema import ALLOWED_STATUSES


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_id(value: Any, fallback: str = "external") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9가-힣_.-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return text[:96] or fallback


def stable_package_id(raw: dict[str, Any]) -> str:
    base = "|".join(
        str(raw.get(key, "") or "").strip()
        for key in ("source_name", "source_url", "strategy_id", "strategy_name", "version")
    )
    digest = hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"ext-{safe_id(raw.get('source_name') or raw.get('strategy_name'), 'package')}-{digest}"


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [item.strip() for item in re.split(r"[,;\n]", stripped) if item.strip()]
    return [value]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "included", "반영", "포함"}


def normalize_performance(raw: Any) -> dict[str, Any]:
    perf = raw if isinstance(raw, dict) else {}
    return {
        "start_date": str(perf.get("start_date", "") or ""),
        "end_date": str(perf.get("end_date", "") or ""),
        "return_pct": _to_float(perf.get("return_pct")),
        "annualized_return_pct": _to_float(perf.get("annualized_return_pct")),
        "mdd_pct": abs(_to_float(perf.get("mdd_pct"))),
        "win_rate_pct": _to_float(perf.get("win_rate_pct")),
        "profit_factor": _to_float(perf.get("profit_factor")),
        "trade_count": _to_int(perf.get("trade_count")),
        "fees_included": _to_bool(perf.get("fees_included")),
        "tax_included": _to_bool(perf.get("tax_included")),
        "slippage_included": _to_bool(perf.get("slippage_included")),
    }


def normalize_training_package(raw: dict[str, Any]) -> dict[str, Any]:
    package = dict(raw or {})
    package.setdefault("package_id", stable_package_id(package))
    package["package_id"] = safe_id(package.get("package_id"), stable_package_id(package))
    package.setdefault("imported_at", now_iso())
    package.setdefault("version", "1")
    package["source_type"] = str(package.get("source_type", "manual") or "manual").strip().lower()
    package["source_name"] = str(package.get("source_name", "") or "").strip()
    package["source_url"] = str(package.get("source_url", "") or "").strip()
    package["license"] = str(package.get("license", "") or "").strip()
    package["strategy_id"] = safe_id(package.get("strategy_id") or package.get("strategy_name"), "strategy")
    package["strategy_name"] = str(package.get("strategy_name", package["strategy_id"]) or package["strategy_id"]).strip()
    package["description"] = str(package.get("description", "") or "").strip()
    for key in (
        "market",
        "regimes",
        "timeframe",
        "entry_rules",
        "exit_rules",
        "stop_rules",
        "position_sizing_rules",
        "avoid_rules",
        "required_indicators",
        "required_data",
        "failure_cases",
        "known_limitations",
        "evidence",
    ):
        package[key] = ensure_list(package.get(key))
    package["market"] = [str(item).strip().upper() for item in package.get("market", []) if str(item).strip()]
    package["timeframe"] = [str(item).strip() for item in package.get("timeframe", []) if str(item).strip()]
    package["performance"] = normalize_performance(package.get("performance"))
    package["confidence"] = max(0.0, min(100.0, _to_float(package.get("confidence"))))
    status = str(package.get("status", "IMPORTED") or "IMPORTED").strip().upper()
    package["status"] = status if status in ALLOWED_STATUSES else "IMPORTED"
    package.setdefault("source_metadata", {})
    package.setdefault("validation", {})
    package.setdefault("promotion", {"allowed": False, "reason": "Stage 1은 연구/검증 전용입니다."})
    return package
