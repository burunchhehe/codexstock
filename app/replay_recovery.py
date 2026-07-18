from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable


_INDEX_WRITE_LOCK = threading.Lock()
_REPLAY_ID_PATTERN = re.compile(r"HREPLAY-[0-9]+")
_JSON_REPLAY_ID_PATTERN = re.compile(r'"id"\s*:\s*"(HREPLAY-[0-9]+)"')
_PAYLOAD_KEYS = {
    "id",
    "symbols",
    "start_date",
    "end_date",
    "strategy_mode",
    "strategy_config",
    "fast",
    "slow",
    "initial_cash",
    "cycles_per_day",
    "commission_bps",
    "slippage_bps",
    "kr_sell_tax_bps",
    "closed_trade_count",
    "total_return_pct",
    "data_mode",
    "data_policy",
    "generated_at",
    "point_in_time_warning",
}


def _payload_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def replay_ledger_requires_data_backfill(row: dict[str, object]) -> bool:
    """Treat both hard data failures and data-contract quarantines as backfill work."""
    status = str(row.get("status") or "")
    if status == "regeneration_failed":
        return row.get("retryable") is False
    if status != "quarantined_new_result":
        return False
    reasons = {
        str(reason or "").strip()
        for reason in (
            row.get("official_return_block_reasons")
            if isinstance(row.get("official_return_block_reasons"), list)
            else []
        )
    }
    return any(
        reason.startswith(
            (
                "price_currency_",
                "price_contract_",
                "market_data_",
                "non_real_market_data",
            )
        )
        for reason in reasons
    )


def load_indexed_contract_payload(
    replay_id: str,
    index_path: Path,
) -> tuple[dict[str, object] | None, Path]:
    path = index_path.resolve()
    if not path.is_file():
        return None, path
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, path
    entries = envelope.get("entries") if isinstance(envelope, dict) else None
    entry = entries.get(replay_id) if isinstance(entries, dict) else None
    payload = entry.get("payload") if isinstance(entry, dict) else None
    if not isinstance(payload, dict):
        return None, path
    expected_hash = str(entry.get("payload_sha256") or "")
    if not expected_hash or not hmac.compare_digest(expected_hash, _payload_hash(payload)):
        return None, path
    return payload, path


def build_backup_contract_index(
    replay_ids: list[str],
    *,
    backup_root: Path,
    index_path: Path,
    now: Callable[[], datetime] = datetime.now,
) -> dict[str, object]:
    requested = list(dict.fromkeys(
        str(replay_id or "").strip().upper()
        for replay_id in replay_ids
        if _REPLAY_ID_PATTERN.fullmatch(str(replay_id or "").strip().upper())
    ))
    target_path = index_path.resolve()
    root = backup_root.resolve()
    if not requested:
        return {
            "ok": False,
            "status": "no_valid_replay_ids",
            "requested_count": 0,
            "index_path": str(target_path),
        }

    existing_entries: dict[str, object] = {}
    if target_path.is_file():
        try:
            existing = json.loads(target_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("entries"), dict):
                existing_entries = dict(existing["entries"])
        except (OSError, json.JSONDecodeError):
            existing_entries = {}
    for entry in existing_entries.values():
        if isinstance(entry, dict) and isinstance(entry.get("payload"), dict):
            entry["payload_sha256"] = _payload_hash(entry["payload"])

    pending = {replay_id for replay_id in requested if replay_id not in existing_entries}
    backup_files = sorted(
        [
            path.resolve()
            for path in root.glob("historical_paper_replays.jsonl.*.bak")
            if path.is_file() and path.resolve().parent == root
        ],
        key=lambda path: (path.stat().st_size, path.stat().st_mtime),
        reverse=True,
    )
    scanned_files: list[dict[str, object]] = []
    found_now: list[str] = []
    for backup_path in backup_files:
        if not pending:
            break
        matched_in_file = 0
        lines_checked = 0
        try:
            with backup_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line_number, line in enumerate(handle, start=1):
                    lines_checked += 1
                    match = _JSON_REPLAY_ID_PATTERN.search(line)
                    if not match or match.group(1) not in pending:
                        continue
                    replay_id = match.group(1)
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(row, dict) or str(row.get("id") or "").strip().upper() != replay_id:
                        continue
                    minimal_payload = {key: row.get(key) for key in _PAYLOAD_KEYS if key in row}
                    existing_entries[replay_id] = {
                        "payload": minimal_payload,
                        "payload_sha256": _payload_hash(minimal_payload),
                        "source_backup_path": str(backup_path),
                        "source_line_number": line_number,
                        "source_line_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    }
                    pending.remove(replay_id)
                    found_now.append(replay_id)
                    matched_in_file += 1
                    if not pending:
                        break
        except OSError:
            continue
        scanned_files.append(
            {
                "path": str(backup_path),
                "size_bytes": backup_path.stat().st_size,
                "lines_checked": lines_checked,
                "matched_count": matched_in_file,
            }
        )

    envelope = {
        "schema_version": "historical-replay-backup-contract-index.v1",
        "generated_at": now().isoformat(timespec="seconds"),
        "entries": existing_entries,
        "entry_count": len(existing_entries),
        "last_request": {
            "requested_count": len(requested),
            "found_count": len(requested) - len(pending),
            "found_now_count": len(found_now),
            "missing_count": len(pending),
            "missing_replay_ids": sorted(pending),
            "scanned_files": scanned_files,
        },
        "safety": "Index contains only Paper replay inputs and backup provenance; it cannot submit orders.",
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.tmp")
    with _INDEX_WRITE_LOCK:
        temp_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, target_path)
    return {
        "ok": not pending,
        "status": "ready" if not pending else "partial",
        "requested_count": len(requested),
        "found_count": len(requested) - len(pending),
        "found_now_count": len(found_now),
        "missing_count": len(pending),
        "missing_replay_ids": sorted(pending),
        "entry_count": len(existing_entries),
        "scanned_file_count": len(scanned_files),
        "index_path": str(target_path),
    }


def build_replay_data_gap_manifest(
    ledger_rows: list[dict[str, object]],
    *,
    contract_loader: Callable[[str], dict[str, object]],
    output_path: Path,
    now: Callable[[], datetime] = datetime.now,
) -> dict[str, object]:
    """Build deterministic Stage 2 dataset requests from latest nonretryable failures."""
    latest_by_source: dict[str, dict[str, object]] = {}
    for row in ledger_rows:
        replay_id = str(row.get("source_replay_id") or "").strip().upper()
        if _REPLAY_ID_PATTERN.fullmatch(replay_id):
            latest_by_source[replay_id] = row
    requests: list[dict[str, object]] = []
    for replay_id, row in sorted(latest_by_source.items()):
        if not replay_ledger_requires_data_backfill(row):
            continue
        contract = contract_loader(replay_id)
        run_arguments = contract.get("run_arguments") if isinstance(contract.get("run_arguments"), dict) else {}
        symbols = sorted({
            str(symbol).strip().upper()
            for symbol in run_arguments.get("symbols", [])
            if str(symbol).strip()
        }) if isinstance(run_arguments.get("symbols"), list) else []
        request_contract = {
            "replay_id": replay_id,
            "symbols": symbols,
            "start_date": run_arguments.get("start_date"),
            "end_date": run_arguments.get("end_date"),
            "timeframe": "1d",
            "required_fields": ["date", "open", "high", "low", "close", "volume"],
            "price_adjustment": "split_and_dividend_adjusted_when_available",
            "point_in_time_required": True,
        }
        request_hash = _payload_hash(request_contract)
        requests.append(
            {
                "request_id": f"HREGAP-{request_hash[:16]}",
                "request_hash": request_hash,
                "status": "awaiting_dataset_backfill",
                "failure_kind": row.get(
                    "failure_kind",
                    "price_currency_unit_contract_unavailable"
                    if str(row.get("status") or "") == "quarantined_new_result"
                    else "input_or_market_data_unavailable",
                ),
                "source_failure_ledger_id": row.get("id"),
                "source_error_preview": str(
                    row.get("error") or row.get("official_return_block_reasons") or ""
                )[:500],
                "contract": request_contract,
                "acceptance_criteria": {
                    "all_symbols_have_rows": True,
                    "date_range_covered": True,
                    "ohlcv_unit_currency_validated": True,
                    "dataset_hash_required": True,
                    "replay_reconciliation_required": True,
                },
                "score_allowed": False,
                "promotion_allowed": False,
                "live_order_allowed": False,
            }
        )
    payload = {
        "ok": True,
        "status": "backfill_required" if requests else "empty",
        "schema_version": "historical-replay-data-gap-queue.v1",
        "generated_at": now().isoformat(timespec="seconds"),
        "request_count": len(requests),
        "requests": requests,
        "output_path": str(output_path.resolve()),
        "policy": {
            "execution_mode": "stage2_dataset_backfill_only",
            "acceptance_gate": "validated dataset hash plus successful Paper replay reconciliation",
            "unverified_data_effect": "no score, promotion, memory, or order effect",
        },
        "paper_only": True,
        "promotion_allowed": False,
        "live_order_allowed": False,
    }
    target_path = output_path.resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.tmp")
    with _INDEX_WRITE_LOCK:
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, target_path)
    return payload
