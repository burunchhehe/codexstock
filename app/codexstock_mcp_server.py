from __future__ import annotations

import copy
import json
import hashlib
import importlib
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVER_NAME = "codexstock-mcp"
SERVER_VERSION = "0.3.1-research-forge-gpt-lite"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
BASE_URL = os.environ.get("CODEXSTOCK_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
DEFAULT_TOOL_RESULT_MAX_CHARS = 18000
HARD_TOOL_RESULT_MAX_CHARS = 40000
MCP_CLIENT_EXPOSURE_RECEIPT_SCHEMA = "codexstock.mcp-client-exposure-receipt.v1"
MCP_HTTP_CACHE_MAX_ENTRIES = 64
MCP_CORE_TOOL_NAMES = (
    "codexstock_mcp_manifest",
    "codexstock_status",
    "codexstock_ask_agent",
    "codexstock_feature_health",
    "codexstock_staff_status",
    "codexstock_internal_developer_status",
    "codexstock_internal_developer_latest_report",
    "codexstock_internal_developer_readonly_diagnostics",
    "codexstock_market_context_snapshot",
    "codexstock_intraday_market_pulse",
    "codexstock_candidate_lane_audit",
    "codexstock_live_candidate_decisions",
    "codexstock_live_order_blackbox",
    "codexstock_live_reconciliation_audit",
    "codexstock_learning_memory_audit",
    "codexstock_staff_learning_effect_audit",
    "codexstock_external_signal_inbox",
    "codexstock_external_engine_status",
    "codexstock_external_learning_report",
    "codexstock_weakness_completion_audit",
)

_USE_HEADERS = False
_HTTP_JSON_CACHE: dict[str, tuple[float, Any]] = {}
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
PACKAGES_DIR = REPO_ROOT / "packages"
MCP_SOURCE_PATH = Path(__file__).resolve()
MCP_PROCESS_STARTED_AT = datetime.now(timezone.utc).isoformat()
try:
    _mcp_loaded_stat = MCP_SOURCE_PATH.stat()
    MCP_SOURCE_LOADED_STAT = (_mcp_loaded_stat.st_mtime_ns, _mcp_loaded_stat.st_size)
    MCP_SOURCE_LOADED_SHA256 = hashlib.sha256(MCP_SOURCE_PATH.read_bytes()).hexdigest()
except OSError:
    MCP_SOURCE_LOADED_STAT = (0, 0)
    MCP_SOURCE_LOADED_SHA256 = ""
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from runtime_paths import active_data_root
from codexstock_research_forge.gateway import RESEARCH_TOOL_NAMES, call_research_tool

try:
    from external_knowledge import ExternalKnowledgeStore
except Exception:  # pragma: no cover - returned through MCP diagnostics
    ExternalKnowledgeStore = None  # type: ignore[assignment]

try:
    from internal_developer_store import InternalDeveloperStore
    from internal_developer_engine import InternalDeveloperEngine
except Exception:  # pragma: no cover - returned through MCP diagnostics
    InternalDeveloperStore = None  # type: ignore[assignment]
    InternalDeveloperEngine = None  # type: ignore[assignment]


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _read_message() -> dict[str, Any] | None:
    global _USE_HEADERS
    while True:
        first = sys.stdin.buffer.readline()
        if not first:
            return None
        if not first.strip():
            continue
        if first.lower().startswith(b"content-length:"):
            _USE_HEADERS = True
            try:
                length = int(first.split(b":", 1)[1].strip())
            except Exception:
                raise ValueError("Invalid Content-Length header")
            while True:
                header = sys.stdin.buffer.readline()
                if header in {b"\r\n", b"\n", b""}:
                    break
            body = sys.stdin.buffer.read(length)
            if not body:
                return None
            return json.loads(body.decode("utf-8-sig"))
        return json.loads(first.decode("utf-8-sig"))


def _send_message(message: dict[str, Any]) -> None:
    raw = _json_dump(message).encode("utf-8")
    if _USE_HEADERS:
        sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(raw)
    else:
        sys.stdout.buffer.write(raw + b"\n")
    sys.stdout.buffer.flush()


def _error_response(msg_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def _http_cache_key(method: str, path: str, params: dict[str, Any] | None) -> str:
    normalized = {
        "method": method.upper(),
        "path": path,
        "params": sorted((str(key), str(value)) for key, value in (params or {}).items()),
    }
    return hashlib.sha256(_json_dump(normalized).encode("utf-8")).hexdigest()


def _cached_http_payload(cache_key: str, max_age_seconds: float, cache_state: str) -> Any | None:
    cached = _HTTP_JSON_CACHE.get(cache_key)
    if not cached:
        return None
    saved_at, value = cached
    age_seconds = max(0.0, time.monotonic() - saved_at)
    if age_seconds > max(0.0, float(max_age_seconds or 0.0)):
        return None
    result = copy.deepcopy(value)
    if isinstance(result, dict):
        result["mcp_transport"] = {
            "cache": cache_state,
            "age_seconds": round(age_seconds, 3),
        }
    return result


def _store_http_payload(cache_key: str, value: Any) -> None:
    if len(_HTTP_JSON_CACHE) >= MCP_HTTP_CACHE_MAX_ENTRIES:
        oldest_key = min(_HTTP_JSON_CACHE, key=lambda key: _HTTP_JSON_CACHE[key][0])
        _HTTP_JSON_CACHE.pop(oldest_key, None)
    _HTTP_JSON_CACHE[cache_key] = (time.monotonic(), copy.deepcopy(value))


def _http_json(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 30.0,
    cache_ttl_seconds: float = 0.0,
    stale_if_error_seconds: float = 0.0,
) -> Any:
    cache_key = _http_cache_key(method, path, params)
    if method.upper() == "GET" and cache_ttl_seconds > 0:
        cached = _cached_http_payload(cache_key, cache_ttl_seconds, "fresh")
        if cached is not None:
            return cached
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=max(0.25, float(timeout_seconds))) as response:
            raw = response.read().decode("utf-8", errors="replace")
            result = json.loads(raw) if raw else {}
            if method.upper() == "GET" and (cache_ttl_seconds > 0 or stale_if_error_seconds > 0):
                _store_http_payload(cache_key, result)
            return result
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = raw
        error = {"ok": False, "http_status": exc.code, "error": body}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        error = {
            "ok": False,
            "error": f"코덱스스톡 로컬 앱에 연결하지 못했습니다: {reason}",
            "base_url": BASE_URL,
            "hint": "먼저 run_app.ps1 또는 StockSuiteHTS.exe로 코덱스스톡을 실행하세요.",
        }
    if method.upper() == "GET" and stale_if_error_seconds > 0:
        stale = _cached_http_payload(cache_key, stale_if_error_seconds, "stale_fallback")
        if stale is not None:
            if isinstance(stale, dict):
                stale["mcp_transport"]["upstream_error"] = error
            return stale
    return error



def _external_knowledge_store() -> Any:
    if ExternalKnowledgeStore is None:
        raise RuntimeError("ExternalKnowledgeStore import failed")
    data_root = active_data_root(REPO_ROOT)
    return ExternalKnowledgeStore(data_root / "external_knowledge")


def _internal_developer_store() -> Any:
    if InternalDeveloperStore is None:
        raise RuntimeError("InternalDeveloperStore import failed")
    return InternalDeveloperStore(REPO_ROOT, data_root=Path(active_data_root(REPO_ROOT)))


def _internal_developer_id(value: object, prefix: str) -> str:
    candidate = str(value or "").strip().upper()
    if not re.fullmatch(rf"{re.escape(prefix)}-[A-Z0-9][A-Z0-9_-]{{0,95}}", candidate):
        raise ValueError(f"invalid {prefix.lower()} id")
    return candidate


def _internal_developer_action_summary(value: object) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    verification = row.get("post_verification") if isinstance(row.get("post_verification"), dict) else {}
    return {
        "action": row.get("action"),
        "status": row.get("status"),
        "executed": bool(row.get("executed")),
        "reason_code": row.get("reason_code"),
        "parameters": row.get("parameters") if isinstance(row.get("parameters"), dict) else {},
        "verified": bool(verification.get("ok") or verification.get("success")),
    }


def _internal_developer_incident_summary(value: object) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    diagnostic = row.get("diagnostic") if isinstance(row.get("diagnostic"), dict) else {}
    attempts = row.get("recovery_attempts") if isinstance(row.get("recovery_attempts"), list) else []
    return {
        "incident_id": row.get("incident_id"),
        "classification": row.get("classification") or diagnostic.get("primary_issue"),
        "component": row.get("component"),
        "severity": row.get("severity"),
        "state": row.get("state"),
        "summary": row.get("summary"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "recurrence_count": row.get("recurrence_count"),
        "reviewed": bool(row.get("reviewed")),
        "recommended_actions": [
            _internal_developer_action_summary(item)
            for item in (
                diagnostic.get("recommended_actions", [])
                if isinstance(diagnostic.get("recommended_actions"), list)
                else []
            )[:8]
        ],
        "latest_attempt": _internal_developer_action_summary(attempts[-1]) if attempts else None,
    }


def _internal_developer_report_summary(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
    diagnostic = payload.get("diagnostic") if isinstance(payload.get("diagnostic"), dict) else {}
    results = payload.get("recovery_results") if isinstance(payload.get("recovery_results"), list) else []
    return {
        "report_id": value.get("report_id"),
        "incident_id": value.get("incident_id"),
        "created_at": value.get("created_at"),
        "updated_at": value.get("updated_at"),
        "review_status": value.get("review_status"),
        "status": payload.get("status"),
        "primary_issue": diagnostic.get("primary_issue"),
        "needs_external_advice": bool(payload.get("needs_external_advice")),
        "advice_id": payload.get("advice_id"),
        "source": payload.get("source"),
        "execution_authorized": False,
        "text_ignored": payload.get("text_ignored"),
        "recovery_results": [
            _internal_developer_action_summary(item) for item in results[:8]
        ],
    }


def _internal_developer_advice_summary(value: object) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    advice = row.get("advice") if isinstance(row.get("advice"), dict) else {}
    policy = row.get("policy_evaluation") if isinstance(row.get("policy_evaluation"), dict) else {}
    application = row.get("application_result") if isinstance(row.get("application_result"), dict) else {}
    results = application.get("results") if isinstance(application.get("results"), list) else []
    return {
        "advice_id": row.get("advice_id"),
        "incident_id": row.get("incident_id"),
        "status": row.get("status"),
        "received_at": row.get("received_at"),
        "updated_at": row.get("updated_at"),
        "advisor": advice.get("advisor"),
        "summary": advice.get("summary"),
        "confidence": advice.get("confidence"),
        "execution_authorized": False,
        "quarantined": bool(policy.get("quarantined")),
        "allowed_action_mentions": policy.get("allowed_action_mentions", []),
        "forbidden_categories": policy.get("forbidden_categories", []),
        "application": {
            "executed": bool(application.get("executed")),
            "success": bool(application.get("success")),
            "text_ignored": application.get("text_ignored"),
            "reason_code": application.get("reason_code"),
            "results": [
                _internal_developer_action_summary(item) for item in results[:8]
            ],
        },
    }


def _internal_developer_event_summary(value: object) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    keys = {
        "incident_id",
        "report_id",
        "advice_id",
        "playbook_id",
        "request_id",
        "from",
        "to",
        "state",
        "status",
        "action",
        "quarantined",
        "reusable",
    }
    return {
        "event_id": row.get("event_id"),
        "event_type": row.get("event_type"),
        "created_at": row.get("created_at"),
        "payload": {key: payload.get(key) for key in keys if key in payload},
    }


def _internal_developer_direct(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    store = _internal_developer_store()
    limit = _int_arg(arguments, "limit", 50, 1, 500)
    if name == "codexstock_internal_developer_status":
        return store.status()
    if name == "codexstock_internal_developer_component_status":
        component = str(arguments.get("component") or "").strip().lower()[:120]
        rows = store.list_incidents(limit=500)
        if component:
            rows = [
                row
                for row in rows
                if component in str(row.get("component") or "").strip().lower()
            ]
        return {
            "ok": True,
            "component": component or "all",
            "incident_count": len(rows),
            "incidents": rows[:limit],
            "status": store.status(),
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_internal_developer_list_incidents":
        rows = store.list_incidents(limit=500)
        state = str(arguments.get("state") or "").strip().upper()
        severity = str(arguments.get("severity") or "").strip().lower()
        if state:
            rows = [row for row in rows if str(row.get("state") or "").upper() == state]
        if severity:
            rows = [row for row in rows if str(row.get("severity") or "").lower() == severity]
        return {
            "ok": True,
            "count": len(rows[:limit]),
            "items": rows[:limit],
            "filters": {"state": state, "severity": severity},
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_internal_developer_get_incident":
        incident_id = _internal_developer_id(arguments.get("incident_id"), "INC")
        incident = store.get_incident(incident_id)
        return {
            "ok": incident is not None,
            "incident": incident,
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_internal_developer_latest_report":
        rows = store.list_reports(limit=1)
        return {
            "ok": True,
            "report": rows[0] if rows else None,
            "report_available": bool(rows),
            "read_does_not_acknowledge": True,
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_internal_developer_brief":
        incident_limit = _int_arg(arguments, "incident_limit", 5, 1, 20)
        activity_limit = _int_arg(arguments, "activity_limit", 10, 1, 100)
        reports = store.list_reports(limit=1)
        return {
            "ok": True,
            "schema": "codexstock.internal-developer-brief.v1",
            "status": store.status(),
            "attention": store.attention_summary(),
            "recent_incidents": [
                _internal_developer_incident_summary(item)
                for item in store.list_incidents(limit=incident_limit)
            ],
            "latest_report": _internal_developer_report_summary(reports[0]) if reports else None,
            "recent_advice": [
                _internal_developer_advice_summary(item)
                for item in store.list_advice(limit=5)
            ],
            "recent_activity": [
                _internal_developer_event_summary(item)
                for item in store.activity(limit=activity_limit)
            ],
            "read_does_not_acknowledge": True,
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_internal_developer_activity":
        event_type = str(arguments.get("event_type") or "").strip().lower() or None
        return {
            "ok": True,
            "items": store.list_events(limit=limit, event_type=event_type),
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_internal_developer_readonly_diagnostics":
        status = store.status()
        return {
            "ok": True,
            "schema": "codexstock.internal-developer-readonly-diagnostics.v1",
            "store_status": status,
            "record_counts": status.get("counts", {}),
            "index_rebuildable_from_individual_records": True,
            "restart_authority": "independent_watchdog_only",
            "automatic_code_edit": False,
            "read_only": True,
            "live_order_allowed": False,
        }
    if name == "codexstock_submit_developer_advice":
        incident_id = _internal_developer_id(arguments.get("incident_id"), "INC")
        proposed = arguments.get("proposed_actions")
        if proposed is None:
            proposed = []
        if not isinstance(proposed, list) or len(proposed) > 8:
            raise ValueError("proposed_actions must be an array with at most 8 items")
        policy_decisions: list[dict[str, Any]] = []
        if InternalDeveloperEngine is not None:
            engine = InternalDeveloperEngine(store)
            policy_decisions = [engine.evaluate_action(item) for item in proposed]
        payload = {
            "incident_id": incident_id,
            "advisor": str(arguments.get("advisor") or "gpt-via-mcp")[:120],
            "summary": str(arguments.get("summary") or "")[:4000],
            "analysis": str(arguments.get("analysis") or "")[:16000],
            "confidence": arguments.get("confidence"),
            "proposed_actions": proposed,
            "policy_decisions": policy_decisions,
            "execution_authorized": False,
            "untrusted_advice": True,
        }
        saved = store.submit_advice(payload)
        return {
            "ok": True,
            "saved": saved,
            "execution_authorized": False,
            "execution_performed": False,
            "next_step": "The independent deterministic policy engine will review structured actions.",
            "live_order_allowed": False,
        }
    raise KeyError(name)


def _attach_internal_developer_attention(payload: Any) -> dict[str, Any]:
    result = dict(payload) if isinstance(payload, dict) else {"data": payload}
    try:
        attention = _internal_developer_store().attention_summary()
        result["internal_developer"] = {
            **attention,
            "served_by": "mcp-direct-store",
            "read_does_not_acknowledge": True,
        }
        result["developer_attention_required"] = bool(attention.get("attention_required"))
    except Exception as exc:
        result["internal_developer"] = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "live_order_allowed": False,
        }
    return result


def _external_knowledge_direct(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    store = _external_knowledge_store()
    limit = _int_arg(arguments, "limit", 12, 1, 500)
    if name == "codexstock_external_sources":
        return store.source_catalog()
    if name == "codexstock_external_packages":
        return store.list_packages(limit=limit, status=str(arguments.get("status", "") or "") or None)
    if name == "codexstock_external_learning_report":
        return store.report(limit=limit)
    if name == "codexstock_external_engine_contract":
        return store.engine_contract()
    if name == "codexstock_external_runtime_audit":
        return store.runtime_isolation_audit()
    if name == "codexstock_external_dataset_snapshots":
        return store.list_dataset_snapshots(limit=limit)
    if name == "codexstock_external_common_snapshot":
        return store.build_common_snapshot_from_ohlcv_cache(
            symbols=arguments.get("symbols", ""),
            max_symbols=_int_arg(arguments, "max_symbols", 3, 1, 10),
            max_rows_per_symbol=_int_arg(arguments, "rows", 120, 20, 260),
            action=str(arguments.get("action", "run_external_backtest") or "run_external_backtest"),
            package_id=str(arguments.get("package_id", "") or ""),
            record=_bool_arg(arguments, "record", False),
            source="mcp-direct-common-snapshot",
        )
    if name == "codexstock_import_training_package":
        package = arguments.get("package") if isinstance(arguments.get("package"), dict) else {}
        return store.import_training_package(package, source="mcp-direct-import", replace=_bool_arg(arguments, "replace", False))
    if name == "codexstock_validate_external_package":
        return store.validate_package(str(arguments.get("package_id", "") or ""), source="mcp-direct-validate")
    if name == "codexstock_run_external_backtest":
        package_id = str(arguments.get("package_id", "") or "")
        return store.plan_stage2_engine_request(
            "run_external_backtest",
            package_id,
            arguments,
            source="mcp-direct-backtest",
        )
    if name == "codexstock_run_external_replay":
        package_id = str(arguments.get("package_id", "") or "")
        return store.plan_stage2_engine_request(
            "run_external_replay",
            package_id,
            arguments,
            source="mcp-direct-replay",
        )
    if name == "codexstock_compare_external_strategy":
        package_id = str(arguments.get("package_id", "") or "")
        return store.plan_stage2_engine_request(
            "compare_external_strategy",
            package_id,
            arguments,
            source="mcp-direct-compare",
        )
    if name == "codexstock_assign_training_mission":
        mission = dict(arguments.get("mission") if isinstance(arguments.get("mission"), dict) else {})
        mission["source"] = "mcp-direct-mission"
        return store.assign_training_mission(mission, source="mcp-direct-mission")
    if name == "codexstock_promote_external_knowledge":
        package_id = str(arguments.get("package_id", "") or "")
        return {
            "ok": False,
            "blocked": True,
            "package_id": package_id,
            "message": "Direct promotion is blocked until Stage 2 backtest/replay reconciliation passes.",
            "report": store.report(limit=5),
            "safety": "promotion is metadata-only blocked; no live candidate/order permission granted.",
        }
    if name == "codexstock_reject_external_knowledge":
        return store.reject_package(
            str(arguments.get("package_id", "") or ""),
            reason=str(arguments.get("reason", "rejected by MCP direct safety policy") or "rejected by MCP direct safety policy"),
            source="mcp-direct-reject",
        )
    raise KeyError(name)


def _external_knowledge_http_or_direct(
    name: str,
    method: str,
    path: str,
    arguments: dict[str, Any],
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    try:
        direct = _external_knowledge_direct(name, arguments)
        if isinstance(direct, dict):
            direct["served_by"] = "mcp-direct-store"
            direct["http_bypassed"] = True
            direct["http_fallback_path"] = path
        return direct
    except Exception as direct_exc:
        direct_error = {
            "error": str(direct_exc),
            "traceback": traceback.format_exc(limit=2),
        }
    upstream = _http_json(method, path, params, payload)
    if not (isinstance(upstream, dict) and upstream.get("ok") is False and (upstream.get("error") or upstream.get("http_status"))):
        if isinstance(upstream, dict):
            upstream.setdefault("served_by", "app-http")
            upstream.setdefault("mcp_direct_store_error", direct_error)
        return upstream
    try:
        direct = _external_knowledge_direct(name, arguments)
        if isinstance(direct, dict):
            direct["served_by"] = "mcp-direct-store"
            direct["http_fallback_reason"] = upstream.get("error") or upstream.get("http_status")
        return direct
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "http_error": upstream,
            "served_by": "mcp-direct-store-failed",
            "traceback": traceback.format_exc(limit=2),
        }


def _tournament_reconciliation_direct(limit: int, queue_limit: int, batch_limit: int) -> dict[str, Any]:
    app = importlib.import_module("stock_suite_app")
    audit_fn = getattr(app, "ai_tournament_reconciliation_audit")
    result = audit_fn(limit=limit, queue_limit=queue_limit, batch_limit=batch_limit)
    if isinstance(result, dict):
        result["served_by"] = "mcp-direct-stock-suite-app"
        result["http_bypassed"] = True
    return result


def _tournament_reconciliation_http_or_direct(limit: int, queue_limit: int, batch_limit: int) -> dict[str, Any]:
    params = {"limit": limit, "queue_limit": queue_limit, "batch_limit": batch_limit}
    try:
        return _tournament_reconciliation_direct(limit, queue_limit, batch_limit)
    except Exception as direct_exc:
        direct_error = {"error": str(direct_exc), "traceback": traceback.format_exc(limit=2)}
    upstream = _http_json("GET", "/api/ai-tournament/reconciliation-audit", params)
    if isinstance(upstream, dict):
        upstream.setdefault("served_by", "app-http")
        upstream.setdefault("mcp_direct_app_error", direct_error)
        return upstream
    return {"ok": False, "served_by": "app-http", "upstream": upstream, "mcp_direct_app_error": direct_error}


REDACTED = "[MCP-REDACTED]"
REDACTED_MONEY = "[MCP-MONEY-REDACTED]"

SENSITIVE_KEY_PARTS = (
    "account_no",
    "account_number",
    "account_masked",
    "acc_no",
    "acct",
    "cano",
    "acnt",
    "api_key",
    "app_key",
    "appkey",
    "app_secret",
    "appsecret",
    "secret",
    "password",
    "passwd",
    "authorization",
    "auth_header",
    "token",
    "access_token",
    "refresh_token",
    "approval_token",
    "bot_token",
    "telegram_token",
    "telegram_chat_id",
    "chat_id",
    "ecos_key",
    "fred_key",
    "dart_key",
    "krx_key",
    "kis_key",
)

MONEY_KEY_PARTS = (
    "cash",
    "pnl",
    "available_cash",
    "available_amount",
    "cash_balance",
    "cash_cap",
    "balance",
    "deposit",
    "deposit_cash",
    "equity",
    "withdrawable",
    "buying_power",
    "orderable",
    "total_asset",
    "total_assets",
    "asset_value",
    "portfolio_value",
    "stock_value",
    "market_value",
    "valuation",
    "evaluation_amount",
    "evaluated_amount",
    "eval_amount",
    "realized_pnl",
    "unrealized_pnl",
    "profit_loss",
    "realized_profit",
    "unrealized_profit",
    "purchase_amount",
    "holding_amount",
)

RATIO_KEY_PARTS = (
    "pct",
    "percent",
    "ratio",
    "weight",
    "rate",
    "allocation",
)


def _normalize_key(key: object) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(key or "").lower()).strip("_")


def _mask_text(text: str) -> str:
    if not text:
        return text

    def mask_long_number(match: re.Match[str]) -> str:
        value = match.group(0)
        if len(value) < 8:
            return value
        return f"{value[:2]}***{value[-2:]}"

    def mask_long_token(match: re.Match[str]) -> str:
        value = match.group(0)
        if len(value) < 20:
            return value
        if value.startswith("codexstock_"):
            return value
        return f"{value[:4]}***{value[-4:]}"

    text = re.sub(r"(?<!\d)\d{8,}(?!\d)", mask_long_number, text)
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", mask_long_token, text)
    text = re.sub(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\\s]+", r"C:\\Users\\[redacted]", text)
    return text


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalize_key(key)
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _is_money_key(key: object) -> bool:
    normalized = _normalize_key(key)
    framed = f"_{normalized}_"
    if any(f"_{part}_" in framed for part in RATIO_KEY_PARTS):
        return False
    return any(f"_{part}_" in framed for part in MONEY_KEY_PARTS)


def _is_public_hash_value(key: object, value: object) -> bool:
    normalized = _normalize_key(key)
    if "hash" not in normalized or _is_sensitive_key(key):
        return False
    return bool(re.fullmatch(r"[A-Fa-f0-9]{32,128}", str(value or "")))


def _is_public_diagnostic_code(key: object, value: object) -> bool:
    normalized = _normalize_key(key)
    if _is_sensitive_key(key):
        return False
    diagnostic_keys = {
        "action",
        "blocker",
        "blockers",
        "classification",
        "component",
        "event_type",
        "issue_code",
        "primary_issue",
        "reason_code",
        "report_type",
        "warning",
        "warnings",
        "status",
        "terminal_status",
        "state",
        "severity",
        "status_reason",
        "blocked_reasons",
        "blocked_reason_labels",
        "accepted_sample_blockers",
        "rejected_sample_blockers",
        "rejected_contract_schema_version_blockers",
        "rejected_contract_identity_blockers",
        "rejected_external_identity_blockers",
        "rejected_external_run_id_quality_blockers",
        "rejected_no_live_order_blockers",
        "rejected_snapshot_evidence_blockers",
        "rejected_return_summary_blockers",
        "rejected_fill_ledger_hash_blockers",
        "rejected_evidence_blockers",
        "rejected_pnl_blockers",
        "rejected_threshold_blockers",
        "rejected_threshold_missing_blockers",
        "rejected_cost_profile_blockers",
        "rejected_unit_evidence_blockers",
        "rejected_unit_policy_blockers",
    }
    if normalized not in diagnostic_keys:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_:-]{2,160}", str(value or "")))


def _is_public_identifier_value(key: object, value: object) -> bool:
    normalized = _normalize_key(key)
    if _is_sensitive_key(key):
        return False
    public_identifier_keys = {
        "schema",
        "schema_version",
        "service_schema",
        "store_schema",
        "server_name",
        "server_version",
        "contract_schema_version",
        "source",
        "served_by",
        "handled_by",
        "routed_via",
        "routed_tool",
        "external_runtime_mode",
        "stage2_action",
    }
    if normalized not in public_identifier_keys:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.:-]{2,180}", str(value or "")))


def _is_public_internal_developer_id(key: object, value: object) -> bool:
    """Keep opaque internal-developer record IDs usable across MCP calls.

    These IDs contain no account, order, credential, or money data.  The key
    allow-list and prefix allow-list are deliberately narrow so the exception
    cannot expose similarly shaped trading identifiers.
    """

    normalized = _normalize_key(key)
    if normalized not in {
        "incident_id",
        "report_id",
        "advice_id",
        "event_id",
        "playbook_id",
        "request_id",
        "attempt_id",
        "latest_incident_id",
        "latest_report_id",
        "latest_advice_id",
    }:
        return False
    return bool(
        re.fullmatch(
            r"(?:INC|REP|ADV|EVT|PB|RST|ATT)-[A-Z0-9][A-Z0-9_-]{0,95}",
            str(value or "").upper(),
        )
    )


def _is_public_profile_id(key: object, value: object) -> bool:
    normalized = _normalize_key(key)
    if _is_sensitive_key(key):
        return False
    return normalized.endswith("profile_id") and bool(re.fullmatch(r"[A-Za-z0-9_.:-]{3,160}", str(value or "")))


def _krw_range_label(value: object) -> str:
    try:
        amount = float(str(value).replace(",", ""))
    except Exception:
        return f"{REDACTED_MONEY}: unknown"
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    bands = [
        (0, "0 KRW"),
        (10_000, "<10k KRW"),
        (30_000, "10k-30k KRW"),
        (50_000, "30k-50k KRW"),
        (100_000, "50k-100k KRW"),
        (300_000, "100k-300k KRW"),
        (500_000, "300k-500k KRW"),
        (1_000_000, "500k-1m KRW"),
        (3_000_000, "1m-3m KRW"),
        (5_000_000, "3m-5m KRW"),
        (10_000_000, "5m-10m KRW"),
        (30_000_000, "10m-30m KRW"),
        (50_000_000, "30m-50m KRW"),
        (100_000_000, "50m-100m KRW"),
        (200_000_000, "100m-200m KRW"),
        (500_000_000, "200m-500m KRW"),
        (1_000_000_000, "500m-1b KRW"),
        (float("inf"), ">=1b KRW"),
    ]
    for upper, label in bands:
        if amount <= upper:
            return f"{REDACTED_MONEY}: {sign}{label}"
    return f"{REDACTED_MONEY}: unknown"


def _sanitize_for_mcp(value: Any, key: object = "") -> Any:
    if _normalize_key(key) in {"tool_names", "external_learning_tool_names", "allowed_tools"} and isinstance(value, list):
        return value
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if _is_sensitive_key(raw_key):
                safe[str(raw_key)] = REDACTED
            elif _is_money_key(raw_key):
                safe[str(raw_key)] = (
                    _sanitize_for_mcp(raw_value, raw_key)
                    if isinstance(raw_value, (dict, list, tuple))
                    else raw_value
                    if isinstance(raw_value, bool)
                    else _krw_range_label(raw_value)
                )
            elif isinstance(raw_value, (dict, list, tuple)):
                safe[str(raw_key)] = _sanitize_for_mcp(raw_value, raw_key)
            else:
                safe[str(raw_key)] = _sanitize_for_mcp(raw_value, raw_key)
        return safe
    if isinstance(value, list):
        return [_sanitize_for_mcp(item, key) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_mcp(item, key) for item in value]
    if _is_sensitive_key(key):
        return REDACTED
    if _is_money_key(key):
        if isinstance(value, bool):
            return value
        return _krw_range_label(value)
    if isinstance(value, str):
        if _is_public_hash_value(key, value):
            return value
        if _is_public_diagnostic_code(key, value):
            return value
        if _is_public_internal_developer_id(key, value):
            return value
        if _is_public_identifier_value(key, value):
            return value
        if _is_public_profile_id(key, value):
            return value
        return _mask_text(value)
    return value


def _compact_list_sample(items: list[Any], limit: int) -> dict[str, Any]:
    return {
        "count": len(items),
        "sample": items[:limit],
        "truncated": max(0, len(items) - limit),
    }


def _compact_for_mcp(value: Any, key: object = "", depth: int = 0) -> Any:
    normalized = _normalize_key(key)
    if depth > 8:
        return "[mcp-truncated-depth]"
    if normalized in {"tool_names", "external_learning_tool_names", "allowed_tools"}:
        return value
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            child_key = _normalize_key(raw_key)
            if child_key in {
                "universe",
                "stock_universe",
                "krx_universe",
                "us_universe",
                "all_symbols",
                "raw",
                "raw_rows",
                "raw_records",
                "ohlcv",
                "bars",
                "candles",
                "minute_bars",
                "prices",
                "price_rows",
            }:
                if isinstance(raw_value, list):
                    compact[str(raw_key)] = _compact_list_sample(raw_value, 8)
                elif isinstance(raw_value, dict):
                    compact[str(raw_key)] = {
                        "count": len(raw_value),
                        "sample_keys": list(raw_value.keys())[:12],
                        "truncated": max(0, len(raw_value) - 12),
                    }
                elif isinstance(raw_value, str) and len(raw_value) > 1200:
                    compact[str(raw_key)] = raw_value[:1200] + "\n...\n[mcp-truncated-large-string]"
                else:
                    compact[str(raw_key)] = raw_value
                continue
            compact[str(raw_key)] = _compact_for_mcp(raw_value, raw_key, depth + 1)
        return compact
    if isinstance(value, list):
        limit = 30
        if any(part in normalized for part in ("candidate", "decision", "trade", "meeting", "insight", "package", "source")):
            limit = 20
        if len(value) > limit:
            return {
                "count": len(value),
                "items": [_compact_for_mcp(item, key, depth + 1) for item in value[:limit]],
                "truncated": len(value) - limit,
            }
        return [_compact_for_mcp(item, key, depth + 1) for item in value]
    if isinstance(value, str) and len(value) > 5000:
        return value[:5000] + "\n...\n[mcp-truncated-large-string]"
    return value


def _tool_result(data: Any, max_chars: int = DEFAULT_TOOL_RESULT_MAX_CHARS, is_error: bool = False) -> dict[str, Any]:
    safe_data = _sanitize_for_mcp(_compact_for_mcp(data))
    text = json.dumps(safe_data, ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        original_chars = len(text)
        preview_budget = max(500, max_chars - 1400)
        envelope: dict[str, Any] = {
            "ok": bool(isinstance(safe_data, dict) and safe_data.get("ok", True)),
            "truncated": True,
            "original_chars": original_chars,
            "max_chars": max_chars,
            "preview_chars": min(preview_budget, original_chars),
            "preview_json_prefix": text[:preview_budget],
            "hint": "Response was too large, so MCP returned a valid JSON truncation envelope. Retry with smaller limit/queue_limit/batch_limit or use a focused tool such as codexstock_stage2_handoff_queue.",
        }
        if isinstance(safe_data, dict):
            for key in ("source", "served_by", "status", "summary", "mcp_server_manifest"):
                if key in safe_data:
                    envelope[key] = safe_data.get(key)
        text = json.dumps(envelope, ensure_ascii=False, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": bool(is_error)}


def _live_trade_explanation_tool_result(data: Any, max_chars: int) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    safe_trades: list[dict[str, Any]] = []
    for row in payload.get("trades", []) if isinstance(payload.get("trades"), list) else []:
        if not isinstance(row, dict):
            continue
        entry = row.get("entry", {}) if isinstance(row.get("entry"), dict) else {}
        exit_row = row.get("exit", {}) if isinstance(row.get("exit"), dict) else {}
        performance = row.get("performance", {}) if isinstance(row.get("performance"), dict) else {}
        entry_timing_basis = [
            str(item)
            for item in (entry.get("timing_basis") or [])
            if "점수 100" not in str(item) and not str(item).startswith("1주 ")
        ]
        safe_trades.append(
            {
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "quantity": row.get("quantity"),
                "entry": {
                    "submitted_at": entry.get("submitted_at"),
                    "price": entry.get("price"),
                    "order_no": entry.get("order_no"),
                    "timing_basis": entry_timing_basis,
                },
                "exit": {key: exit_row.get(key) for key in ("submitted_at", "price", "order_no", "timing_basis")},
                "holding_seconds": row.get("holding_seconds"),
                "holding_minutes": row.get("holding_minutes"),
                "interpretation_warnings": row.get("interpretation_warnings", []),
                "entry_timing_risks": row.get("entry_timing_risks", []),
                "authoritative_fields": row.get("authoritative_fields", {}),
                "decision_evidence_quality": row.get("decision_evidence_quality", {}),
                "post_trade_review": row.get("post_trade_review", {}),
                "performance": {
                    key: performance.get(key)
                    for key in ("gross_pnl", "gross_pnl_pct", "estimated_cost", "estimated_net_pnl", "estimated_net_pnl_pct")
                },
                "evidence": row.get("evidence", {}),
                "plain_summary": row.get("plain_summary"),
            }
        )
    reconciliation = payload.get("net_pnl_reconciliation", {}) if isinstance(payload.get("net_pnl_reconciliation"), dict) else {}
    safe_payload = {
        "ok": bool(payload.get("ok", True)),
        "date": payload.get("date"),
        "schema": payload.get("schema"),
        "count": len(safe_trades),
        "trades": safe_trades,
        "net_pnl_reconciliation": {
            key: reconciliation.get(key)
            for key in ("status", "fully_closed", "gross_realized_pnl", "estimated_cost_total", "estimated_net_pnl")
        },
        "source_contract": payload.get("source_contract", {}),
        "questions_supported": payload.get("questions_supported", []),
        "safety": "Read-only exact trade explanation. Account balances, credentials, and raw logs are excluded.",
    }
    text = json.dumps(_compact_for_mcp(safe_payload), ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        text = json.dumps({**safe_payload, "trades": safe_trades[:3], "truncated": True}, ensure_ascii=False, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _live_order_blackbox_tool_result(data: Any, max_chars: int) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    safe_records: list[dict[str, Any]] = []
    for row in payload.get("records", []) if isinstance(payload.get("records"), list) else []:
        if not isinstance(row, dict):
            continue
        safe_records.append(
            {
                key: row.get(key)
                for key in (
                    "id", "created_at", "symbol", "name", "side", "side_label", "status",
                    "quantity", "price", "order_no", "reason", "selection_reason", "quality",
                    "candidate_summary", "candidate_score", "candidate_strategy", "alternative_count",
                    "performance", "decision_blackbox_available", "blackbox_provenance", "blackbox_completeness", "decision_blackbox",
                )
            }
        )
    safe_payload = {
        "ok": bool(payload.get("ok", True)),
        "created_at": payload.get("created_at"),
        "schema": "codexstock_live_order_blackbox_mcp_v1",
        "counts": payload.get("counts", {}),
        "headline": payload.get("headline"),
        "records": safe_records,
        "safety": "Read-only decision blackbox. Account data, credentials, ticket metadata, and unrestricted context snapshots are excluded.",
    }
    text = json.dumps(_compact_for_mcp(safe_payload), ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        safe_payload["records"] = safe_records[:2]
        safe_payload["truncated"] = True
        text = json.dumps(safe_payload, ensure_ascii=False, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _mcp_tool_category(name: str) -> str:
    if name in RESEARCH_TOOL_NAMES:
        return "research_forge"
    if name in {
        "codexstock_internal_developer_status",
        "codexstock_internal_developer_component_status",
        "codexstock_internal_developer_list_incidents",
        "codexstock_internal_developer_get_incident",
        "codexstock_internal_developer_latest_report",
        "codexstock_internal_developer_brief",
        "codexstock_internal_developer_activity",
        "codexstock_internal_developer_readonly_diagnostics",
        "codexstock_submit_developer_advice",
    }:
        return "internal_developer"
    if name in {
        "codexstock_mcp_manifest",
        "codexstock_status",
        "codexstock_scorecard",
        "codexstock_runtime_deployment_freshness",
    }:
        return "status_manifest"
    if name in {
        "codexstock_staff_status",
        "codexstock_staff_meetings",
        "codexstock_learning_insights",
        "codexstock_staff_long_horizon_audit",
        "codexstock_staff_learning_effect_audit",
        "codexstock_staff_learning_counterfactual_schedule",
        "codexstock_staff_learning_counterfactual_runtime",
        "codexstock_staff_learning_counterfactual_preregistration",
        "codexstock_staff_indicator_catalog",
    }:
        return "staff_learning"
    if name in {
        "codexstock_live_pilot_plan",
        "codexstock_live_candidate_decisions",
        "codexstock_today_trades",
        "codexstock_live_reconciliation_audit",
    }:
        return "live_trade_safety"
    if name in {
        "codexstock_radar",
        "codexstock_screener",
        "codexstock_sector_news",
        "codexstock_sector_committee",
        "codexstock_market_context_snapshot",
        "codexstock_market_news_evidence",
        "codexstock_intraday_market_pulse",
    }:
        return "market_research"
    if name in {
        "codexstock_jsonl_compaction_dry_run",
        "codexstock_sqlite_storage_audit",
        "codexstock_runtime_data_separation_audit",
    }:
        return "storage_runtime"
    if name in {
        "codexstock_knowledge_curator_status",
        "codexstock_knowledge_search",
        "codexstock_knowledge_engine_plan",
    }:
        return "knowledge_management"
    if (
        name.startswith("codexstock_external_")
        or "_external_" in name
        or name
        in {
            "codexstock_import_training_package",
            "codexstock_validate_external_package",
            "codexstock_assign_training_mission",
            "codexstock_promote_external_knowledge",
            "codexstock_reject_external_knowledge",
        }
    ):
        return "external_engine_learning"
    if name in {
        "codexstock_feature_health",
        "codexstock_score_saturation_audit",
        "codexstock_candidate_lane_audit",
        "codexstock_learning_memory_audit",
        "codexstock_sector_concentration_audit",
        "codexstock_quote_unit_audit",
        "codexstock_common_quote_snapshot",
        "codexstock_position_unit_audit",
        "codexstock_tournament_standings",
        "codexstock_tournament_champion_audit",
        "codexstock_tournament_reconciliation_audit",
        "codexstock_historical_replay_completion_audit",
        "codexstock_historical_market_data_cache_status",
        "codexstock_promotion_candidate_evidence_audit",
        "codexstock_promotion_candidate_discovery_audit",
        "codexstock_promotion_forward_observation_audit",
        "codexstock_promotion_rehearsal_evidence_audit",
        "codexstock_monte_carlo_evidence_audit",
        "codexstock_staff_learning_decision_reflection_audit",
        "codexstock_weakness_completion_audit",
        "codexstock_stage2_handoff_queue",
        "codexstock_stage2_result_gate",
    }:
        return "quality_reconciliation_audit"
    if name == "codexstock_ask_agent":
        return "agent_router"
    return "other"


def _mcp_client_exposure_receipt_path() -> Path:
    return active_data_root(REPO_ROOT) / "mcp" / "client_exposure_receipt.json"


def _mcp_stale_client_exposure_receipt_path() -> Path:
    return active_data_root(REPO_ROOT) / "mcp" / "client_exposure_receipt.stale.json"


def _read_mcp_client_exposure_receipt() -> dict[str, Any]:
    path = _mcp_client_exposure_receipt_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("schema") != MCP_CLIENT_EXPOSURE_RECEIPT_SCHEMA:
        return {}
    names = payload.get("client_tool_names")
    if not isinstance(names, list):
        return {}
    payload["client_tool_names"] = sorted(
        {str(value).strip() for value in names if str(value).strip()}
    )
    aliases = payload.get("client_tool_aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    normalized_aliases = {
        str(alias).strip(): str(canonical).strip()
        for alias, canonical in aliases.items()
        if str(alias).strip() and str(canonical).strip()
    }
    if any(alias not in payload["client_tool_names"] for alias in normalized_aliases):
        return {}
    payload["client_tool_aliases"] = dict(sorted(normalized_aliases.items()))
    resolved_names = sorted(
        {
            normalized_aliases.get(name, name)
            for name in payload["client_tool_names"]
        }
    )
    if len(resolved_names) != len(payload["client_tool_names"]):
        return {}
    payload["client_resolved_tool_names"] = resolved_names
    return payload


def _read_mcp_stale_client_exposure_receipt() -> dict[str, Any]:
    path = _mcp_stale_client_exposure_receipt_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("schema") != MCP_CLIENT_EXPOSURE_RECEIPT_SCHEMA:
        return {}
    names = payload.get("client_tool_names")
    if not isinstance(names, list):
        return {}
    payload["client_tool_names"] = sorted(
        {str(value).strip() for value in names if str(value).strip()}
    )
    aliases = payload.get("client_tool_aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    normalized_aliases = {
        str(alias).strip(): str(canonical).strip()
        for alias, canonical in aliases.items()
        if str(alias).strip() and str(canonical).strip()
    }
    if any(alias not in payload["client_tool_names"] for alias in normalized_aliases):
        return {}
    payload["client_tool_aliases"] = dict(sorted(normalized_aliases.items()))
    resolved_names = sorted(
        {
            normalized_aliases.get(name, name)
            for name in payload["client_tool_names"]
        }
    )
    if len(resolved_names) != len(payload["client_tool_names"]):
        return {}
    payload["client_resolved_tool_names"] = resolved_names
    return payload


def _quarantine_mcp_client_exposure_receipt(
    receipt: dict[str, Any],
    *,
    server_schema_sha256: str,
    reason: str,
) -> dict[str, Any]:
    if not receipt:
        return {}
    quarantined = dict(receipt)
    quarantined.update(
        {
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "quarantine_reason": reason,
            "current_server_schema_sha256": server_schema_sha256,
            "active_cache": False,
            "refresh_required": True,
        }
    )
    stale_path = _mcp_stale_client_exposure_receipt_path()
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = stale_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(quarantined, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(stale_path)
    try:
        _mcp_client_exposure_receipt_path().unlink()
    except FileNotFoundError:
        pass
    return quarantined


def _record_mcp_client_exposure(arguments: dict[str, Any]) -> dict[str, Any] | None:
    raw_names = arguments.get("client_tool_names")
    if not isinstance(raw_names, list):
        return None
    names: set[str] = set()
    aliases: dict[str, str] = {}
    for raw_value in raw_names:
        value = str(raw_value).strip()
        if not value:
            continue
        if "=>" in value:
            alias, canonical = (part.strip() for part in value.split("=>", 1))
            if not alias or not canonical:
                raise ValueError("client tool aliases must use 'visible_name=>server_name'")
            if len(alias) > 256 or len(canonical) > 256:
                raise ValueError("client tool alias names cannot exceed 256 characters")
            previous = aliases.get(alias)
            if previous and previous != canonical:
                raise ValueError(f"conflicting client tool alias: {alias}")
            aliases[alias] = canonical
            names.add(alias)
        else:
            if len(value) > 256:
                raise ValueError("client tool names cannot exceed 256 characters")
            names.add(value)
    names = sorted(names)
    if len(names) > 500:
        raise ValueError("client_tool_names cannot contain more than 500 tools")
    server_names = {str(tool.get("name") or "").strip() for tool in TOOLS}
    unknown_alias_targets = sorted(set(aliases.values()) - server_names)
    if unknown_alias_targets:
        raise ValueError(
            "client tool alias target is not published by this server: "
            + ", ".join(unknown_alias_targets[:5])
        )
    resolved_names = sorted({aliases.get(name, name) for name in names})
    if len(resolved_names) != len(names):
        raise ValueError("client tool aliases collapse multiple visible tools into one server tool")
    schema_sha256 = str(arguments.get("client_schema_sha256") or "").strip().lower()
    if schema_sha256 and not re.fullmatch(r"[0-9a-f]{64}", schema_sha256):
        raise ValueError("client_schema_sha256 must be a 64-character SHA-256 hex digest")
    observed_at = str(arguments.get("client_observed_at") or "").strip()
    if not observed_at:
        raise ValueError("client_observed_at is required when reporting client_tool_names")
    try:
        parsed_observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("client_observed_at must be an ISO-8601 timestamp") from exc
    if parsed_observed_at.tzinfo is None:
        raise ValueError("client_observed_at must include a timezone offset")
    received_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema": MCP_CLIENT_EXPOSURE_RECEIPT_SCHEMA,
        "client_name": str(arguments.get("client_name") or "unspecified-client").strip()
        or "unspecified-client",
        "client_tool_names": names,
        "client_tool_count": len(names),
        "client_tool_aliases": dict(sorted(aliases.items())),
        "client_tool_alias_count": len(aliases),
        "client_resolved_tool_names": resolved_names,
        "client_tool_names_sha256": hashlib.sha256(
            json.dumps(names, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "client_resolved_tool_names_sha256": hashlib.sha256(
            json.dumps(resolved_names, ensure_ascii=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest(),
        "client_schema_sha256": schema_sha256 or None,
        "client_observed_at": parsed_observed_at.isoformat(),
        "received_at": received_at,
    }
    path = _mcp_client_exposure_receipt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return payload


def _mcp_runtime_source_freshness() -> dict[str, Any]:
    """Report whether this MCP process is executing the current source file."""
    try:
        current_stat = MCP_SOURCE_PATH.stat()
        current_stat_key = (current_stat.st_mtime_ns, current_stat.st_size)
        if current_stat_key == MCP_SOURCE_LOADED_STAT:
            current_sha256 = MCP_SOURCE_LOADED_SHA256
        else:
            current_sha256 = hashlib.sha256(MCP_SOURCE_PATH.read_bytes()).hexdigest()
        restart_required = bool(
            not MCP_SOURCE_LOADED_SHA256
            or current_sha256 != MCP_SOURCE_LOADED_SHA256
        )
        return {
            "ok": not restart_required,
            "status": "restart_required" if restart_required else "current",
            "process_started_at": MCP_PROCESS_STARTED_AT,
            "source_path": str(MCP_SOURCE_PATH),
            "loaded_source_sha256": MCP_SOURCE_LOADED_SHA256 or None,
            "current_source_sha256": current_sha256 or None,
            "source_changed_since_process_start": restart_required,
            "restart_required": restart_required,
            "read_only": True,
            "live_order_allowed": False,
        }
    except OSError as exc:
        return {
            "ok": False,
            "status": "source_unavailable",
            "process_started_at": MCP_PROCESS_STARTED_AT,
            "source_path": str(MCP_SOURCE_PATH),
            "error": f"{type(exc).__name__}: {exc}",
            "source_changed_since_process_start": None,
            "restart_required": None,
            "read_only": True,
            "live_order_allowed": False,
        }


def _mcp_manifest() -> dict[str, Any]:
    names = [str(tool.get("name", "")) for tool in TOOLS]
    schema_material = [
        {
            "name": str(tool.get("name", "")),
            "description": str(tool.get("description", "")),
            "inputSchema": tool.get("inputSchema", {}),
        }
        for tool in TOOLS
    ]
    server_schema_sha256 = hashlib.sha256(
        json.dumps(
            schema_material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    receipt = _read_mcp_client_exposure_receipt()
    quarantined_receipt: dict[str, Any] = (
        {} if receipt else _read_mcp_stale_client_exposure_receipt()
    )
    if receipt:
        receipt_names = set(
            receipt.get("client_resolved_tool_names")
            or receipt.get("client_tool_names")
            or []
        )
        receipt_schema_sha256 = str(receipt.get("client_schema_sha256") or "").lower()
        receipt_name_set_matches = receipt_names == set(names)
        receipt_schema_matches = receipt_schema_sha256 == server_schema_sha256
        if not receipt_name_set_matches or (
            receipt_schema_sha256 and not receipt_schema_matches
        ):
            reasons = []
            if not receipt_name_set_matches:
                reasons.append("tool_name_set_mismatch")
            if receipt_schema_sha256 and not receipt_schema_matches:
                reasons.append("schema_hash_mismatch")
            quarantined_receipt = _quarantine_mcp_client_exposure_receipt(
                receipt,
                server_schema_sha256=server_schema_sha256,
                reason="+".join(reasons),
            )
            receipt = {}
    exposed_raw = str(os.environ.get("CODEXSTOCK_MCP_EXPOSED_TOOL_NAMES", "") or "").strip()
    exposed_schema_sha256 = str(
        os.environ.get("CODEXSTOCK_MCP_EXPOSED_SCHEMA_SHA256", "") or ""
    ).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", exposed_schema_sha256):
        exposed_schema_sha256 = ""
    last_schema_refresh_at = str(
        os.environ.get("CODEXSTOCK_MCP_LAST_SCHEMA_REFRESH_AT", "") or ""
    ).strip()
    exposed_names: list[str] | None = None
    resolved_exposed_names: list[str] | None = None
    exposed_aliases: dict[str, str] = {}
    observation_source = "not_reported_by_client"
    if exposed_raw:
        try:
            parsed_exposed = json.loads(exposed_raw)
        except json.JSONDecodeError:
            parsed_exposed = [value.strip() for value in exposed_raw.split(",") if value.strip()]
        if isinstance(parsed_exposed, list):
            exposed_names = sorted({str(value) for value in parsed_exposed if str(value)})
            resolved_exposed_names = list(exposed_names)
            observation_source = "CODEXSTOCK_MCP_EXPOSED_TOOL_NAMES"
    elif receipt:
        exposed_names = list(receipt.get("client_tool_names") or [])
        resolved_exposed_names = list(
            receipt.get("client_resolved_tool_names") or exposed_names
        )
        exposed_aliases = dict(receipt.get("client_tool_aliases") or {})
        exposed_schema_sha256 = str(receipt.get("client_schema_sha256") or "").lower()
        last_schema_refresh_at = str(receipt.get("client_observed_at") or "")
        observation_source = "persistent_client_receipt"
    elif quarantined_receipt:
        observation_source = "quarantined_stale_client_receipt"
        last_schema_refresh_at = str(quarantined_receipt.get("client_observed_at") or "")
    server_name_set = set(names)
    exposed_name_set = set(resolved_exposed_names or exposed_names or [])
    names_match = exposed_name_set == server_name_set if exposed_names is not None else None
    hash_match = (
        exposed_schema_sha256 == server_schema_sha256
        if exposed_schema_sha256
        else None
    )
    if names_match is None and hash_match is None:
        exposure_status = "CLIENT_EXPOSURE_UNOBSERVED"
        schema_match: bool | None = None
    elif names_match is True and hash_match is None:
        exposure_status = "NAMES_MATCHED_SCHEMA_UNVERIFIED"
        schema_match = None
    elif names_match is True and hash_match is True:
        exposure_status = "MATCHED"
        schema_match = True
    else:
        exposure_status = "MISMATCH"
        schema_match = False
    active_quarantined_receipt = quarantined_receipt if exposed_names is None else {}
    stale_name_set = set(
        active_quarantined_receipt.get("client_resolved_tool_names")
        or active_quarantined_receipt.get("client_tool_names")
        or []
    )
    # A quarantined receipt is historical context, never current client
    # exposure evidence. Only an active receipt or explicit environment
    # observation may produce current missing/core coverage counts.
    observed_name_set = exposed_name_set
    has_observed_names = exposed_names is not None
    missing_on_client = sorted(server_name_set - observed_name_set) if has_observed_names else []
    unknown_on_client = sorted(observed_name_set - server_name_set) if has_observed_names else []
    declared_core_name_set = set(MCP_CORE_TOOL_NAMES)
    undeclared_core_tools = sorted(declared_core_name_set - server_name_set)
    core_name_set = declared_core_name_set & server_name_set
    core_exposed_names = sorted(core_name_set & observed_name_set) if has_observed_names else []
    core_missing_on_client = sorted(core_name_set - observed_name_set) if has_observed_names else []
    core_coverage_pct = (
        round(len(core_exposed_names) / len(core_name_set) * 100.0, 2)
        if core_name_set and has_observed_names
        else None
    )
    if not has_observed_names:
        core_exposure_status = "CLIENT_EXPOSURE_UNOBSERVED"
    elif undeclared_core_tools:
        core_exposure_status = "SERVER_CORE_DECLARATION_INVALID"
    elif core_missing_on_client:
        core_exposure_status = "CORE_MISMATCH"
    else:
        core_exposure_status = "CORE_MATCHED"
    server_publish_complete = bool(
        names
        and len(names) == len(schema_material)
        and len(server_name_set) == len(names)
        and all(names)
    )
    if exposure_status == "MATCHED":
        client_cache_status = "CURRENT"
        client_schema_refresh_required: bool | None = False
        availability_truth = "server_published_all_and_client_schema_matched"
    elif exposure_status == "MISMATCH":
        client_cache_status = "REFRESH_REQUIRED"
        client_schema_refresh_required = True
        availability_truth = "server_published_all_client_schema_refresh_required"
    elif exposure_status == "NAMES_MATCHED_SCHEMA_UNVERIFIED":
        client_cache_status = "SCHEMA_HASH_VERIFICATION_REQUIRED"
        client_schema_refresh_required = None
        availability_truth = "server_published_all_client_schema_hash_unverified"
    else:
        client_cache_status = "OBSERVATION_REQUIRED"
        client_schema_refresh_required = None
        availability_truth = "server_published_all_client_observation_pending"
    if exposure_status == "MATCHED":
        reconciliation_next_action = "NONE"
    elif exposure_status == "NAMES_MATCHED_SCHEMA_UNVERIFIED":
        reconciliation_next_action = "RESUBMIT_RECEIPT_WITH_SCHEMA_HASH"
    elif exposure_status == "MISMATCH":
        reconciliation_next_action = "REFRESH_CONNECTOR_SCHEMA_AND_RESUBMIT_RECEIPT"
    else:
        reconciliation_next_action = "REPORT_CLIENT_TOOL_SURFACE"
    exposure = {
        "status": exposure_status,
        "sync_status": exposure_status,
        "server_publish_status": (
            "ALL_SERVER_TOOLS_PUBLISHED" if server_publish_complete else "SERVER_PUBLICATION_INCOMPLETE"
        ),
        "server_publish_complete": server_publish_complete,
        "server_side_filter_active": False,
        "server_side_hidden_tool_count": 0,
        "server_side_hidden_tool_names": [],
        "server_published_tool_count": len(names),
        "server_tool_count": len(names),
        "exposed_tool_count": len(exposed_names) if exposed_names is not None else None,
        "client_exposed_tool_count": len(exposed_names) if exposed_names is not None else None,
        "client_cached_tool_count": len(exposed_names) if exposed_names is not None else None,
        "last_observed_stale_tool_count": (
            int(active_quarantined_receipt.get("client_tool_count") or len(stale_name_set))
            if active_quarantined_receipt
            else None
        ),
        "stale_observation_quarantined": bool(active_quarantined_receipt),
        "client_cache_status": client_cache_status,
        "client_schema_refresh_required": client_schema_refresh_required,
        "client_observation_required": bool(
            exposure_status == "CLIENT_EXPOSURE_UNOBSERVED" or active_quarantined_receipt
        ),
        "availability_truth": availability_truth,
        "schema_match": schema_match,
        "tool_name_set_match": names_match,
        "schema_hash_match": hash_match,
        "server_manifest_hash": server_schema_sha256,
        "server_schema_sha256": server_schema_sha256,
        "exposed_schema_hash": exposed_schema_sha256 or None,
        "last_schema_refresh_at": last_schema_refresh_at or None,
        "client_name": (
            receipt.get("client_name")
            if observation_source == "persistent_client_receipt"
            else active_quarantined_receipt.get("client_name")
            if active_quarantined_receipt
            else None
        ),
        "client_observed_at": (
            receipt.get("client_observed_at")
            if observation_source == "persistent_client_receipt"
            else active_quarantined_receipt.get("client_observed_at")
            if active_quarantined_receipt
            else last_schema_refresh_at or None
        ),
        "receipt_received_at": (
            receipt.get("received_at")
            if observation_source == "persistent_client_receipt"
            else active_quarantined_receipt.get("received_at")
            if active_quarantined_receipt
            else None
        ),
        "client_tool_names_sha256": (
            receipt.get("client_tool_names_sha256")
            if observation_source == "persistent_client_receipt"
            else active_quarantined_receipt.get("client_tool_names_sha256")
            if active_quarantined_receipt
            else None
        ),
        "client_resolved_tool_names_sha256": (
            receipt.get("client_resolved_tool_names_sha256")
            if observation_source == "persistent_client_receipt"
            else active_quarantined_receipt.get("client_resolved_tool_names_sha256")
            if active_quarantined_receipt
            else None
        ),
        "client_tool_alias_count": len(exposed_aliases),
        "client_tool_aliases_applied": bool(exposed_aliases),
        "evidence_level": (
            "full_name_and_schema_hash"
            if exposure_status == "MATCHED"
            else "tool_names_only"
            if exposure_status == "NAMES_MATCHED_SCHEMA_UNVERIFIED"
            else "mismatch"
            if exposure_status == "MISMATCH"
            else "none"
        ),
        "missing_on_client": missing_on_client,
        "missing_on_client_count": len(missing_on_client),
        "client_cache_missing_tool_names": missing_on_client,
        "unknown_on_client": unknown_on_client,
        "unknown_on_client_count": len(unknown_on_client),
        "filtered_tool_names": missing_on_client,
        "stale_tool_names": unknown_on_client,
        "core_exposure_status": core_exposure_status,
        "core_server_tool_count": len(core_name_set),
        "core_client_exposed_tool_count": (
            len(core_exposed_names) if has_observed_names else None
        ),
        "core_coverage_pct": core_coverage_pct,
        "core_tool_name_set_match": (
            not core_missing_on_client and not undeclared_core_tools
            if has_observed_names
            else None
        ),
        "core_missing_on_client": core_missing_on_client,
        "core_missing_on_client_count": len(core_missing_on_client),
        "undeclared_core_tools": undeclared_core_tools,
        "undeclared_core_tool_count": len(undeclared_core_tools),
        "reconciliation": {
            "schema": "codexstock.mcp-exposure-reconciliation.v3",
            "full_surface_status": exposure_status,
            "core_surface_status": core_exposure_status,
            "server_schema_sha256": server_schema_sha256,
            "client_schema_sha256": exposed_schema_sha256 or None,
            "full_server_tool_count": len(names),
            "full_client_tool_count": len(observed_name_set) if has_observed_names else None,
            "full_missing_tool_count": len(missing_on_client),
            "core_server_tool_count": len(core_name_set),
            "core_client_tool_count": len(core_exposed_names) if has_observed_names else None,
            "core_missing_tool_count": len(core_missing_on_client),
            "next_action": reconciliation_next_action,
            "exact_match_requires_names_and_schema_hash": True,
            "connector_name_aliases_supported": True,
            "connector_name_alias_count": len(exposed_aliases),
            "automatically_reconciled_on_manifest_call": True,
        },
        "observation_source": observation_source,
        "receipt_path": str(_mcp_client_exposure_receipt_path()),
        "stale_receipt_path": (
            str(_mcp_stale_client_exposure_receipt_path())
            if active_quarantined_receipt
            else None
        ),
        "human_status": (
            f"코덱스스톡 서버는 {len(names)}개 기능을 모두 게시했습니다. "
            + (
                "ChatGPT 연결기 스키마도 일치합니다."
                if exposure_status == "MATCHED"
                else (
                    f"과거 {int(active_quarantined_receipt.get('client_tool_count') or len(stale_name_set))}개 "
                    "관측 기록은 현재 스키마와 달라 격리했으며, 최신 연결기 재관측이 필요합니다."
                )
                if active_quarantined_receipt
                else f"ChatGPT 연결기 캐시는 {len(exposed_names)}개이며 재동기화가 필요합니다."
                if exposure_status == "MISMATCH" and exposed_names is not None
                else "ChatGPT 연결기에서 전체 기능 목록과 스키마 해시를 다시 확인해야 합니다."
            )
        ),
    }
    categories: dict[str, list[str]] = {}
    for name in names:
        categories.setdefault(_mcp_tool_category(name), []).append(name)
    external_names = [
        name
        for name in names
        if (
            name.startswith("codexstock_external_")
            or "_external_" in name
            or name
            in {
                "codexstock_import_training_package",
                "codexstock_validate_external_package",
                "codexstock_assign_training_mission",
            }
        )
    ]
    runtime_source = _mcp_runtime_source_freshness()
    return {
        "server_name": SERVER_NAME,
        "server_version": SERVER_VERSION,
        "base_url": BASE_URL,
        "runtime_source": runtime_source,
        "tool_count": len(names),
        "tool_names": names,
        "tool_category_counts": {key: len(value) for key, value in categories.items()},
        "tool_categories": categories,
        "external_learning_tool_count": len(external_names),
        "external_learning_tool_names": external_names,
        "core_tool_count": len(core_name_set),
        "core_tool_names": sorted(core_name_set),
        "undeclared_core_tools": undeclared_core_tools,
        "server_schema_sha256": server_schema_sha256,
        "client_exposure": exposure,
        "diagnosis_hint": (
            f"The MCP server publishes all {len(names)} tools without a server-side filter. "
            "If ChatGPT shows fewer tools, refresh the ChatGPT connector schema cache."
        ),
        "fallback_hint": (
            "Until ChatGPT refreshes the tool schema, call codexstock_status for this manifest "
            "or codexstock_ask_agent with 'external signal inbox', 'external learning report', "
            "or 'MCP tool list'."
        ),
    }


def _mcp_manifest_summary() -> dict[str, Any]:
    manifest = _mcp_manifest()
    return {
        "server_name": manifest.get("server_name"),
        "server_version": manifest.get("server_version"),
        "base_url": manifest.get("base_url"),
        "tool_count": manifest.get("tool_count"),
        "tool_category_counts": manifest.get("tool_category_counts", {}),
        "external_learning_tool_count": manifest.get("external_learning_tool_count"),
        "server_schema_sha256": manifest.get("server_schema_sha256"),
        "runtime_source": manifest.get("runtime_source", {}),
        "client_exposure": manifest.get("client_exposure", {}),
        "diagnosis_hint": manifest.get("diagnosis_hint"),
        "fallback_hint": manifest.get("fallback_hint"),
        "full_manifest_tool": "codexstock_mcp_manifest",
        "summary_only": True,
    }


def _attach_mcp_manifest(payload: Any) -> Any:
    if isinstance(payload, dict):
        enriched = {"mcp_server_manifest": _mcp_manifest_summary()}
        enriched.update(payload)
        return enriched
    return {"ok": True, "upstream": payload, "mcp_server_manifest": _mcp_manifest_summary()}


def _weakness_completion_audit_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "request_succeeded": False,
            "error": "invalid_weakness_completion_audit_payload",
            "summary_only": True,
        }
    if payload.get("error"):
        compact_error = dict(payload)
        compact_error["request_succeeded"] = False
        compact_error["summary_only"] = True
        return compact_error

    item_rows: list[dict[str, Any]] = []
    for row in payload.get("items", []):
        if not isinstance(row, dict):
            continue
        item_rows.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "implementation_verified": bool(row.get("implementation_verified")),
                "current_evidence_passed": bool(row.get("current_evidence_passed")),
                "status": row.get("status"),
                "blockers": row.get("blockers") or [],
            }
        )

    objective = payload.get("objective_scope") if isinstance(payload.get("objective_scope"), dict) else {}
    track_rows: list[dict[str, Any]] = []
    for row in objective.get("tracks", []):
        if not isinstance(row, dict):
            continue
        detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
        track_rows.append(
            {
                "id": row.get("id"),
                "label": row.get("label"),
                "system_ready": bool(row.get("system_ready")),
                "current_outcome_passed": bool(row.get("current_outcome_passed")),
                "completion_requirement": row.get("completion_requirement"),
                "status": detail.get("status"),
                "progress_label": detail.get("progress_label"),
                "blockers": detail.get("blockers") or [],
            }
        )

    pending_rows: list[dict[str, Any]] = []
    pending_keys = (
        "id",
        "status",
        "next_action",
        "next_candidate_start_date",
        "minimum_candidate_end_date",
        "next_eligible_date",
        "days_until_next_eligible",
        "official_blocker",
        "confidence_gate_blockers",
        "future_counterfactual_state",
        "preregistration_status",
        "preregistration_contract_remaining_triplet_count",
        "due_preregistration_status",
        "operator_message",
    )
    for row in payload.get("pending_evidence_summary", []):
        if isinstance(row, dict):
            pending_rows.append({key: row.get(key) for key in pending_keys if key in row})

    technical = payload.get("technical_review") if isinstance(payload.get("technical_review"), dict) else {}
    return {
        "ok": bool(payload.get("ok")),
        "request_succeeded": True,
        "schema": payload.get("schema"),
        "evidence_contract_version": payload.get("evidence_contract_version"),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
        "items": item_rows,
        "objective_scope": {
            "track_count": objective.get("track_count"),
            "system_ready_count": objective.get("system_ready_count"),
            "system_progress_pct": objective.get("system_progress_pct"),
            "current_outcome_passed_count": objective.get("current_outcome_passed_count"),
            "current_outcome_progress_pct": objective.get("current_outcome_progress_pct"),
            "implementation_ready": objective.get("implementation_ready"),
            "required_outcomes_ready": objective.get("required_outcomes_ready"),
            "tracks": track_rows,
        },
        "technical_review": {
            "status": technical.get("status"),
            "summary": technical.get("summary") if isinstance(technical.get("summary"), dict) else {},
        },
        "pending_evidence_summary": pending_rows,
        "pending_evidence_operator_messages": payload.get("pending_evidence_operator_messages") or [],
        "next_best_actions": payload.get("next_best_actions") or [],
        "collector_errors": payload.get("collector_errors") if isinstance(payload.get("collector_errors"), dict) else {},
        "official_completion_claim_allowed": bool(payload.get("official_completion_claim_allowed")),
        "unverified_result_affects_score": bool(payload.get("unverified_result_affects_score")),
        "unverified_result_affects_live_candidate": bool(payload.get("unverified_result_affects_live_candidate")),
        "live_order_allowed": False,
        "safety": payload.get("safety"),
        "cache": {
            "cached": bool(payload.get("cached")),
            "stale": bool(payload.get("stale")),
            "refreshing": bool(payload.get("refreshing")),
            "refresh_requested": bool(payload.get("refresh_requested")),
            "cache_age_seconds": payload.get("cache_age_seconds"),
            "cache_source": payload.get("cache_source"),
            "status_cache_error": payload.get("status_cache_error"),
            "refresh_timed_out": bool(payload.get("refresh_timed_out")),
        },
        "summary_only": True,
        "full_audit_endpoint": "/api/codexstock/weakness-completion-audit",
    }


def _external_improvement_status_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_improvement_status_payload"}
    if payload.get("ok") is False:
        return dict(payload)
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    state_keys = (
        "schema",
        "cycle_id",
        "status",
        "started_at",
        "finished_at",
        "phase",
        "phase_index",
        "phase_count",
        "progress_pct",
        "symbols",
        "quality_pass_count",
        "contract_pass_count",
        "verified_lesson_count",
        "retraining_task_count",
        "new_retraining_task_count",
        "suppressed_exhausted_task_count",
        "active_retraining_task_count",
        "claimed_retraining_task_count",
        "retraining_usage",
        "strategy_corroborated",
        "candidate_score_delta",
        "strategy_version_recorded",
        "strategy_version_id",
        "strategy_version_state",
        "learning_memory_refreshed",
        "learning_memory_refresh_error",
        "error",
        "live_order_allowed",
        "promotion_allowed",
    )
    lessons: list[dict[str, Any]] = []
    for row in payload.get("latest_verified_lessons", []):
        if not isinstance(row, dict):
            continue
        engine_lessons = []
        for engine_row in row.get("engine_lessons", []):
            if not isinstance(engine_row, dict):
                continue
            engine_lessons.append(
                {
                    "engine_id": engine_row.get("engine_id"),
                    "accepted": engine_row.get("accepted"),
                    "action": engine_row.get("action"),
                    "quality_blockers": engine_row.get("quality_blockers") or [],
                    "contract_errors": engine_row.get("contract_errors") or [],
                }
            )
        lessons.append(
            {
                "created_at": row.get("created_at"),
                "cycle_id": row.get("cycle_id"),
                "engine_count": row.get("engine_count"),
                "contract_pass_count": row.get("contract_pass_count"),
                "quality_pass_count": row.get("quality_pass_count"),
                "strategy_corroborated": row.get("strategy_corroborated"),
                "candidate_score_delta": row.get("candidate_score_delta"),
                "learning_memory_eligible": row.get("learning_memory_eligible"),
                "engine_lessons": engine_lessons,
            }
        )
    def compact_tasks(rows: Any) -> list[dict[str, Any]]:
        return [{
            "task_id": row.get("task_id"),
            "status": row.get("status"),
            "engine_id": row.get("engine_id"),
            "requested_action": row.get("requested_action"),
            "attempt_count": row.get("attempt_count"),
            "max_attempts": row.get("max_attempts"),
            "blocker_summary": row.get("blocker_summary"),
            "contract_errors": row.get("contract_errors") or [],
            "quality_blockers": row.get("quality_blockers") or [],
            "resolution_blockers": row.get("resolution_blockers") or [],
        }
        for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    tasks = compact_tasks(payload.get("latest_retraining_tasks", []))
    active_tasks = compact_tasks(payload.get("active_retraining_tasks", []))
    compact_state = {key: state.get(key) for key in state_keys if key in state}
    compact_state["engine_results"] = [
        {
            "engine_id": row.get("engine_id"),
            "execution_ok": row.get("execution_ok"),
            "quality_gate_passed": row.get("quality_gate_passed"),
            "contract_passed": row.get("contract_passed"),
            "blockers": row.get("blockers") or [],
        }
        for row in state.get("engine_results", [])
        if isinstance(row, dict)
    ]
    compact_state["claimed_retraining_tasks"] = compact_tasks(
        state.get("claimed_retraining_tasks", [])
    )
    resolution = state.get("retraining_resolution") if isinstance(
        state.get("retraining_resolution"), dict
    ) else {}
    resolved_tasks = compact_tasks(resolution.get("resolved", []))
    retry_tasks = compact_tasks(resolution.get("retry_queued", []))
    exhausted_tasks = compact_tasks(resolution.get("exhausted", []))
    outcome_tasks = resolved_tasks + retry_tasks + exhausted_tasks
    # Older long-running backends may expose the immutable queue rows here.
    # The terminal resolution ledger is authoritative for the latest cycle.
    if outcome_tasks:
        tasks = outcome_tasks
    compact_state["retraining_resolution"] = {
        key: resolution.get(key)
        for key in (
            "claimed_count",
            "resolved_count",
            "retry_queued_count",
            "exhausted_count",
            "active_count",
        )
        if key in resolution
    }
    compact_state["retraining_resolution"].update(
        {
            "resolved": resolved_tasks,
            "retry_queued": retry_tasks,
            "exhausted": exhausted_tasks,
        }
    )
    compact_state["vectorbt_retraining_attempts"] = [
        {
            "attempt": row.get("attempt"),
            "fast_window": row.get("fast_window"),
            "slow_window": row.get("slow_window"),
            "quality_gate_passed": row.get("quality_gate_passed"),
        }
        for row in state.get("vectorbt_retraining_attempts", [])
        if isinstance(row, dict)
    ]
    compact_state["qlib_retraining_attempts"] = [
        {
            "attempt": row.get("attempt"),
            "fold_count": row.get("fold_count"),
            "quality_gate_passed": row.get("quality_gate_passed"),
            "learning_eligible": row.get("learning_eligible"),
            "blockers": row.get("blockers") or [],
        }
        for row in state.get("qlib_retraining_attempts", [])
        if isinstance(row, dict)
    ]
    return {
        "ok": True,
        "state": compact_state,
        "thread_alive": bool(payload.get("thread_alive")),
        "heavy_research_lock_active": bool(payload.get("heavy_research_lock_active")),
        "latest_verified_lessons": lessons,
        "latest_retraining_tasks": tasks,
        "active_retraining_tasks": active_tasks,
        "contract": payload.get("contract") if isinstance(payload.get("contract"), dict) else {},
        "live_order_allowed": False,
        "promotion_allowed": False,
        "summary_only": True,
    }


def _knowledge_curator_status_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_knowledge_curator_status_payload"}
    if payload.get("ok") is False:
        return dict(payload)
    scheduler = payload.get("scheduler") if isinstance(payload.get("scheduler"), dict) else {}
    status_cache = payload.get("status_cache") if isinstance(payload.get("status_cache"), dict) else {}
    engine_rows: list[dict[str, Any]] = []
    failed_count = 1 if str(scheduler.get("last_error") or "").strip() else 0
    stale_count = 0
    ready_count = 0
    latest_engine_completed_at = ""
    for row in payload.get("engines", []):
        if not isinstance(row, dict):
            continue
        last_status = str(row.get("last_status") or "")
        if last_status == "failed":
            failed_count += 1
        if bool(row.get("index_stale")):
            stale_count += 1
        if bool(row.get("operational_ready")):
            ready_count += 1
        completed_at = str(row.get("last_completed_at") or "")
        if completed_at > latest_engine_completed_at:
            latest_engine_completed_at = completed_at
        engine_rows.append(
            {
                "engine_id": row.get("engine_id"),
                "readiness": row.get("readiness"),
                "runtime_installed": bool(row.get("runtime_installed")),
                "runtime_probe": row.get("runtime_probe"),
                "runtime_probe_stale": bool(row.get("runtime_probe_stale")),
                "automatic_enabled": bool(row.get("automatic_enabled")),
                "last_status": last_status,
                "last_completed_at": completed_at,
                "coverage_state": row.get("coverage_state"),
                "index_stale": bool(row.get("index_stale")),
                "blockers": row.get("prerequisite_blockers") or [],
            }
        )
    last_indexed_at = str(
        scheduler.get("last_success_at")
        or latest_engine_completed_at
        or ""
    )
    source_freshness_seconds: float | None = None
    if last_indexed_at:
        try:
            parsed = datetime.fromisoformat(last_indexed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            source_freshness_seconds = round(
                max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()),
                1,
            )
        except ValueError:
            source_freshness_seconds = None
    current_phase = str(scheduler.get("current_phase") or "")
    pending = current_phase not in {"", "idle", "sleeping"}
    return {
        "ok": True,
        "schema": "codexstock_knowledge_curator_status_summary_v1",
        "employee": payload.get("employee"),
        "mode": payload.get("mode"),
        "indexed_documents": payload.get("indexed_documents"),
        "indexed_sources": payload.get("indexed_sources"),
        "discoverable_source_count": payload.get("discoverable_source_count"),
        "archive_source_count": payload.get("archive_source_count"),
        "last_indexed_at": last_indexed_at or None,
        "source_freshness_seconds": source_freshness_seconds,
        "pending": pending,
        "failures": failed_count,
        "duplicates": None,
        "duplicates_available": False,
        "scheduler": {
            "running": bool(scheduler.get("running")),
            "thread_alive": bool(scheduler.get("thread_alive")),
            "current_phase": current_phase or None,
            "current_engine": scheduler.get("current_engine") or None,
            "last_success_at": scheduler.get("last_success_at") or None,
            "last_error": scheduler.get("last_error") or None,
            "last_elapsed_seconds": scheduler.get("last_elapsed_seconds"),
        },
        "engine_summary": {
            "count": len(engine_rows),
            "operational_ready_count": ready_count,
            "stale_count": stale_count,
            "failed_count": sum(1 for row in engine_rows if row["last_status"] == "failed"),
        },
        "engines": engine_rows,
        "dependency_probe_mode": payload.get("dependency_probe_mode"),
        "status_cache": {
            "cached": bool(status_cache.get("cached")),
            "age_seconds": status_cache.get("age_seconds"),
            "refresh_in_progress": bool(status_cache.get("refresh_in_progress")),
        },
        "source_immutable": bool(payload.get("source_immutable")),
        "live_order_allowed": False,
        "summary_only": True,
    }


ASK_AGENT_ROUTABLE_TOOLS = {
    "codexstock_knowledge_curator_status",
    "codexstock_knowledge_search",
    "codexstock_knowledge_engine_plan",
    "codexstock_internal_developer_status",
    "codexstock_internal_developer_component_status",
    "codexstock_internal_developer_list_incidents",
    "codexstock_internal_developer_get_incident",
    "codexstock_internal_developer_latest_report",
    "codexstock_internal_developer_brief",
    "codexstock_internal_developer_activity",
    "codexstock_internal_developer_readonly_diagnostics",
    "codexstock_submit_developer_advice",
    "codexstock_external_signal_inbox",
    "codexstock_external_signal_stage2_queue",
    "codexstock_external_signal_stage2_result",
    "codexstock_external_signal_stage2_run",
    "codexstock_external_signal_stage2_status",
    "codexstock_external_sources",
    "codexstock_external_packages",
    "codexstock_external_learning_report",
    "codexstock_import_training_package",
    "codexstock_validate_external_package",
    "codexstock_run_external_backtest",
    "codexstock_run_external_replay",
    "codexstock_compare_external_strategy",
    "codexstock_assign_training_mission",
    "codexstock_external_engine_contract",
    "codexstock_external_runtime_audit",
    "codexstock_external_dataset_snapshots",
    "codexstock_external_common_snapshot",
    "codexstock_stage2_handoff_queue",
    "codexstock_stage2_result_gate",
    "codexstock_market_context_snapshot",
    "codexstock_market_news_evidence",
    "codexstock_intraday_market_pulse",
    "codexstock_staff_long_horizon_audit",
    "codexstock_staff_learning_effect_audit",
    "codexstock_staff_learning_decision_reflection_audit",
    "codexstock_staff_learning_counterfactual_schedule",
    "codexstock_staff_learning_counterfactual_runtime",
    "codexstock_staff_learning_counterfactual_preregistration",
    "codexstock_staff_indicator_catalog",
    "codexstock_historical_replay_completion_audit",
    "codexstock_historical_market_data_cache_status",
    "codexstock_promotion_candidate_evidence_audit",
    "codexstock_promotion_candidate_discovery_audit",
    "codexstock_promotion_forward_observation_audit",
    "codexstock_promotion_rehearsal_evidence_audit",
    "codexstock_monte_carlo_evidence_audit",
    "codexstock_weakness_completion_audit",
    "codexstock_runtime_deployment_freshness",
    "codexstock_market_priority_resource_gate",
    "codexstock_external_engine_status",
    "codexstock_external_improvement_status",
    "codexstock_external_improvement_run",
    "codexstock_promote_external_knowledge",
    "codexstock_reject_external_knowledge",
}


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _parse_agent_router_payload(question: str) -> tuple[str, dict[str, Any]] | None:
    text = _strip_json_fence(question)
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    tool_name = str(payload.get("mcp_tool") or payload.get("tool") or payload.get("name") or "").strip()
    arguments = payload.get("arguments")
    if not tool_name:
        return None
    return tool_name, dict(arguments if isinstance(arguments, dict) else {})


def _agent_local_fallback(question: str, max_chars: int) -> dict[str, Any] | None:
    routed = _parse_agent_router_payload(question)
    if routed is not None:
        tool_name, routed_arguments = routed
        if tool_name not in ASK_AGENT_ROUTABLE_TOOLS:
            return _tool_result(
                {
                    "ok": False,
                    "blocked": True,
                    "message": "codexstock_ask_agent router only allows bounded read-only operations and explicitly approved advice intake tools.",
                    "requested_tool": tool_name,
                    "allowed_tools": sorted(ASK_AGENT_ROUTABLE_TOOLS),
                    "mcp_server_manifest": _mcp_manifest(),
                },
                max_chars=max_chars,
                is_error=True,
            )
        routed_arguments.setdefault("max_chars", max_chars)
        result = _call_tool(tool_name, routed_arguments)
        if isinstance(result, dict):
            result["routed_via"] = "codexstock_ask_agent"
            result["routed_tool"] = tool_name
        return result

    compact = re.sub(r"\s+", "", question.lower())
    internal_developer_tokens = (
        "internaldeveloper",
        "internal-developer",
        "internal_developer",
        "internaldev",
        "selfrepair",
        "developerreport",
        "내부개발자",
        "자체수리",
        "수리보고서",
        "장애보고서",
    )
    if any(token in compact for token in internal_developer_tokens):
        if any(token in compact for token in ("diagnostic", "diagnosis", "진단", "점검")):
            tool_name = "codexstock_internal_developer_readonly_diagnostics"
            routed_arguments: dict[str, Any] = {}
        elif any(token in compact for token in ("latestreport", "report", "보고서")):
            tool_name = "codexstock_internal_developer_latest_report"
            routed_arguments = {}
        elif any(token in compact for token in ("activity", "audit", "활동", "기록")):
            tool_name = "codexstock_internal_developer_activity"
            routed_arguments = {"limit": 20}
        elif any(token in compact for token in ("incident", "incidents", "장애", "사건")):
            tool_name = "codexstock_internal_developer_list_incidents"
            routed_arguments = {"limit": 20}
        else:
            tool_name = "codexstock_internal_developer_brief"
            routed_arguments = {"incident_limit": 5, "activity_limit": 10}
        routed_arguments["max_chars"] = max_chars
        result = _call_tool(tool_name, routed_arguments)
        if isinstance(result, dict):
            result["routed_via"] = "codexstock_ask_agent"
            result["routed_tool"] = tool_name
            result["schema_cache_fallback"] = True
        return result
    knowledge_curator_tokens = (
        "knowledgecurator",
        "knowledge-curator",
        "knowledge_curator",
        "knowledgesearch",
        "knowledge-search",
        "knowledge_search",
        "knowledgeengineplan",
        "knowledge-engine-plan",
        "knowledge_engine_plan",
        "지식관리",
        "지식정리",
        "지식검색",
        "자료정리",
        "회의기록검색",
        "연구기록검색",
    )
    if any(token in compact for token in knowledge_curator_tokens):
        if any(token in compact for token in ("search", "find", "검색", "찾아", "조회")) and not any(
            token in compact for token in ("status", "상태", "현황", "최근색인")
        ):
            tool_name = "codexstock_knowledge_search"
            routed_arguments = {"query": question, "limit": 10}
        elif any(token in compact for token in ("engineplan", "engine-plan", "engine_plan", "실행계획", "엔진계획")):
            tool_name = "codexstock_knowledge_engine_plan"
            routed_arguments = {
                "changed_documents": 0,
                "market_open": False,
                "heavy_work_allowed": False,
            }
        else:
            tool_name = "codexstock_knowledge_curator_status"
            routed_arguments = {}
        routed_arguments["max_chars"] = max_chars
        result = _call_tool(tool_name, routed_arguments)
        if isinstance(result, dict):
            result["routed_via"] = "codexstock_ask_agent"
            result["routed_tool"] = tool_name
            result["schema_cache_fallback"] = True
        return result
    if any(token in compact for token in ("mcp", "tools/list", "toolmanifest", "toolcount", "manifest", "도구", "함수")):
        return _tool_result({"ok": True, "handled_by": "mcp-local-manifest", "mcp_server_manifest": _mcp_manifest()}, max_chars=max_chars)
    external_signal_tokens = (
        "externalsignal",
        "external-signal",
        "external_signal",
        "inbox",
        "latest_external_signal_report",
        "외부신호",
        "수신함",
        "인박스",
        "최신신호",
        "최신보고서",
    )
    if any(token in compact for token in external_signal_tokens):
        include_report = not any(token in compact for token in ("statusonly", "상태만", "요약만"))
        endpoint_payload = _http_json(
            "GET",
            "/api/external-signal/latest" if include_report else "/api/external-signal/status",
        )
        return _tool_result(
            {
                "ok": True,
                "handled_by": "mcp-local-external-signal-inbox",
                "data": endpoint_payload,
                "mcp_server_manifest": _mcp_manifest_summary(),
            },
            max_chars=max_chars,
        )
    external_improvement_tokens = (
        "externalimprovement",
        "external-improvement",
        "external_improvement",
        "improvementloop",
        "improvement-loop",
        "improvement_loop",
        "외부엔진개선",
        "전략개선루프",
        "자동개선루프",
        "반복검증",
        "재훈련대기",
    )
    if any(token in compact for token in external_improvement_tokens):
        endpoint_payload = _external_improvement_status_summary(
            _http_json("GET", "/api/external-engines/improvement-loop/status")
        )
        return _tool_result(
            {
                "ok": True,
                "handled_by": "mcp-local-external-improvement-status",
                "data": endpoint_payload,
                "mcp_server_manifest": _mcp_manifest_summary(),
            },
            max_chars=max_chars,
        )
    if any(token in compact for token in ("external", "github", "source", "package", "learning", "engine", "adapter", "최강", "외부", "깃허브", "엔진")):
        if any(token in compact for token in ("source", "sources", "깃허브", "소스")):
            endpoint_payload = _external_knowledge_http_or_direct("codexstock_external_sources", "GET", "/api/external-knowledge/sources", {})
            handled_by = "mcp-local-external-sources"
        elif any(token in compact for token in ("package", "packages", "패키지", "목록")):
            endpoint_payload = _external_knowledge_http_or_direct(
                "codexstock_external_packages",
                "GET",
                "/api/external-knowledge/packages",
                {"limit": 200},
                params={"limit": 200, "status": ""},
            )
            handled_by = "mcp-local-external-packages"
        elif any(token in compact for token in ("engine", "adapter", "contract", "엔진", "어댑터")):
            endpoint_payload = _external_knowledge_http_or_direct("codexstock_external_engine_contract", "GET", "/api/external-knowledge/engine-contract", {})
            handled_by = "mcp-local-external-engine-contract"
        else:
            endpoint_payload = _external_knowledge_http_or_direct(
                "codexstock_external_learning_report",
                "GET",
                "/api/external-knowledge/report",
                {"limit": 12},
                params={"limit": 12},
            )
            handled_by = "mcp-local-external-report"
        return _tool_result(
            {"ok": True, "handled_by": handled_by, "data": endpoint_payload, "mcp_server_manifest": _mcp_manifest_summary()},
            max_chars=max_chars,
        )
    return None
def _bool_arg(arguments: dict[str, Any], name: str, default: bool = False) -> bool:
    value = arguments.get(name, default)
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "y", "on"}


def _int_arg(arguments: dict[str, Any], name: str, default: int, lo: int = 1, hi: int = 100) -> int:
    try:
        return max(lo, min(int(arguments.get(name, default) or default), hi))
    except Exception:
        return default


def _float_arg(arguments: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(arguments.get(name, default) or default)
    except Exception:
        return default


def _stage2_result_gate(arguments: dict[str, Any]) -> dict[str, Any]:
    limit = _int_arg(arguments, "limit", 300, 10, 1000)
    queue_limit = _int_arg(arguments, "queue_limit", 20, 1, 500)
    batch_limit = _int_arg(arguments, "batch_limit", 12, 1, 200)
    audit = _tournament_reconciliation_http_or_direct(limit, queue_limit, batch_limit)
    handoff = audit.get("stage2_handoff") if isinstance(audit, dict) and isinstance(audit.get("stage2_handoff"), dict) else {}
    batches = handoff.get("batches") if isinstance(handoff.get("batches"), list) else []
    stage2_job_id = str(arguments.get("stage2_job_id") or "").strip()
    contract_hash_prefix = str(arguments.get("contract_hash_prefix") or "").strip()
    matched_job: dict[str, Any] = {}
    for row in batches:
        if not isinstance(row, dict):
            continue
        row_job_id = str(row.get("stage2_job_id") or "")
        row_hash_prefix = str(row.get("contract_hash_prefix") or "")
        if stage2_job_id and row_job_id == stage2_job_id:
            matched_job = row
            break
        if contract_hash_prefix and row_hash_prefix == contract_hash_prefix:
            matched_job = row
            break
    blockers: list[str] = []
    warnings: list[str] = []
    if not matched_job:
        blockers.append("stage2_contract_not_found")

    expected_hash = str(matched_job.get("contract_hash") or "")
    expected_hash_prefix = str(matched_job.get("contract_hash_prefix") or "")
    echo_hash = str(arguments.get("contract_hash_echo") or "").strip()
    exact_hash_match = bool(expected_hash and echo_hash == expected_hash)
    prefix_hash_match = bool(expected_hash_prefix and (echo_hash == expected_hash_prefix or echo_hash.startswith(expected_hash_prefix)))
    if not echo_hash:
        blockers.append("contract_hash_echo_missing")
    elif not exact_hash_match:
        if prefix_hash_match:
            blockers.append("contract_hash_prefix_only_not_promotable")
        else:
            blockers.append("contract_hash_mismatch")

    expected_contract_schema_version = str(matched_job.get("contract_schema_version") or handoff.get("contract_schema_version") or "").strip()
    expected_idempotency_key = str(matched_job.get("idempotency_key") or "").strip()
    expected_replay_id = str(matched_job.get("replay_id") or "").strip()
    expected_stage2_action = str(matched_job.get("stage2_action") or "").strip()
    expected_preferred_package_id = str(matched_job.get("preferred_package_id") or "").strip()
    expected_preferred_package_source = str(matched_job.get("preferred_package_source") or "").strip()
    expected_external_runtime_mode = str(matched_job.get("external_runtime_mode") or "").strip().lower()
    try:
        expected_timeout_seconds = float(matched_job.get("timeout_seconds") or 0)
    except Exception:
        expected_timeout_seconds = 0.0
    try:
        expected_max_concurrent_external_jobs = int(float(matched_job.get("max_concurrent_external_jobs") or 0))
    except Exception:
        expected_max_concurrent_external_jobs = 0
    try:
        expected_max_temp_artifact_bytes = int(float(matched_job.get("max_temp_artifact_bytes") or 0))
    except Exception:
        expected_max_temp_artifact_bytes = 0
    contract_schema_version_echo = str(arguments.get("contract_schema_version_echo") or "").strip()
    idempotency_key_echo = str(arguments.get("idempotency_key_echo") or "").strip()
    replay_id_echo = str(arguments.get("replay_id_echo") or "").strip()
    stage2_action_echo = str(arguments.get("stage2_action_echo") or "").strip()
    preferred_package_id_echo = str(arguments.get("preferred_package_id_echo") or "").strip()
    preferred_package_source_echo = str(arguments.get("preferred_package_source_echo") or "").strip()
    external_runtime_mode_echo = str(arguments.get("external_runtime_mode_echo") or "").strip().lower()
    runtime_budget_evidence = arguments.get("external_runtime_budget_evidence")
    runtime_budget_evidence_present = isinstance(runtime_budget_evidence, dict) and bool(runtime_budget_evidence)
    runtime_budget_missing_fields: list[str] = []
    runtime_budget_timeout_seconds = -1.0
    runtime_budget_actual_seconds = -1.0
    runtime_budget_max_concurrent_external_jobs = -1
    runtime_cleanup_evidence = arguments.get("external_runtime_cleanup_evidence")
    runtime_cleanup_evidence_present = isinstance(runtime_cleanup_evidence, dict) and bool(runtime_cleanup_evidence)
    runtime_cleanup_missing_fields: list[str] = []
    runtime_cleanup_completed = False
    runtime_cleanup_resident_process_count = -1
    runtime_cleanup_temp_artifact_bytes = -1
    runtime_cleanup_max_temp_artifact_bytes = -1
    contract_schema_version_matched = bool(
        expected_contract_schema_version and contract_schema_version_echo == expected_contract_schema_version
    )
    idempotency_key_matched = bool(expected_idempotency_key and idempotency_key_echo == expected_idempotency_key)
    replay_id_matched = bool(expected_replay_id and replay_id_echo == expected_replay_id)
    stage2_action_matched = bool(expected_stage2_action and stage2_action_echo == expected_stage2_action)
    preferred_package_id_matched = bool(
        expected_preferred_package_id and preferred_package_id_echo == expected_preferred_package_id
    )
    preferred_package_source_matched = bool(
        expected_preferred_package_source and preferred_package_source_echo == expected_preferred_package_source
    )
    external_runtime_mode_matched = bool(
        expected_external_runtime_mode and external_runtime_mode_echo == expected_external_runtime_mode
    )
    if runtime_budget_evidence_present:
        for field in ("timeout_seconds", "actual_runtime_seconds", "max_concurrent_external_jobs"):
            value = runtime_budget_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                runtime_budget_missing_fields.append(field)
        try:
            runtime_budget_timeout_seconds = float(runtime_budget_evidence.get("timeout_seconds"))
        except Exception:
            runtime_budget_timeout_seconds = -1.0
        try:
            runtime_budget_actual_seconds = float(runtime_budget_evidence.get("actual_runtime_seconds"))
        except Exception:
            runtime_budget_actual_seconds = -1.0
        try:
            runtime_budget_max_concurrent_external_jobs = int(float(runtime_budget_evidence.get("max_concurrent_external_jobs")))
        except Exception:
            runtime_budget_max_concurrent_external_jobs = -1
    else:
        runtime_budget_missing_fields = ["timeout_seconds", "actual_runtime_seconds", "max_concurrent_external_jobs"]
    runtime_budget_timeout_matched = bool(
        expected_timeout_seconds > 0 and abs(runtime_budget_timeout_seconds - expected_timeout_seconds) <= 0.000001
    )
    runtime_budget_actual_valid = runtime_budget_actual_seconds >= 0
    runtime_budget_actual_within_timeout = bool(
        runtime_budget_actual_valid and expected_timeout_seconds > 0 and runtime_budget_actual_seconds <= expected_timeout_seconds
    )
    runtime_budget_max_concurrent_matched = bool(
        expected_max_concurrent_external_jobs > 0
        and runtime_budget_max_concurrent_external_jobs == expected_max_concurrent_external_jobs
    )
    if runtime_cleanup_evidence_present:
        for field in ("cleanup_completed", "resident_process_count", "temp_artifact_bytes", "max_temp_artifact_bytes"):
            value = runtime_cleanup_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                runtime_cleanup_missing_fields.append(field)
        runtime_cleanup_completed = _bool_arg(runtime_cleanup_evidence, "cleanup_completed", False)
        try:
            runtime_cleanup_resident_process_count = int(float(runtime_cleanup_evidence.get("resident_process_count")))
        except Exception:
            runtime_cleanup_resident_process_count = -1
        try:
            runtime_cleanup_temp_artifact_bytes = int(float(runtime_cleanup_evidence.get("temp_artifact_bytes")))
        except Exception:
            runtime_cleanup_temp_artifact_bytes = -1
        try:
            runtime_cleanup_max_temp_artifact_bytes = int(float(runtime_cleanup_evidence.get("max_temp_artifact_bytes")))
        except Exception:
            runtime_cleanup_max_temp_artifact_bytes = -1
    else:
        runtime_cleanup_missing_fields = [
            "cleanup_completed",
            "resident_process_count",
            "temp_artifact_bytes",
            "max_temp_artifact_bytes",
        ]
    runtime_cleanup_resident_process_count_ok = runtime_cleanup_resident_process_count == 0
    runtime_cleanup_temp_artifact_bytes_valid = runtime_cleanup_temp_artifact_bytes >= 0
    runtime_cleanup_temp_artifact_within_budget = bool(
        runtime_cleanup_temp_artifact_bytes_valid
        and expected_max_temp_artifact_bytes > 0
        and runtime_cleanup_temp_artifact_bytes <= expected_max_temp_artifact_bytes
    )
    runtime_cleanup_max_temp_artifact_matched = bool(
        expected_max_temp_artifact_bytes > 0
        and runtime_cleanup_max_temp_artifact_bytes == expected_max_temp_artifact_bytes
    )
    external_runtime_mode_has_on_demand_token = any(
        token in external_runtime_mode_echo
        for token in ("on_demand", "ondemand", "spawn-on-demand", "spawn_on_demand")
    )
    external_runtime_mode_unsafe_token = ""
    for token in (
        "always_on",
        "always-on",
        "daemon",
        "resident",
        "background_service",
        "background-service",
        "long_running",
        "long-running",
        "server_mode",
        "service_mode",
        "preloaded",
        "embedded",
        "in_process",
    ):
        if token in external_runtime_mode_echo:
            external_runtime_mode_unsafe_token = token
            break
    if expected_contract_schema_version:
        if not contract_schema_version_echo:
            blockers.append("contract_schema_version_echo_missing")
        elif not contract_schema_version_matched:
            blockers.append("contract_schema_version_echo_mismatch")
    if expected_idempotency_key:
        if not idempotency_key_echo:
            blockers.append("idempotency_key_echo_missing")
        elif not idempotency_key_matched:
            blockers.append("idempotency_key_echo_mismatch")
    if expected_replay_id:
        if not replay_id_echo:
            blockers.append("replay_id_echo_missing")
        elif not replay_id_matched:
            blockers.append("replay_id_echo_mismatch")
    if expected_stage2_action:
        if not stage2_action_echo:
            blockers.append("stage2_action_echo_missing")
        elif not stage2_action_matched:
            blockers.append("stage2_action_echo_mismatch")
    if expected_preferred_package_id:
        if not preferred_package_id_echo:
            blockers.append("preferred_package_id_echo_missing")
        elif not preferred_package_id_matched:
            blockers.append("preferred_package_id_echo_mismatch")
    if expected_preferred_package_source:
        if not preferred_package_source_echo:
            blockers.append("preferred_package_source_echo_missing")
        elif not preferred_package_source_matched:
            blockers.append("preferred_package_source_echo_mismatch")
    if expected_external_runtime_mode:
        if not external_runtime_mode_echo:
            blockers.append("external_runtime_mode_echo_missing")
        elif not external_runtime_mode_matched:
            blockers.append("external_runtime_mode_echo_mismatch")
    if not external_runtime_mode_has_on_demand_token:
        blockers.append("external_runtime_mode_not_on_demand")
    if external_runtime_mode_unsafe_token:
        blockers.append("external_runtime_mode_unsafe_token")
    if not runtime_budget_evidence_present:
        blockers.append("external_runtime_budget_evidence_missing")
    if runtime_budget_missing_fields:
        blockers.append("external_runtime_budget_evidence_incomplete")
    if not runtime_budget_timeout_matched:
        blockers.append("external_runtime_timeout_echo_mismatch")
    if not runtime_budget_actual_valid:
        blockers.append("external_runtime_actual_seconds_invalid")
    elif not runtime_budget_actual_within_timeout:
        blockers.append("external_runtime_timeout_exceeded")
    if not runtime_budget_max_concurrent_matched:
        blockers.append("external_runtime_max_concurrent_echo_mismatch")
    if not runtime_cleanup_evidence_present:
        blockers.append("external_runtime_cleanup_evidence_missing")
    if runtime_cleanup_missing_fields:
        blockers.append("external_runtime_cleanup_evidence_incomplete")
    if not runtime_cleanup_completed:
        blockers.append("external_runtime_cleanup_not_completed")
    if not runtime_cleanup_resident_process_count_ok:
        blockers.append("external_runtime_resident_processes_remaining")
    if not runtime_cleanup_temp_artifact_bytes_valid:
        blockers.append("external_runtime_temp_artifact_bytes_invalid")
    elif not runtime_cleanup_temp_artifact_within_budget:
        blockers.append("external_runtime_temp_artifact_budget_exceeded")
    if not runtime_cleanup_max_temp_artifact_matched:
        blockers.append("external_runtime_max_temp_artifact_echo_mismatch")

    no_live_order_proof = _bool_arg(arguments, "no_live_order_proof", False)
    snapshot_hash_matched = _bool_arg(arguments, "snapshot_hash_matched", False)
    fees_taxes_slippage_applied = _bool_arg(arguments, "fees_taxes_slippage_applied", False)
    one_engine_pass = _bool_arg(arguments, "one_engine_pass", False)
    external_engine_name = str(arguments.get("external_engine_name") or "").strip()
    external_run_id = str(arguments.get("external_run_id") or "").strip()
    external_run_id_len = len(external_run_id)
    external_run_id_format_valid = bool(re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", external_run_id))
    external_run_id_placeholder = any(
        token in external_run_id.lower()
        for token in ("test", "placeholder", "dummy", "sample", "todo", "example")
    )
    external_run_id_contract_hash_prefix_matched = False
    external_run_id_replay_id_matched = False
    if not no_live_order_proof:
        blockers.append("no_live_order_proof_missing")
    if not snapshot_hash_matched:
        blockers.append("snapshot_hash_not_confirmed")
    if not fees_taxes_slippage_applied:
        blockers.append("fee_tax_slippage_not_confirmed")
    if not one_engine_pass:
        blockers.append("one_engine_pass_not_confirmed")
    if not external_engine_name:
        blockers.append("external_engine_name_missing")
    if not external_run_id:
        blockers.append("external_run_id_missing")
    else:
        if external_run_id_len < 8:
            blockers.append("external_run_id_too_short")
        if not external_run_id_format_valid:
            blockers.append("external_run_id_invalid_format")
        if external_run_id_placeholder:
            blockers.append("external_run_id_placeholder")
        external_run_id_contract_hash_prefix_matched = bool(
            expected_hash_prefix and expected_hash_prefix.lower() in external_run_id.lower()
        )
        if expected_hash_prefix and not external_run_id_contract_hash_prefix_matched:
            blockers.append("external_run_id_contract_hash_prefix_missing")
        external_run_id_replay_id_matched = bool(
            expected_replay_id and expected_replay_id.lower() in external_run_id.lower()
        )
        if expected_replay_id and not external_run_id_replay_id_matched:
            blockers.append("external_run_id_replay_id_missing")

    no_live_order_evidence = arguments.get("no_live_order_evidence")
    no_live_order_evidence_present = isinstance(no_live_order_evidence, dict) and bool(no_live_order_evidence)
    no_live_order_evidence_missing_fields: list[str] = []
    order_api_call_count = -1
    live_order_allowed_evidence = True
    account_route_disabled = False
    broker_order_id_count = -1
    account_mutation_count = -1
    position_mutation_count = -1
    mutation_audit_source = ""
    mutation_audit_scope = ""
    mutation_audit_source_placeholder = False
    mutation_audit_scope_covers_account_position = False
    no_live_order_runtime_mode = ""
    no_live_order_runtime_mode_has_safe_token = False
    no_live_order_runtime_mode_unsafe_token = ""
    no_live_order_runtime_mode_safe = False
    if no_live_order_evidence_present:
        for field in (
            "order_api_call_count",
            "live_order_allowed",
            "account_route_disabled",
            "runtime_mode",
            "account_mutation_count",
            "position_mutation_count",
            "mutation_audit_source",
            "mutation_audit_scope",
        ):
            value = no_live_order_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                no_live_order_evidence_missing_fields.append(field)
        if "broker_order_ids" not in no_live_order_evidence:
            no_live_order_evidence_missing_fields.append("broker_order_ids")
        try:
            order_api_call_count = int(no_live_order_evidence.get("order_api_call_count"))
        except Exception:
            order_api_call_count = -1
        live_order_allowed_evidence = _bool_arg(no_live_order_evidence, "live_order_allowed", True)
        account_route_disabled = _bool_arg(no_live_order_evidence, "account_route_disabled", False)
        try:
            account_mutation_count = int(no_live_order_evidence.get("account_mutation_count"))
        except Exception:
            account_mutation_count = -1
        try:
            position_mutation_count = int(no_live_order_evidence.get("position_mutation_count"))
        except Exception:
            position_mutation_count = -1
        broker_order_ids = no_live_order_evidence.get("broker_order_ids")
        if isinstance(broker_order_ids, list):
            broker_order_id_count = len([item for item in broker_order_ids if str(item or "").strip()])
        elif broker_order_ids in (None, ""):
            broker_order_id_count = 0
        else:
            broker_order_id_count = 1
        no_live_order_runtime_mode = str(no_live_order_evidence.get("runtime_mode") or "").strip().lower()
        no_live_order_runtime_mode_has_safe_token = any(
            token in no_live_order_runtime_mode
            for token in ("paper", "historical", "backtest", "replay", "dry_run", "simulation", "offline", "read_only")
        )
        for token in (
            "live_order",
            "real_order",
            "submit_order",
            "order_submit",
            "broker_route_enabled",
            "account_route_enabled",
            "production",
            "prod_live",
            "live_trading",
            "livetrading",
        ):
            if token in no_live_order_runtime_mode:
                no_live_order_runtime_mode_unsafe_token = token
                break
        no_live_order_runtime_mode_safe = (
            no_live_order_runtime_mode_has_safe_token and not no_live_order_runtime_mode_unsafe_token
        )
    else:
        no_live_order_evidence_missing_fields = [
            "order_api_call_count",
            "live_order_allowed",
            "account_route_disabled",
            "runtime_mode",
            "broker_order_ids",
            "account_mutation_count",
            "position_mutation_count",
            "mutation_audit_source",
            "mutation_audit_scope",
        ]
        blockers.append("no_live_order_evidence_missing")
    if no_live_order_evidence_missing_fields:
        blockers.append("no_live_order_evidence_incomplete")
    if order_api_call_count != 0:
        blockers.append("no_live_order_api_calls_detected")
    if live_order_allowed_evidence:
        blockers.append("no_live_order_live_allowed_true")
    if not account_route_disabled:
        blockers.append("no_live_order_account_route_not_disabled")
    if broker_order_id_count != 0:
        blockers.append("no_live_order_broker_order_ids_present")
    if account_mutation_count != 0:
        blockers.append("no_live_order_account_mutations_detected")
    if position_mutation_count != 0:
        blockers.append("no_live_order_position_mutations_detected")
    if no_live_order_evidence_present:
        mutation_audit_source = str(no_live_order_evidence.get("mutation_audit_source") or "").strip()
        mutation_audit_scope = str(no_live_order_evidence.get("mutation_audit_scope") or "").strip()
        mutation_audit_source_placeholder = any(
            token in mutation_audit_source.lower()
            for token in ("test", "placeholder", "dummy", "sample", "todo", "example", "unknown")
        )
        mutation_audit_scope_lower = mutation_audit_scope.lower()
        mutation_audit_scope_covers_account_position = (
            "account" in mutation_audit_scope_lower and "position" in mutation_audit_scope_lower
        )
    if mutation_audit_source_placeholder:
        blockers.append("no_live_order_mutation_audit_source_placeholder")
    if not mutation_audit_scope_covers_account_position:
        blockers.append("no_live_order_mutation_audit_scope_incomplete")
    if not no_live_order_runtime_mode_safe:
        blockers.append("no_live_order_runtime_mode_unsafe")
    if no_live_order_runtime_mode_unsafe_token:
        blockers.append("no_live_order_runtime_mode_unsafe_token")

    contract_cost_profile = matched_job.get("fee_tax_slippage_profile") if isinstance(matched_job.get("fee_tax_slippage_profile"), dict) else {}
    contract_unit_policy = matched_job.get("unit_currency_policy") if isinstance(matched_job.get("unit_currency_policy"), dict) else {}
    expected_unit_currency = str(contract_unit_policy.get("currency") or contract_cost_profile.get("currency") or "").strip().upper()
    expected_unit_quote_unit = str(contract_unit_policy.get("quote_unit") or "share").strip().lower()
    unit_split_adjustment_required = _bool_arg(contract_unit_policy, "split_adjustment_required", True)

    def _canonical_quote_unit(value: object) -> str:
        normalized = re.sub(r"[\s\-]+", "_", str(value or "").strip().lower())
        if normalized in {"share", "shares", "stock_share", "equity_share", "per_share", "price_per_share", "주", "주식"}:
            return "share"
        return normalized

    expected_unit_quote_unit_canonical = _canonical_quote_unit(expected_unit_quote_unit)

    expected_snapshot_id = str(matched_job.get("required_snapshot_id") or "").strip()
    expected_dataset_hash_prefix = str(matched_job.get("dataset_hash_prefix") or "").strip()
    expected_snapshot_scope = str(matched_job.get("required_snapshot_scope") or "common_stage2_snapshot").strip()
    expected_snapshot_source = str(
        matched_job.get("required_snapshot_source") or contract_unit_policy.get("source") or "codexstock_common_snapshot_contract"
    ).strip()
    try:
        expected_trade_count = int(float(matched_job.get("trade_count") or 0))
    except Exception:
        expected_trade_count = 0
    def _symbol_list(value: object) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            raw_items = value
        elif isinstance(value, str):
            raw_items = re.split(r"[,;\s]+", value)
        else:
            raw_items = []
        symbols: list[str] = []
        for item in raw_items:
            symbol = str(item or "").strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
        return symbols

    expected_sample_symbols = _symbol_list(matched_job.get("sample_symbols"))
    contract_sample_symbol_invalid: list[str] = []
    if matched_job and not expected_sample_symbols:
        blockers.append("contract_sample_symbols_missing")
    if expected_unit_currency == "KRW":
        contract_sample_symbol_invalid = [
            symbol for symbol in expected_sample_symbols if not re.fullmatch(r"\d{6}", symbol)
        ]
        if contract_sample_symbol_invalid:
            blockers.append("contract_sample_symbol_format_invalid")
    snapshot_evidence = arguments.get("snapshot_hash_evidence")
    snapshot_evidence_present = isinstance(snapshot_evidence, dict) and bool(snapshot_evidence)
    snapshot_evidence_missing_fields: list[str] = []
    actual_snapshot_id = ""
    actual_dataset_hash_prefix = ""
    actual_snapshot_price_currency = ""
    actual_snapshot_scope = ""
    actual_snapshot_source = ""
    actual_snapshot_symbols: list[str] = []
    snapshot_symbol_missing: list[str] = []
    snapshot_symbol_coverage_matched = False
    snapshot_price_currency_matched = False
    snapshot_scope_matched = False
    snapshot_source_matched = False
    actual_snapshot_price_quote_unit = ""
    actual_snapshot_price_quote_unit_canonical = ""
    snapshot_price_quote_unit_matched = False
    snapshot_id_matched = False
    dataset_hash_prefix_matched = False
    if snapshot_evidence_present:
        snapshot_required_fields = (
            "required_snapshot_id",
            "dataset_hash_prefix",
            "price_currency",
            "price_quote_unit",
            "snapshot_scope",
            "snapshot_source",
        )
        for field in snapshot_required_fields:
            value = snapshot_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                snapshot_evidence_missing_fields.append(field)
        actual_snapshot_id = str(snapshot_evidence.get("required_snapshot_id") or snapshot_evidence.get("snapshot_id") or "").strip()
        actual_dataset_hash_prefix = str(
            snapshot_evidence.get("dataset_hash_prefix")
            or snapshot_evidence.get("dataset_hash")
            or snapshot_evidence.get("snapshot_hash")
            or ""
        ).strip()
        actual_snapshot_price_currency = str(snapshot_evidence.get("price_currency") or "").strip().upper()
        actual_snapshot_price_quote_unit = str(snapshot_evidence.get("price_quote_unit") or "").strip().lower()
        actual_snapshot_price_quote_unit_canonical = _canonical_quote_unit(actual_snapshot_price_quote_unit)
        actual_snapshot_scope = str(snapshot_evidence.get("snapshot_scope") or snapshot_evidence.get("scope") or "").strip()
        actual_snapshot_source = str(snapshot_evidence.get("snapshot_source") or snapshot_evidence.get("source") or "").strip()
        actual_snapshot_symbols = _symbol_list(
            snapshot_evidence.get("sample_symbols")
            or snapshot_evidence.get("symbols")
            or snapshot_evidence.get("symbol_universe")
        )
    else:
        snapshot_evidence_missing_fields = [
            "required_snapshot_id",
            "dataset_hash_prefix",
            "price_currency",
            "price_quote_unit",
            "snapshot_scope",
            "snapshot_source",
        ]
        blockers.append("snapshot_hash_evidence_missing")
    if snapshot_evidence_missing_fields:
        blockers.append("snapshot_hash_evidence_incomplete")
    if expected_snapshot_id and actual_snapshot_id:
        snapshot_id_matched = actual_snapshot_id == expected_snapshot_id
        if not snapshot_id_matched:
            blockers.append("snapshot_id_mismatch")
    elif expected_snapshot_id and not actual_snapshot_id:
        blockers.append("snapshot_id_mismatch")
    if expected_dataset_hash_prefix and actual_dataset_hash_prefix:
        dataset_hash_prefix_matched = (
            actual_dataset_hash_prefix == expected_dataset_hash_prefix
            or actual_dataset_hash_prefix.startswith(expected_dataset_hash_prefix)
            or expected_dataset_hash_prefix.startswith(actual_dataset_hash_prefix)
        )
        if not dataset_hash_prefix_matched:
            blockers.append("dataset_hash_prefix_mismatch")
    elif expected_dataset_hash_prefix and not actual_dataset_hash_prefix:
        blockers.append("dataset_hash_prefix_mismatch")
    if expected_unit_currency and actual_snapshot_price_currency:
        snapshot_price_currency_matched = actual_snapshot_price_currency == expected_unit_currency
        if not snapshot_price_currency_matched:
            blockers.append("snapshot_price_currency_mismatch")
    if expected_unit_quote_unit_canonical and actual_snapshot_price_quote_unit:
        snapshot_price_quote_unit_matched = (
            actual_snapshot_price_quote_unit_canonical == expected_unit_quote_unit_canonical
        )
        if not snapshot_price_quote_unit_matched:
            blockers.append("snapshot_price_quote_unit_mismatch")
    if expected_snapshot_scope:
        snapshot_scope_matched = actual_snapshot_scope == expected_snapshot_scope
        if not actual_snapshot_scope:
            blockers.append("snapshot_scope_missing")
        elif not snapshot_scope_matched:
            blockers.append("snapshot_scope_mismatch")
    if expected_snapshot_source:
        snapshot_source_matched = actual_snapshot_source == expected_snapshot_source
        if not actual_snapshot_source:
            blockers.append("snapshot_source_missing")
        elif not snapshot_source_matched:
            blockers.append("snapshot_source_mismatch")
    if expected_sample_symbols:
        if not actual_snapshot_symbols:
            snapshot_symbol_missing = expected_sample_symbols
            blockers.append("snapshot_symbol_coverage_missing")
        else:
            actual_symbol_set = set(actual_snapshot_symbols)
            snapshot_symbol_missing = [symbol for symbol in expected_sample_symbols if symbol not in actual_symbol_set]
            snapshot_symbol_coverage_matched = not snapshot_symbol_missing
            if snapshot_symbol_missing:
                blockers.append("snapshot_symbol_coverage_mismatch")

    cost_evidence = arguments.get("fee_tax_slippage_evidence")
    cost_evidence_present = isinstance(cost_evidence, dict) and bool(cost_evidence)
    cost_evidence_missing_fields: list[str] = []
    cost_profile_matched = False
    cost_currency_matched = False
    cost_applied_trade_count = 0
    cost_fill_ledger_hash = ""
    cost_fill_ledger_hash_matched = False
    cost_return_count_matched = False
    cost_applied_symbols: list[str] = []
    cost_symbol_missing: list[str] = []
    cost_symbol_coverage_matched = False
    cost_rate_tolerance = 0.0000001
    if not cost_evidence_present:
        blockers.append("fee_tax_slippage_evidence_missing")
    else:
        cost_required_fields = (
            "profile_id",
            "currency",
            "broker_fee_rate",
            "sell_transaction_tax_rate",
            "slippage_bps",
            "applied_trade_count",
            "applied_symbols",
            "fill_ledger_hash",
        )
        for field in cost_required_fields:
            value = cost_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                cost_evidence_missing_fields.append(field)
        if cost_evidence_missing_fields:
            blockers.append("fee_tax_slippage_evidence_incomplete")
        cost_applied_trade_count = _int_arg(cost_evidence, "applied_trade_count", 0, 0, 1_000_000)
        cost_applied_symbols = _symbol_list(
            cost_evidence.get("applied_symbols")
            or cost_evidence.get("trade_symbols")
            or cost_evidence.get("sample_symbols")
            or cost_evidence.get("symbols")
            or cost_evidence.get("symbol_universe")
        )
        cost_fill_ledger_hash = str(cost_evidence.get("fill_ledger_hash") or "").strip()
        if cost_applied_trade_count <= 0:
            blockers.append("fee_tax_slippage_applied_trade_count_invalid")
        if expected_sample_symbols:
            if not cost_applied_symbols:
                cost_symbol_missing = expected_sample_symbols
                blockers.append("fee_tax_slippage_symbol_coverage_missing")
            else:
                cost_symbol_set = set(cost_applied_symbols)
                cost_symbol_missing = [
                    symbol for symbol in expected_sample_symbols if symbol not in cost_symbol_set
                ]
                cost_symbol_coverage_matched = not cost_symbol_missing
                if cost_symbol_missing:
                    blockers.append("fee_tax_slippage_symbol_coverage_mismatch")
        expected_profile_id = str(contract_cost_profile.get("profile_id") or "")
        actual_profile_id = str(cost_evidence.get("profile_id") or "")
        expected_cost_currency = str(contract_cost_profile.get("currency") or "").strip().upper()
        actual_cost_currency = str(cost_evidence.get("currency") or "").strip().upper()
        cost_currency_matched = bool(expected_cost_currency and actual_cost_currency == expected_cost_currency)
        broker_fee_diff = abs(_float_arg(cost_evidence, "broker_fee_rate", -1.0) - _float_arg(contract_cost_profile, "broker_fee_rate", -2.0))
        sell_tax_diff = abs(
            _float_arg(cost_evidence, "sell_transaction_tax_rate", -1.0)
            - _float_arg(contract_cost_profile, "sell_transaction_tax_rate", -2.0)
        )
        slippage_diff = abs(_float_arg(cost_evidence, "slippage_bps", -1.0) - _float_arg(contract_cost_profile, "slippage_bps", -2.0))
        cost_profile_matched = (
            bool(expected_profile_id)
            and actual_profile_id == expected_profile_id
            and cost_currency_matched
            and broker_fee_diff <= cost_rate_tolerance
            and sell_tax_diff <= cost_rate_tolerance
            and slippage_diff <= cost_rate_tolerance
        )
        if not cost_profile_matched:
            blockers.append("fee_tax_slippage_profile_mismatch")

    entry_exit_evidence = arguments.get("entry_exit_return_reason_evidence")
    evidence_required_fields = (
        "engine_name",
        "entry_price",
        "exit_price",
        "pnl_pct",
        "exit_reason",
        "price_currency",
        "price_quote_unit",
        "price_snapshot_id",
        "price_dataset_hash_prefix",
        "price_snapshot_scope",
        "price_snapshot_source",
        "price_sample_symbols",
        "fill_ledger_hash",
        "same_engine_confirmed",
    )
    evidence_missing_fields: list[str] = []
    evidence_present = isinstance(entry_exit_evidence, dict) and bool(entry_exit_evidence)
    evidence_same_engine_confirmed = False
    evidence_price_currency = ""
    evidence_price_currency_matched = False
    evidence_price_quote_unit = ""
    evidence_price_quote_unit_canonical = ""
    evidence_price_quote_unit_matched = False
    evidence_price_snapshot_id = ""
    evidence_price_snapshot_id_matched = False
    evidence_price_dataset_hash_prefix = ""
    evidence_price_dataset_hash_prefix_matched = False
    evidence_price_snapshot_scope = ""
    evidence_price_snapshot_scope_matched = False
    evidence_price_snapshot_source = ""
    evidence_price_snapshot_source_matched = False
    evidence_price_sample_symbols: list[str] = []
    evidence_price_symbol_missing: list[str] = []
    evidence_price_symbol_coverage_matched = False
    evidence_fill_ledger_hash = ""
    evidence_fill_ledger_hash_matched = False
    evidence_pnl_expected_pct = 0.0
    evidence_pnl_reported_pct = 0.0
    evidence_pnl_diff_pct = 0.0
    evidence_pnl_tolerance_pct = 0.05
    evidence_pnl_reconciled = False
    exit_reason_threshold_pct: float | None = None
    exit_reason_threshold_expected_pct = 0.0
    exit_reason_threshold_diff_pct = 0.0
    exit_reason_threshold_tolerance_pct = 0.25
    exit_reason_threshold_reconciled = True
    exit_reason_threshold_required = False
    threshold_execution_explained = False
    threshold_execution_explanation = ""
    if not evidence_present:
        blockers.append("entry_exit_return_reason_evidence_missing")
    else:
        for field in evidence_required_fields:
            value = entry_exit_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                evidence_missing_fields.append(field)
        evidence_same_engine_confirmed = _bool_arg(entry_exit_evidence, "same_engine_confirmed", False)
        if evidence_missing_fields:
            blockers.append("entry_exit_return_reason_evidence_incomplete")
        if not evidence_same_engine_confirmed:
            blockers.append("entry_exit_return_reason_same_engine_not_confirmed")
        evidence_engine_name = str(entry_exit_evidence.get("engine_name") or "").strip()
        if external_engine_name and evidence_engine_name and external_engine_name != evidence_engine_name:
            blockers.append("external_engine_identity_mismatch")
        evidence_price_currency = str(entry_exit_evidence.get("price_currency") or "").strip().upper()
        evidence_price_quote_unit = str(entry_exit_evidence.get("price_quote_unit") or "").strip().lower()
        evidence_price_quote_unit_canonical = _canonical_quote_unit(evidence_price_quote_unit)
        evidence_price_snapshot_id = str(
            entry_exit_evidence.get("price_snapshot_id")
            or entry_exit_evidence.get("required_snapshot_id")
            or entry_exit_evidence.get("snapshot_id")
            or ""
        ).strip()
        evidence_price_dataset_hash_prefix = str(
            entry_exit_evidence.get("price_dataset_hash_prefix")
            or entry_exit_evidence.get("dataset_hash_prefix")
            or entry_exit_evidence.get("dataset_hash")
            or entry_exit_evidence.get("snapshot_hash")
            or ""
        ).strip()
        evidence_price_snapshot_scope = str(
            entry_exit_evidence.get("price_snapshot_scope")
            or entry_exit_evidence.get("snapshot_scope")
            or entry_exit_evidence.get("scope")
            or ""
        ).strip()
        evidence_price_snapshot_source = str(
            entry_exit_evidence.get("price_snapshot_source")
            or entry_exit_evidence.get("snapshot_source")
            or entry_exit_evidence.get("source")
            or ""
        ).strip()
        evidence_price_sample_symbols = _symbol_list(
            entry_exit_evidence.get("price_sample_symbols")
            or entry_exit_evidence.get("sample_symbols")
            or entry_exit_evidence.get("trade_symbols")
            or entry_exit_evidence.get("symbols")
        )
        evidence_fill_ledger_hash = str(entry_exit_evidence.get("fill_ledger_hash") or "").strip()
        if expected_unit_currency and evidence_price_currency:
            evidence_price_currency_matched = evidence_price_currency == expected_unit_currency
            if not evidence_price_currency_matched:
                blockers.append("entry_exit_price_currency_mismatch")
        if expected_unit_quote_unit_canonical and evidence_price_quote_unit:
            evidence_price_quote_unit_matched = evidence_price_quote_unit_canonical == expected_unit_quote_unit_canonical
            if not evidence_price_quote_unit_matched:
                blockers.append("entry_exit_price_quote_unit_mismatch")
        if expected_snapshot_id and evidence_price_snapshot_id:
            evidence_price_snapshot_id_matched = evidence_price_snapshot_id == expected_snapshot_id
            if not evidence_price_snapshot_id_matched:
                blockers.append("entry_exit_price_snapshot_id_mismatch")
        if expected_dataset_hash_prefix and evidence_price_dataset_hash_prefix:
            evidence_price_dataset_hash_prefix_matched = (
                evidence_price_dataset_hash_prefix == expected_dataset_hash_prefix
                or evidence_price_dataset_hash_prefix.startswith(expected_dataset_hash_prefix)
                or expected_dataset_hash_prefix.startswith(evidence_price_dataset_hash_prefix)
            )
            if not evidence_price_dataset_hash_prefix_matched:
                blockers.append("entry_exit_price_dataset_hash_prefix_mismatch")
        if expected_snapshot_scope:
            evidence_price_snapshot_scope_matched = evidence_price_snapshot_scope == expected_snapshot_scope
            if not evidence_price_snapshot_scope:
                blockers.append("entry_exit_price_snapshot_scope_missing")
            elif not evidence_price_snapshot_scope_matched:
                blockers.append("entry_exit_price_snapshot_scope_mismatch")
        if expected_snapshot_source:
            evidence_price_snapshot_source_matched = evidence_price_snapshot_source == expected_snapshot_source
            if not evidence_price_snapshot_source:
                blockers.append("entry_exit_price_snapshot_source_missing")
            elif not evidence_price_snapshot_source_matched:
                blockers.append("entry_exit_price_snapshot_source_mismatch")
        if expected_sample_symbols:
            if not evidence_price_sample_symbols:
                evidence_price_symbol_missing = expected_sample_symbols
                blockers.append("entry_exit_symbol_coverage_missing")
            else:
                evidence_price_symbol_set = set(evidence_price_sample_symbols)
                evidence_price_symbol_missing = [
                    symbol for symbol in expected_sample_symbols if symbol not in evidence_price_symbol_set
                ]
                evidence_price_symbol_coverage_matched = not evidence_price_symbol_missing
                if evidence_price_symbol_missing:
                    blockers.append("entry_exit_symbol_coverage_mismatch")
        if not any(field in evidence_missing_fields for field in ("entry_price", "exit_price", "pnl_pct")):
            entry_price = _float_arg(entry_exit_evidence, "entry_price", 0.0)
            exit_price = _float_arg(entry_exit_evidence, "exit_price", 0.0)
            evidence_pnl_reported_pct = _float_arg(entry_exit_evidence, "pnl_pct", 0.0)
            trade_side = str(entry_exit_evidence.get("trade_side") or "long").strip().lower()
            if entry_price <= 0 or exit_price <= 0:
                blockers.append("entry_exit_return_reason_price_invalid")
            else:
                if trade_side in {"short", "sell_short"}:
                    evidence_pnl_expected_pct = ((entry_price - exit_price) / entry_price) * 100.0
                else:
                    evidence_pnl_expected_pct = ((exit_price - entry_price) / entry_price) * 100.0
                evidence_pnl_diff_pct = abs(evidence_pnl_expected_pct - evidence_pnl_reported_pct)
                evidence_pnl_reconciled = evidence_pnl_diff_pct <= evidence_pnl_tolerance_pct
                if not evidence_pnl_reconciled:
                    blockers.append("entry_exit_pnl_mismatch")
                exit_reason_text = str(entry_exit_evidence.get("exit_reason") or "").lower()
                exit_reason_threshold_required = any(
                    token in exit_reason_text
                    for token in ("take", "profit", "target", "stop", "loss", "trail", "익절", "손절")
                )
                for threshold_key in ("exit_reason_threshold_pct", "reason_threshold_pct", "exit_threshold_pct", "threshold_pct"):
                    if threshold_key in entry_exit_evidence:
                        try:
                            exit_reason_threshold_pct = float(entry_exit_evidence.get(threshold_key) or 0.0)
                        except Exception:
                            exit_reason_threshold_pct = 0.0
                        break
                if exit_reason_threshold_pct is None and exit_reason_threshold_required:
                    blockers.append("exit_reason_threshold_missing")
                    exit_reason_threshold_reconciled = False
                elif exit_reason_threshold_pct is not None:
                    exit_reason_threshold_expected_pct = exit_reason_threshold_pct
                    if exit_reason_threshold_pct > 0 and any(token in exit_reason_text for token in ("stop", "loss", "손절")):
                        exit_reason_threshold_expected_pct = -abs(exit_reason_threshold_pct)
                    elif exit_reason_threshold_pct > 0 and any(token in exit_reason_text for token in ("take", "profit", "target", "익절")):
                        exit_reason_threshold_expected_pct = abs(exit_reason_threshold_pct)
                    exit_reason_threshold_diff_pct = abs(evidence_pnl_reported_pct - exit_reason_threshold_expected_pct)
                    threshold_execution_explained = _bool_arg(entry_exit_evidence, "threshold_execution_explained", False)
                    threshold_execution_explanation = str(
                        entry_exit_evidence.get("threshold_breach_explanation")
                        or entry_exit_evidence.get("execution_price_explanation")
                        or ""
                    ).strip()
                    exit_reason_threshold_reconciled = (
                        exit_reason_threshold_diff_pct <= exit_reason_threshold_tolerance_pct
                        or (threshold_execution_explained and bool(threshold_execution_explanation))
                    )
                    if not exit_reason_threshold_reconciled:
                        blockers.append("exit_reason_threshold_mismatch")
                    elif exit_reason_threshold_diff_pct > exit_reason_threshold_tolerance_pct:
                        warnings.append("exit_reason_threshold_breach_explained")

    unit_evidence = arguments.get("unit_currency_audit_evidence")
    unit_evidence_present = isinstance(unit_evidence, dict) and bool(unit_evidence)
    unit_evidence_required_fields = ("status", "currency", "quote_unit", "split_adjustment_checked")
    unit_evidence_missing_fields: list[str] = []
    unit_evidence_status = ""
    unit_currency = ""
    unit_quote_unit = ""
    unit_quote_unit_canonical = ""
    unit_currency_matched = False
    unit_quote_unit_matched = False
    unit_split_adjustment_checked = False
    if unit_evidence_present:
        for field in unit_evidence_required_fields:
            value = unit_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                unit_evidence_missing_fields.append(field)
        unit_evidence_status = str(unit_evidence.get("status") or "").strip().lower()
        unit_currency = str(unit_evidence.get("currency") or "").strip().upper()
        unit_quote_unit = str(unit_evidence.get("quote_unit") or "").strip().lower()
        unit_quote_unit_canonical = _canonical_quote_unit(unit_quote_unit)
        unit_split_adjustment_checked = _bool_arg(unit_evidence, "split_adjustment_checked", False)
    else:
        unit_evidence_missing_fields = list(unit_evidence_required_fields)
        blockers.append("unit_currency_audit_evidence_missing")
    if unit_evidence_missing_fields:
        blockers.append("unit_currency_audit_evidence_incomplete")
    if unit_evidence_status not in {"pass", "passed", "ok"}:
        blockers.append("unit_currency_audit_evidence_not_pass")
    if not unit_currency:
        blockers.append("unit_currency_currency_missing")
    if not unit_quote_unit:
        blockers.append("unit_currency_quote_unit_missing")
    if expected_unit_currency and unit_currency:
        unit_currency_matched = unit_currency == expected_unit_currency
        if not unit_currency_matched:
            blockers.append("unit_currency_currency_mismatch")
    elif not expected_unit_currency:
        warnings.append("unit_currency_expected_currency_missing")
    if expected_unit_quote_unit_canonical and unit_quote_unit:
        unit_quote_unit_matched = unit_quote_unit_canonical == expected_unit_quote_unit_canonical
        if not unit_quote_unit_matched:
            blockers.append("unit_currency_quote_unit_mismatch")
    elif not expected_unit_quote_unit_canonical:
        warnings.append("unit_currency_expected_quote_unit_missing")
    if unit_split_adjustment_required and not unit_split_adjustment_checked:
        blockers.append("unit_currency_split_adjustment_not_confirmed")

    unit_status = str(arguments.get("unit_currency_audit_status") or "").strip().lower()
    if unit_status not in {"pass", "passed", "ok"}:
        blockers.append("unit_currency_audit_not_pass")
        if unit_status in {"blocker", "blocked", "review_required"}:
            warnings.append("unit_currency_audit_declared_blocker")

    exit_reason_alignment = str(arguments.get("exit_reason_alignment") or "").strip().lower()
    if exit_reason_alignment not in {"pass", "passed", "matched", "ok"}:
        blockers.append("exit_reason_alignment_not_pass")
    exit_reason_alignment_evidence = arguments.get("exit_reason_alignment_evidence")
    exit_reason_alignment_evidence_present = isinstance(exit_reason_alignment_evidence, dict) and bool(exit_reason_alignment_evidence)
    exit_reason_alignment_evidence_missing_fields: list[str] = []
    exit_reason_alignment_checked_count = 0
    exit_reason_alignment_matched_count = 0
    exit_reason_alignment_mismatch_count = 0
    exit_reason_alignment_fill_ledger_hash = ""
    exit_reason_alignment_fill_ledger_hash_matched = False
    exit_reason_alignment_return_count_matched = False
    exit_reason_alignment_symbols: list[str] = []
    exit_reason_alignment_symbol_missing: list[str] = []
    exit_reason_alignment_symbol_coverage_matched = False
    if not exit_reason_alignment_evidence_present:
        exit_reason_alignment_evidence_missing_fields = [
            "checked_count",
            "matched_count",
            "mismatch_count",
            "fill_ledger_hash",
            "checked_symbols",
        ]
        blockers.append("exit_reason_alignment_evidence_missing")
    else:
        exit_reason_alignment_required_fields = (
            "checked_count",
            "matched_count",
            "mismatch_count",
            "fill_ledger_hash",
            "checked_symbols",
        )
        for field in exit_reason_alignment_required_fields:
            value = exit_reason_alignment_evidence.get(field)
            if value is None or value == "" or value == [] or value == {}:
                exit_reason_alignment_evidence_missing_fields.append(field)
        if exit_reason_alignment_evidence_missing_fields:
            blockers.append("exit_reason_alignment_evidence_incomplete")
        exit_reason_alignment_checked_count = _int_arg(exit_reason_alignment_evidence, "checked_count", 0, 0, 1_000_000)
        exit_reason_alignment_matched_count = _int_arg(exit_reason_alignment_evidence, "matched_count", 0, 0, 1_000_000)
        exit_reason_alignment_mismatch_count = _int_arg(exit_reason_alignment_evidence, "mismatch_count", 0, 0, 1_000_000)
        exit_reason_alignment_fill_ledger_hash = str(exit_reason_alignment_evidence.get("fill_ledger_hash") or "").strip()
        exit_reason_alignment_symbols = _symbol_list(
            exit_reason_alignment_evidence.get("checked_symbols")
            or exit_reason_alignment_evidence.get("aligned_symbols")
            or exit_reason_alignment_evidence.get("reconciled_symbols")
            or exit_reason_alignment_evidence.get("trade_symbols")
            or exit_reason_alignment_evidence.get("sample_symbols")
            or exit_reason_alignment_evidence.get("symbols")
        )
        if exit_reason_alignment_checked_count <= 0:
            blockers.append("exit_reason_alignment_no_checked_trades")
        if exit_reason_alignment_matched_count < exit_reason_alignment_checked_count:
            blockers.append("exit_reason_alignment_not_all_matched")
        if exit_reason_alignment_mismatch_count > 0:
            blockers.append("exit_reason_alignment_mismatches_present")
        if expected_sample_symbols:
            if not exit_reason_alignment_symbols:
                exit_reason_alignment_symbol_missing = expected_sample_symbols
                blockers.append("exit_reason_alignment_symbol_coverage_missing")
            else:
                exit_reason_alignment_symbol_set = set(exit_reason_alignment_symbols)
                exit_reason_alignment_symbol_missing = [
                    symbol for symbol in expected_sample_symbols if symbol not in exit_reason_alignment_symbol_set
                ]
                exit_reason_alignment_symbol_coverage_matched = not exit_reason_alignment_symbol_missing
                if exit_reason_alignment_symbol_missing:
                    blockers.append("exit_reason_alignment_symbol_coverage_mismatch")

    fill_ledger_hash = str(arguments.get("fill_ledger_hash") or "").strip()
    fill_ledger_hash_format_valid = bool(
        re.fullmatch(r"(?:[A-Fa-f0-9]{32,128}|sha256:[A-Fa-f0-9]{64})", fill_ledger_hash)
    )
    fill_ledger_hash_placeholder = any(
        token in fill_ledger_hash.lower()
        for token in ("test", "placeholder", "dummy", "sample")
    )
    fill_ledger_evidence = arguments.get("fill_ledger_evidence")
    fill_ledger_evidence_present = isinstance(fill_ledger_evidence, dict) and bool(fill_ledger_evidence)
    fill_ledger_evidence_missing_fields: list[str] = []
    fill_ledger_evidence_hash = ""
    fill_ledger_evidence_hash_matched = False
    fill_ledger_trade_count = 0
    fill_ledger_return_count_matched = False
    fill_ledger_symbols: list[str] = []
    fill_ledger_symbol_missing: list[str] = []
    fill_ledger_symbol_coverage_matched = False
    if not fill_ledger_evidence_present:
        fill_ledger_evidence_missing_fields = ["fill_ledger_hash", "trade_count", "trade_symbols"]
        blockers.append("fill_ledger_evidence_missing")
    else:
        for field in ("fill_ledger_hash", "trade_count", "trade_symbols"):
            value = fill_ledger_evidence.get(field)
            if value is None or value == "":
                fill_ledger_evidence_missing_fields.append(field)
        if fill_ledger_evidence_missing_fields:
            blockers.append("fill_ledger_evidence_incomplete")
        fill_ledger_evidence_hash = str(fill_ledger_evidence.get("fill_ledger_hash") or "").strip()
        fill_ledger_trade_count = _int_arg(fill_ledger_evidence, "trade_count", 0, 0, 1_000_000)
        fill_ledger_symbols = _symbol_list(
            fill_ledger_evidence.get("trade_symbols")
            or fill_ledger_evidence.get("sample_symbols")
            or fill_ledger_evidence.get("symbols")
            or fill_ledger_evidence.get("symbol_universe")
        )
        if fill_ledger_hash and fill_ledger_evidence_hash:
            fill_ledger_evidence_hash_matched = fill_ledger_evidence_hash == fill_ledger_hash
            if not fill_ledger_evidence_hash_matched:
                blockers.append("fill_ledger_hash_evidence_mismatch")
        if fill_ledger_trade_count <= 0:
            blockers.append("fill_ledger_trade_count_invalid")
        if expected_sample_symbols:
            if not fill_ledger_symbols:
                fill_ledger_symbol_missing = expected_sample_symbols
                blockers.append("fill_ledger_symbol_coverage_missing")
            else:
                fill_ledger_symbol_set = set(fill_ledger_symbols)
                fill_ledger_symbol_missing = [
                    symbol for symbol in expected_sample_symbols if symbol not in fill_ledger_symbol_set
                ]
                fill_ledger_symbol_coverage_matched = not fill_ledger_symbol_missing
                if fill_ledger_symbol_missing:
                    blockers.append("fill_ledger_symbol_coverage_mismatch")
    return_reconciliation_summary = arguments.get("return_reconciliation_summary")
    return_summary_present = isinstance(return_reconciliation_summary, dict) and bool(return_reconciliation_summary)
    return_needs_review = 0
    return_blocker_count = 0
    return_warning_count = 0
    return_checked_count = 0
    return_ok_count = 0
    return_mismatch_count = 0
    return_summary_fill_ledger_hash = ""
    return_summary_fill_ledger_hash_matched = False
    return_checked_symbols: list[str] = []
    return_symbol_missing: list[str] = []
    return_symbol_coverage_matched = False
    return_contract_trade_count_matched = False
    fill_ledger_contract_trade_count_matched = False
    cost_contract_trade_count_matched = False
    exit_reason_alignment_contract_trade_count_matched = False
    return_summary_incomplete = False
    if not fill_ledger_hash:
        blockers.append("fill_ledger_hash_missing")
    elif not fill_ledger_hash_format_valid:
        blockers.append("fill_ledger_hash_invalid")
    if fill_ledger_hash_placeholder:
        blockers.append("fill_ledger_hash_placeholder")
    if cost_evidence_present:
        if fill_ledger_hash and cost_fill_ledger_hash:
            cost_fill_ledger_hash_matched = cost_fill_ledger_hash == fill_ledger_hash
            if not cost_fill_ledger_hash_matched:
                blockers.append("fee_tax_slippage_fill_ledger_hash_mismatch")
        else:
            blockers.append("fee_tax_slippage_fill_ledger_hash_missing")
    if evidence_present:
        if fill_ledger_hash and evidence_fill_ledger_hash:
            evidence_fill_ledger_hash_matched = evidence_fill_ledger_hash == fill_ledger_hash
            if not evidence_fill_ledger_hash_matched:
                blockers.append("entry_exit_fill_ledger_hash_mismatch")
        else:
            blockers.append("entry_exit_fill_ledger_hash_missing")
    if exit_reason_alignment_evidence_present:
        if fill_ledger_hash and exit_reason_alignment_fill_ledger_hash:
            exit_reason_alignment_fill_ledger_hash_matched = exit_reason_alignment_fill_ledger_hash == fill_ledger_hash
            if not exit_reason_alignment_fill_ledger_hash_matched:
                blockers.append("exit_reason_alignment_fill_ledger_hash_mismatch")
        else:
            blockers.append("exit_reason_alignment_fill_ledger_hash_missing")
    if not return_summary_present:
        blockers.append("return_reconciliation_summary_missing")
    else:
        return_needs_review = _int_arg(return_reconciliation_summary, "needs_review", 0, 0, 1_000_000)
        return_blocker_count = _int_arg(return_reconciliation_summary, "blocker_count", 0, 0, 1_000_000)
        return_warning_count = _int_arg(return_reconciliation_summary, "warning_count", 0, 0, 1_000_000)
        return_checked_count = _int_arg(return_reconciliation_summary, "checked_count", 0, 0, 1_000_000)
        return_ok_count = _int_arg(return_reconciliation_summary, "ok_count", 0, 0, 1_000_000)
        return_mismatch_count = _int_arg(return_reconciliation_summary, "mismatch_count", 0, 0, 1_000_000)
        return_summary_fill_ledger_hash = str(return_reconciliation_summary.get("fill_ledger_hash") or "").strip()
        return_summary_required_fields = (
            "needs_review",
            "blocker_count",
            "checked_count",
            "ok_count",
            "mismatch_count",
            "fill_ledger_hash",
            "checked_symbols",
        )
        if any(field not in return_reconciliation_summary for field in return_summary_required_fields):
            return_summary_incomplete = True
            blockers.append("return_reconciliation_summary_incomplete")
        return_checked_symbols = _symbol_list(
            return_reconciliation_summary.get("checked_symbols")
            or return_reconciliation_summary.get("reconciled_symbols")
            or return_reconciliation_summary.get("trade_symbols")
            or return_reconciliation_summary.get("sample_symbols")
            or return_reconciliation_summary.get("symbols")
        )
        if fill_ledger_hash and return_summary_fill_ledger_hash:
            return_summary_fill_ledger_hash_matched = return_summary_fill_ledger_hash == fill_ledger_hash
            if not return_summary_fill_ledger_hash_matched:
                blockers.append("return_reconciliation_fill_ledger_hash_mismatch")
        else:
            blockers.append("return_reconciliation_fill_ledger_hash_missing")
        if return_checked_count <= 0:
            blockers.append("return_reconciliation_no_checked_trades")
        if return_ok_count < return_checked_count:
            blockers.append("return_reconciliation_not_all_trades_ok")
        if return_mismatch_count > 0:
            blockers.append("return_reconciliation_mismatches_present")
        if return_needs_review > 0:
            blockers.append("return_reconciliation_needs_review")
        if return_blocker_count > 0:
            blockers.append("return_reconciliation_blockers_present")
        if expected_sample_symbols:
            if not return_checked_symbols:
                return_symbol_missing = expected_sample_symbols
                blockers.append("return_reconciliation_symbol_coverage_missing")
            else:
                return_symbol_set = set(return_checked_symbols)
                return_symbol_missing = [
                    symbol for symbol in expected_sample_symbols if symbol not in return_symbol_set
                ]
                return_symbol_coverage_matched = not return_symbol_missing
                if return_symbol_missing:
                    blockers.append("return_reconciliation_symbol_coverage_mismatch")
    if expected_trade_count > 0 and return_summary_present:
        return_contract_trade_count_matched = return_checked_count == expected_trade_count
        if not return_contract_trade_count_matched:
            blockers.append("return_reconciliation_contract_trade_count_mismatch")
    if exit_reason_alignment_evidence_present and return_summary_present:
        exit_reason_alignment_return_count_matched = exit_reason_alignment_checked_count == return_checked_count
        if not exit_reason_alignment_return_count_matched:
            blockers.append("exit_reason_alignment_return_count_mismatch")
    if expected_trade_count > 0 and exit_reason_alignment_evidence_present:
        exit_reason_alignment_contract_trade_count_matched = exit_reason_alignment_checked_count == expected_trade_count
        if not exit_reason_alignment_contract_trade_count_matched:
            blockers.append("exit_reason_alignment_contract_trade_count_mismatch")
    if fill_ledger_evidence_present and return_summary_present:
        fill_ledger_return_count_matched = fill_ledger_trade_count == return_checked_count
        if not fill_ledger_return_count_matched:
            blockers.append("fill_ledger_trade_count_mismatch")
    if expected_trade_count > 0 and fill_ledger_evidence_present:
        fill_ledger_contract_trade_count_matched = fill_ledger_trade_count == expected_trade_count
        if not fill_ledger_contract_trade_count_matched:
            blockers.append("fill_ledger_contract_trade_count_mismatch")
    if cost_evidence_present and return_summary_present:
        cost_return_count_matched = cost_applied_trade_count == return_checked_count
        if not cost_return_count_matched:
            blockers.append("fee_tax_slippage_applied_trade_count_mismatch")
    if expected_trade_count > 0 and cost_evidence_present:
        cost_contract_trade_count_matched = cost_applied_trade_count == expected_trade_count
        if not cost_contract_trade_count_matched:
            blockers.append("fee_tax_slippage_contract_trade_count_mismatch")

    accepted = not blockers
    return {
        "ok": True,
        "source": "codexstock_stage2_result_gate",
        "accepted_for_promotion": accepted,
        "state": "accepted_for_stage2_promotion" if accepted else "blocked_before_promotion",
        "blockers": blockers,
        "warnings": warnings,
        "checks": {
            "exact_hash_match": exact_hash_match,
            "prefix_hash_match": prefix_hash_match,
            "contract_schema_version_echo_present": bool(contract_schema_version_echo),
            "contract_schema_version_matched": contract_schema_version_matched,
            "idempotency_key_echo_present": bool(idempotency_key_echo),
            "idempotency_key_matched": idempotency_key_matched,
            "replay_id_echo_present": bool(replay_id_echo),
            "replay_id_matched": replay_id_matched,
            "stage2_action_expected": expected_stage2_action,
            "stage2_action_echo": stage2_action_echo,
            "stage2_action_matched": stage2_action_matched,
            "preferred_package_id_expected": expected_preferred_package_id,
            "preferred_package_id_echo": preferred_package_id_echo,
            "preferred_package_id_matched": preferred_package_id_matched,
            "preferred_package_source_expected": expected_preferred_package_source,
            "preferred_package_source_echo": preferred_package_source_echo,
            "preferred_package_source_matched": preferred_package_source_matched,
            "external_engine_name": external_engine_name,
            "external_run_id_present": bool(external_run_id),
            "external_run_id_length": external_run_id_len,
            "external_run_id_format_valid": external_run_id_format_valid,
            "external_run_id_placeholder": external_run_id_placeholder,
            "external_run_id_expected_contract_hash_prefix": expected_hash_prefix,
            "external_run_id_contract_hash_prefix_matched": external_run_id_contract_hash_prefix_matched,
            "external_run_id_expected_replay_id": expected_replay_id,
            "external_run_id_replay_id_matched": external_run_id_replay_id_matched,
            "external_runtime_mode_expected": expected_external_runtime_mode,
            "external_runtime_mode_echo": external_runtime_mode_echo,
            "external_runtime_mode_matched": external_runtime_mode_matched,
            "external_runtime_mode_has_on_demand_marker": external_runtime_mode_has_on_demand_token,
            "external_runtime_mode_unsafe_marker": external_runtime_mode_unsafe_token,
            "external_runtime_budget_evidence_present": runtime_budget_evidence_present,
            "external_runtime_budget_missing_fields": runtime_budget_missing_fields,
            "external_runtime_expected_timeout_seconds": expected_timeout_seconds,
            "external_runtime_timeout_seconds": runtime_budget_timeout_seconds,
            "external_runtime_timeout_matched": runtime_budget_timeout_matched,
            "external_runtime_actual_seconds": runtime_budget_actual_seconds,
            "external_runtime_actual_within_timeout": runtime_budget_actual_within_timeout,
            "external_runtime_expected_max_concurrent_jobs": expected_max_concurrent_external_jobs,
            "external_runtime_max_concurrent_jobs": runtime_budget_max_concurrent_external_jobs,
            "external_runtime_max_concurrent_matched": runtime_budget_max_concurrent_matched,
            "external_runtime_cleanup_evidence_present": runtime_cleanup_evidence_present,
            "external_runtime_cleanup_missing_fields": runtime_cleanup_missing_fields,
            "external_runtime_cleanup_completed": runtime_cleanup_completed,
            "external_runtime_resident_process_count": runtime_cleanup_resident_process_count,
            "external_runtime_resident_process_count_ok": runtime_cleanup_resident_process_count_ok,
            "external_runtime_expected_max_temp_artifact_bytes": expected_max_temp_artifact_bytes,
            "external_runtime_temp_artifact_bytes": runtime_cleanup_temp_artifact_bytes,
            "external_runtime_temp_artifact_within_budget": runtime_cleanup_temp_artifact_within_budget,
            "external_runtime_max_temp_artifact_bytes": runtime_cleanup_max_temp_artifact_bytes,
            "external_runtime_max_temp_artifact_matched": runtime_cleanup_max_temp_artifact_matched,
            "no_live_order_proof": no_live_order_proof,
            "no_live_order_evidence_present": no_live_order_evidence_present,
            "no_live_order_evidence_missing_fields": no_live_order_evidence_missing_fields,
            "no_live_order_order_api_call_count": order_api_call_count,
            "no_live_order_live_order_allowed": live_order_allowed_evidence,
            "no_live_order_account_route_disabled": account_route_disabled,
            "no_live_order_broker_order_id_count": broker_order_id_count,
            "no_live_order_account_mutation_count": account_mutation_count,
            "no_live_order_position_mutation_count": position_mutation_count,
            "no_live_order_mutation_audit_source": mutation_audit_source,
            "no_live_order_mutation_audit_scope": mutation_audit_scope,
            "no_live_order_mutation_audit_source_placeholder": mutation_audit_source_placeholder,
            "no_live_order_mutation_audit_scope_covers_account_position": mutation_audit_scope_covers_account_position,
            "no_live_order_runtime_mode": no_live_order_runtime_mode,
            "no_live_order_runtime_mode_has_safe_marker": no_live_order_runtime_mode_has_safe_token,
            "no_live_order_runtime_mode_unsafe_marker": no_live_order_runtime_mode_unsafe_token,
            "no_live_order_runtime_mode_safe": no_live_order_runtime_mode_safe,
            "snapshot_hash_matched": snapshot_hash_matched,
            "contract_sample_symbols_present": bool(expected_sample_symbols),
            "contract_sample_symbols": expected_sample_symbols,
            "contract_sample_symbol_format_valid": not contract_sample_symbol_invalid,
            "contract_sample_symbol_invalid": contract_sample_symbol_invalid,
            "snapshot_hash_evidence_present": snapshot_evidence_present,
            "snapshot_hash_evidence_missing_fields": snapshot_evidence_missing_fields,
            "snapshot_expected_id": expected_snapshot_id,
            "snapshot_actual_id": actual_snapshot_id,
            "snapshot_id_matched": snapshot_id_matched,
            "dataset_hash_expected_prefix": expected_dataset_hash_prefix,
            "dataset_hash_actual_prefix": actual_dataset_hash_prefix,
            "dataset_hash_prefix_matched": dataset_hash_prefix_matched,
            "snapshot_price_expected_currency": expected_unit_currency,
            "snapshot_price_currency": actual_snapshot_price_currency,
            "snapshot_price_currency_matched": snapshot_price_currency_matched,
            "snapshot_price_expected_quote_unit": expected_unit_quote_unit,
            "snapshot_price_quote_unit": actual_snapshot_price_quote_unit,
            "snapshot_price_quote_unit_canonical": actual_snapshot_price_quote_unit_canonical,
            "snapshot_price_quote_unit_matched": snapshot_price_quote_unit_matched,
            "snapshot_expected_scope": expected_snapshot_scope,
            "snapshot_scope": actual_snapshot_scope,
            "snapshot_scope_matched": snapshot_scope_matched,
            "snapshot_expected_source": expected_snapshot_source,
            "snapshot_source": actual_snapshot_source,
            "snapshot_source_matched": snapshot_source_matched,
            "snapshot_expected_sample_symbols": expected_sample_symbols,
            "snapshot_sample_symbols": actual_snapshot_symbols,
            "snapshot_symbol_missing": snapshot_symbol_missing,
            "snapshot_symbol_coverage_matched": snapshot_symbol_coverage_matched,
            "fees_taxes_slippage_applied": fees_taxes_slippage_applied,
            "fee_tax_slippage_evidence_present": cost_evidence_present,
            "fee_tax_slippage_evidence_missing_fields": cost_evidence_missing_fields,
            "fee_tax_slippage_profile_matched": cost_profile_matched,
            "fee_tax_slippage_expected_profile_id": contract_cost_profile.get("profile_id", ""),
            "fee_tax_slippage_actual_profile_id": cost_evidence.get("profile_id", "") if isinstance(cost_evidence, dict) else "",
            "fee_tax_slippage_expected_currency": contract_cost_profile.get("currency", ""),
            "fee_tax_slippage_actual_currency": cost_evidence.get("currency", "") if isinstance(cost_evidence, dict) else "",
            "fee_tax_slippage_currency_matched": cost_currency_matched,
            "fee_tax_slippage_applied_trade_count": cost_applied_trade_count,
            "fee_tax_slippage_expected_trade_count": expected_trade_count,
            "fee_tax_slippage_contract_trade_count_matched": cost_contract_trade_count_matched,
            "fee_tax_slippage_expected_sample_symbols": expected_sample_symbols,
            "fee_tax_slippage_applied_symbols": cost_applied_symbols,
            "fee_tax_slippage_symbol_missing": cost_symbol_missing,
            "fee_tax_slippage_symbol_coverage_matched": cost_symbol_coverage_matched,
            "fee_tax_slippage_fill_ledger_hash": cost_fill_ledger_hash,
            "fee_tax_slippage_fill_ledger_hash_matched": cost_fill_ledger_hash_matched,
            "fee_tax_slippage_return_count_matched": cost_return_count_matched,
            "one_engine_pass": one_engine_pass,
            "entry_exit_return_reason_evidence_present": evidence_present,
            "entry_exit_return_reason_evidence_missing_fields": evidence_missing_fields,
            "entry_exit_return_reason_same_engine_confirmed": evidence_same_engine_confirmed,
            "entry_exit_price_expected_currency": expected_unit_currency,
            "entry_exit_price_currency": evidence_price_currency,
            "entry_exit_price_currency_matched": evidence_price_currency_matched,
            "entry_exit_price_expected_quote_unit": expected_unit_quote_unit,
            "entry_exit_price_quote_unit": evidence_price_quote_unit,
            "entry_exit_price_quote_unit_canonical": evidence_price_quote_unit_canonical,
            "entry_exit_price_quote_unit_matched": evidence_price_quote_unit_matched,
            "entry_exit_price_expected_snapshot_id": expected_snapshot_id,
            "entry_exit_price_snapshot_id": evidence_price_snapshot_id,
            "entry_exit_price_snapshot_id_matched": evidence_price_snapshot_id_matched,
            "entry_exit_price_expected_dataset_hash_prefix": expected_dataset_hash_prefix,
            "entry_exit_price_dataset_hash_prefix": evidence_price_dataset_hash_prefix,
            "entry_exit_price_dataset_hash_prefix_matched": evidence_price_dataset_hash_prefix_matched,
            "entry_exit_price_expected_snapshot_scope": expected_snapshot_scope,
            "entry_exit_price_snapshot_scope": evidence_price_snapshot_scope,
            "entry_exit_price_snapshot_scope_matched": evidence_price_snapshot_scope_matched,
            "entry_exit_price_expected_snapshot_source": expected_snapshot_source,
            "entry_exit_price_snapshot_source": evidence_price_snapshot_source,
            "entry_exit_price_snapshot_source_matched": evidence_price_snapshot_source_matched,
            "entry_exit_price_expected_sample_symbols": expected_sample_symbols,
            "entry_exit_price_sample_symbols": evidence_price_sample_symbols,
            "entry_exit_price_symbol_missing": evidence_price_symbol_missing,
            "entry_exit_price_symbol_coverage_matched": evidence_price_symbol_coverage_matched,
            "entry_exit_fill_ledger_hash": evidence_fill_ledger_hash,
            "entry_exit_fill_ledger_hash_matched": evidence_fill_ledger_hash_matched,
            "entry_exit_pnl_expected_pct": round(evidence_pnl_expected_pct, 6),
            "entry_exit_pnl_reported_pct": round(evidence_pnl_reported_pct, 6),
            "entry_exit_pnl_diff_pct": round(evidence_pnl_diff_pct, 6),
            "entry_exit_pnl_tolerance_pct": evidence_pnl_tolerance_pct,
            "entry_exit_pnl_reconciled": evidence_pnl_reconciled,
            "exit_reason_threshold_pct": exit_reason_threshold_pct,
            "exit_reason_threshold_required": exit_reason_threshold_required,
            "exit_reason_threshold_expected_pct": round(exit_reason_threshold_expected_pct, 6),
            "exit_reason_threshold_diff_pct": round(exit_reason_threshold_diff_pct, 6),
            "exit_reason_threshold_tolerance_pct": exit_reason_threshold_tolerance_pct,
            "exit_reason_threshold_reconciled": exit_reason_threshold_reconciled,
            "threshold_execution_explained": threshold_execution_explained,
            "threshold_execution_explanation_present": bool(threshold_execution_explanation),
            "unit_currency_audit_evidence_present": unit_evidence_present,
            "unit_currency_audit_evidence_missing_fields": unit_evidence_missing_fields,
            "unit_currency_audit_evidence_status": unit_evidence_status,
            "unit_currency_expected_currency": expected_unit_currency,
            "unit_currency_currency": unit_currency,
            "unit_currency_currency_matched": unit_currency_matched,
            "unit_currency_expected_quote_unit": expected_unit_quote_unit,
            "unit_currency_expected_quote_unit_canonical": expected_unit_quote_unit_canonical,
            "unit_currency_quote_unit": unit_quote_unit,
            "unit_currency_quote_unit_canonical": unit_quote_unit_canonical,
            "unit_currency_quote_unit_matched": unit_quote_unit_matched,
            "unit_currency_split_adjustment_required": unit_split_adjustment_required,
            "unit_currency_split_adjustment_checked": unit_split_adjustment_checked,
            "unit_currency_audit_status": unit_status,
            "exit_reason_alignment": exit_reason_alignment,
            "exit_reason_alignment_evidence_present": exit_reason_alignment_evidence_present,
            "exit_reason_alignment_evidence_missing_fields": exit_reason_alignment_evidence_missing_fields,
            "exit_reason_alignment_checked_count": exit_reason_alignment_checked_count,
            "exit_reason_alignment_expected_trade_count": expected_trade_count,
            "exit_reason_alignment_contract_trade_count_matched": exit_reason_alignment_contract_trade_count_matched,
            "exit_reason_alignment_matched_count": exit_reason_alignment_matched_count,
            "exit_reason_alignment_mismatch_count": exit_reason_alignment_mismatch_count,
            "exit_reason_alignment_expected_sample_symbols": expected_sample_symbols,
            "exit_reason_alignment_checked_symbols": exit_reason_alignment_symbols,
            "exit_reason_alignment_symbol_missing": exit_reason_alignment_symbol_missing,
            "exit_reason_alignment_symbol_coverage_matched": exit_reason_alignment_symbol_coverage_matched,
            "exit_reason_alignment_fill_ledger_hash": exit_reason_alignment_fill_ledger_hash,
            "exit_reason_alignment_fill_ledger_hash_matched": exit_reason_alignment_fill_ledger_hash_matched,
            "exit_reason_alignment_return_count_matched": exit_reason_alignment_return_count_matched,
            "fill_ledger_hash_present": bool(fill_ledger_hash),
            "fill_ledger_hash_format_valid": fill_ledger_hash_format_valid,
            "fill_ledger_hash_placeholder": fill_ledger_hash_placeholder,
            "fill_ledger_evidence_present": fill_ledger_evidence_present,
            "fill_ledger_evidence_missing_fields": fill_ledger_evidence_missing_fields,
            "fill_ledger_evidence_hash": fill_ledger_evidence_hash,
            "fill_ledger_evidence_hash_matched": fill_ledger_evidence_hash_matched,
            "fill_ledger_trade_count": fill_ledger_trade_count,
            "fill_ledger_return_count_matched": fill_ledger_return_count_matched,
            "fill_ledger_expected_trade_count": expected_trade_count,
            "fill_ledger_contract_trade_count_matched": fill_ledger_contract_trade_count_matched,
            "fill_ledger_expected_sample_symbols": expected_sample_symbols,
            "fill_ledger_trade_symbols": fill_ledger_symbols,
            "fill_ledger_symbol_missing": fill_ledger_symbol_missing,
            "fill_ledger_symbol_coverage_matched": fill_ledger_symbol_coverage_matched,
            "return_reconciliation_summary_present": return_summary_present,
            "return_reconciliation_summary_incomplete": return_summary_incomplete,
            "return_reconciliation_needs_review": return_needs_review,
            "return_reconciliation_blocker_count": return_blocker_count,
            "return_reconciliation_warning_count": return_warning_count,
            "return_reconciliation_checked_count": return_checked_count,
            "return_reconciliation_expected_trade_count": expected_trade_count,
            "return_reconciliation_contract_trade_count_matched": return_contract_trade_count_matched,
            "return_reconciliation_expected_sample_symbols": expected_sample_symbols,
            "return_reconciliation_checked_symbols": return_checked_symbols,
            "return_reconciliation_symbol_missing": return_symbol_missing,
            "return_reconciliation_symbol_coverage_matched": return_symbol_coverage_matched,
            "return_reconciliation_ok_count": return_ok_count,
            "return_reconciliation_mismatch_count": return_mismatch_count,
            "return_reconciliation_fill_ledger_hash": return_summary_fill_ledger_hash,
            "return_reconciliation_fill_ledger_hash_matched": return_summary_fill_ledger_hash_matched,
        },
        "matched_contract": {
            "found": bool(matched_job),
            "stage2_job_id": matched_job.get("stage2_job_id", "") if matched_job else "",
            "contract_schema_version": expected_contract_schema_version,
            "contract_hash_prefix": expected_hash_prefix,
            "replay_id": matched_job.get("replay_id", "") if matched_job else "",
            "stage2_action": matched_job.get("stage2_action", "") if matched_job else "",
            "preferred_package_id": matched_job.get("preferred_package_id", "") if matched_job else "",
            "external_runtime_mode": matched_job.get("external_runtime_mode", "") if matched_job else "",
            "timeout_seconds": matched_job.get("timeout_seconds", "") if matched_job else "",
            "max_concurrent_external_jobs": matched_job.get("max_concurrent_external_jobs", "") if matched_job else "",
            "max_temp_artifact_bytes": matched_job.get("max_temp_artifact_bytes", "") if matched_job else "",
            "preferred_package_source": matched_job.get("preferred_package_source", "") if matched_job else "",
            "required_snapshot_id": matched_job.get("required_snapshot_id", "") if matched_job else "",
            "required_snapshot_scope": matched_job.get("required_snapshot_scope", "") if matched_job else "",
            "required_snapshot_source": matched_job.get("required_snapshot_source", "") if matched_job else "",
            "dataset_hash_prefix": matched_job.get("dataset_hash_prefix", "") if matched_job else "",
            "sample_symbols": matched_job.get("sample_symbols", []) if matched_job else [],
            "trade_count": matched_job.get("trade_count", "") if matched_job else "",
        },
        "required_policy": {
            "requires_exact_contract_hash_echo": True,
            "requires_contract_schema_version_echo": True,
            "requires_contract_identity_echo": True,
            "requires_stage2_action_echo": True,
            "requires_preferred_package_identity_echo": True,
            "requires_external_engine_identity": True,
            "requires_external_run_id_quality": True,
            "requires_external_run_id_contract_binding": True,
            "requires_external_run_id_replay_binding": True,
            "requires_external_runtime_mode_echo": True,
            "requires_on_demand_external_runtime": True,
            "requires_external_runtime_budget_evidence": True,
            "requires_external_runtime_cleanup_evidence": True,
            "requires_no_live_order_proof": True,
            "requires_no_live_order_evidence": True,
            "requires_no_live_order_empty_broker_order_ids": True,
            "requires_no_live_order_no_account_position_mutations": True,
            "requires_no_live_order_mutation_audit_source": True,
            "rejects_unsafe_runtime_mode_markers": True,
            "requires_snapshot_hash_evidence": True,
            "requires_contract_sample_symbols": True,
            "requires_contract_sample_symbol_format": True,
            "requires_snapshot_provenance_evidence": True,
            "requires_snapshot_symbol_coverage_evidence": True,
            "requires_snapshot_price_unit_evidence": True,
            "requires_fee_tax_slippage_confirmation": True,
            "requires_fee_tax_slippage_evidence": True,
            "requires_fee_tax_slippage_currency_match": True,
            "requires_fee_tax_slippage_applied_trade_count": True,
            "requires_fee_tax_slippage_symbol_coverage": True,
            "requires_fee_tax_slippage_fill_ledger_hash": True,
            "requires_fee_tax_slippage_return_count_match": True,
            "requires_fee_tax_slippage_contract_trade_count_match": True,
            "requires_one_engine_entry_exit_reason_return": True,
            "requires_entry_exit_return_reason_evidence": True,
            "requires_entry_exit_price_unit_evidence": True,
            "requires_entry_exit_price_snapshot_echo": True,
            "requires_entry_exit_price_snapshot_provenance": True,
            "requires_entry_exit_symbol_coverage": True,
            "requires_entry_exit_fill_ledger_hash": True,
            "requires_fill_ledger_hash_format": True,
            "rejects_fill_ledger_hash_placeholders": True,
            "requires_fill_ledger_evidence": True,
            "requires_fill_ledger_symbol_coverage": True,
            "requires_fill_ledger_return_count_match": True,
            "requires_fill_ledger_contract_trade_count_match": True,
            "requires_return_reconciliation_counts": True,
            "requires_return_reconciliation_fill_ledger_hash": True,
            "requires_return_reconciliation_contract_trade_count_match": True,
            "requires_return_reconciliation_symbol_coverage": True,
            "requires_exit_reason_alignment_evidence": True,
            "requires_exit_reason_alignment_fill_ledger_hash": True,
            "requires_exit_reason_alignment_return_count_match": True,
            "requires_exit_reason_alignment_contract_trade_count_match": True,
            "requires_exit_reason_alignment_symbol_coverage": True,
            "requires_unit_currency_audit_evidence": True,
            "requires_unit_currency_policy_match": True,
            "live_order_allowed": False,
        },
        "mcp_server_manifest": _mcp_manifest(),
    }


def _tool(name: str, description: str, properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    schema_properties = dict(properties or {})
    schema_properties.setdefault(
        "max_chars",
        {
            "type": "integer",
            "minimum": 2000,
            "maximum": HARD_TOOL_RESULT_MAX_CHARS,
            "default": DEFAULT_TOOL_RESULT_MAX_CHARS,
            "description": "응답 JSON의 최대 문자 수",
        },
    )
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": schema_properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool("research_forge_status", "Return local Research Forge status and immutable research-only safety policy.", {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}}),
    _tool("research_forge_doctor", "Run local Research Forge safety, registry, and adapter diagnostics.", {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}}),
    _tool("research_forge_readiness", "Evaluate operational, research-evidence, and full-spec readiness without enabling live trading.", {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "analytical"}}),
    _tool("research_forge_mcp_manifest", "Return the Research Forge sub-engine manifest."),
    _tool("research_corporate_action_adjust", "Backward-adjust OHLCV for official KRX splits, reverse splits, cash dividends, or rights issues and return an immutable adjustment ledger.", {"rows": {"type": "array", "items": {"type": "object"}, "minItems": 2, "maxItems": 10000}, "actions": {"type": "array", "items": {"type": "object"}, "minItems": 1, "maxItems": 100}}, ["rows", "actions"]),
    _tool("research_corporate_action_status", "Return integrity-verified official corporate-action datasets and completeness declarations."),
    _tool("research_corporate_action_register", "Persist an official-source corporate-action history with a deterministic content hash.", {"dataset_id": {"type": "string"}, "symbol": {"type": "string"}, "actions": {"type": "array", "items": {"type": "object"}, "minItems": 1, "maxItems": 10000}, "complete_history": {"type": "boolean", "default": False}}, ["dataset_id", "symbol", "actions"]),
    _tool("research_corporate_action_register_verified", "Download each KRX/KIND source document read-only, verify its exact SHA-256, and then persist the corporate-action history.", {"dataset_id": {"type": "string"}, "symbol": {"type": "string"}, "actions": {"type": "array", "items": {"type": "object"}, "minItems": 1, "maxItems": 1000}, "complete_history": {"type": "boolean", "default": False}, "history_start": {"type": "string", "default": ""}, "history_end": {"type": "string", "default": ""}, "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 60, "default": 15}, "max_document_bytes": {"type": "integer", "minimum": 1024, "maximum": 50000000, "default": 10000000}, "attempts": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3}}, ["dataset_id", "symbol", "actions"]),
    _tool("research_corporate_action_query", "Query a registered corporate-action dataset over an inclusive effective-date range.", {"dataset_id": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}, ["dataset_id"]),
    _tool("research_corporate_action_adjust_registered", "Backward-adjust OHLCV using only actions from an integrity-verified registered dataset.", {"dataset_id": {"type": "string"}, "rows": {"type": "array", "items": {"type": "object"}, "minItems": 2, "maxItems": 10000}}, ["dataset_id", "rows"]),
    _tool("research_corporate_action_reconcile", "Audit expected symbols against complete source-verified corporate-action coverage without placing orders.", {"symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5000}, "coverage_start": {"type": "string"}, "coverage_end": {"type": "string"}}, ["symbols", "coverage_start", "coverage_end"]),
    _tool("research_instrument_contracts", "List strict research data contracts for Korean and US equities and ETFs, including currency, quote unit, timezone, lot size, and provider boundaries."),
    _tool("research_instrument_validate", "Validate one market snapshot against its market, asset, currency, quote-unit, timestamp, lot-size, and provider contract.", {"snapshot": {"type": "object"}}, ["snapshot"]),
    _tool("research_shard_batch_create", "Create a durable research-only batch split into integrity-hashed shards for independent workers.", {"job_type": {"type": "string"}, "payloads": {"type": "array", "items": {"type": "object"}, "minItems": 1, "maxItems": 10000}}, ["job_type", "payloads"]),
    _tool("research_shard_claim", "Atomically claim one pending research shard with a bounded worker lease.", {"batch_id": {"type": "string"}, "worker_id": {"type": "string"}, "lease_seconds": {"type": "integer", "minimum": 30, "maximum": 3600, "default": 300}}, ["batch_id", "worker_id"]),
    _tool("research_shard_heartbeat", "Refresh ownership of a running research shard.", {"batch_id": {"type": "string"}, "shard_id": {"type": "string"}, "worker_token": {"type": "string"}}, ["batch_id", "shard_id", "worker_token"]),
    _tool("research_shard_finish", "Persist a hashed research shard result or safely requeue/fail it; never executes orders.", {"batch_id": {"type": "string"}, "shard_id": {"type": "string"}, "worker_token": {"type": "string"}, "result": {"type": "object"}, "error": {"type": "string", "default": ""}, "retryable": {"type": "boolean", "default": False}}, ["batch_id", "shard_id", "worker_token"]),
    _tool("research_shard_status", "Verify and summarize a durable distributed research batch.", {"batch_id": {"type": "string"}}, ["batch_id"]),
    _tool("research_stability_record", "Append an integrity-chained read-only snapshot of every sub-engine for long-term reliability evidence.", {"dashboard": {"type": "object"}, "min_interval_seconds": {"type": "integer", "minimum": 1, "maximum": 86400, "default": 300}}, ["dashboard"]),
    _tool("research_stability_audit", "Audit sub-engine success ratios, observation gaps, contract drift, and consecutive failures over time.", {"window_days": {"type": "integer", "minimum": 1, "maximum": 3650, "default": 30}, "max_gap_seconds": {"type": "integer", "minimum": 1, "maximum": 86400, "default": 900}}),
    _tool("research_strategy_validate", "Validate a research-only strategy definition without executing it.", {"strategy": {"type": "object", "additionalProperties": True}}, ["strategy"]),
    _tool(
        "research_experiment_create",
        "Create a reproducible Research Forge experiment. Does not execute or submit orders.",
        {
            "adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"},
            "strategy": {"type": "object", "additionalProperties": True},
            "data_snapshot": {"type": "object", "additionalProperties": True},
            "execution_model": {"type": "object", "additionalProperties": True},
        },
        ["strategy", "data_snapshot"],
    ),
    _tool("research_experiment_get", "Get one Research Forge experiment by id.", {"experiment_id": {"type": "string"}}, ["experiment_id"]),
    _tool("research_experiment_list", "List recent Research Forge experiments.", {"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}}),
    _tool("research_lifecycle_readiness", "Evaluate evidence gates for manual research-only PAPER_CANDIDATE nomination.", {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "experiment_id": {"type": "string"}}, ["experiment_id"]),
    _tool("research_lifecycle_review", "Record a manual nominate/reject/more-data/archive decision, update state, and create a research-only meeting card.", {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "experiment_id": {"type": "string"}, "action": {"type": "string", "enum": ["NOMINATE_PAPER", "REJECT", "NEEDS_MORE_DATA", "ARCHIVE"]}, "reviewer": {"type": "string"}, "rationale": {"type": "string"}, "confirmation": {"type": "string", "description": "NOMINATE_PAPER requires I_CONFIRM_RESEARCH_ONLY_PAPER_CANDIDATE."}}, ["experiment_id", "action", "reviewer", "rationale"]),
    _tool("research_lifecycle_history", "Verify and return the hash-chained research decision audit log.", {"experiment_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100}}),
    _tool(
        "research_backtest_run",
        "Run an existing experiment through a research-only backtest adapter. Live orders are structurally forbidden.",
        {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "experiment_id": {"type": "string"}},
        ["experiment_id"],
    ),
    _tool(
        "research_walk_forward_run",
        "Run chronological out-of-period folds for an existing research experiment.",
        {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "experiment_id": {"type": "string"}, "folds": {"type": "integer", "minimum": 2, "maximum": 10, "default": 4}},
        ["experiment_id"],
    ),
    _tool(
        "research_strict_walk_forward_run",
        "Select parameters on anchored training windows and evaluate only on following unused windows, with optional purge and embargo gaps for overlapping labels.",
        {
            "adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"},
            "experiment_id": {"type": "string"},
            "folds": {"type": "integer", "minimum": 2, "maximum": 8, "default": 3},
            "fast_values": {"type": "array", "items": {"type": "integer", "minimum": 2, "maximum": 250}, "maxItems": 12},
            "slow_values": {"type": "array", "items": {"type": "integer", "minimum": 3, "maximum": 250}, "maxItems": 12},
            "purge_days": {"type": "integer", "minimum": 0, "maximum": 365, "default": 0},
            "embargo_days": {"type": "integer", "minimum": 0, "maximum": 365, "default": 0},
            "purge_rows": {"type": "integer", "minimum": 0, "maximum": 10000, "default": 0},
            "embargo_rows": {"type": "integer", "minimum": 0, "maximum": 10000, "default": 0},
        },
        ["experiment_id"],
    ),
    _tool("research_storage_status", "Return DuckDB/Parquet analytical storage readiness and bounded summary."),
    _tool("research_storage_import_collection", "Import normalized collection JSON files into deduplicated DuckDB bars."),
    _tool(
        "research_storage_import_legacy_ohlcv",
        "Stream a legacy OHLCV cache into DuckDB without loading the full JSON file into memory.",
        {"cache_name": {"type": "string"}, "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 3000}, "max_symbols": {"type": "integer", "minimum": 0, "maximum": 3000, "default": 0}},
    ),
    _tool(
        "research_storage_query",
        "Query bounded OHLCV ranges from DuckDB by symbols, timeframe, and timestamps.",
        {"symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 1000}, "start": {"type": "string"}, "end": {"type": "string"}, "timeframe": {"type": "string", "default": "1d"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 10000}},
        ["start", "end"],
    ),
    _tool("research_storage_export_parquet", "Export DuckDB bars to ZSTD Parquet partitioned by timeframe/year/month/symbol bucket."),
    _tool(
        "research_async_submit",
        "Queue a persistent background backtest, strict walk-forward, collection, or microstructure worker job.",
        {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "job_type": {"type": "string", "enum": ["backtest", "strict_walk_forward", "collection", "microstructure"]}, "payload": {"type": "object"}},
        ["job_type", "payload"],
    ),
    _tool("research_async_status", "Get persistent async job progress or recent queue state.", {"job_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}}),
    _tool("research_async_cancel", "Request cancellation of a queued or running Research Forge job.", {"job_id": {"type": "string"}}, ["job_id"]),
    _tool("research_async_retry", "Retry a failed, cancelled, or process-interrupted job from its persisted payload.", {"job_id": {"type": "string"}}, ["job_id"]),
    _tool("research_async_resume_interrupted", "Detect dead worker owners, atomically claim their jobs, and resume them from persisted payloads.", {"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}, "orphan_grace_seconds": {"type": "number", "minimum": 0, "maximum": 3600, "default": 30}}),
    _tool("research_performance_run", "Run and persist bounded DuckDB-query and all-indicator performance gates.", {"indicator_row_count": {"type": "integer", "minimum": 1000, "maximum": 250000, "default": 100000}}),
    _tool("research_execution_manifest", "Return optimistic, realistic, and conservative fill assumptions including VI and queue policies."),
    _tool("research_execution_compare", "Apply identical signals under all three execution modes for sensitivity analysis.", {"rows": {"type": "array", "items": {"type": "object"}, "maxItems": 5000}, "entry_signals": {"type": "array", "items": {"type": "boolean"}, "maxItems": 5000}, "exit_signals": {"type": "array", "items": {"type": "boolean"}, "maxItems": 5000}, "base_model": {"type": "object"}}, ["rows", "entry_signals", "exit_signals"]),
    _tool("research_custom_indicator_register", "Register an immutable non-executable custom indicator after golden, determinism, and no-future-data checks.", {"definition": {"type": "object"}}, ["definition"]),
    _tool("research_custom_indicator_list", "List verified custom indicator definitions."),
    _tool("research_custom_indicator_calculate", "Calculate a verified custom indicator version.", {"name": {"type": "string"}, "version": {"type": "string"}, "rows": {"type": "array", "items": {"type": "object"}, "maxItems": 5000}}, ["name", "version", "rows"]),
    _tool("research_multitimeframe_backtest", "Align only completed higher-timeframe bars to an execution timeframe and run a research-only next-bar backtest.", {"rules": {"type": "object"}, "rows_by_context": {"type": "object"}, "execution_model": {"type": "object"}}, ["rules", "rows_by_context", "execution_model"]),
    _tool("research_concurrency_soak", "Run concurrent collection, DuckDB writes/reads, indicators, and a compatible stored backtest with persistent evidence.", {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "analytical"}, "iterations": {"type": "integer", "minimum": 2, "maximum": 100, "default": 20}}),
    _tool(
        "research_robustness_run",
        "Test neighboring strategy parameters to detect brittle optimization.",
        {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "experiment_id": {"type": "string"}, "radius": {"type": "integer", "minimum": 1, "maximum": 5, "default": 2}},
        ["experiment_id"],
    ),
    _tool(
        "research_experiment_compare",
        "Compare two or more Research Forge experiments and report whether their dataset and adapter are comparable.",
        {"adapter": {"type": "string", "enum": ["ohlcv", "analytical", "native", "mock"], "default": "ohlcv"}, "experiment_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 20}},
        ["experiment_ids"],
    ),
    _tool(
        "research_replay_get",
        "Return read-only trades and equity events for replaying a Research Forge experiment.",
        {"experiment_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500}},
        ["experiment_id"],
    ),
    _tool(
        "research_replay_create",
        "Create an immutable multi-timeframe bars, tick, orderbook, flow, and trade replay timeline.",
        {"experiment_id": {"type": "string"}, "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 100}, "start": {"type": "string"}, "end": {"type": "string"}, "timeframes": {"type": "array", "items": {"type": "string"}, "maxItems": 10}, "max_events": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 50000}, "microstructure_source": {"type": "string", "enum": ["live", "archive", "hybrid"], "default": "hybrid"}},
        ["experiment_id", "start", "end"],
    ),
    _tool(
        "research_replay_page",
        "Read a cursor page from an immutable replay and reconstruct chart, orderbook, and position state.",
        {"session_id": {"type": "string"}, "cursor": {"type": "integer", "minimum": 0, "default": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500}},
        ["session_id"],
    ),
    _tool("research_replay_verify", "Recompute and verify a replay's full frame-file, index, event-count, frame-ID, and timeline hashes.", {"session_id": {"type": "string"}}, ["session_id"]),
    _tool(
        "research_report_export",
        "Export an evidence-hashed Research Forge report bundle as JSON, Markdown, Excel, and CSV.",
        {"experiment_id": {"type": "string"}},
        ["experiment_id"],
    ),
    _tool("research_report_verify", "Verify report artifacts against their manifest and current experiment record.", {"experiment_id": {"type": "string"}}, ["experiment_id"]),
    _tool("research_microstructure_status", "Return local tick/orderbook/program-flow checkpoint status. Does not contact providers."),
    _tool("research_microstructure_provider_status", "Return KIS read-only polling capabilities and explicitly unavailable feeds."),
    _tool("research_microstructure_worker_status", "Return persistent polling worker checkpoints.", {"worker_id": {"type": "string"}}),
    _tool("research_microstructure_worker_start", "Run a bounded KIS read-only tick/orderbook polling worker.", {"symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 100}, "interval_seconds": {"type": "number", "minimum": 0.05, "maximum": 60, "default": 1}, "max_cycles": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1}, "gap_seconds": {"type": "integer", "minimum": 1, "maximum": 3600, "default": 10}}, ["symbols"]),
    _tool("research_microstructure_worker_resume", "Resume a KIS polling worker from its persistent checkpoint.", {"worker_id": {"type": "string"}, "max_cycles": {"type": "integer", "minimum": 1, "maximum": 100000}}, ["worker_id"]),
    _tool("research_realtime_status", "Return read-only KIS WebSocket configuration, dependency and checkpoint status."),
    _tool("research_realtime_start", "Start bounded read-only KIS WebSocket tick/order-book collection with reconnect and subscription restore.", {"symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 40}, "max_messages": {"type": "integer", "minimum": 0, "maximum": 100000, "default": 1000}, "duration_seconds": {"type": "number", "minimum": 0, "maximum": 86400, "default": 0}, "max_reconnects": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 20}, "heartbeat_timeout": {"type": "number", "minimum": 1, "maximum": 300, "default": 30}}, ["symbols"]),
    _tool("research_realtime_resume", "Resume only the remaining duration of a failed or stale read-only realtime collection and preserve run lineage.", {"max_reconnects": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 20}, "heartbeat_timeout": {"type": "number", "minimum": 1, "maximum": 300, "default": 30}}),
    _tool("research_realtime_runs", "Verify and return immutable SHA-256 evidence from bounded KIS WebSocket collection runs.", {"limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50}}),
    _tool("research_microstructure_quality", "Return duplicate and timestamp-gap quality evidence for recorded microstructure streams."),
    _tool(
        "research_microstructure_ingest",
        "Append provider-supplied tick/orderbook/program-flow events to the local research-only store. Never places orders.",
        {
            "events": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "minItems": 1, "maxItems": 5000},
            "gap_seconds": {"type": "integer", "minimum": 1, "maximum": 3600, "default": 10},
        },
        ["events"],
    ),
    _tool("research_microstructure_archive_status", "Return incremental Parquet archive coverage for microstructure events."),
    _tool("research_microstructure_archive_export", "Snapshot complete JSONL lines into immutable ZSTD Parquet chunks without blocking the live collector.", {"max_source_files": {"type": "integer", "minimum": 0, "maximum": 100000, "default": 0}}),
    _tool("research_microstructure_archive_verify", "Verify the microstructure archive manifest and every Parquet SHA-256 hash."),
    _tool("research_microstructure_archive_query", "Run a bounded DuckDB query over archived microstructure Parquet chunks.", {"symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 100}, "start": {"type": "string"}, "end": {"type": "string"}, "event_types": {"type": "array", "items": {"type": "string", "enum": ["tick", "orderbook", "program_flow"]}}, "limit": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 10000}}, ["symbols", "start", "end"]),
    _tool("research_indicator_list", "List Research Forge indicators and calculation profiles, including verification status."),
    _tool("research_hts_reference_register", "Register an immutable source-hashed LS, Kiwoom, or KIS export and verify every reference timestamp.", {"package": {"type": "object"}}, ["package"]),
    _tool("research_hts_csv_template", "Return the exact chronological OHLCV plus hts_* CSV header required for one HTS profile and indicator.", {"profile": {"type": "string", "enum": ["LS_HTS", "KIWOOM_HTS", "KIS"]}, "indicator": {"type": "string", "enum": ["SMA", "EMA", "RSI", "BOLLINGER", "ENVELOPE", "ATR", "WMA", "MACD", "ROC", "OBV", "VWAP", "STOCHASTIC", "WILLIAMS_R", "MFI", "CCI", "ADX"]}}, ["profile", "indicator"]),
    _tool("research_hts_csv_import", "Strictly parse an HTS CSV export, hash its exact text, build a reference package, and register per-indicator verification evidence.", {"csv_text": {"type": "string"}, "metadata": {"type": "object"}}, ["csv_text", "metadata"]),
    _tool("research_hts_reference_status", "Return per-indicator HTS compatibility evidence without promoting unverified profiles.", {"profile": {"type": "string", "enum": ["LS_HTS", "KIWOOM_HTS", "KIS"]}}),
    _tool(
        "research_indicator_calculate",
        "Calculate a deterministic indicator series from supplied OHLCV rows.",
        {
            "indicator": {"type": "string", "enum": ["SMA", "EMA", "RSI", "BOLLINGER", "ENVELOPE", "ATR", "WMA", "MACD", "ROC", "OBV", "VWAP", "STOCHASTIC", "WILLIAMS_R", "MFI", "CCI", "ADX"]},
            "rows": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "minItems": 2, "maxItems": 10000},
            "parameters": {"type": "object", "additionalProperties": True},
            "profile": {"type": "string", "enum": ["STANDARD", "CUTLER", "LS_HTS", "KIWOOM_HTS", "KIS"], "default": "STANDARD"},
        },
        ["indicator", "rows"],
    ),
    _tool(
        "research_indicator_verify",
        "Compare the latest calculated outputs with externally supplied HTS reference values.",
        {
            "indicator": {"type": "string", "enum": ["SMA", "EMA", "RSI", "BOLLINGER", "ENVELOPE", "ATR", "WMA", "MACD", "ROC", "OBV", "VWAP", "STOCHASTIC", "WILLIAMS_R", "MFI", "CCI", "ADX"]},
            "rows": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "minItems": 2, "maxItems": 10000},
            "parameters": {"type": "object", "additionalProperties": True},
            "profile": {"type": "string", "enum": ["STANDARD", "CUTLER", "LS_HTS", "KIWOOM_HTS", "KIS"], "default": "STANDARD"},
            "expected": {"type": "object", "additionalProperties": {"type": "number"}},
            "tolerance": {"type": "number", "minimum": 0, "default": 0.000001},
        },
        ["indicator", "rows", "expected"],
    ),
    _tool("research_universe_status", "List registered point-in-time universe datasets and hashes."),
    _tool(
        "research_universe_register",
        "Register a versioned listing/delisting symbol master as survivorship-bias evidence.",
        {
            "dataset_id": {"type": "string"},
            "source": {"type": "string"},
            "records": {"type": "array", "items": {"type": "object", "additionalProperties": True}, "minItems": 1, "maxItems": 10000},
        },
        ["dataset_id", "source", "records"],
    ),
    _tool(
        "research_universe_query",
        "Reconstruct active symbols from a registered universe at a historical date.",
        {
            "dataset_id": {"type": "string"}, "as_of": {"type": "string"},
            "markets": {"type": "array", "items": {"type": "string"}},
            "security_types": {"type": "array", "items": {"type": "string"}},
        },
        ["dataset_id", "as_of"],
    ),
    _tool(
        "research_universe_validate",
        "Verify that strategy symbols are covered by listing intervals for the entire backtest period.",
        {
            "dataset_id": {"type": "string"}, "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 50},
            "start_date": {"type": "string"}, "end_date": {"type": "string"},
        },
        ["dataset_id", "symbols", "start_date", "end_date"],
    ),
    _tool("research_universe_integrity", "Audit overlapping listing intervals, reused symbols, and official code-lineage evidence for a point-in-time universe.", {"dataset_id": {"type": "string"}}, ["dataset_id"]),
    _tool("research_collection_status", "Return Research Forge collection jobs or one checkpoint.", {"job_id": {"type": "string", "default": ""}}),
    _tool(
        "research_collection_start",
        "Start a bounded read-only collection job with persisted transient-network and rate-limit retry evidence.",
        {
            "provider": {"type": "string", "enum": ["mock", "kis"], "default": "mock"},
            "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 1000},
            "timeframe": {"type": "string", "enum": ["1d", "minute"], "default": "1d"},
            "interval": {"type": "integer", "enum": [1, 3, 5, 10, 15, 30, 60], "default": 1},
            "start": {"type": "string"}, "end": {"type": "string"},
            "max_symbols": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 1000},
            "retry_max_attempts": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            "retry_base_seconds": {"type": "number", "minimum": 0, "maximum": 30, "default": 0.25},
        },
        ["start", "end"],
    ),
    _tool("research_collection_resume", "Resume a partial mock collection job from its symbol checkpoint.", {"job_id": {"type": "string"}}, ["job_id"]),
    _tool("research_collection_storage_summary", "Return normalized bar file counts and local storage bytes."),
    _tool("research_provider_status", "Return masked, read-only provider readiness without contacting the network.", {"provider": {"type": "string", "enum": ["kis", "mock"], "default": "kis"}}),
    _tool(
        "research_universe_sync_krx",
        "Fetch and register an official KRX security-master snapshot. A single snapshot is not full historical coverage.",
        {
            "as_of": {"type": "string"}, "dataset_id": {"type": "string", "default": ""},
            "markets": {"type": "array", "items": {"type": "string", "enum": ["KOSPI", "KOSDAQ", "KONEX"]}},
        },
        ["as_of"],
    ),
    _tool(
        "research_universe_sync_kind",
        "Fetch the official current KRX KIND listed-company snapshot, register exact-date evidence, and optionally extend a snapshot chain.",
        {"as_of": {"type": "string"}, "dataset_id": {"type": "string", "default": ""}, "history_id": {"type": "string", "default": ""}},
    ),
    _tool(
        "research_universe_sync_global_history",
        "Fetch official KRX Global annual listing/delisting statistics, combine them with today's KIND snapshot, and register survivorship evidence.",
        {"start": {"type": "string", "format": "date"}, "end": {"type": "string", "format": "date"}, "dataset_id": {"type": "string", "default": ""}},
        ["start", "end"],
    ),
    _tool("research_universe_history_status", "List captured official point-in-time universe snapshot chains."),
    _tool("research_universe_history_query", "Reconstruct the symbol universe on a captured date from baseline and listing/removal/update events.", {"history_id": {"type": "string"}, "as_of": {"type": "string"}}, ["history_id", "as_of"]),
    _tool("research_universe_history_code_change", "Record a source-hashed official KRX stock-code change in a captured history.", {"history_id": {"type": "string"}, "effective_date": {"type": "string"}, "old_symbol": {"type": "string"}, "new_record": {"type": "object"}, "source_url": {"type": "string"}, "source_hash": {"type": "string"}}, ["history_id", "effective_date", "old_symbol", "new_record", "source_url", "source_hash"]),
    _tool(
        "codexstock_mcp_manifest",
        "Return the CodexStock MCP manifest and optionally persist the client's observed tool surface for exact reconciliation.",
        {
            "client_name": {"type": "string", "default": ""},
            "client_tool_names": {"type": "array", "items": {"type": "string"}, "maxItems": 500},
            "client_schema_sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
            "client_observed_at": {"type": "string", "format": "date-time"},
        },
    ),
    _tool(
        "codexstock_status",
        "Return CodexStock operating status. Defaults to an instant in-memory GPT profile; request quick or full only when needed.",
        {
            "detail": {"type": "string", "enum": ["instant", "quick", "full"], "default": "instant"},
            "full": {"type": "boolean", "default": False, "description": "Legacy alias for detail='full'."},
        },
    ),
    _tool(
        "codexstock_knowledge_curator_status",
        "지식관리 직원의 상시 실행 상태, 원본 불변 인덱스 규모, LlamaIndex·Qdrant·Graphiti·GraphRAG 준비도와 최근 실행 증거를 조회합니다.",
    ),
    _tool(
        "codexstock_knowledge_search",
        "회의·복기·연구·매매일지 검색 투영에서 근거 경로와 해시를 포함해 지식을 검색합니다. 원본 원장은 수정하지 않습니다.",
        {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        ["query"],
    ),
    _tool(
        "codexstock_knowledge_engine_plan",
        "새 근거량과 장 운영 상태에 따라 어떤 지식 하위엔진을 실행하거나 미룰지 읽기 전용으로 확인합니다.",
        {
            "changed_documents": {"type": "integer", "minimum": 0, "maximum": 1000000, "default": 0},
            "market_open": {"type": "boolean", "default": False},
            "heavy_work_allowed": {"type": "boolean", "default": False},
        },
    ),
    _tool(
        "codexstock_internal_developer_status",
        "Return current self-repair status, open incident counts, and unreviewed developer attention from the local direct store.",
    ),
    _tool(
        "codexstock_internal_developer_component_status",
        "Return internal-developer incidents for one named component. Read-only.",
        {
            "component": {"type": "string", "maxLength": 120, "default": ""},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
        },
    ),
    _tool(
        "codexstock_internal_developer_list_incidents",
        "List local operational incidents without marking reports reviewed.",
        {
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            "state": {"type": "string", "maxLength": 40, "default": ""},
            "severity": {"type": "string", "maxLength": 32, "default": ""},
        },
    ),
    _tool(
        "codexstock_internal_developer_get_incident",
        "Get one internal-developer incident and its recovery evidence. Read-only.",
        {"incident_id": {"type": "string", "pattern": "^INC-[A-Za-z0-9_-]{1,96}$"}},
        ["incident_id"],
    ),
    _tool(
        "codexstock_internal_developer_latest_report",
        "Return the latest developer escalation or recovery report without acknowledging it.",
    ),
    _tool(
        "codexstock_internal_developer_brief",
        "Return a compact GPT handoff containing health, attention, recent incidents, latest report, and activity.",
        {
            "incident_limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            "activity_limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
        },
    ),
    _tool(
        "codexstock_internal_developer_activity",
        "Return recent internal-developer audit activity. Read-only.",
        {
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            "event_type": {"type": "string", "maxLength": 64, "default": ""},
        },
    ),
    _tool(
        "codexstock_internal_developer_readonly_diagnostics",
        "Check the local internal-developer store and safety boundary without repairing, restarting, or submitting orders.",
    ),
    _tool(
        "codexstock_submit_developer_advice",
        "Store bounded GPT advice as untrusted guidance. This tool never executes the advice or grants recovery authority.",
        {
            "incident_id": {"type": "string", "pattern": "^INC-[A-Za-z0-9_-]{1,96}$"},
            "advisor": {"type": "string", "maxLength": 120, "default": "gpt-via-mcp"},
            "summary": {"type": "string", "maxLength": 4000},
            "analysis": {"type": "string", "maxLength": 16000},
            "confidence": {"type": ["number", "string", "null"]},
            "proposed_actions": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "parameters": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["action", "parameters"],
                    "additionalProperties": False,
                },
            },
        },
        ["incident_id", "summary"],
    ),
    _tool("codexstock_scorecard", "Return CodexStock maturity scorecard.", {"refresh": {"type": "boolean", "default": False}}),
    _tool(
        "codexstock_staff_status",
        "Return AI staff status. Defaults to the instant GPT profile; use full only for cumulative records.",
        {
            "detail": {"type": "string", "enum": ["instant", "quick", "full"], "default": "instant"},
            "full": {"type": "boolean", "default": False, "description": "Legacy alias for detail='full'."},
        },
    ),
    _tool(
        "codexstock_staff_meetings",
        "Return paginated AI staff meeting records. Compact summaries are the default.",
        {
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            "offset": {"type": "integer", "minimum": 0, "maximum": 200, "default": 0},
            "group": {"type": "string", "enum": ["manual", "auto"]},
            "quick": {"type": "boolean"},
            "full": {"type": "boolean", "default": False},
        },
    ),
    _tool("codexstock_live_pilot_plan", "Return live pilot candidate plan. Read-only."),
    _tool("codexstock_live_candidate_decisions", "Return live candidate include/exclude decisions. Read-only."),
    _tool("codexstock_today_trades", "Return today paper/live trade summary. Read-only."),
    _tool(
        "codexstock_live_trade_explanations",
        "Explain what was bought and sold, when, why, timing evidence, order numbers, holding time, and reconciled P/L. Read-only.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 12}},
    ),
    _tool(
        "codexstock_live_order_blackbox",
        "Return live-order decision blackboxes including staff opinions, chair decision, rejected alternatives, gate checks, and point-in-time evidence hashes. Read-only.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 8}},
    ),
    _tool("codexstock_live_reconciliation_audit", "Return read-only live order vs broker execution reconciliation audit.", {"limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 120}}),
    _tool("codexstock_radar", "Return radar summary for news, filings, finance, price, and themes.", {"force": {"type": "boolean", "default": False}}),
    _tool(
        "codexstock_screener",
        "Run/read AI screener candidates.",
        {"symbols": {"type": "string", "description": "Comma separated symbols. Empty means default universe.", "default": ""}, "force": {"type": "boolean", "default": False}},
    ),
    _tool("codexstock_sector_news", "Return sector news and theme summary.", {"force": {"type": "boolean", "default": False}}),
    _tool("codexstock_sector_committee", "Return sector-first investment committee result.", {"force": {"type": "boolean", "default": False}}),
    _tool(
        "codexstock_market_context_snapshot",
        "Return the shared verified macro, calendar, flows, FX, global-market, and market-news snapshot. Read-only; unverified evidence cannot affect scores or live candidates.",
        {"force": {"type": "boolean", "default": False}},
    ),
    _tool(
        "codexstock_market_news_evidence",
        "Return news original-source, independent-domain, and official-disclosure corroboration evidence. Read-only.",
        {
            "force": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
        },
    ),
    _tool(
        "codexstock_intraday_market_pulse",
        "Return read-only intraday turnover, volume, gainers, losers, foreign, and institution flow pulse. Does not persist or submit orders.",
        {
            "force": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30},
        },
    ),
    _tool("codexstock_feature_health", "Return feature/API/MCP health board.", {"probe": {"type": "boolean", "default": False}, "record": {"type": "boolean", "default": False}}),
    _tool("codexstock_score_saturation_audit", "Return read-only screener score saturation audit."),
    _tool("codexstock_candidate_lane_audit", "Return read-only daytrade/swing/midterm/longterm candidate lane separation audit."),
    _tool("codexstock_learning_memory_audit", "Return read-only trace audit proving which deduplicated training evidence affects each candidate."),
    _tool("codexstock_sector_concentration_audit", "Return read-only sector concentration and representative-limit audit."),
    _tool(
        "codexstock_jsonl_compaction_dry_run",
        "Return read-only JSONL storage compaction dry-run. Does not modify files.",
        {
            "target": {"type": "string", "default": "missed_buy_reviews.jsonl"},
            "keep_rows": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 600},
        },
    ),
    _tool(
        "codexstock_sqlite_storage_audit",
        "Return read-only SQLite storage/index health audit. Does not modify databases.",
    ),
    _tool(
        "codexstock_market_priority_resource_gate",
        "Return read-only market-time lightweight resource gate for heavy research/external engines and SQLite latency. Never submits orders.",
    ),
    _tool(
        "codexstock_runtime_data_separation_audit",
        "Return read-only runtime-data/code-folder separation audit. Does not move or read secret contents.",
    ),
    _tool(
        "codexstock_quote_unit_audit",
        "Audit quote price/currency/unit consistency before P/L or sizing.",
        {"symbols": {"type": "string", "description": "Comma separated symbols. Empty means watchlist.", "default": ""}, "prefer_live": {"type": "boolean", "default": False}, "record": {"type": "boolean", "default": False}},
    ),
    _tool(
        "codexstock_common_quote_snapshot",
        "Return the common guarded quote snapshot used for safe marks.",
        {"symbols": {"type": "string", "description": "Comma separated symbols. Empty means watchlist.", "default": ""}, "prefer_live": {"type": "boolean", "default": False}, "record": {"type": "boolean", "default": False}},
    ),
    _tool(
        "codexstock_position_unit_audit",
        "Audit paper/live position quantity, notional, currency, and quote-unit consistency before trusting P/L or sizing.",
        {"include_live": {"type": "boolean", "default": True}, "prefer_live_quotes": {"type": "boolean", "default": False}, "record": {"type": "boolean", "default": False}},
    ),
    _tool("codexstock_learning_insights", "Return recent learning insights and rules.", {"force": {"type": "boolean", "default": False}}),
    _tool(
        "codexstock_staff_long_horizon_audit",
        "Return stored 2000-2026 staff long-horizon performance evidence with costs, benchmark, currency-boundary proof, and official/reference-only claim status. Read-only.",
    ),
    _tool(
        "codexstock_staff_learning_effect_audit",
        "Return chronological, tamper-evident staff learning pairs and measured risk-adjusted improvement. Growth requires three non-overlapping paired periods and a positive 95% confidence lower bound; repetition alone is not learning.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 300}},
    ),
    _tool(
        "codexstock_staff_learning_decision_reflection_audit",
        "Return a point-in-time audit proving whether causal Paper outcomes change the next staff strategy decision. It blocks repeated regressed parameter changes even under new strategy ids and reports performance proof separately. Read-only; never submits or promotes live orders.",
        {"as_of_date": {"type": "string", "description": "Optional YYYY-MM-DD point-in-time cutoff.", "default": ""}},
    ),
    _tool(
        "codexstock_staff_learning_counterfactual_schedule",
        "Return the read-only scheduler gate for staff learning counterfactual triplets. Shows whether Paper-only learning validation is deferred for market priority, ready for the night/weekend slot, or blocked; never runs replay jobs or live orders.",
        {"max_triplets": {"type": "integer", "minimum": 1, "maximum": 6, "default": 2}},
    ),
    _tool(
        "codexstock_staff_learning_counterfactual_runtime",
        "Return the read-only background runtime state for automatic Paper-only learning counterfactual validation, including run id, completion counts, and last error. Never submits live orders.",
    ),
    _tool(
        "codexstock_staff_learning_counterfactual_preregistration",
        "Return the read-only immutable forward-test preregistration status, including strategy-lock time, fixed target dates, contract hash, tamper blockers, and registered staff count. Full strategies and live orders are never exposed.",
    ),
    _tool(
        "codexstock_promotion_candidate_evidence_audit",
        "Return the read-only promotion-candidate provenance audit. It quarantines synthetic/mock prices and requires a manually nominated Research Forge experiment with provider OHLCV, dataset hash, point-in-time universe, adjusted prices, next-bar fills, costs, liquidity, strict walk-forward, robustness, a verified report, and a next-KRX-session cooling boundary.",
    ),
    _tool(
        "codexstock_promotion_candidate_discovery_audit",
        "Return the read-only Research Forge Paper-candidate discovery audit, including bounded scan size, manual nomination counts, verified imports, scheduler-eligible candidates, pending nominations, deduplication, and next-KRX-session cooling. Never runs research or submits orders.",
    ),
    _tool(
        "codexstock_promotion_forward_observation_audit",
        "Return the read-only 90-day forward-operation evidence audit. It requires dense KRX-session observations, hash-chain integrity, and Paper-only guards; two distant timestamps cannot satisfy it.",
    ),
    _tool(
        "codexstock_promotion_rehearsal_evidence_audit",
        "Return the read-only Paper promotion-rehearsal evidence audit. A sample counts only when the official quote evidence, Paper ticket, candidate ledger, session date, and safety guards reconcile; readiness also requires 20 samples across at least 5 KRX sessions and 3 symbols.",
    ),
    _tool(
        "codexstock_monte_carlo_evidence_audit",
        "Return the verified Monte Carlo evidence audit, including reconciled actual-trade sample size, tail and ruin metrics, blockers, and Paper-only retraining candidates. Read-only; never submits or promotes live orders.",
    ),
    _tool(
        "codexstock_staff_learning_counterfactual_triplet_batch",
        "Run bounded Paper-only same-period counterfactual triplets to prove whether staff learning improves decisions. Respects market-priority deferral; never submits live orders or promotes unverified results.",
        {
            "max_triplets": {"type": "integer", "minimum": 1, "maximum": 6, "default": 2},
            "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "start_date": {"type": "string", "description": "Optional YYYY-MM-DD. Empty uses the scheduler-selected independent period.", "default": ""},
            "end_date": {"type": "string", "description": "Optional YYYY-MM-DD. Empty uses the scheduler-selected independent period.", "default": ""},
            "allow_simulated_fallback": {"type": "boolean", "default": False},
        },
    ),
    _tool(
        "codexstock_staff_indicator_catalog",
        "Return the indicators and market signals every AI staff member can read, including native replay versus Research Forge Stage 2 support. Read-only.",
    ),
    _tool(
        "codexstock_tournament_standings",
        "Return official tournament standings separately from quarantined reference activity, including deep replay certification progress. Read-only; never promotes or submits orders.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 300, "default": 100}},
    ),
    _tool(
        "codexstock_tournament_champion_audit",
        "Audit champion/benchmark records and legendary returns.",
        {"limit": {"type": "integer", "minimum": 10, "maximum": 300, "default": 300}, "legend_threshold": {"type": "number", "minimum": 100, "maximum": 10000, "default": 500}},
    ),
    _tool(
        "codexstock_tournament_reconciliation_audit",
        "Audit tournament/backtest entry, exit, reason, and return reconciliation quality.",
        {
            "limit": {"type": "integer", "minimum": 10, "maximum": 1000, "default": 300},
            "queue_limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 20},
            "batch_limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 12},
        },
    ),
    _tool(
        "codexstock_historical_replay_completion_audit",
        "Return 757 historical Paper replay progress and the signed completion-certificate state. Read-only; incomplete evidence remains quarantined.",
    ),
    _tool(
        "codexstock_historical_replay_regeneration_manual_batch",
        "Run a bounded Paper-only historical replay reconciliation batch. Respects cooldowns; never submits live orders or promotes unverified results.",
        {"max_cycles": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1}},
    ),
    _tool(
        "codexstock_historical_market_data_cache_status",
        "Return the bounded integrity-checked SQLite cache status used only by isolated historical Paper replay workers. Read-only.",
    ),
    _tool(
        "codexstock_weakness_completion_audit",
        "Return the 10-weakness implementation and current-evidence scoreboards separately. Read-only; pending evidence cannot affect scores or live candidates.",
        {"force": {"type": "boolean", "default": False}},
    ),
    _tool(
        "codexstock_runtime_deployment_freshness",
        "Return whether the running app loaded the current source or needs a safe restart. Read-only; never submits orders.",
    ),
    _tool(
        "codexstock_stage2_handoff_queue",
        "Return ready/blocked Stage 2 on-demand sub-engine handoff queue preview. Read-only; does not execute external engines.",
        {
            "limit": {"type": "integer", "minimum": 10, "maximum": 1000, "default": 300},
            "queue_limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 20},
            "batch_limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 12},
        },
    ),
    _tool(
        "codexstock_stage2_result_gate",
        "Validate a Stage 2 external sub-engine result against its handoff contract before promotion. Read-only.",
        {
            "stage2_job_id": {"type": "string", "default": ""},
            "contract_hash_prefix": {"type": "string", "default": ""},
            "contract_hash_echo": {"type": "string", "default": ""},
            "contract_schema_version_echo": {"type": "string", "default": ""},
            "idempotency_key_echo": {"type": "string", "default": ""},
            "replay_id_echo": {"type": "string", "default": ""},
            "stage2_action_echo": {"type": "string", "default": ""},
            "preferred_package_id_echo": {"type": "string", "default": ""},
            "preferred_package_source_echo": {"type": "string", "default": ""},
            "external_runtime_mode_echo": {"type": "string", "default": ""},
            "external_runtime_budget_evidence": {"type": "object", "additionalProperties": True},
            "external_runtime_cleanup_evidence": {"type": "object", "additionalProperties": True},
            "external_engine_name": {"type": "string", "default": ""},
            "external_run_id": {
                "type": "string",
                "default": "",
                "pattern": "^[A-Za-z0-9._:-]{8,128}$",
                "description": "Unique external engine run identifier. Placeholder/test/sample/dummy values are rejected.",
            },
            "no_live_order_proof": {"type": "boolean", "default": False},
            "no_live_order_evidence": {"type": "object", "additionalProperties": True},
            "snapshot_hash_matched": {"type": "boolean", "default": False},
            "snapshot_hash_evidence": {"type": "object", "additionalProperties": True},
            "fees_taxes_slippage_applied": {"type": "boolean", "default": False},
            "one_engine_pass": {"type": "boolean", "default": False},
            "fee_tax_slippage_evidence": {"type": "object", "additionalProperties": True},
            "entry_exit_return_reason_evidence": {"type": "object", "additionalProperties": True},
            "unit_currency_audit_evidence": {"type": "object", "additionalProperties": True},
            "unit_currency_audit_status": {"type": "string", "default": ""},
            "exit_reason_alignment": {"type": "string", "default": ""},
            "exit_reason_alignment_evidence": {"type": "object", "additionalProperties": True},
            "fill_ledger_hash": {
                "type": "string",
                "default": "",
                "pattern": "^(?:[A-Fa-f0-9]{32,128}|sha256:[A-Fa-f0-9]{64})$",
                "description": "Canonical fill-ledger digest. Placeholder/test/dummy/sample values are rejected.",
            },
            "fill_ledger_evidence": {"type": "object", "additionalProperties": True},
            "return_reconciliation_summary": {"type": "object", "additionalProperties": True},
            "limit": {"type": "integer", "minimum": 10, "maximum": 1000, "default": 300},
            "queue_limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 20},
            "batch_limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 12},
        },
    ),
    _tool(
        "codexstock_external_signal_inbox",
        "Read the latest external information scout report accepted by CodexStock. Information-only; never submits orders.",
        {"include_report": {"type": "boolean", "default": True}},
    ),
    _tool(
        "codexstock_external_signal_stage2_queue",
        "Return deterministic Stage 2 contracts for fresh external-scout signals. Read-only; engines remain stopped until explicitly requested.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}},
    ),
    _tool(
        "codexstock_external_signal_stage2_result",
        "Submit one research-only external-engine result for strict Stage 2 validation and audit recording. Never grants score or live-order authority.",
        {"result": {"type": "object", "additionalProperties": True}},
        ["result"],
    ),
    _tool(
        "codexstock_external_signal_stage2_run",
        "Start one fresh external-scout Stage 2 job in the background with Nautilus. Explicit on-demand research only; one job at a time and no live orders.",
        {"stage2_job_id": {"type": "string", "default": ""}},
    ),
    _tool(
        "codexstock_external_signal_stage2_status",
        "Return progress, phase, ETA, and result for the current external-scout Stage 2 background job. Read-only.",
    ),
    _tool("codexstock_external_sources", "Return curated external source catalog and safety rules."),
    _tool("codexstock_external_packages", "Return imported external training packages.", {"limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 200}, "status": {"type": "string", "default": ""}}),
    _tool("codexstock_external_learning_report", "Return external learning report and Stage 2 readiness.", {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12}}),
    _tool("codexstock_external_engine_contract", "Return external sub-engine contract and adapter readiness."),
    _tool(
        "codexstock_external_engine_status",
        "Return all registered external sub-engine connection, readiness, current-job, progress, and on-demand status. Set force=true to bypass the short dashboard cache. Read-only.",
        {"force": {"type": "boolean", "default": False}},
    ),
    _tool(
        "codexstock_research_forge_integration_audit",
        "Verify that Research Forge is recognized and consumed by CodexStock staff, experiment validation, Paper promotion, feature health, MCP, and the shared runtime root. Read-only.",
    ),
    _tool(
        "codexstock_external_improvement_status",
        "Return the research-only external-engine improvement loop state, per-engine validation results, verified lessons, and retraining queue. Read-only and never submits orders.",
        {
            "lesson_limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            "task_limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
    ),
    _tool(
        "codexstock_external_improvement_run",
        "Start one bounded research-only improvement cycle across OpenBB, Lean, vectorbt, Qlib, and Nautilus. It is deferred during market-priority windows, runs one heavy job at a time, and cannot submit orders or promote strategies.",
        {
            "symbols": {"type": "string", "description": "Comma separated symbols; empty uses safe local defaults.", "default": ""},
            "max_symbols": {"type": "integer", "minimum": 2, "maximum": 10, "default": 5},
            "rows": {"type": "integer", "minimum": 120, "maximum": 520, "default": 260},
            "fast_window": {"type": "integer", "minimum": 2, "maximum": 60, "default": 10},
            "slow_window": {"type": "integer", "minimum": 3, "maximum": 200, "default": 40},
            "fold_count": {"type": "integer", "minimum": 3, "maximum": 8, "default": 4},
            "timeout_seconds": {"type": "integer", "minimum": 60, "maximum": 600, "default": 240},
        },
    ),
    _tool("codexstock_external_runtime_audit", "Return read-only audit of external engine on-demand isolation and bloat risk."),
    _tool("codexstock_external_dataset_snapshots", "Return dataset snapshot/hash readiness for external engines.", {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}),
    _tool(
        "codexstock_external_common_snapshot",
        "Build a bounded common OHLCV snapshot contract for Stage 2. Does not execute external code or submit orders.",
        {
            "symbols": {"type": "string", "description": "Comma separated symbols. Empty means safe defaults from local OHLCV cache.", "default": ""},
            "max_symbols": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            "rows": {"type": "integer", "minimum": 20, "maximum": 260, "default": 120},
            "package_id": {"type": "string", "default": ""},
            "action": {"type": "string", "default": "run_external_backtest"},
            "record": {"type": "boolean", "default": False},
        },
    ),
    _tool("codexstock_import_training_package", "Import a metadata-only external training package. No real orders.", {"package": {"type": "object", "additionalProperties": True}, "replace": {"type": "boolean", "default": False}}, ["package"]),
    _tool("codexstock_validate_external_package", "Validate an imported external package.", {"package_id": {"type": "string"}}, ["package_id"]),
    _tool("codexstock_run_external_backtest", "Prepare Stage 2 external backtest contract. Does not execute external code.", {"package_id": {"type": "string"}, "dataset_snapshot": {"type": "object", "additionalProperties": True}}),
    _tool("codexstock_run_external_replay", "Prepare Stage 2 external replay contract. Does not execute external code.", {"package_id": {"type": "string"}, "dataset_snapshot": {"type": "object", "additionalProperties": True}}),
    _tool("codexstock_compare_external_strategy", "Prepare external strategy comparison contract. Does not execute external code.", {"package_id": {"type": "string"}, "dataset_snapshot": {"type": "object", "additionalProperties": True}}),
    _tool("codexstock_assign_training_mission", "Assign a research-only external learning mission to AI staff.", {"mission": {"type": "object", "additionalProperties": True}}, ["mission"]),
    _tool("codexstock_promote_external_knowledge", "Request promotion of external knowledge. Blocked until Stage 2 reconciliation.", {"package_id": {"type": "string"}}),
    _tool("codexstock_reject_external_knowledge", "Reject an external package without deleting it.", {"package_id": {"type": "string"}, "reason": {"type": "string", "default": "rejected by policy"}}, ["package_id"]),
    _tool("codexstock_ask_agent", "Ask CodexStock internal agent. Real order approval/submission commands are blocked.", {"question": {"type": "string", "description": "Question text"}}, ["question"]),
]
ORDER_KEYWORDS = (
    "final submit",
    "submit order",
    "real order",
    "approve order",
    "\uc8fc\ubb38",
    "\uc2e4\uc8fc\ubb38",
    "\ub9e4\uc218",
    "\ub9e4\ub3c4",
    "\uc2b9\uc778",
    "buy",
    "sell",
    "submit",
    "approve",
    "order",
)


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    max_chars = _int_arg(arguments, "max_chars", DEFAULT_TOOL_RESULT_MAX_CHARS, 2000, HARD_TOOL_RESULT_MAX_CHARS)
    if name in RESEARCH_TOOL_NAMES:
        payload = call_research_tool(
            name,
            arguments,
            runtime_root=Path(active_data_root(REPO_ROOT)),
            repo_root=REPO_ROOT,
        )
        return _tool_result(payload, max_chars=max_chars)
    if name == "codexstock_mcp_manifest":
        _record_mcp_client_exposure(arguments)
        return _tool_result(_mcp_manifest(), max_chars=max_chars)
    if name == "codexstock_status":
        detail = str(arguments.get("detail") or "instant").strip().lower()
        if _bool_arg(arguments, "full", False):
            detail = "full"
        path = {
            "instant": "/api/mcp/overview",
            "quick": "/api/ops/status/poll",
            "full": "/api/ops/status",
        }.get(detail, "/api/mcp/overview")
        timeout_seconds = 3.0 if detail == "instant" else 10.0 if detail == "quick" else 30.0
        payload = _http_json(
            "GET",
            path,
            timeout_seconds=timeout_seconds,
            cache_ttl_seconds=2.0 if detail != "full" else 0.0,
            stale_if_error_seconds=120.0 if detail != "full" else 0.0,
        )
        payload = _attach_internal_developer_attention(payload)
        return _tool_result(_attach_mcp_manifest(payload), max_chars=max_chars)
    if name == "codexstock_knowledge_curator_status":
        payload = _http_json("GET", "/api/knowledge-curator/status", timeout_seconds=15.0)
        return _tool_result(
            _knowledge_curator_status_summary(payload),
            max_chars=max_chars,
        )
    if name == "codexstock_knowledge_search":
        return _tool_result(
            _http_json(
                "GET",
                "/api/knowledge-curator/search",
                {
                    "q": str(arguments.get("query") or ""),
                    "limit": _int_arg(arguments, "limit", 10, 1, 50),
                },
                timeout_seconds=15.0,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_knowledge_engine_plan":
        return _tool_result(
            _http_json(
                "GET",
                "/api/knowledge-curator/engine-plan",
                {
                    "changed_documents": _int_arg(arguments, "changed_documents", 0, 0, 1000000),
                    "market_open": int(_bool_arg(arguments, "market_open", False)),
                    "heavy_work_allowed": int(_bool_arg(arguments, "heavy_work_allowed", False)),
                },
                timeout_seconds=15.0,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_internal_developer_status":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_component_status":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_list_incidents":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_get_incident":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_latest_report":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_brief":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_activity":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_internal_developer_readonly_diagnostics":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_submit_developer_advice":
        return _tool_result(_internal_developer_direct(name, arguments), max_chars=max_chars)
    if name == "codexstock_scorecard":
        refresh = _bool_arg(arguments, "refresh", False)
        return _tool_result(
            _http_json("GET", "/api/codexstock/maturity", {"record": 0, "refresh": int(refresh)}),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_status":
        detail = str(arguments.get("detail") or "instant").strip().lower()
        if _bool_arg(arguments, "full", False):
            detail = "full"
        path = {
            "instant": "/api/mcp/staff",
            "quick": "/api/agent/staff/quick",
            "full": "/api/agent/staff",
        }.get(detail, "/api/mcp/staff")
        params = {"ttl": 30} if detail == "quick" else None
        timeout_seconds = 3.0 if detail == "instant" else 10.0 if detail == "quick" else 30.0
        return _tool_result(
            _http_json(
                "GET",
                path,
                params,
                timeout_seconds=timeout_seconds,
                cache_ttl_seconds=3.0 if detail != "full" else 0.0,
                stale_if_error_seconds=120.0 if detail != "full" else 0.0,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_meetings":
        limit = _int_arg(arguments, "limit", 5, 1, 20)
        offset = _int_arg(arguments, "offset", 0, 0, 200)
        full = _bool_arg(arguments, "full", False)
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "group": str(arguments.get("group") or "").strip().lower() or None,
            "compact": 0 if full else 1,
        }
        if "quick" in arguments:
            params["quick"] = int(_bool_arg(arguments, "quick", False))
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/staff/meetings",
                params,
                timeout_seconds=10.0,
                cache_ttl_seconds=3.0,
                stale_if_error_seconds=120.0,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_live_pilot_plan":
        full = _bool_arg(arguments, "full", False)
        params = {
            "symbol": str(arguments.get("symbol", "AI") or "AI").upper(),
            "side": str(arguments.get("side", "BUY") or "BUY").upper(),
            "quantity": _float_arg(arguments, "quantity", 1.0),
            "force": int(_bool_arg(arguments, "force", False)),
            "detail": "full" if full else "quick",
            "quick": 0 if full else 1,
        }
        return _tool_result(_http_json("GET", "/api/ops/live-pilot/plan", params), max_chars=max_chars)
    if name == "codexstock_live_candidate_decisions":
        limit = _int_arg(arguments, "limit", 10, 1, 50)
        return _tool_result(_http_json("GET", "/api/ops/live-candidate-decisions", {"limit": limit}), max_chars=max_chars)
    if name == "codexstock_today_trades":
        return _tool_result(_http_json("GET", "/api/ops/today-trades/quick"), max_chars=max_chars)
    if name == "codexstock_live_trade_explanations":
        limit = _int_arg(arguments, "limit", 12, 1, 30)
        return _live_trade_explanation_tool_result(
            _http_json("GET", "/api/agent/live-trade-explanations", {"limit": limit}),
            max_chars=max_chars,
        )
    if name == "codexstock_live_order_blackbox":
        limit = _int_arg(arguments, "limit", 8, 1, 30)
        return _live_order_blackbox_tool_result(
            _http_json("GET", "/api/ops/live-order-blackbox", {"limit": limit, "persist": 0}),
            max_chars=max_chars,
        )
    if name == "codexstock_live_reconciliation_audit":
        limit = _int_arg(arguments, "limit", 120, 1, 500)
        return _tool_result(_http_json("GET", "/api/ops/live-reconciliation-audit", {"limit": limit}), max_chars=max_chars)
    if name == "codexstock_radar":
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/radar",
                {"symbols": str(arguments.get("symbols", "") or ""), "force": int(_bool_arg(arguments, "force", False))},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_screener":
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/screener",
                {"symbols": str(arguments.get("symbols", "") or ""), "force": int(_bool_arg(arguments, "force", False))},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_sector_news":
        return _tool_result(
            _http_json("GET", "/api/agent/sector-news", {"force": int(_bool_arg(arguments, "force", False))}),
            max_chars=max_chars,
        )
    if name == "codexstock_sector_committee":
        return _tool_result(
            _http_json("GET", "/api/agent/sector-committee", {"force": int(_bool_arg(arguments, "force", False))}),
            max_chars=max_chars,
        )
    if name == "codexstock_market_context_snapshot":
        return _tool_result(
            _http_json("GET", "/api/market/context-snapshot", {"force": int(_bool_arg(arguments, "force", False))}),
            max_chars=max_chars,
        )
    if name == "codexstock_market_news_evidence":
        return _tool_result(
            _http_json(
                "GET",
                "/api/market/news-evidence",
                {
                    "force": int(_bool_arg(arguments, "force", False)),
                    "limit": _int_arg(arguments, "limit", 8, 1, 20),
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_intraday_market_pulse":
        return _tool_result(
            _http_json(
                "GET",
                "/api/market/intraday-market-pulse",
                {
                    "force": int(_bool_arg(arguments, "force", False)),
                    "limit": _int_arg(arguments, "limit", 30, 1, 100),
                    "persist": 0,
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_feature_health":
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/feature-health",
                {"probe": int(_bool_arg(arguments, "probe", False)), "record": int(_bool_arg(arguments, "record", False))},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_score_saturation_audit":
        return _tool_result(
            _http_json("GET", "/api/agent/score-saturation"),
            max_chars=max_chars,
        )
    if name == "codexstock_candidate_lane_audit":
        return _tool_result(
            _http_json("GET", "/api/agent/candidate-lanes"),
            max_chars=max_chars,
        )
    if name == "codexstock_sector_concentration_audit":
        return _tool_result(
            _http_json("GET", "/api/agent/sector-concentration"),
            max_chars=max_chars,
        )
    if name == "codexstock_jsonl_compaction_dry_run":
        return _tool_result(
            _http_json(
                "GET",
                "/api/system/jsonl-compaction",
                {
                    "target": str(arguments.get("target", "") or "missed_buy_reviews.jsonl"),
                    "keep_rows": _int_arg(arguments, "keep_rows", 600, 1, 20000),
                    "apply": 0,
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_sqlite_storage_audit":
        return _tool_result(
            _http_json("GET", "/api/system/sqlite-storage"),
            max_chars=max_chars,
        )
    if name == "codexstock_market_priority_resource_gate":
        return _tool_result(
            _http_json("GET", "/api/system/market-priority-resource-gate"),
            max_chars=max_chars,
        )
    if name == "codexstock_runtime_data_separation_audit":
        return _tool_result(
            _http_json("GET", "/api/system/runtime-data-separation"),
            max_chars=max_chars,
        )
    if name == "codexstock_quote_unit_audit":
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/quote-unit-audit",
                {
                    "symbols": str(arguments.get("symbols", "") or ""),
                    "prefer_live": int(_bool_arg(arguments, "prefer_live", False)),
                    "record": int(_bool_arg(arguments, "record", False)),
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_common_quote_snapshot":
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/common-quote-snapshot",
                {
                    "symbols": str(arguments.get("symbols", "") or ""),
                    "prefer_live": int(_bool_arg(arguments, "prefer_live", False)),
                    "record": int(_bool_arg(arguments, "record", False)),
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_position_unit_audit":
        return _tool_result(
            _http_json(
                "GET",
                "/api/agent/position-unit-audit",
                {
                    "include_live": int(_bool_arg(arguments, "include_live", True)),
                    "prefer_live_quotes": int(_bool_arg(arguments, "prefer_live_quotes", False)),
                    "record": int(_bool_arg(arguments, "record", False)),
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_learning_insights":
        return _tool_result(
            _http_json("GET", "/api/agent/learning-insights", {"force": int(_bool_arg(arguments, "force", False))}),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_long_horizon_audit":
        return _tool_result(_http_json("GET", "/api/ai-tournament/staff-long-horizon"), max_chars=max_chars)
    if name == "codexstock_staff_learning_effect_audit":
        return _tool_result(
            _http_json(
                "GET",
                "/api/ai-tournament/staff-learning-audit",
                {"limit": _int_arg(arguments, "limit", 300, 1, 1000)},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_learning_decision_reflection_audit":
        as_of_date = str(arguments.get("as_of_date") or "").strip()
        params = {"as_of_date": as_of_date} if as_of_date else None
        return _tool_result(
            _http_json(
                "GET",
                "/api/ai-tournament/staff-learning-decision-reflection-audit",
                params,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_learning_counterfactual_schedule":
        return _tool_result(
            _http_json(
                "GET",
                "/api/ai-tournament/staff-learning-counterfactual-schedule",
                {"max_triplets": _int_arg(arguments, "max_triplets", 2, 1, 6)},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_learning_counterfactual_runtime":
        return _tool_result(
            _http_json("GET", "/api/ai-tournament/staff-learning-counterfactual-runtime"),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_learning_counterfactual_preregistration":
        return _tool_result(
            _http_json(
                "GET",
                "/api/ai-tournament/staff-learning-counterfactual-preregistration",
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_promotion_candidate_evidence_audit":
        return _tool_result(
            _http_json("GET", "/api/strategy/promotion-candidate-evidence-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_promotion_candidate_discovery_audit":
        return _tool_result(
            _http_json("GET", "/api/strategy/promotion-candidate-discovery-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_promotion_forward_observation_audit":
        return _tool_result(
            _http_json("GET", "/api/strategy/promotion-forward-observation-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_promotion_rehearsal_evidence_audit":
        return _tool_result(
            _http_json("GET", "/api/strategy/promotion-rehearsal-evidence-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_monte_carlo_evidence_audit":
        return _tool_result(
            _http_json("GET", "/api/ai-tournament/monte-carlo-evidence-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_learning_counterfactual_triplet_batch":
        symbols_arg = arguments.get("symbols")
        symbols = (
            [str(symbol).strip() for symbol in symbols_arg if str(symbol).strip()]
            if isinstance(symbols_arg, list)
            else []
        )
        return _tool_result(
            _http_json(
                "POST",
                "/api/ai-tournament/staff-learning-counterfactual-triplet-batch",
                payload={
                    "max_triplets": _int_arg(arguments, "max_triplets", 2, 1, 6),
                    "symbols": symbols[:5],
                    "start_date": str(arguments.get("start_date") or ""),
                    "end_date": str(arguments.get("end_date") or ""),
                    "allow_simulated_fallback": _bool_arg(arguments, "allow_simulated_fallback", False),
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_staff_indicator_catalog":
        return _tool_result(_http_json("GET", "/api/ai-tournament/indicator-catalog"), max_chars=max_chars)
    if name == "codexstock_learning_memory_audit":
        return _tool_result(_http_json("GET", "/api/agent/learning-memory"), max_chars=max_chars)
    if name == "codexstock_tournament_standings":
        return _tool_result(
            _http_json(
                "GET",
                "/api/ai-tournament/standings",
                {"limit": _int_arg(arguments, "limit", 100, 1, 300)},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_tournament_champion_audit":
        limit = _int_arg(arguments, "limit", 300, 10, 300)
        legend_threshold = _float_arg(arguments, "legend_threshold", 500.0)
        return _tool_result(
            _http_json(
                "GET",
                "/api/ai-tournament/champion-audit",
                {"limit": limit, "legend_threshold": legend_threshold},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_tournament_reconciliation_audit":
        limit = _int_arg(arguments, "limit", 300, 10, 1000)
        queue_limit = _int_arg(arguments, "queue_limit", 20, 1, 500)
        batch_limit = _int_arg(arguments, "batch_limit", 12, 1, 200)
        return _tool_result(
            _tournament_reconciliation_http_or_direct(limit, queue_limit, batch_limit),
            max_chars=max_chars,
        )
    if name == "codexstock_historical_replay_completion_audit":
        return _tool_result(
            _http_json("GET", "/api/ai-tournament/regeneration-completion-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_historical_replay_regeneration_manual_batch":
        max_cycles = _int_arg(arguments, "max_cycles", 1, 1, 5)
        return _tool_result(
            _http_json(
                "POST",
                "/api/ai-tournament/regeneration-worker/manual-batch",
                payload={"max_cycles": max_cycles},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_historical_market_data_cache_status":
        return _tool_result(
            _http_json("GET", "/api/ai-tournament/historical-market-data-cache"),
            max_chars=max_chars,
        )
    if name == "codexstock_weakness_completion_audit":
        refresh_requested = _bool_arg(arguments, "force", False)
        audit = _http_json(
            "GET",
            "/api/codexstock/weakness-completion-audit",
            {"refresh": 1} if refresh_requested else {"force": 0},
        )
        return _tool_result(
            _weakness_completion_audit_summary(audit),
            max_chars=max_chars,
        )
    if name == "codexstock_runtime_deployment_freshness":
        return _tool_result(
            _http_json("GET", "/api/runtime/deployment-freshness"),
            max_chars=max_chars,
        )
    if name == "codexstock_stage2_handoff_queue":
        limit = _int_arg(arguments, "limit", 300, 10, 1000)
        queue_limit = _int_arg(arguments, "queue_limit", 20, 1, 500)
        batch_limit = _int_arg(arguments, "batch_limit", 12, 1, 200)
        audit = _tournament_reconciliation_http_or_direct(limit, queue_limit, batch_limit)
        handoff = audit.get("stage2_handoff") if isinstance(audit, dict) and isinstance(audit.get("stage2_handoff"), dict) else {}
        summary = audit.get("summary") if isinstance(audit, dict) and isinstance(audit.get("summary"), dict) else {}
        payload = {
            "ok": bool(handoff),
            "source": "codexstock_stage2_handoff_queue",
            "summary": {
                "status": summary.get("status"),
                "stage2_snapshot_ready": handoff.get("stage2_snapshot_ready"),
                "contract_schema_version": handoff.get("contract_schema_version"),
                "next_contract_hash_prefix": handoff.get("next_contract_hash_prefix"),
                "contract_missing_input_job_count": handoff.get("contract_missing_input_job_count"),
                "contract_missing_input_total_count": handoff.get("contract_missing_input_total_count"),
                "stage2_candidate_package_count": handoff.get("stage2_candidate_package_count"),
                "stage2_ready_package_count": handoff.get("stage2_ready_package_count"),
                "stage2_ready_package_display_count": handoff.get("stage2_ready_package_display_count"),
                "stage2_excluded_package_count": handoff.get("stage2_excluded_package_count"),
                "stage2_action": handoff.get("stage2_action"),
                "preferred_package_source": handoff.get("preferred_package_source"),
                "package_selection_rule": handoff.get("package_selection_rule"),
                "ready_count": handoff.get("ready_count"),
                "blocked_count": handoff.get("blocked_count"),
                "ready_queue_preview_count": handoff.get("ready_queue_preview_count"),
                "duplicate_job_count": handoff.get("duplicate_job_count"),
                "blocked_unit_audit_symbols_csv": handoff.get("blocked_unit_audit_symbols_csv"),
                "blocked_unit_audit_status": (handoff.get("blocked_unit_audit_preview") or {}).get("status")
                if isinstance(handoff.get("blocked_unit_audit_preview"), dict)
                else "",
                "blocked_unit_resolution_count": (handoff.get("blocked_unit_audit_preview") or {}).get("resolution_plan_count", 0)
                if isinstance(handoff.get("blocked_unit_audit_preview"), dict)
                else 0,
                "max_concurrent_external_jobs": handoff.get("max_concurrent_external_jobs"),
                "external_runtime_mode": handoff.get("external_runtime_mode"),
                "live_order_allowed": handoff.get("live_order_allowed"),
            },
            "next_ready_job": handoff.get("next_ready_job", {}),
            "ready_queue_preview": handoff.get("ready_queue_preview", []),
            "contract_required_inputs": handoff.get("contract_required_inputs", []),
            "contract_expected_outputs": handoff.get("contract_expected_outputs", []),
            "contract_acceptance_criteria": handoff.get("contract_acceptance_criteria", []),
            "fee_tax_slippage_profile": handoff.get("fee_tax_slippage_profile", {}),
            "unit_currency_policy": handoff.get("unit_currency_policy", {}),
            "blocked_reason_counts": handoff.get("blocked_reason_counts", {}),
            "blocked_unit_audit_symbols": handoff.get("blocked_unit_audit_symbols", []),
            "blocked_unit_audit_tool": handoff.get("blocked_unit_audit_tool", ""),
            "blocked_unit_audit_preview": handoff.get("blocked_unit_audit_preview", {}),
            "blocked_unit_resolution_plan": (handoff.get("blocked_unit_audit_preview") or {}).get("resolution_plan", [])
            if isinstance(handoff.get("blocked_unit_audit_preview"), dict)
            else [],
            "stage2_candidate_packages": handoff.get("stage2_candidate_packages", []),
            "stage2_excluded_package_preview": handoff.get("stage2_excluded_package_preview", []),
            "safety": "Read-only MCP queue preview. Does not execute external engines and cannot submit live orders.",
            "mcp_server_manifest": _mcp_manifest(),
        }
        return _tool_result(payload, max_chars=max_chars)
    if name == "codexstock_stage2_result_gate":
        return _tool_result(_stage2_result_gate(arguments), max_chars=max_chars)
    if name == "codexstock_external_signal_inbox":
        include_report = _bool_arg(arguments, "include_report", True)
        return _tool_result(
            _http_json("GET", "/api/external-signal/latest" if include_report else "/api/external-signal/status"),
            max_chars=max_chars,
        )
    if name == "codexstock_external_signal_stage2_queue":
        limit = _int_arg(arguments, "limit", 20, 1, 200)
        return _tool_result(
            _http_json("GET", "/api/external-signal/stage2-queue", {"limit": limit}),
            max_chars=max_chars,
        )
    if name == "codexstock_external_signal_stage2_result":
        result = arguments.get("result")
        if not isinstance(result, dict):
            return _tool_result(
                {"ok": False, "error": "result_object_required", "live_order_allowed": False},
                max_chars=max_chars,
            )
        return _tool_result(
            _http_json("POST", "/api/external-signal/stage2-result", payload=result),
            max_chars=max_chars,
        )
    if name == "codexstock_external_signal_stage2_run":
        return _tool_result(
            _http_json(
                "POST",
                "/api/external-signal/stage2-run",
                payload={"stage2_job_id": str(arguments.get("stage2_job_id") or "")},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_external_signal_stage2_status":
        return _tool_result(
            _http_json("GET", "/api/external-signal/stage2-job"),
            max_chars=max_chars,
        )
    if name == "codexstock_external_sources":
        return _tool_result(
            _external_knowledge_http_or_direct(name, "GET", "/api/external-knowledge/sources", arguments),
            max_chars=max_chars,
        )
    if name == "codexstock_external_packages":
        limit = _int_arg(arguments, "limit", 200, 1, 500)
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "GET",
                "/api/external-knowledge/packages",
                arguments,
                params={"limit": limit, "status": str(arguments.get("status", "") or "")},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_external_learning_report":
        limit = _int_arg(arguments, "limit", 12, 1, 50)
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "GET",
                "/api/external-knowledge/report",
                arguments,
                params={"limit": limit},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_external_engine_contract":
        return _tool_result(
            _external_knowledge_http_or_direct(name, "GET", "/api/external-knowledge/engine-contract", arguments),
            max_chars=max_chars,
        )
    if name == "codexstock_external_engine_status":
        force = bool(arguments.get("force", False))
        path = "/api/external-engines/status?force=1" if force else "/api/external-engines/status"
        return _tool_result(_http_json("GET", path), max_chars=max_chars)
    if name == "codexstock_research_forge_integration_audit":
        return _tool_result(
            _http_json("GET", "/api/research-forge/integration-audit"),
            max_chars=max_chars,
        )
    if name == "codexstock_external_improvement_status":
        lesson_limit = _int_arg(arguments, "lesson_limit", 5, 1, 20)
        task_limit = _int_arg(arguments, "task_limit", 10, 1, 50)
        return _tool_result(
            _external_improvement_status_summary(_http_json(
                "GET",
                "/api/external-engines/improvement-loop/status",
                {"lesson_limit": lesson_limit, "task_limit": task_limit},
            )),
            max_chars=max_chars,
        )
    if name == "codexstock_external_improvement_run":
        payload = {
            "symbols": str(arguments.get("symbols") or ""),
            "max_symbols": _int_arg(arguments, "max_symbols", 5, 2, 10),
            "rows": _int_arg(arguments, "rows", 260, 120, 520),
            "fast_window": _int_arg(arguments, "fast_window", 10, 2, 60),
            "slow_window": _int_arg(arguments, "slow_window", 40, 3, 200),
            "fold_count": _int_arg(arguments, "fold_count", 4, 3, 8),
            "timeout_seconds": _int_arg(arguments, "timeout_seconds", 240, 60, 600),
            "requested_by": "codexstock-mcp",
        }
        return _tool_result(
            _http_json("POST", "/api/external-engines/improvement-loop/run", payload=payload),
            max_chars=max_chars,
        )
    if name == "codexstock_external_runtime_audit":
        return _tool_result(
            _external_knowledge_http_or_direct(name, "GET", "/api/external-knowledge/runtime-audit", arguments),
            max_chars=max_chars,
        )
    if name == "codexstock_external_dataset_snapshots":
        limit = _int_arg(arguments, "limit", 20, 1, 100)
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "GET",
                "/api/external-knowledge/dataset-snapshots",
                arguments,
                params={"limit": limit},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_external_common_snapshot":
        max_symbols = _int_arg(arguments, "max_symbols", 3, 1, 10)
        rows = _int_arg(arguments, "rows", 120, 20, 260)
        record = _bool_arg(arguments, "record", False)
        payload = {
            "symbols": str(arguments.get("symbols", "") or ""),
            "max_symbols": max_symbols,
            "rows": rows,
            "package_id": str(arguments.get("package_id", "") or ""),
            "action": str(arguments.get("action", "run_external_backtest") or "run_external_backtest"),
            "record": record,
            "source": "mcp-external-common-snapshot",
        }
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST" if record else "GET",
                "/api/external-knowledge/common-snapshot",
                arguments,
                params=payload if not record else None,
                payload=payload if record else None,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_import_training_package":
        package = arguments.get("package") if isinstance(arguments.get("package"), dict) else {}
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/import",
                arguments,
                payload={"package": package, "replace": _bool_arg(arguments, "replace", False), "source": "mcp-external-import"},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_validate_external_package":
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/validate",
                arguments,
                payload={"package_id": str(arguments.get("package_id", "") or ""), "source": "mcp-external-validate"},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_run_external_backtest":
        dataset_snapshot = arguments.get("dataset_snapshot") if isinstance(arguments.get("dataset_snapshot"), dict) else None
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/backtest",
                arguments,
                payload={"package_id": str(arguments.get("package_id", "") or ""), "source": "mcp-external-backtest", "dataset_snapshot": dataset_snapshot},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_run_external_replay":
        dataset_snapshot = arguments.get("dataset_snapshot") if isinstance(arguments.get("dataset_snapshot"), dict) else None
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/replay",
                arguments,
                payload={"package_id": str(arguments.get("package_id", "") or ""), "source": "mcp-external-replay", "dataset_snapshot": dataset_snapshot},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_compare_external_strategy":
        dataset_snapshot = arguments.get("dataset_snapshot") if isinstance(arguments.get("dataset_snapshot"), dict) else None
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/compare",
                arguments,
                payload={"package_id": str(arguments.get("package_id", "") or ""), "source": "mcp-external-compare", "dataset_snapshot": dataset_snapshot},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_assign_training_mission":
        mission = dict(arguments.get("mission") if isinstance(arguments.get("mission"), dict) else {})
        mission["source"] = "mcp-external-mission"
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/assign-mission",
                arguments,
                payload=mission,
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_promote_external_knowledge":
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/promote",
                arguments,
                payload={"package_id": str(arguments.get("package_id", "") or ""), "source": "mcp-external-promote"},
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_reject_external_knowledge":
        return _tool_result(
            _external_knowledge_http_or_direct(
                name,
                "POST",
                "/api/external-knowledge/reject",
                arguments,
                payload={
                    "package_id": str(arguments.get("package_id", "") or ""),
                    "reason": str(
                        arguments.get("reason", "사용자 검증 정책에 따라 거절")
                        or "사용자 검증 정책에 따라 거절"
                    ),
                    "source": "mcp-external-reject",
                },
            ),
            max_chars=max_chars,
        )
    if name == "codexstock_ask_agent":
        question = str(arguments.get("question", "") or "").strip()
        lowered = question.lower()
        # Forward only an explicit daily allocation delegation. Ordinary order
        # commands remain blocked at the MCP boundary.
        explicit_delegation = bool(
            re.search(r"\b\d{1,3}(?:\.\d+)?\s*%", question)
            and any(token in lowered for token in ("위임", "자동매매", "실전", "허용", "delegat", "auto-trad", "live", "allow"))
            and any(token in lowered for token in ("오늘", "하루", "당일", "today", "daily"))
        )
        if explicit_delegation:
            return _tool_result(
                _http_json("POST", "/api/agent/command", payload={"command": question, "source": "mcp-explicit-delegation"}),
                max_chars=max_chars,
            )
        local_fallback = _agent_local_fallback(question, max_chars)
        if local_fallback is not None:
            return local_fallback
        if any(keyword in lowered or keyword in question for keyword in ORDER_KEYWORDS):
            return _tool_result(
                {
                    "ok": False,
                    "blocked": True,
                    "message": (
                        "MCP에서는 실주문 승인과 최종 전송 명령을 차단합니다. "
                        "코덱스스톡 PC 화면 또는 텔레그램 승인 절차를 사용하세요."
                    ),
                },
                is_error=True,
            )
        return _tool_result(
            _http_json("POST", "/api/agent/command", payload={"command": question, "source": "mcp-readonly"}),
            max_chars=max_chars,
        )
    return _tool_result({"ok": False, "error": f"Unknown tool: {name}"}, is_error=True)


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    msg_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    if method.startswith("notifications/") or method.startswith("$/"):
        return None
    if method == "initialize":
        client_version = str(params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": client_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        try:
            result = _call_tool(name, arguments)
        except Exception as exc:
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            result = _tool_result(
                {
                    "ok": False,
                    "tool": name,
                    "error": str(exc),
                    "message": "MCP tool failed safely. The server stayed alive; retry with force=false or smaller max_chars.",
                },
                is_error=True,
            )
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    return _error_response(msg_id, -32601, f"Method not found: {method}")


def main() -> int:
    request: dict[str, Any] | None = None
    while True:
        try:
            request = _read_message()
            if request is None:
                return 0
            response = _handle(request)
            if response is not None:
                _send_message(response)
        except Exception as exc:
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            msg_id = request.get("id") if isinstance(request, dict) else None
            if msg_id is None:
                continue
            _send_message(_error_response(msg_id, -32603, str(exc)))


if __name__ == "__main__":
    raise SystemExit(main())
