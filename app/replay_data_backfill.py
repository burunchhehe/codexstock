from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


_BACKFILL_INDEX_LOCK = threading.RLock()


def _dataset_hash(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _expected_currency_and_unit(symbol: str) -> tuple[str, str]:
    if symbol.isdigit() and len(symbol) == 6:
        return "KRW", "won_integer"
    return "USD", "decimal_usd"


def validate_replay_data_backfill(
    request: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    contract = request.get("contract") if isinstance(request.get("contract"), dict) else {}
    requested_symbols = list(dict.fromkeys(
        str(symbol).strip().upper()
        for symbol in contract.get("symbols", [])
        if str(symbol).strip()
    ))
    required_fields = [str(field) for field in contract.get("required_fields", [])]
    start_date = str(contract.get("start_date") or "")
    end_date = str(contract.get("end_date") or "")
    rows = result.get("dataset_rows") if isinstance(result.get("dataset_rows"), list) else []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    blockers: list[str] = []
    warnings: list[str] = []

    if result.get("schema") != "codexstock_openbb_historical_backfill_result_v1":
        blockers.append("schema_mismatch")
    if result.get("action") != "fetch_historical_ohlcv":
        blockers.append("action_mismatch")
    if str(result.get("request_id") or "") != str(request.get("request_id") or ""):
        blockers.append("request_id_mismatch")
    if str(result.get("request_hash") or "") != str(request.get("request_hash") or ""):
        blockers.append("request_hash_mismatch")
    if result.get("decision") != "VERIFY_ONLY":
        blockers.append("decision_not_verify_only")
    if result.get("score_allowed") is not False:
        blockers.append("score_gate_open")
    if result.get("promotion_allowed") is not False:
        blockers.append("promotion_gate_open")
    if result.get("live_order_allowed") is not False:
        blockers.append("live_order_gate_open")
    if result.get("adjustment_applied") != "splits_and_dividends":
        blockers.append("price_adjustment_mismatch")
    if not rows:
        blockers.append("dataset_rows_missing")

    actual_hash = _dataset_hash(rows)
    if actual_hash != str(result.get("dataset_hash") or ""):
        blockers.append("dataset_hash_mismatch")

    seen_keys: set[tuple[str, str]] = set()
    row_symbols: set[str] = set()
    symbol_counts: dict[str, int] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        row_date = str(row.get("date") or "")[:10]
        row_symbols.add(symbol)
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        key = (symbol, row_date)
        if key in seen_keys:
            blockers.append("duplicate_symbol_date")
        seen_keys.add(key)
        if symbol not in requested_symbols:
            blockers.append("unexpected_symbol")
        if any(field not in row for field in required_fields):
            blockers.append("required_field_missing")
        try:
            parsed_date = date.fromisoformat(row_date)
            if start_date and parsed_date < date.fromisoformat(start_date):
                blockers.append("row_before_requested_range")
            if end_date and parsed_date > date.fromisoformat(end_date):
                blockers.append("row_after_requested_range")
        except ValueError:
            blockers.append("invalid_row_date")
        try:
            open_price = float(row.get("open"))
            high_price = float(row.get("high"))
            low_price = float(row.get("low"))
            close_price = float(row.get("close"))
            volume = float(row.get("volume"))
            if min(open_price, high_price, low_price, close_price) <= 0 or volume < 0:
                blockers.append("invalid_ohlcv_value")
            price_tolerance = max(
                1e-8,
                max(abs(open_price), abs(high_price), abs(low_price), abs(close_price)) * 1e-10,
            )
            if (
                high_price + price_tolerance < max(open_price, close_price, low_price)
                or low_price - price_tolerance > min(open_price, close_price)
            ):
                blockers.append("invalid_ohlc_relationship")
        except (TypeError, ValueError):
            blockers.append("non_numeric_ohlcv")
        expected_currency, expected_unit = _expected_currency_and_unit(symbol)
        if str(row.get("currency") or "") != expected_currency:
            blockers.append("currency_mismatch")
        if str(row.get("price_unit") or "") != expected_unit:
            blockers.append("price_unit_mismatch")

    missing_symbols = sorted(set(requested_symbols) - row_symbols)
    if missing_symbols:
        blockers.append("requested_symbol_missing")
    if set(requested_symbols) != row_symbols and rows:
        warnings.append("symbol_scope_differs")
    expected_weekdays = 0
    try:
        cursor = date.fromisoformat(start_date)
        requested_end = date.fromisoformat(end_date)
        while cursor <= requested_end:
            expected_weekdays += int(cursor.weekday() < 5)
            cursor += timedelta(days=1)
    except ValueError:
        expected_weekdays = 0
    minimum_long_range_rows = int(expected_weekdays * 0.65) if expected_weekdays >= 180 else 1
    insufficient_symbols = sorted(
        symbol
        for symbol in requested_symbols
        if symbol_counts.get(symbol, 0) < minimum_long_range_rows
    )
    if insufficient_symbols:
        blockers.append("symbol_date_range_coverage_insufficient")

    unique_blockers = sorted(set(blockers))
    unique_warnings = sorted(set(warnings))
    accepted = bool(requested_symbols) and not unique_blockers
    return {
        "ok": accepted,
        "status": "accepted_for_paper_replay" if accepted else "blocked",
        "request_id": request.get("request_id"),
        "request_hash": request.get("request_hash"),
        "dataset_hash": actual_hash,
        "requested_symbol_count": len(requested_symbols),
        "received_symbol_count": len(row_symbols),
        "row_count": len(rows),
        "symbol_row_counts": symbol_counts,
        "expected_weekday_count": expected_weekdays,
        "minimum_long_range_rows_per_symbol": minimum_long_range_rows,
        "insufficient_coverage_symbols": insufficient_symbols,
        "missing_symbols": missing_symbols,
        "blocker_count": len(unique_blockers),
        "blockers": unique_blockers,
        "warning_count": len(unique_warnings),
        "warnings": unique_warnings,
        "score_allowed": False,
        "promotion_allowed": False,
        "live_order_allowed": False,
    }


def persist_replay_data_backfill(
    request: dict[str, Any],
    result: dict[str, Any],
    validation: dict[str, Any],
    *,
    output_dir: Path,
) -> Path:
    request_id = str(request.get("request_id") or "unknown")
    safe_request_id = "".join(char for char in request_id if char.isalnum() or char in {"-", "_"})[:80]
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{safe_request_id}.json"
    payload = {
        "schema_version": "historical-replay-data-backfill-artifact.v1",
        "request": request,
        "engine_result": result,
        "validation": validation,
        "paper_only": True,
        "score_allowed": False,
        "promotion_allowed": False,
        "live_order_allowed": False,
    }
    temp_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, target_path)
    return target_path


def upsert_replay_data_backfill_index(
    request: dict[str, Any],
    result: dict[str, Any],
    validation: dict[str, Any],
    *,
    artifact_path: Path,
    index_path: Path,
) -> dict[str, Any]:
    contract = request.get("contract") if isinstance(request.get("contract"), dict) else {}
    symbols = list(dict.fromkeys(
        str(symbol).strip().upper()
        for symbol in contract.get("symbols", [])
        if str(symbol).strip()
    ))
    symbol_counts = validation.get("symbol_row_counts") if isinstance(validation.get("symbol_row_counts"), dict) else {}
    target_path = Path(index_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with _BACKFILL_INDEX_LOCK, closing(sqlite3.connect(target_path, timeout=5.0)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS replay_data_backfills (
                request_id TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                replay_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                dataset_hash TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                status TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS replay_data_backfill_symbols (
                request_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                PRIMARY KEY (request_id, symbol),
                FOREIGN KEY (request_id) REFERENCES replay_data_backfills(request_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_replay_backfill_symbol ON replay_data_backfill_symbols(symbol, request_id)"
        )
        connection.execute(
            """
            INSERT INTO replay_data_backfills (
                request_id, request_hash, replay_id, start_date, end_date,
                dataset_hash, artifact_path, status, row_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(request_id) DO UPDATE SET
                request_hash=excluded.request_hash,
                replay_id=excluded.replay_id,
                start_date=excluded.start_date,
                end_date=excluded.end_date,
                dataset_hash=excluded.dataset_hash,
                artifact_path=excluded.artifact_path,
                status=excluded.status,
                row_count=excluded.row_count,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                str(request.get("request_id") or ""),
                str(request.get("request_hash") or ""),
                str(contract.get("replay_id") or ""),
                str(contract.get("start_date") or ""),
                str(contract.get("end_date") or ""),
                str(validation.get("dataset_hash") or result.get("dataset_hash") or ""),
                str(Path(artifact_path).resolve()),
                str(validation.get("status") or "blocked"),
                int(validation.get("row_count") or 0),
            ),
        )
        request_id = str(request.get("request_id") or "")
        connection.execute("DELETE FROM replay_data_backfill_symbols WHERE request_id = ?", (request_id,))
        connection.executemany(
            "INSERT INTO replay_data_backfill_symbols (request_id, symbol, row_count) VALUES (?, ?, ?)",
            [(request_id, symbol, int(symbol_counts.get(symbol) or 0)) for symbol in symbols],
        )
        connection.commit()
        artifact_count = int(connection.execute("SELECT COUNT(*) FROM replay_data_backfills").fetchone()[0])
        symbol_count = int(connection.execute("SELECT COUNT(*) FROM replay_data_backfill_symbols").fetchone()[0])
    return {
        "ok": True,
        "status": "indexed",
        "request_id": request.get("request_id"),
        "artifact_count": artifact_count,
        "symbol_count": symbol_count,
        "index_path": str(target_path),
        "live_order_allowed": False,
    }


def _indexed_artifact_candidates(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    index_path: Path,
) -> list[Path]:
    target_path = Path(index_path).resolve()
    if not target_path.is_file():
        return []
    try:
        with _BACKFILL_INDEX_LOCK, closing(sqlite3.connect(target_path, timeout=2.0)) as connection:
            connection.execute("PRAGMA busy_timeout=2000")
            rows = connection.execute(
                """
                SELECT b.artifact_path
                FROM replay_data_backfills b
                JOIN replay_data_backfill_symbols s ON s.request_id = b.request_id
                WHERE s.symbol = ?
                  AND b.start_date <= ?
                  AND b.end_date >= ?
                  AND b.status = 'accepted_for_paper_replay'
                ORDER BY b.updated_at DESC
                LIMIT 20
                """,
                (symbol, start_date, end_date),
            ).fetchall()
        return [Path(str(row[0])).resolve() for row in rows]
    except (OSError, sqlite3.Error):
        return []


def audit_replay_data_backfill_storage(
    *,
    result_dir: Path,
    index_path: Path,
) -> dict[str, Any]:
    directory = Path(result_dir).resolve()
    target_index = Path(index_path).resolve()
    artifacts = sorted(directory.glob("HREGAP-*.json")) if directory.is_dir() else []
    temp_files = sorted(directory.glob("*.tmp")) if directory.is_dir() else []
    accepted_paths: set[str] = set()
    invalid_paths: list[str] = []
    blocked_paths: list[str] = []
    dataset_groups: dict[str, list[Path]] = {}
    total_bytes = 0
    for path in artifacts:
        try:
            total_bytes += path.stat().st_size
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid_paths.append(str(path))
            continue
        validation = payload.get("validation") if isinstance(payload, dict) and isinstance(payload.get("validation"), dict) else {}
        dataset_hash = str(validation.get("dataset_hash") or "")
        if validation.get("ok") and validation.get("status") == "accepted_for_paper_replay":
            accepted_paths.add(str(path.resolve()))
            if dataset_hash:
                dataset_groups.setdefault(dataset_hash, []).append(path)
        else:
            blocked_paths.append(str(path))

    indexed_paths: set[str] = set()
    integrity = "missing"
    indexed_artifact_count = 0
    indexed_symbol_count = 0
    if target_index.is_file():
        try:
            with _BACKFILL_INDEX_LOCK, closing(sqlite3.connect(target_index, timeout=2.0)) as connection:
                connection.execute("PRAGMA busy_timeout=2000")
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                indexed_paths = {
                    str(Path(str(row[0])).resolve())
                    for row in connection.execute("SELECT artifact_path FROM replay_data_backfills").fetchall()
                }
                indexed_artifact_count = int(
                    connection.execute("SELECT COUNT(*) FROM replay_data_backfills").fetchone()[0]
                )
                indexed_symbol_count = int(
                    connection.execute("SELECT COUNT(*) FROM replay_data_backfill_symbols").fetchone()[0]
                )
        except sqlite3.Error as exc:
            integrity = f"error:{str(exc)[:160]}"
    unindexed_paths = sorted(accepted_paths - indexed_paths)
    missing_index_paths = sorted(path for path in indexed_paths if not Path(path).is_file())
    duplicate_groups = {
        dataset_hash: paths
        for dataset_hash, paths in dataset_groups.items()
        if len(paths) > 1
    }
    duplicate_reclaimable_bytes = 0
    for paths in duplicate_groups.values():
        ordered = sorted(paths, key=lambda path: path.stat().st_mtime_ns, reverse=True)
        duplicate_reclaimable_bytes += sum(path.stat().st_size for path in ordered[1:])
    blockers = []
    if integrity not in {"ok", "missing"}:
        blockers.append("sqlite_integrity_failed")
    if invalid_paths:
        blockers.append("invalid_artifact_json")
    if unindexed_paths:
        blockers.append("accepted_artifact_not_indexed")
    if missing_index_paths:
        blockers.append("index_points_to_missing_artifact")
    return {
        "ok": not blockers,
        "status": "healthy" if not blockers else "review_required",
        "artifact_count": len(artifacts),
        "accepted_artifact_count": len(accepted_paths),
        "blocked_artifact_count": len(blocked_paths),
        "invalid_artifact_count": len(invalid_paths),
        "total_bytes": total_bytes,
        "temp_file_count": len(temp_files),
        "duplicate_dataset_group_count": len(duplicate_groups),
        "duplicate_reclaimable_bytes": duplicate_reclaimable_bytes,
        "unindexed_artifact_count": len(unindexed_paths),
        "missing_index_artifact_count": len(missing_index_paths),
        "indexed_artifact_count": indexed_artifact_count,
        "indexed_symbol_count": indexed_symbol_count,
        "sqlite_integrity": integrity,
        "blockers": blockers,
        "samples": {
            "invalid_paths": invalid_paths[:5],
            "unindexed_paths": unindexed_paths[:5],
            "missing_index_paths": missing_index_paths[:5],
        },
        "retention_policy": {
            "accepted_artifacts": "retain while referenced by the SQLite index and replay evidence",
            "blocked_artifacts": "retain for diagnosis; delete only through a separate backed-up dry-run workflow",
            "duplicates": "report only; never delete automatically",
            "temporary_files": "report only; never delete while a worker may be active",
        },
        "cleanup_applied": False,
        "dry_run_only": True,
        "live_order_allowed": False,
    }
def load_verified_replay_data_backfill(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    result_dir: Path,
    index_path: Path | None = None,
) -> dict[str, Any] | None:
    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        return None
    directory = Path(result_dir).resolve()
    if not directory.is_dir():
        return None
    candidates = (
        _indexed_artifact_candidates(
            normalized_symbol,
            start_date,
            end_date,
            index_path=index_path,
        )
        if index_path is not None
        else []
    )
    if not candidates:
        try:
            candidates = sorted(directory.glob("HREGAP-*.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
        except OSError:
            return None
    for path in candidates:
        try:
            path.relative_to(directory)
        except ValueError:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
        request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        contract = request.get("contract") if isinstance(request.get("contract"), dict) else {}
        result = payload.get("engine_result") if isinstance(payload.get("engine_result"), dict) else {}
        if not validation.get("ok") or validation.get("status") != "accepted_for_paper_replay":
            continue
        if payload.get("score_allowed") is not False or payload.get("promotion_allowed") is not False:
            continue
        if payload.get("live_order_allowed") is not False or result.get("live_order_allowed") is not False:
            continue
        if str(contract.get("start_date") or "") > start_date or str(contract.get("end_date") or "") < end_date:
            continue
        contract_symbols = {str(item).strip().upper() for item in contract.get("symbols", [])}
        if normalized_symbol not in contract_symbols:
            continue
        rows = [
            dict(row)
            for row in result.get("dataset_rows", [])
            if isinstance(row, dict)
            and str(row.get("symbol") or "").strip().upper() == normalized_symbol
            and start_date <= str(row.get("date") or "")[:10] <= end_date
        ]
        rows.sort(key=lambda row: str(row.get("date") or ""))
        if not rows or _dataset_hash(
            sorted(
                [dict(row) for row in result.get("dataset_rows", []) if isinstance(row, dict)],
                key=lambda row: (str(row.get("symbol") or ""), str(row.get("date") or "")),
            )
        ) != str(result.get("dataset_hash") or ""):
            continue
        for row in rows:
            row["adjusted_close"] = row.get("close")
        return {
            "source": "verified_stage2_data_backfill",
            "provider": "openbb_yfinance_verified",
            "request_id": request.get("request_id"),
            "request_hash": request.get("request_hash"),
            "dataset_hash": result.get("dataset_hash"),
            "artifact_path": str(path),
            "rows": rows,
            "errors": [],
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }
    return None


class ReplayDataBackfillService:
    """Coordinate external OHLCV backfill without coupling it to the web app."""

    def __init__(
        self,
        *,
        queue_loader: Callable[[], dict[str, Any]],
        engine_run: Callable[..., dict[str, Any]],
        replay_regenerate: Callable[..., dict[str, Any]],
        queue_refresh: Callable[[], dict[str, Any]],
        append_ledger: Callable[[Path, dict[str, Any]], None],
        result_dir: Path,
        index_path: Path,
        ledger_path: Path,
    ) -> None:
        self.queue_loader = queue_loader
        self.engine_run = engine_run
        self.replay_regenerate = replay_regenerate
        self.queue_refresh = queue_refresh
        self.append_ledger = append_ledger
        self.result_dir = Path(result_dir).resolve()
        self.index_path = Path(index_path).resolve()
        self.ledger_path = Path(ledger_path).resolve()

    def _recent_request_attempts(self, cooldown_seconds: int = 6 * 60 * 60) -> dict[str, datetime]:
        if not self.ledger_path.is_file():
            return {}
        cutoff = datetime.now(ZoneInfo("Asia/Seoul")).timestamp() - max(60, int(cooldown_seconds))
        latest: dict[str, datetime] = {}
        try:
            lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        for line in lines[-1000:]:
            try:
                row = json.loads(line)
                request_id = str(row.get("request_id") or "").strip()
                attempted_at = datetime.fromisoformat(str(row.get("generated_at") or ""))
                if request_id and attempted_at.timestamp() >= cutoff:
                    latest[request_id] = attempted_at
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return latest

    def next_candidate(self, *, replay_busy: bool) -> dict[str, Any]:
        if replay_busy:
            return {
                "ok": True,
                "status": "waiting_for_replay_worker",
                "paper_only": True,
                "live_order_allowed": False,
            }
        manifest = self.queue_loader()
        requests = manifest.get("requests") if isinstance(manifest.get("requests"), list) else []
        if not requests:
            return {
                "ok": True,
                "status": "queue_empty",
                "request_count": 0,
                "paper_only": True,
                "live_order_allowed": False,
            }
        recent_attempts = self._recent_request_attempts()
        eligible_requests = [
            request
            for request in requests
            if isinstance(request, dict)
            and str(request.get("request_id") or "") not in recent_attempts
        ]
        if not eligible_requests:
            return {
                "ok": True,
                "status": "retry_cooldown",
                "request_count": len(requests),
                "deferred_request_count": len(recent_attempts),
                "cooldown_seconds": 6 * 60 * 60,
                "paper_only": True,
                "score_allowed": False,
                "promotion_allowed": False,
                "live_order_allowed": False,
            }
        request = eligible_requests[0]
        contract = request.get("contract") if isinstance(request.get("contract"), dict) else {}
        return {
            "ok": True,
            "status": "ready",
            "request_id": request.get("request_id", ""),
            "source_replay_id": contract.get("replay_id", ""),
            "symbol_count": len(contract.get("symbols", [])) if isinstance(contract.get("symbols"), list) else 0,
            "request_count": len(requests),
            "deferred_request_count": len(requests) - len(eligible_requests),
            "paper_only": True,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    def _reusable_result(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = str(request.get("request_id") or "")
        path = (self.result_dir / f"{request_id}.json").resolve()
        try:
            path.relative_to(self.result_dir)
        except ValueError:
            return {}
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        result = payload.get("engine_result") if isinstance(payload, dict) and isinstance(payload.get("engine_result"), dict) else {}
        return dict(result) if validate_replay_data_backfill(request, result).get("ok") else {}

    def run(self, request_id: str) -> dict[str, Any]:
        normalized_id = str(request_id or "").strip()
        manifest = self.queue_loader()
        requests = manifest.get("requests") if isinstance(manifest.get("requests"), list) else []
        request = next(
            (
                dict(item)
                for item in requests
                if isinstance(item, dict) and str(item.get("request_id") or "") == normalized_id
            ),
            None,
        )
        if request is None:
            return {
                "ok": False,
                "status": "data_gap_request_not_found",
                "request_id": normalized_id,
                "score_allowed": False,
                "promotion_allowed": False,
                "live_order_allowed": False,
            }
        contract = request.get("contract") if isinstance(request.get("contract"), dict) else {}
        engine_result = self._reusable_result(request)
        artifact_reused = bool(engine_result)
        if not engine_result:
            engine_result = self.engine_run(
                contract,
                request_id=normalized_id,
                request_hash=str(request.get("request_hash") or ""),
                timeout_seconds=600,
            )
        validation = validate_replay_data_backfill(request, engine_result)
        artifact_path = persist_replay_data_backfill(
            request,
            engine_result,
            validation,
            output_dir=self.result_dir,
        )
        index_result = upsert_replay_data_backfill_index(
            request,
            engine_result,
            validation,
            artifact_path=artifact_path,
            index_path=self.index_path,
        )
        ledger = {
            "id": f"HREGAPRESULT-{int(time.time() * 1000)}",
            "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "status": validation.get("status"),
            "request_id": normalized_id,
            "request_hash": request.get("request_hash"),
            "source_replay_id": contract.get("replay_id"),
            "engine_name": engine_result.get("engine_name", "OpenBB"),
            "engine_schema": engine_result.get("schema", ""),
            "dataset_hash": validation.get("dataset_hash", ""),
            "row_count": validation.get("row_count", 0),
            "requested_symbol_count": validation.get("requested_symbol_count", 0),
            "received_symbol_count": validation.get("received_symbol_count", 0),
            "blocker_count": validation.get("blocker_count", 0),
            "blockers": validation.get("blockers", []),
            "artifact_path": str(artifact_path),
            "index_path": str(self.index_path),
            "engine_error": str(engine_result.get("error") or "")[:300],
            "paper_only": True,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }
        self.append_ledger(self.ledger_path, ledger)
        replay_result: dict[str, Any] = {}
        if validation.get("ok"):
            replay_result = self.replay_regenerate(str(contract.get("replay_id") or ""), force=True)
            self.queue_refresh()
        return {
            "ok": bool(validation.get("ok")) and bool(replay_result.get("ok")),
            "status": (
                "backfill_and_reconciliation_complete"
                if validation.get("ok") and replay_result.get("ok")
                else replay_result.get("status") or validation.get("status")
            ),
            "request_id": normalized_id,
            "source_replay_id": contract.get("replay_id"),
            "validation": validation,
            "artifact_path": str(artifact_path),
            "index": index_result,
            "ledger_path": str(self.ledger_path),
            "engine_runtime_ms": engine_result.get("runtime_elapsed_ms"),
            "artifact_reused": artifact_reused,
            "engine_error": ledger["engine_error"],
            "replay_regeneration": replay_result,
            "paper_only": True,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }
