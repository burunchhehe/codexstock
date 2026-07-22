"""Evidence audit for long-running Shadow execution validation."""

from __future__ import annotations

import json
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from .runtime_evidence import audit_runtime_evidence
from .execution_sidecar import OrderSignal


def _read(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _canonical_result(value: dict[str, object]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _ticket_evidence(path: Path, max_bytes: int = 4_000_000) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        size = handle.seek(0, 2)
        offset = max(0, size - max_bytes)
        handle.seek(offset)
        if offset:
            handle.readline()
        raw_lines = handle.readlines()
    evidence: dict[str, dict[str, object]] = {}
    for raw in raw_lines:
        try:
            ticket = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(ticket, dict) or not ticket.get("id"):
            continue
        unsigned_ticket = dict(ticket)
        unsigned_ticket.pop("shadow_signal", None)
        encoded = json.dumps(
            unsigned_ticket,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        evidence[str(ticket["id"])] = {
            "hash": hashlib.sha256(encoded).hexdigest(),
            "risk_status": str(ticket.get("risk_status") or "").upper().strip(),
            "mode": str(ticket.get("mode") or "").lower().strip(),
            "symbol": str(ticket.get("symbol") or "").upper().strip(),
            "created_at": ticket.get("created_at"),
        }
    return evidence


def audit_shadow_runtime(
    root: Path,
    min_observation_hours: float = 24.0,
    min_result_count: int = 10,
    min_symbol_count: int = 2,
) -> dict[str, object]:
    root = Path(root)
    status = _read(root / "status.json")
    status_mode = str(status.get("mode") or "shadow")
    now = datetime.now().astimezone()
    updated = _parse(status.get("updated_at"))
    started = _parse(status.get("started_at"))
    heartbeat_age = (now - updated).total_seconds() if updated else None
    runtime_evidence = audit_runtime_evidence(root / "runtime_evidence.sqlite3")
    observation_hours = float(runtime_evidence.get("continuous_hours") or 0.0)
    shadow_candidate_scheduler = _read(root / "shadow_candidate_scheduler.json")
    scheduler_checked_at = _parse(shadow_candidate_scheduler.get("last_checked_at"))
    scheduler_age_seconds = (
        (now - scheduler_checked_at).total_seconds() if scheduler_checked_at else None
    )
    scheduler_status = str(shadow_candidate_scheduler.get("last_status") or "")
    scheduler_market_open = shadow_candidate_scheduler.get("market_open") is True
    scheduler_blocked = scheduler_market_open and scheduler_status in {
        "ERROR", "PUBLISH_BLOCKED", "NO_CANDIDATE"
    }
    scheduler_healthy = (
        bool(shadow_candidate_scheduler)
        and scheduler_age_seconds is not None
        and scheduler_age_seconds >= -5
        and scheduler_age_seconds <= 900
        and not scheduler_blocked
    )

    result_paths = sorted((root / "results").glob("*.json")) if (root / "results").exists() else []
    rows = [_read(path) for path in result_paths]
    rows = [row for row in rows if row]
    processed_count = len(list((root / "processed").glob("*.json"))) if (root / "processed").exists() else 0
    result_by_id = {str(row.get("signal_id") or ""): row for row in rows if row.get("signal_id")}
    source_by_id: dict[str, dict[str, object]] = {}
    if (root / "processed").exists():
        for path in (root / "processed").glob("*.json"):
            source = _read(path)
            signal_id = str(source.get("signal_id") or path.stem)
            source_by_id[signal_id] = source
    ticket_evidence = _ticket_evidence(root.parent / "order_tickets.jsonl")
    continuous_started_at = _parse(runtime_evidence.get("continuous_started_at"))
    candidate_ticket_hash_mismatches: list[str] = []
    candidate_signature_mismatches: list[str] = []
    try:
        signing_secret = (root / "signal_secret").read_bytes().strip()
    except OSError:
        signing_secret = b""
    diagnostic_markers = ("diagnostic", "e2e", "test", "drill", "simulation")
    diagnostic_signal_ids = sorted(
        signal_id for signal_id, source in source_by_id.items()
        if any(marker in str(source.get("strategy_id") or "").lower() for marker in diagnostic_markers)
    )
    qualification_failures: dict[str, list[str]] = {}
    qualifying_rows: list[dict[str, object]] = []
    for row in rows:
        signal_id = str(row.get("signal_id") or "")
        source = source_by_id.get(signal_id, {})
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
        reasons: list[str] = []
        if signal_id in diagnostic_signal_ids:
            reasons.append("diagnostic_strategy")
        if source.get("origin") != "candidate_ledger":
            reasons.append("missing_candidate_ledger_origin")
        elif not signing_secret:
            reasons.append("missing_signing_secret")
            candidate_signature_mismatches.append(signal_id)
        else:
            try:
                signature_valid = OrderSignal(**source).verify(signing_secret)
            except (TypeError, ValueError):
                signature_valid = False
            if not signature_valid:
                reasons.append("invalid_candidate_signature")
                candidate_signature_mismatches.append(signal_id)
        ticket_hash = str(source.get("candidate_ticket_hash") or "")
        ticket = ticket_evidence.get(signal_id, {})
        if len(ticket_hash) != 64:
            reasons.append("missing_candidate_ticket_hash")
        elif source.get("origin") == "candidate_ledger" and ticket.get("hash") != ticket_hash:
            reasons.append("candidate_ticket_hash_mismatch")
            candidate_ticket_hash_mismatches.append(signal_id)
        if ticket.get("risk_status") != "PASSED":
            reasons.append("upstream_gate_not_passed")
        if ticket.get("mode") != "live_candidate":
            reasons.append("not_live_candidate_ticket")
        source_symbol = str(source.get("symbol") or "").upper().strip()
        result_symbol = str(result.get("symbol") or "").upper().strip()
        if not source_symbol or ticket.get("symbol") != source_symbol or result_symbol != source_symbol:
            reasons.append("candidate_symbol_mismatch")
        source_created_at = _parse(source.get("created_at"))
        ticket_created_at = _parse(ticket.get("created_at"))
        if continuous_started_at is None:
            reasons.append("runtime_segment_start_missing")
        elif source_created_at is None or source_created_at < continuous_started_at:
            reasons.append("signal_predates_runtime_segment")
        elif ticket_created_at is None or ticket_created_at < continuous_started_at:
            reasons.append("ticket_predates_runtime_segment")
        if not str(snapshot.get("data_source") or "").startswith("KIS_READONLY"):
            reasons.append("non_kis_readonly_snapshot")
        if reasons:
            qualification_failures[signal_id] = reasons
        else:
            qualifying_rows.append(row)
    ledger_by_id: dict[str, dict[str, object]] = {}
    ledger_path = root / "ledger.sqlite3"
    if ledger_path.exists():
        try:
            db = sqlite3.connect(f"file:{ledger_path.as_posix()}?mode=ro", uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            try:
                ledger_by_id = {
                    str(row["signal_id"]): dict(row)
                    for row in db.execute(
                        "SELECT signal_id,payload_hash,state,reason,result_json FROM signals"
                    )
                }
            finally:
                db.close()
        except sqlite3.Error:
            ledger_by_id = {}
    ledger_missing_results = sorted(set(ledger_by_id) - set(result_by_id))
    result_missing_ledger = sorted(set(result_by_id) - set(ledger_by_id))
    ledger_result_mismatches = sorted(
        signal_id for signal_id in set(ledger_by_id) & set(result_by_id)
        if ledger_by_id[signal_id].get("state") != result_by_id[signal_id].get("state")
        or ledger_by_id[signal_id].get("reason") != result_by_id[signal_id].get("reason")
    )
    result_payload_mismatches: list[str] = []
    for signal_id in set(ledger_by_id) & set(result_by_id):
        try:
            ledger_result = json.loads(str(ledger_by_id[signal_id].get("result_json") or "{}"))
        except json.JSONDecodeError:
            result_payload_mismatches.append(signal_id)
            continue
        file_result = result_by_id[signal_id].get("result")
        if not isinstance(ledger_result, dict) or not isinstance(file_result, dict):
            result_payload_mismatches.append(signal_id)
            continue
        if _canonical_result(ledger_result) != _canonical_result(file_result):
            result_payload_mismatches.append(signal_id)
    source_hash_mismatches: list[str] = []
    for signal_id, ledger_row in ledger_by_id.items():
        source_path = root / "processed" / f"{signal_id}.json"
        if not source_path.exists():
            source_hash_mismatches.append(signal_id)
            continue
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            source_hash = hashlib.sha256(encoded).hexdigest()
        except (OSError, json.JSONDecodeError):
            source_hash = ""
        if source_hash != ledger_row.get("payload_hash"):
            source_hash_mismatches.append(signal_id)
    real_order_violations = [
        str(row.get("signal_id") or "")
        for row in rows
        if isinstance(row.get("result"), dict) and row["result"].get("real_order_submitted") is True
    ]
    invalid_acceptances: list[str] = []
    observed_symbols: set[str] = set()
    for row in rows:
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        symbol = str(result.get("symbol") or "").upper().strip()
        if row in qualifying_rows and symbol:
            observed_symbols.add(symbol)
        if row.get("state") not in {"SHADOW_ACCEPTED", "PAPER_FILLED"}:
            continue
        snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
        if snapshot.get("account_ok") is not True or snapshot.get("snapshot_errors"):
            invalid_acceptances.append(str(row.get("signal_id") or ""))

    paper_reconciliation = status.get("paper_reconciliation")
    paper_ledger_ok = (
        status.get("mode") != "paper"
        or isinstance(paper_reconciliation, dict) and paper_reconciliation.get("ok") is True
    )
    candidate_pipeline = status.get("candidate_pipeline")
    candidate_pipeline_ok = not isinstance(candidate_pipeline, dict) or candidate_pipeline.get("ok") is not False
    checks = {
        "heartbeat_fresh": heartbeat_age is not None and -5 <= heartbeat_age <= 5,
        "service_reports_ok": status.get("ok") is True,
        "archive_result_parity": processed_count >= len(rows),
        "ledger_result_parity": (
            not ledger_missing_results
            and not result_missing_ledger
            and not ledger_result_mismatches
            and not result_payload_mismatches
        ),
        "source_hash_parity": not source_hash_mismatches,
        "no_real_order_submission": not real_order_violations,
        "no_invalid_acceptance": not invalid_acceptances,
        "inbox_drained": int(status.get("inbox_pending") or 0) == 0,
        "paper_ledger_reconciled": paper_ledger_ok,
        "runtime_evidence_healthy": runtime_evidence.get("ok") is True,
        "runtime_mode_matches_service": runtime_evidence.get("current_mode") == status_mode,
        "candidate_pipeline_no_publish_failures": candidate_pipeline_ok,
        "candidate_ticket_hash_parity": not candidate_ticket_hash_mismatches,
        "candidate_signature_parity": not candidate_signature_mismatches,
        "shadow_candidate_scheduler_healthy": scheduler_healthy,
    }
    operational_ok = all(checks.values())
    time_evidence_complete = observation_hours >= float(min_observation_hours)
    coverage_complete = len(qualifying_rows) >= int(min_result_count) and len(observed_symbols) >= int(min_symbol_count)
    return {
        "schema": "codexstock.shadow-execution-audit.v1",
        "generated_at": now.isoformat(timespec="seconds"),
        "operational_ok": operational_ok,
        "proof_complete": operational_ok and time_evidence_complete and coverage_complete,
        "observation_hours": round(observation_hours, 3),
        "required_observation_hours": float(min_observation_hours),
        "required_result_count": int(min_result_count),
        "required_symbol_count": int(min_symbol_count),
        "coverage_complete": coverage_complete,
        "heartbeat_age_seconds": round(heartbeat_age, 3) if heartbeat_age is not None else None,
        "checks": checks,
        "evidence": {
            "result_count": len(rows),
            "qualifying_result_count": len(qualifying_rows),
            "diagnostic_signal_ids": diagnostic_signal_ids,
            "qualification_failures": qualification_failures,
            "candidate_ticket_hash_mismatches": sorted(candidate_ticket_hash_mismatches),
            "candidate_signature_mismatches": sorted(candidate_signature_mismatches),
            "processed_archive_count": processed_count,
            "accepted_count": sum(1 for row in rows if row.get("state") in {"SHADOW_ACCEPTED", "PAPER_FILLED"}),
            "rejected_count": sum(1 for row in rows if row.get("state") == "REJECTED"),
            "real_order_violations": real_order_violations,
            "invalid_acceptances": invalid_acceptances,
            "observed_symbols": sorted(observed_symbols),
            "observed_symbol_count": len(observed_symbols),
            "ledger_count": len(ledger_by_id),
            "ledger_missing_results": ledger_missing_results,
            "result_missing_ledger": result_missing_ledger,
            "ledger_result_mismatches": ledger_result_mismatches,
            "result_payload_mismatches": sorted(result_payload_mismatches),
            "source_hash_mismatches": source_hash_mismatches,
        },
        "status": status,
        "runtime_evidence": runtime_evidence,
        "shadow_candidate_scheduler": {
            **shadow_candidate_scheduler,
            "age_seconds": round(scheduler_age_seconds, 3) if scheduler_age_seconds is not None else None,
            "blocked": scheduler_blocked,
        },
    }
