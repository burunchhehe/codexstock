from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .realtime import realtime_run_history


def evaluate_readiness(forge: Any, external: dict[str, Any] | None = None) -> dict[str, Any]:
    external = dict(external or {}); base = forge.registry.root.parent
    doctor = forge.doctor(); storage = forge.storage().summary(); archive = forge.microstructure_archive(); archive_verify = archive.verify(); archive_status = archive.status()
    performance = _verified_performance(base / "benchmarks" / "latest.json"); concurrency = _verified_concurrency(base / "benchmarks" / "concurrency_latest.json")
    universes = forge.universe().status(); hts = forge.hts_references().status(); corporate_actions = forge.corporate_actions().status(); realtime = realtime_run_history(base / "realtime", 500)
    records = list(forge.registry.list())
    strict_records, robust_records, verified_reports, report_verification_errors = [], [], [], []
    for record in records:
        strict = record.validation.get("strict_walk_forward") if isinstance(record.validation.get("strict_walk_forward"), dict) else {}
        try: declared_horizon = int(record.strategy.rules.get("label_horizon_rows") or 0); applied_purge_rows = int(strict.get("purge_rows") or 0); horizon_covered = 0 <= declared_horizon <= 10_000 and applied_purge_rows >= declared_horizon
        except (TypeError, ValueError): horizon_covered = False
        if bool((strict.get("summary") or {}).get("passed")) and not bool((strict.get("summary") or {}).get("temporal_leakage_detected")) and strict.get("parameter_selection_uses_oos") is False and horizon_covered: strict_records.append(record.id)
        robust = record.validation.get("parameter_robustness") if isinstance(record.validation.get("parameter_robustness"), dict) else {}
        if bool((robust.get("summary") or {}).get("robust")): robust_records.append(record.id)
        try:
            if forge.verify_export(record.id).get("ok"): verified_reports.append(record.id)
        except Exception as exc: report_verification_errors.append({"experiment_id": record.id, "type": type(exc).__name__, "message": str(exc)[:500]})
    historical = [row for row in universes["datasets"] if bool((row.get("evidence") or {}).get("includes_delisted"))]
    complete_history = [row for row in historical if _complete_universe_evidence(row)]
    required_hts_profiles = {"LS_HTS", "KIWOOM_HTS", "KIS"}
    hts_complete = bool(hts.get("ok")) and set(hts["profiles"]) == required_hts_profiles and all(bool(hts["profiles"][name].get("fully_verified")) for name in required_hts_profiles)
    verified_corporate_actions = [row for row in corporate_actions["datasets"] if _complete_corporate_action_evidence(row)]
    completed_data_runs = [row for row in realtime.get("runs", []) if row.get("status") == "COMPLETED" and int((row.get("run") or {}).get("data_messages") or 0) > 0 and int((row.get("run") or {}).get("accepted_events") or 0) > 0 and bool((row.get("run") or {}).get("in_session_quality_ok")) and bool(row.get("stream_summaries"))]
    long_runs = qualified_full_session_runs(realtime); active_realtime = active_realtime_progress(base / "realtime")
    report_required = [record.id for record in records if bool(record.result)]; all_reports_verified = bool(report_required) and set(report_required).issubset(verified_reports)
    operational = [
        _check("doctor", doctor.get("ok"), "all local engine diagnostics pass"),
        _check("research_only", not forge.policy.live_order_allowed, "live orders remain impossible"),
        _check("market_provider", external.get("kis_configured"), "KIS read-only credentials configured"),
        _check("websocket_runtime", external.get("websocket_available"), "WebSocket client dependency available"),
        _check("analytical_storage", int(storage.get("row_count") or 0) > 0, f"{storage.get('row_count', 0)} OHLCV rows"),
        _check("performance_gate", performance.get("passed"), "latest bounded performance evidence passes"),
        _check("concurrency_gate", concurrency.get("passed"), "latest concurrent workload evidence passes"),
        _check("archive_integrity", archive_verify.get("verified"), f"{archive_status.get('chunk_count', 0)} Parquet chunks verified"),
    ]
    research = [
        _check("strict_walk_forward_experiment", bool(strict_records), f"experiments={strict_records}"),
        _check("robustness_experiment", bool(robust_records), f"experiments={robust_records}"),
        _check("verified_report_bundle", all_reports_verified, f"required={report_required}; verified={verified_reports}"),
        _check("delisted_universe_present", bool(historical), f"datasets={[row.get('dataset_id') for row in historical]}"),
        _check("realtime_run_hashes", realtime.get("verified") and bool(completed_data_runs), f"runs={realtime.get('run_count', 0)}; completed_data_runs={[row['run']['run_id'] for row in completed_data_runs]}"),
    ]
    full = [
        _check("complete_historical_universe", bool(complete_history), "no clipped listing dates and complete daily history"),
        _check("verified_corporate_action_history", bool(verified_corporate_actions), f"complete source-verified datasets={[row.get('dataset_id') for row in verified_corporate_actions]}"),
        _check("all_hts_profiles_verified", hts_complete, "LS/Kiwoom/KIS all 16 indicators verified from real exports"),
        _check("full_session_realtime_soak", bool(long_runs), f"qualified_runs={[row['run']['run_id'] for row in long_runs]}; active={active_realtime}"),
    ]
    operational_blockers = _blockers(operational)
    research_blockers = _blockers(operational + research)
    full_spec_blockers = _blockers(operational + research + full)
    return {
        "ok": all(row["ok"] for row in operational), "engine_operational_ready": all(row["ok"] for row in operational),
        "research_evidence_ready": all(row["ok"] for row in operational + research), "full_spec_evidence_ready": all(row["ok"] for row in operational + research + full),
        "remaining_operational_blockers": operational_blockers,
        "remaining_research_blockers": research_blockers,
        "remaining_full_spec_blockers": full_spec_blockers,
        "automatic_live_trading_allowed": False, "checks": {"operational": operational, "research": research, "full_spec": full},
        "blockers": {"operational": operational_blockers, "research": _blockers(research), "full_spec": _blockers(full)},
        "evidence": {"storage": storage, "performance": performance, "concurrency": concurrency, "archive": archive_status, "realtime_runs": realtime["run_count"], "realtime_completed_data_runs": realtime["completed_data_run_count"], "active_realtime": active_realtime, "universe_dataset_count": universes["dataset_count"], "corporate_action_dataset_count": corporate_actions["dataset_count"], "verified_corporate_action_dataset_count": len(verified_corporate_actions), "hts_package_count": hts["package_count"], "report_verification_errors": report_verification_errors},
    }


def _check(identifier: str, ok: Any, detail: str) -> dict[str, Any]: return {"id": identifier, "ok": bool(ok), "detail": detail}
def _blockers(rows: list[dict[str, Any]]) -> list[str]: return [row["id"] for row in rows if not row["ok"]]


def _complete_universe_evidence(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    coverage_start, coverage_end = str(evidence.get("coverage_start") or ""), str(evidence.get("coverage_end") or "")
    try:
        coverage_valid = bool(coverage_start and coverage_end and datetime.fromisoformat(coverage_start) <= datetime.fromisoformat(coverage_end))
    except ValueError:
        coverage_valid = False
    return bool(
        evidence.get("official") is True
        and evidence.get("includes_delisted") is True
        and evidence.get("complete_daily_history") is True
        and int(evidence.get("precoverage_listing_dates_clipped") or 0) == 0
        and str(evidence.get("grade") or "") in {"official_listing_interval_history", "complete_listing_history"}
        and coverage_valid
    )


def _complete_corporate_action_evidence(row: dict[str, Any]) -> bool:
    return bool(
        row.get("complete_history") is True
        and row.get("source_documents_verified") is True
        and int(row.get("verified_source_document_count") or 0) > 0
    )
def _json(path: Path) -> dict[str, Any]:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError): return {}


def _verified_evidence(path: Path) -> dict[str, Any]:
    payload = _json(path); stored = str(payload.get("evidence_hash") or "")
    canonical = json.dumps({key: value for key, value in payload.items() if key not in {"evidence_hash", "path"}}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
    payload["evidence_verified"] = bool(stored and stored == expected)
    if not payload["evidence_verified"]: payload["passed"] = False
    return payload


def _verified_performance(path: Path) -> dict[str, Any]:
    payload = _verified_evidence(path); measurements = payload.get("measurements") if isinstance(payload.get("measurements"), list) else []
    names = {str(row.get("name")) for row in measurements if isinstance(row, dict) and row.get("passed") is True}
    payload["structure_verified"] = payload.get("schema_version") == 1 and {"duckdb_bounded_query", "all_indicators"}.issubset(names)
    if not payload["structure_verified"]: payload["passed"] = False
    return payload


def _verified_concurrency(path: Path) -> dict[str, Any]:
    payload = _verified_evidence(path); measurements = payload.get("measurements") if isinstance(payload.get("measurements"), dict) else {}
    required = {"storage_write", "storage_read", "indicator_compute", "collection", "backtest"}
    payload["structure_verified"] = payload.get("schema_version") == 1 and int(payload.get("iterations") or 0) >= 2 and required.issubset(measurements) and payload.get("errors") == []
    if not payload["structure_verified"]: payload["passed"] = False
    return payload


def qualified_full_session_runs(history: dict[str, Any]) -> list[dict[str, Any]]:
    qualified = []
    for row in history.get("runs", []):
        run = row.get("run") or {}; requested = float(run.get("requested_duration_seconds") or 0); elapsed = _elapsed(run)
        duration_completed = bool(run.get("duration_completed")) if "duration_completed" in run else elapsed + 0.05 >= requested
        duration_reason_ok = run.get("completion_reason") == "duration_reached" if "completion_reason" in run else True
        recovery_ok = bool(run.get("reconnect_recovery_ok")) if "reconnect_recovery_ok" in run else int(run.get("reconnects") or 0) == 0
        safety_ok = row.get("provider") == "kis-readonly-websocket" and row.get("read_only") is True and row.get("order_allowed") is False
        if row.get("status") == "COMPLETED" and safety_ok and requested >= 14_400 and elapsed >= 14_400 and duration_completed and duration_reason_ok and recovery_ok and int(run.get("data_messages") or 0) > 0 and bool(run.get("in_session_quality_ok")):
            qualified.append(row)
    return qualified


def _elapsed(run: dict[str, Any]) -> float:
    if run.get("elapsed_seconds") is not None: return float(run.get("elapsed_seconds") or 0)
    try: return max(0.0, (datetime.fromisoformat(str(run["finished_at"])) - datetime.fromisoformat(str(run["started_at"]))).total_seconds())
    except (KeyError, TypeError, ValueError): return 0.0


def active_realtime_progress(root: Path, stale_after_seconds: float = 120.0) -> dict[str, Any] | None:
    checkpoint = _json(root / "checkpoint.json")
    if checkpoint.get("status") != "RUNNING": return None
    try:
        started = datetime.fromisoformat(str(checkpoint["run_started_at"])); updated = datetime.fromisoformat(str(checkpoint["updated_at"]))
        now = datetime.now(timezone.utc); elapsed = max(0.0, (now - started).total_seconds()); age = max(0.0, (now - updated).total_seconds())
    except (KeyError, TypeError, ValueError): return {"run_id": checkpoint.get("run_id"), "fresh": False, "reason": "invalid checkpoint timestamps"}
    requested = max(0.0, float(checkpoint.get("requested_duration_seconds") or 0)); progress = min(100.0, elapsed / requested * 100.0) if requested else None
    per_run = "run_message_count" in checkpoint
    return {
        "run_id": checkpoint.get("run_id"), "fresh": age <= max(1.0, float(stale_after_seconds)),
        "checkpoint_age_seconds": round(age, 3), "elapsed_seconds": round(elapsed, 3),
        "requested_duration_seconds": requested, "duration_progress_percent": round(progress, 3) if progress is not None else None,
        "counter_scope": "current_run" if per_run else "cumulative_legacy",
        "run_messages": int(checkpoint.get("run_message_count") if per_run else checkpoint.get("message_count") or 0),
        "run_data_messages": int(checkpoint.get("run_data_messages") if per_run else checkpoint.get("data_messages") or 0),
        "run_accepted_events": int(checkpoint.get("run_accepted_events") if per_run else checkpoint.get("accepted_events") or 0),
        "run_duplicate_events": int(checkpoint.get("run_duplicate_events") if per_run else checkpoint.get("duplicate_events") or 0),
        "run_reconnects": int(checkpoint.get("run_reconnect_count") if per_run else checkpoint.get("reconnect_count") or 0),
        "cumulative_data_messages": int(checkpoint.get("data_messages") or 0), "cumulative_accepted_events": int(checkpoint.get("accepted_events") or 0),
        "cumulative_duplicate_events": int(checkpoint.get("duplicate_events") or 0), "last_error": checkpoint.get("last_error"),
        "read_only": bool(checkpoint.get("read_only")), "order_allowed": bool(checkpoint.get("order_allowed")),
    }
