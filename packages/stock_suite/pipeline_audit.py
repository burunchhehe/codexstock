"""Audit the candidate-ledger to signed-signal handoff without executing orders."""

from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path


def _parse_time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def _tail_jsonl(path: Path, max_bytes: int = 2_000_000) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("rb") as handle:
        size = handle.seek(0, 2)
        offset = max(0, size - max_bytes)
        handle.seek(offset)
        if offset:
            handle.readline()
        raw_lines = handle.readlines()
    rows: list[dict[str, object]] = []
    for raw in raw_lines:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _latest_time(row: dict[str, object]) -> datetime | None:
    for key in ("recorded_at", "plan_generated_at", "generated_at", "created_at"):
        parsed = _parse_time(row.get(key))
        if parsed:
            return parsed
    return None


def _is_regular_market_session(now: datetime) -> bool:
    local = now.astimezone()
    return local.weekday() < 5 and time(9, 0) <= local.time().replace(tzinfo=None) <= time(15, 30)


def _count_json_files(path: Path | None, *, today: object | None = None) -> int:
    if path is None or not Path(path).exists():
        return 0
    files = list(Path(path).glob("*.json"))
    if today is None:
        return len(files)
    count = 0
    for item in files:
        try:
            modified = datetime.fromtimestamp(item.stat().st_mtime).astimezone().date()
        except OSError:
            continue
        if modified == today:
            count += 1
    return count


def _json_file_ids(path: Path | None, *, today: object | None = None) -> set[str]:
    if path is None or not Path(path).exists():
        return set()
    identifiers: set[str] = set()
    for item in Path(path).glob("*.json"):
        if today is not None:
            try:
                modified = datetime.fromtimestamp(item.stat().st_mtime).astimezone().date()
            except OSError:
                continue
            if modified != today:
                continue
        identifiers.add(item.stem)
    return identifiers


def _json_documents(path: Path | None, *, today: object | None = None) -> dict[str, dict[str, object]]:
    if path is None or not Path(path).exists():
        return {}
    documents: dict[str, dict[str, object]] = {}
    for item in Path(path).glob("*.json"):
        if today is not None:
            try:
                modified = datetime.fromtimestamp(item.stat().st_mtime).astimezone().date()
            except OSError:
                continue
            if modified != today:
                continue
        try:
            value = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            documents[item.stem] = value
    return documents


def _ticket_execution_mode(ticket: dict[str, object]) -> str:
    metadata = ticket.get("metadata") if isinstance(ticket.get("metadata"), dict) else {}
    explicit = str(metadata.get("execution_mode") or "").strip()
    if explicit:
        return explicit
    authority = metadata.get("execution_authority") if isinstance(metadata.get("execution_authority"), dict) else {}
    explicit = str(authority.get("control_mode") or "").strip()
    if explicit:
        return explicit
    status = str(ticket.get("status") or "").strip()
    if status == "DELEGATED_SIGNAL_READY":
        return "delegated_auto"
    if status == "APPROVAL_REQUIRED":
        return "manual_approval"
    return "unspecified"


def _candidate_key(item: dict[str, object], fallback: str) -> str:
    return str(
        item.get("symbol")
        or item.get("stock_code")
        or item.get("code")
        or item.get("name")
        or fallback
    ).strip()


def _latest_matching_file_time(path: Path | None, identifiers: set[str]) -> datetime | None:
    if path is None or not Path(path).exists() or not identifiers:
        return None
    observed: list[datetime] = []
    for identifier in identifiers:
        item = Path(path) / f"{identifier}.json"
        try:
            observed.append(datetime.fromtimestamp(item.stat().st_mtime).astimezone())
        except OSError:
            continue
    return max(observed, default=None)


def _continuous_validation_pending_since(
    rows: list[dict[str, object]],
    *,
    today: object,
) -> dict[str, datetime]:
    pending_since: dict[str, datetime] = {}
    for row_index, row in enumerate(rows):
        observed_at = _latest_time(row)
        if observed_at is None or observed_at.astimezone().date() != today:
            continue
        items = [item for item in (row.get("items") or []) if isinstance(item, dict)]
        current: set[str] = set()
        for item_index, item in enumerate(items):
            if float(item.get("score") or 0.0) < 70.0:
                continue
            if item.get("detail_validation_passed") is True:
                continue
            key = _candidate_key(item, f"row-{row_index}-item-{item_index}")
            current.add(key)
            pending_since.setdefault(key, observed_at)
        for key in list(pending_since):
            if key not in current:
                pending_since.pop(key, None)
    return pending_since


def audit_candidate_pipeline(
    ticket_file: Path,
    outbox: Path,
    processed_dir: Path | None = None,
    results_dir: Path | None = None,
    market_pulse_file: Path | None = None,
    minute_radar_file: Path | None = None,
    candidate_decision_file: Path | None = None,
    *,
    handoff_timeout_seconds: float = 120.0,
    scan_timeout_seconds: float = 600.0,
    validation_timeout_seconds: float = 300.0,
    promotion_timeout_seconds: float = 120.0,
    service_mode: str = "",
    control_mode: str = "",
    now: datetime | None = None,
) -> dict[str, object]:
    now = now or datetime.now().astimezone()
    all_tickets = [row for row in _tail_jsonl(Path(ticket_file)) if row.get("mode") == "live_candidate"]
    today = now.date()
    tickets = [
        row for row in all_tickets
        if (_parse_time(row.get("created_at")) or datetime.min.astimezone()).astimezone().date() == today
    ]
    passed = [row for row in tickets if row.get("risk_status") == "PASSED"]
    published = [
        row for row in passed
        if isinstance(row.get("shadow_signal"), dict) and row["shadow_signal"].get("published") is True
    ]
    failed = [
        row for row in passed
        if isinstance(row.get("shadow_signal"), dict) and row["shadow_signal"].get("published") is False
    ]
    latest = tickets[-1] if tickets else {}
    latest_at = _parse_time(latest.get("created_at"))
    age_seconds = max(0.0, (now - latest_at).total_seconds()) if latest_at else None
    inbox_count = _count_json_files(Path(outbox))
    processed_count = _count_json_files(processed_dir, today=today)
    result_count = _count_json_files(results_dir, today=today)
    processed_ids = _json_file_ids(processed_dir)
    result_ids = _json_file_ids(results_dir)
    processed_documents = _json_documents(processed_dir, today=today)
    result_documents = _json_documents(results_dir, today=today)
    published_signal_rows: list[dict[str, object]] = []
    for row in published:
        signal = row.get("shadow_signal") if isinstance(row.get("shadow_signal"), dict) else {}
        signal_id = str(signal.get("signal_id") or row.get("id") or "").strip()
        created_at = _parse_time(row.get("created_at"))
        signal_age = max(0.0, (now - created_at).total_seconds()) if created_at else None
        published_signal_rows.append({
            "signal_id": signal_id,
            "created_at": created_at,
            "age_seconds": signal_age,
            "processed": bool(signal_id and signal_id in processed_ids),
            "result_recorded": bool(signal_id and signal_id in result_ids),
        })
    matched_processed_count = sum(bool(row["processed"]) for row in published_signal_rows)
    matched_result_count = sum(bool(row["result_recorded"]) for row in published_signal_rows)
    overdue_handoffs = [
        row for row in published_signal_rows
        if not row["result_recorded"]
        and row["age_seconds"] is not None
        and float(row["age_seconds"]) > max(1.0, float(handoff_timeout_seconds))
    ]
    legacy_approval_observed = [
        row for row in tickets
        if str(row.get("status") or "") == "DELEGATED_SIGNAL_READY"
        and bool(row.get("approval_token"))
    ]
    # Old full-auto tickets could contain an inert approval token.  It is a
    # migration defect, not an active gate, once the signed signal and matching
    # executor result prove the delegated handoff completed.
    legacy_approval = []
    for row in legacy_approval_observed:
        signal = row.get("shadow_signal") if isinstance(row.get("shadow_signal"), dict) else {}
        signal_id = str(signal.get("signal_id") or row.get("id") or "").strip()
        if not signal.get("published") or not signal_id or signal_id not in result_ids:
            legacy_approval.append(row)

    ticket_modes = {
        mode for row in tickets
        if (mode := _ticket_execution_mode(row)) != "unspecified"
    }
    signal_modes = {
        str(document.get("execution_mode") or "").strip()
        for document in processed_documents.values()
        if str(document.get("execution_mode") or "").strip() not in {"", "unspecified"}
    }
    result_modes = {
        str((document.get("result") or {}).get("mode") or "").strip()
        for document in result_documents.values()
        if isinstance(document.get("result"), dict)
        and str((document.get("result") or {}).get("mode") or "").strip()
    }
    effective_control_mode = str(control_mode or "").strip() or (
        next(iter(ticket_modes)) if len(ticket_modes) == 1 else ""
    )
    expected_service_mode = "live" if effective_control_mode == "delegated_auto" else ""
    mode_mismatch = bool(
        len(ticket_modes) > 1
        or (effective_control_mode and ticket_modes and ticket_modes != {effective_control_mode})
        or (expected_service_mode and service_mode and service_mode != expected_service_mode)
        or (effective_control_mode == "delegated_auto" and result_modes and result_modes != {"live"})
        or (effective_control_mode == "manual_approval" and "live" in result_modes)
    )
    semi_auto_approval_bypass = [
        row for row in tickets
        if _ticket_execution_mode(row) == "manual_approval"
        and isinstance(row.get("shadow_signal"), dict)
        and row["shadow_signal"].get("published") is True
        and not bool(row.get("approval_token"))
    ]
    pulse_rows = _tail_jsonl(Path(market_pulse_file)) if market_pulse_file else []
    radar_rows = _tail_jsonl(Path(minute_radar_file)) if minute_radar_file else []
    decision_rows = _tail_jsonl(Path(candidate_decision_file)) if candidate_decision_file else []
    latest_pulse = pulse_rows[-1] if pulse_rows else {}
    latest_radar = radar_rows[-1] if radar_rows else {}
    latest_decision = decision_rows[-1] if decision_rows else {}
    pulse_at = _latest_time(latest_pulse)
    radar_at = _latest_time(latest_radar)
    decision_at = _latest_time(latest_decision)
    pulse_age = max(0.0, (now - pulse_at).total_seconds()) if pulse_at else None
    radar_age = max(0.0, (now - radar_at).total_seconds()) if radar_at else None
    decision_age = max(0.0, (now - decision_at).total_seconds()) if decision_at else None
    decision_checks = (
        latest_decision.get("checks_summary")
        if isinstance(latest_decision.get("checks_summary"), dict)
        else {}
    )
    decision_blocker_contract = (
        decision_checks.get("blocker_classification")
        if isinstance(decision_checks.get("blocker_classification"), dict)
        else {}
    )
    decision_blocker_classification = str(
        decision_blocker_contract.get("primary") or ""
    ).strip().upper()
    radar_items = [item for item in (latest_radar.get("items") or []) if isinstance(item, dict)]
    validation_pending = [
        item for item in radar_items
        if float(item.get("score") or 0.0) >= 70.0 and item.get("detail_validation_passed") is not True
    ]
    validation_complete = [item for item in radar_items if item.get("detail_validation_passed") is True]
    validation_pending_since = _continuous_validation_pending_since(
        radar_rows,
        today=today,
    )
    oldest_validation_pending_at = (
        min(validation_pending_since.values()) if validation_pending_since else None
    )
    validation_pending_age = (
        max(0.0, (now - oldest_validation_pending_at).total_seconds())
        if oldest_validation_pending_at
        else None
    )
    session_active = _is_regular_market_session(now)
    local_now = now.astimezone()
    session_start = local_now.replace(hour=9, minute=0, second=0, microsecond=0)
    session_elapsed_seconds = max(0.0, (local_now - session_start).total_seconds())
    scan_observed_today = bool(
        pulse_at and pulse_at.astimezone().date() == local_now.date()
    )
    radar_observed_today = bool(
        radar_at and radar_at.astimezone().date() == local_now.date()
    )
    incidents: list[dict[str, object]] = []
    if failed:
        incidents.append({
            "code": "SIGNED_SIGNAL_MISSING",
            "severity": "high",
            "detail": "A risk-passed candidate failed signed-signal publication.",
            "count": len(failed),
        })
    if overdue_handoffs:
        incidents.append({
            "code": "EXECUTOR_HANDOFF_FAILED",
            "severity": "high",
            "detail": "Signed signals have no matching executor result within the handoff timeout.",
            "count": len(overdue_handoffs),
            "signal_ids": [str(row["signal_id"]) for row in overdue_handoffs[:10]],
            "oldest_age_seconds": round(
                max(float(row["age_seconds"] or 0.0) for row in overdue_handoffs),
                3,
            ),
        })
    if legacy_approval:
        incidents.append({
            "code": "LEGACY_APPROVAL_GATE_ACTIVE",
            "severity": "high",
            "detail": "A delegated-auto ticket unexpectedly contains an approval token.",
            "count": len(legacy_approval),
        })
    if semi_auto_approval_bypass:
        incidents.append({
            "code": "APPROVAL_GATE_BYPASSED",
            "severity": "high",
            "detail": "A semi-auto ticket reached signed-signal publication without an approval token.",
            "count": len(semi_auto_approval_bypass),
        })
    if mode_mismatch:
        incidents.append({
            "code": "EXECUTION_MODE_MISMATCH",
            "severity": "high",
            "detail": "Ticket, signal, service, or executor-result modes do not agree.",
            "ticket_modes": sorted(ticket_modes),
            "signal_modes": sorted(signal_modes),
            "service_mode": service_mode,
            "result_modes": sorted(result_modes),
        })
    if (
        market_pulse_file is not None
        and session_active
        and session_elapsed_seconds > scan_timeout_seconds
        and (not scan_observed_today or pulse_age is None or pulse_age > scan_timeout_seconds)
    ):
        incidents.append({
            "code": "MARKET_SCAN_STALLED",
            "severity": "high",
            "detail": (
                "No intraday market scan was recorded today."
                if not scan_observed_today
                else "The intraday market scan exceeded its allowed age."
            ),
            "age_seconds": round(pulse_age, 3) if pulse_age is not None else None,
        })
    if (
        session_active
        and scan_observed_today
        and int(latest_pulse.get("count") or len(latest_pulse.get("items") or [])) > 0
        and session_elapsed_seconds > validation_timeout_seconds
        and not radar_observed_today
    ):
        incidents.append({
            "code": "CANDIDATE_VALIDATION_STALLED",
            "severity": "high",
            "detail": "Market scan produced items but no candidate radar validation was recorded today.",
            "count": int(latest_pulse.get("count") or len(latest_pulse.get("items") or [])),
            "age_seconds": None,
        })
    elif (
        session_active
        and validation_pending
        and validation_pending_age is not None
        and validation_pending_age > validation_timeout_seconds
    ):
        incidents.append({
            "code": "CANDIDATE_VALIDATION_STALLED",
            "severity": "high",
            "detail": "High-score candidates remained unvalidated beyond the deadline.",
            "count": len(validation_pending),
            "age_seconds": round(validation_pending_age, 3),
            "candidate_ids": sorted(validation_pending_since)[:10],
        })
    if (
        session_active
        and latest_decision.get("candidate_ready") is True
        and latest_decision.get("broker_submit_ready") is True
        and decision_age is not None
        and decision_age > promotion_timeout_seconds
        and not tickets
    ):
        incidents.append({
            "code": "CANDIDATE_PROMOTION_STALLED",
            "severity": "high",
            "detail": "An execution-ready decision did not become a live candidate ticket.",
            "age_seconds": round(decision_age, 3),
        })
    existing_incident_codes = {str(item.get("code") or "") for item in incidents}
    if (
        session_active
        and decision_age is not None
        and decision_age > validation_timeout_seconds
        and decision_blocker_classification in {"DATA_UNAVAILABLE", "SYSTEM_BOTTLENECK"}
    ):
        issue_code = (
            "CANDIDATE_VALIDATION_STALLED"
            if decision_blocker_classification == "DATA_UNAVAILABLE"
            else "CANDIDATE_PROMOTION_STALLED"
        )
        if issue_code not in existing_incident_codes:
            incidents.append({
                "code": issue_code,
                "severity": "high",
                "detail": (
                    "Candidate processing remained blocked by unavailable data."
                    if decision_blocker_classification == "DATA_UNAVAILABLE"
                    else "Candidate processing remained blocked by a system bottleneck."
                ),
                "age_seconds": round(decision_age, 3),
                "blocker_classification": decision_blocker_classification,
            })
    healthy = not incidents
    if incidents:
        state = "pipeline_stalled"
        no_trade_classification = "SYSTEM_BOTTLENECK"
    elif published and matched_result_count == len(published):
        state = "connected"
        no_trade_classification = "EXECUTION_OBSERVED"
    elif published:
        state = "executor_processing"
        no_trade_classification = "NORMAL_IN_PROGRESS"
    elif tickets:
        state = "candidate_not_promoted"
        no_trade_classification = "NORMAL_RISK_BLOCK" if not passed else "SYSTEM_BOTTLENECK"
    elif decision_blocker_classification == "DATA_UNAVAILABLE":
        state = "data_wait"
        no_trade_classification = "DATA_UNAVAILABLE"
    elif decision_blocker_classification == "SYSTEM_BOTTLENECK":
        state = "system_bottleneck"
        no_trade_classification = "SYSTEM_BOTTLENECK"
    elif latest_decision and latest_decision.get("candidate_ready") is False:
        state = "normal_risk_block"
        no_trade_classification = "NORMAL_RISK_BLOCK"
    else:
        state = "normal_watch"
        no_trade_classification = "NORMAL_WATCH"
    evidence_levels = {
        "market_scan": "recent_success" if scan_observed_today else "not_observed_today",
        "candidate_validation": "recent_success" if validation_complete else (
            "in_progress" if validation_pending else "not_observed_today"
        ),
        "candidate_promotion": "recent_success" if tickets else (
            "risk_blocked" if latest_decision else "not_observed_today"
        ),
        "signed_signal": "recent_success" if published else "not_observed_today",
        "executor_handoff": "end_to_end_success" if published and matched_result_count == len(published) else (
            "in_progress" if published else "not_observed_today"
        ),
    }
    matching_result_ids = {
        str(row["signal_id"])
        for row in published_signal_rows
        if row["result_recorded"] and str(row["signal_id"])
    }
    latest_result_at = _latest_matching_file_time(
        results_dir,
        matching_result_ids,
    )
    blocked_labels = []
    if isinstance(latest_decision.get("checks_summary"), dict):
        blocked_labels = [
            str(value)
            for value in latest_decision["checks_summary"].get("blocked_labels", [])
            if str(value).strip()
        ]
    return {
        "schema": "codexstock_candidate_pipeline_audit_v2",
        "ok": healthy,
        "system_healthy": True,
        "trading_pipeline_healthy": healthy,
        "state": state,
        "no_trade_classification": no_trade_classification,
        "checked_at": now.isoformat(timespec="seconds"),
        "latest_candidate_at": latest_at.isoformat(timespec="seconds") if latest_at else "",
        "latest_candidate_age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "recent_live_candidate_count": len(tickets),
        "historical_live_candidate_count": len(all_tickets),
        "recent_passed_count": len(passed),
        "signed_signal_published_count": len(published),
        "publish_failure_count": len(failed),
        "last_publish_failure": failed[-1].get("shadow_signal") if failed else {},
        "inbox_pending": inbox_count,
        "executor_processed_count": processed_count,
        "executor_result_count": result_count,
        "matched_executor_processed_count": matched_processed_count,
        "matched_executor_result_count": matched_result_count,
        "pending_handoff_count": len(published) - matched_result_count,
        "pending_handoff_signal_ids": [
            str(row["signal_id"])
            for row in published_signal_rows
            if not row["result_recorded"]
        ][:10],
        "legacy_approval_token_count": len(legacy_approval),
        "legacy_approval_token_observed_count": len(legacy_approval_observed),
        "execution_mode_contract": {
            "control_mode": effective_control_mode or "unknown",
            "ticket_modes": sorted(ticket_modes),
            "signal_modes": sorted(signal_modes),
            "service_mode": service_mode or "unknown",
            "result_modes": sorted(result_modes),
            "mode_consistent": not mode_mismatch,
            "approval_required": effective_control_mode == "manual_approval",
        },
        "executor_result_summary": {
            "total": len(result_documents),
            "states": {
                state: sum(1 for row in result_documents.values() if str(row.get("state") or "UNKNOWN") == state)
                for state in sorted({str(row.get("state") or "UNKNOWN") for row in result_documents.values()})
            },
            "reasons": {
                reason: sum(1 for row in result_documents.values() if str(row.get("reason") or "unknown") == reason)
                for reason in sorted({str(row.get("reason") or "unknown") for row in result_documents.values()})
            },
        },
        "market_session_active": session_active,
        "latest_market_scan_at": pulse_at.isoformat(timespec="seconds") if pulse_at else "",
        "latest_market_scan_age_seconds": round(pulse_age, 3) if pulse_age is not None else None,
        "latest_radar_at": radar_at.isoformat(timespec="seconds") if radar_at else "",
        "latest_decision_at": decision_at.isoformat(timespec="seconds") if decision_at else "",
        "latest_matching_result_at": latest_result_at.isoformat(timespec="seconds") if latest_result_at else "",
        "normal_watch_reason": {
            "classification": no_trade_classification,
            "blocker_classification": decision_blocker_classification or "UNCLASSIFIED",
            "blocked_labels": blocked_labels[:10],
            "market_scan_items": int(latest_pulse.get("count") or len(latest_pulse.get("items") or [])),
            "validated_candidates": len(validation_complete),
        },
        "incidents": incidents,
        "evidence_levels": evidence_levels,
        "evidence_generated_at": now.isoformat(timespec="seconds"),
        "sla_seconds": {
            "market_scan": float(scan_timeout_seconds),
            "candidate_validation": float(validation_timeout_seconds),
            "candidate_promotion": float(promotion_timeout_seconds),
            "executor_handoff": float(handoff_timeout_seconds),
        },
        "stage_last_success_at": {
            "market_scan": pulse_at.isoformat(timespec="seconds") if pulse_at else "",
            "candidate_validation": radar_at.isoformat(timespec="seconds") if validation_complete and radar_at else "",
            "candidate_decision": decision_at.isoformat(timespec="seconds") if decision_at else "",
            "candidate_ticket": latest_at.isoformat(timespec="seconds") if latest_at else "",
            "signed_signal": latest_at.isoformat(timespec="seconds") if published and latest_at else "",
            "executor_result": latest_result_at.isoformat(timespec="seconds") if latest_result_at else "",
        },
        "stage_counts": {
            "candidate_tickets": len(tickets),
            "market_scan_items": int(latest_pulse.get("count") or len(latest_pulse.get("items") or [])),
            "radar_candidates": len(radar_items),
            "validation_pending": len(validation_pending),
            "validation_complete": len(validation_complete),
            "execution_ready_decisions": int(
                latest_decision.get("candidate_ready") is True
                and latest_decision.get("broker_submit_ready") is True
            ),
            "risk_passed": len(passed),
            "signed_signal_published": len(published),
            "executor_inbox_pending": inbox_count,
            "executor_processed": processed_count,
            "executor_results": result_count,
            "matched_executor_processed": matched_processed_count,
            "matched_executor_results": matched_result_count,
        },
        "note": {
            "normal_watch": "No live candidate ticket exists; this is normal watch until scan evidence says otherwise.",
            "candidate_not_promoted": "Candidate tickets exist but none reached signed-signal publication.",
            "executor_processing": "A signed signal was published and is still within the executor handoff window.",
            "connected": "Candidate-to-signal-to-executor result handoff observed.",
            "normal_risk_block": "Candidates were reviewed and intentionally blocked by recorded risk checks.",
            "data_wait": "Candidates were blocked because required market evidence was unavailable.",
            "system_bottleneck": "Candidates were blocked by a recorded system workflow bottleneck.",
            "pipeline_stalled": "A concrete candidate execution pipeline incident requires diagnosis.",
        }[state],
    }
