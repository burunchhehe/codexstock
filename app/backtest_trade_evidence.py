from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import zlib
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVIDENCE_SCHEMA_VERSION = "backtest-trade-evidence.v1"
AUDIT_SCHEMA_VERSION = "backtest-trade-evidence-audit.v1"
LEDGER_CODEC = "zlib-json-v1"
REQUIRED_LIQUIDITY_BASIS = "prior_completed_20d_average_volume"


def make_run_id(engine: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    suffix = hashlib.sha256(f"{engine}:{timestamp}".encode("utf-8")).hexdigest()[:10]
    return f"{timestamp}-{suffix}"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_run_fingerprint(
    *,
    engine: str,
    source_paths: list[Path],
    data_paths: list[Path],
    configs: list[dict[str, object]],
    options: dict[str, object],
) -> str:
    sources = []
    for path in source_paths:
        resolved = Path(path)
        sources.append(
            {
                "path": str(resolved.resolve()),
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest() if resolved.is_file() else "missing",
            }
        )
    data_files = []
    for path in data_paths:
        resolved = Path(path)
        stat = resolved.stat() if resolved.is_file() else None
        data_files.append(
            {
                "path": str(resolved.resolve()),
                "size": int(stat.st_size) if stat else -1,
                "mtime_ns": int(stat.st_mtime_ns) if stat else -1,
            }
        )
    payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "engine": engine,
        "sources": sources,
        "data_files": data_files,
        "configs": configs,
        "options": options,
    }
    return hashlib.sha256(_json_text(payload).encode("utf-8")).hexdigest()


def load_reusable_verified_summary(
    result_path: Path,
    *,
    expected_fingerprint: str,
    ledger_path: Path,
    engine: str,
) -> dict[str, object] | None:
    result_path = Path(result_path)
    ledger_path = Path(ledger_path)
    if not result_path.is_file() or not ledger_path.is_file():
        return None
    try:
        summary = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(summary, dict) or summary.get("status", "DONE") != "DONE":
            return None
        if str(summary.get("run_fingerprint") or "") != str(expected_fingerprint):
            return None
        trade_evidence = summary.get("trade_evidence") if isinstance(summary.get("trade_evidence"), dict) else {}
        if trade_evidence.get("all_results_verified") is not True:
            return None
        run_id = str(trade_evidence.get("run_id") or "")
        result_count = int(trade_evidence.get("result_count", 0) or 0)
        if not run_id or result_count <= 0:
            return None
        with closing(
            sqlite3.connect(f"file:{ledger_path.resolve().as_posix()}?mode=ro", uri=True, timeout=5.0)
        ) as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if not quick_check or str(quick_check[0]).lower() != "ok":
                return None
            rows = connection.execute(
                """
                SELECT audit_json
                FROM strategy_trade_ledgers
                WHERE engine = ? AND run_id = ?
                """,
                (engine, run_id),
            ).fetchall()
        stored_count = len(rows)
        verified_count = 0
        for row in rows:
            audit = json.loads(str(row[0]))
            if isinstance(audit, dict) and audit.get("official_return_claim_allowed") is True:
                verified_count += 1
        if stored_count != result_count or verified_count != result_count:
            return None
        return summary
    except (OSError, ValueError, TypeError, sqlite3.Error, json.JSONDecodeError):
        return None


def _number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _close(left: float, right: float, *, absolute: float = 0.02, relative: float = 1e-8) -> bool:
    return math.isclose(left, right, abs_tol=absolute, rel_tol=relative)


def canonical_trade_actions(actions: list[dict[str, object]]) -> tuple[str, str]:
    text = _json_text(actions)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def reconcile_trade_actions(
    actions: list[dict[str, object]],
    *,
    initial_cash: float,
    final_equity: float,
    open_positions: list[dict[str, object]],
    required_timing_model_version: str,
) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    open_lots: dict[str, dict[str, object]] = {}
    cash = float(initial_cash)
    sell_count = 0

    def issue(code: str, sequence: int, detail: str) -> None:
        if len(issues) < 100:
            issues.append({"code": code, "sequence": sequence, "detail": detail})

    for sequence, raw_action in enumerate(actions, 1):
        action = raw_action if isinstance(raw_action, dict) else {}
        side = str(action.get("side") or "").upper()
        symbol = str(action.get("symbol") or "").strip()
        execution_at = str(action.get("execution_at") or action.get("date") or "").strip()
        decision_as_of = str(action.get("decision_data_as_of") or "").strip()
        quantity_number = _number(action.get("quantity"))
        price = _number(action.get("price"))
        if side not in {"BUY", "SELL"}:
            issue("invalid_side", sequence, side or "missing")
            continue
        if not symbol:
            issue("missing_symbol", sequence, "symbol is required")
        if not execution_at or not decision_as_of:
            issue("missing_timing_evidence", sequence, "decision_data_as_of and execution_at are required")
        elif decision_as_of >= execution_at:
            issue("non_past_decision", sequence, f"decision={decision_as_of} execution={execution_at}")
        if not math.isfinite(quantity_number) or quantity_number <= 0 or not float(quantity_number).is_integer():
            issue("invalid_quantity", sequence, str(action.get("quantity")))
            continue
        if not math.isfinite(price) or price <= 0:
            issue("invalid_price", sequence, str(action.get("price")))
            continue
        quantity = int(quantity_number)
        cost_pct = _number(action.get("cost_pct"))
        gross_price = _number(action.get("gross_price"))
        if not math.isfinite(cost_pct) or cost_pct < 0:
            issue("invalid_cost_pct", sequence, str(action.get("cost_pct")))
        elif not math.isfinite(gross_price) or gross_price <= 0:
            issue("missing_gross_price", sequence, "gross_price is required")
        else:
            multiplier = 1.0 + cost_pct / 100.0 if side == "BUY" else 1.0 - cost_pct / 100.0
            expected_effective = gross_price * multiplier
            if not _close(price, expected_effective, absolute=0.0001):
                issue("cost_reconciliation_mismatch", sequence, f"price={price} expected={expected_effective}")

        if side == "BUY":
            if str(action.get("liquidity_volume_basis") or "") != REQUIRED_LIQUIDITY_BASIS:
                issue("unsafe_liquidity_basis", sequence, str(action.get("liquidity_volume_basis") or "missing"))
            current = open_lots.get(symbol)
            if current is None:
                current = {
                    "quantity": 0,
                    "cost": 0.0,
                    "entry_date": execution_at,
                }
                open_lots[symbol] = current
            current["quantity"] = int(current["quantity"]) + quantity
            current["cost"] = float(current["cost"]) + quantity * price
            cash -= quantity * price
            continue

        sell_count += 1
        lot = open_lots.get(symbol)
        if lot is None:
            issue("sell_without_buy", sequence, symbol)
            continue
        lot_quantity = int(lot["quantity"])
        average_price = float(lot["cost"]) / max(1, lot_quantity)
        if quantity != lot_quantity:
            issue("quantity_mismatch", sequence, f"sell={quantity} open={lot_quantity}")
        reported_entry = _number(action.get("entry_price"))
        if not math.isfinite(reported_entry) or not _close(reported_entry, average_price, absolute=0.0001):
            issue("entry_price_mismatch", sequence, f"reported={reported_entry} expected={average_price}")
        if str(action.get("entry_date") or "") != str(lot["entry_date"]):
            issue("entry_date_mismatch", sequence, f"reported={action.get('entry_date')} expected={lot['entry_date']}")
        if not str(action.get("exit_reason") or action.get("reason") or "").strip():
            issue("missing_exit_reason", sequence, "exit reason is required")
        expected_return = (price / average_price - 1.0) * 100.0
        reported_return = _number(action.get("return_pct"))
        if not math.isfinite(reported_return) or not _close(reported_return, expected_return, absolute=0.011):
            issue("return_mismatch", sequence, f"reported={reported_return} expected={expected_return}")
        cash += quantity * price
        del open_lots[symbol]

    reported_open = {
        str(row.get("symbol") or ""): row
        for row in open_positions
        if isinstance(row, dict) and str(row.get("symbol") or "")
    }
    if set(reported_open) != set(open_lots):
        issue("open_position_set_mismatch", 0, f"ledger={sorted(open_lots)} reported={sorted(reported_open)}")
    mark_to_market = 0.0
    for symbol, lot in open_lots.items():
        row = reported_open.get(symbol, {})
        quantity = int(lot["quantity"])
        average_price = float(lot["cost"]) / max(1, quantity)
        reported_quantity = _number(row.get("quantity"))
        reported_average = _number(row.get("avg_price"))
        last_price = _number(row.get("last_price"))
        if not math.isfinite(reported_quantity) or int(reported_quantity) != quantity:
            issue("open_quantity_mismatch", 0, f"{symbol}: reported={reported_quantity} expected={quantity}")
        if not math.isfinite(reported_average) or not _close(reported_average, average_price, absolute=0.0001):
            issue("open_average_price_mismatch", 0, f"{symbol}: reported={reported_average} expected={average_price}")
        if not math.isfinite(last_price) or last_price <= 0:
            issue("missing_open_mark_price", 0, symbol)
            continue
        mark_to_market += quantity * last_price

    reconstructed_equity = cash + mark_to_market
    equity_tolerance = max(0.1, abs(float(final_equity)) * 1e-8)
    if not _close(reconstructed_equity, float(final_equity), absolute=equity_tolerance):
        issue(
            "final_equity_mismatch",
            0,
            f"reported={float(final_equity):.8f} reconstructed={reconstructed_equity:.8f} tolerance={equity_tolerance:.8f}",
        )

    _, ledger_hash = canonical_trade_actions(actions)
    calculation_passed = not issues
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "required_timing_model_version": required_timing_model_version,
        "calculation_passed": calculation_passed,
        "durable_ledger_verified": False,
        "official_return_claim_allowed": False,
        "action_count": len(actions),
        "closed_position_count": sell_count,
        "open_position_count": len(open_lots),
        "ledger_sha256": ledger_hash,
        "reported_final_equity": round(float(final_equity), 8),
        "reconstructed_final_equity": round(reconstructed_equity, 8),
        "final_equity_delta": round(reconstructed_equity - float(final_equity), 8),
        "issue_count": len(issues),
        "issues": issues,
    }


class TradeEvidenceStore:
    def __init__(self, path: Path, *, engine: str, run_id: str) -> None:
        self.path = Path(path)
        self.engine = str(engine)
        self.run_id = str(run_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30.0)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_trade_ledgers (
                engine TEXT NOT NULL,
                run_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                evidence_schema_version TEXT NOT NULL,
                timing_model_version TEXT NOT NULL,
                action_count INTEGER NOT NULL,
                closed_position_count INTEGER NOT NULL,
                ledger_sha256 TEXT NOT NULL,
                codec TEXT NOT NULL,
                compressed_actions BLOB NOT NULL,
                config_json TEXT NOT NULL,
                timing_model_json TEXT NOT NULL,
                audit_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (engine, run_id, strategy_name)
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trade_ledgers_engine_run ON strategy_trade_ledgers(engine, run_id)"
        )
        self.connection.commit()

    def persist(
        self,
        *,
        strategy_name: str,
        config: dict[str, object],
        actions: list[dict[str, object]],
        timing_model: dict[str, object],
        audit: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        canonical_text, ledger_hash = canonical_trade_actions(actions)
        compressed = zlib.compress(canonical_text.encode("utf-8"), level=6)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.connection.execute(
            """
            INSERT OR REPLACE INTO strategy_trade_ledgers (
                engine, run_id, strategy_name, evidence_schema_version,
                timing_model_version, action_count, closed_position_count,
                ledger_sha256, codec, compressed_actions, config_json,
                timing_model_json, audit_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.engine,
                self.run_id,
                strategy_name,
                EVIDENCE_SCHEMA_VERSION,
                str(timing_model.get("version") or ""),
                len(actions),
                int(audit.get("closed_position_count", 0) or 0),
                ledger_hash,
                LEDGER_CODEC,
                sqlite3.Binary(compressed),
                _json_text(config),
                _json_text(timing_model),
                _json_text(audit),
                created_at,
            ),
        )
        self.connection.commit()
        row = self.connection.execute(
            """
            SELECT compressed_actions, ledger_sha256, action_count
            FROM strategy_trade_ledgers
            WHERE engine = ? AND run_id = ? AND strategy_name = ?
            """,
            (self.engine, self.run_id, strategy_name),
        ).fetchone()
        durable_verified = False
        if row:
            restored_text = zlib.decompress(bytes(row[0])).decode("utf-8")
            restored_hash = hashlib.sha256(restored_text.encode("utf-8")).hexdigest()
            restored_actions = json.loads(restored_text)
            durable_verified = (
                restored_hash == str(row[1]) == ledger_hash
                and isinstance(restored_actions, list)
                and len(restored_actions) == int(row[2]) == len(actions)
            )
        final_audit = {
            **audit,
            "durable_ledger_verified": durable_verified,
            "official_return_claim_allowed": bool(audit.get("calculation_passed") and durable_verified),
        }
        self.connection.execute(
            """
            UPDATE strategy_trade_ledgers SET audit_json = ?
            WHERE engine = ? AND run_id = ? AND strategy_name = ?
            """,
            (_json_text(final_audit), self.engine, self.run_id, strategy_name),
        )
        self.connection.commit()
        ledger_reference = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "storage": "sqlite_zlib",
            "database_path": str(self.path),
            "engine": self.engine,
            "run_id": self.run_id,
            "strategy_name": strategy_name,
            "action_count": len(actions),
            "ledger_sha256": ledger_hash,
            "codec": LEDGER_CODEC,
            "persisted_and_readback_verified": durable_verified,
        }
        return final_audit, ledger_reference

    def prune_old_runs(self, *, keep_runs: int = 5) -> int:
        rows = self.connection.execute(
            "SELECT DISTINCT run_id FROM strategy_trade_ledgers WHERE engine = ? ORDER BY run_id DESC",
            (self.engine,),
        ).fetchall()
        stale = [str(row[0]) for row in rows[max(1, int(keep_runs)) :]]
        deleted = 0
        for run_id in stale:
            cursor = self.connection.execute(
                "DELETE FROM strategy_trade_ledgers WHERE engine = ? AND run_id = ?",
                (self.engine, run_id),
            )
            deleted += max(0, int(cursor.rowcount or 0))
        if stale:
            self.connection.commit()
        return deleted

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "TradeEvidenceStore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def finalize_trade_evidence(
    *,
    engine: str,
    strategy_name: str,
    config: dict[str, object],
    actions: list[dict[str, object]],
    initial_cash: float,
    final_equity: float,
    open_positions: list[dict[str, object]],
    timing_model: dict[str, object],
    store: TradeEvidenceStore | None,
) -> tuple[dict[str, object], dict[str, object]]:
    timing_version = str(timing_model.get("version") or "")
    audit = reconcile_trade_actions(
        actions,
        initial_cash=initial_cash,
        final_equity=final_equity,
        open_positions=open_positions,
        required_timing_model_version=timing_version,
    )
    if store is None:
        return audit, {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "storage": "not_persisted",
            "engine": engine,
            "strategy_name": strategy_name,
            "action_count": len(actions),
            "ledger_sha256": audit["ledger_sha256"],
            "persisted_and_readback_verified": False,
        }
    return store.persist(
        strategy_name=strategy_name,
        config=config,
        actions=actions,
        timing_model=timing_model,
        audit=audit,
    )
