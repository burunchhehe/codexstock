"""Immutable trade lifecycle evidence ledger and reconciliation checks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


STAGES = ("CANDIDATE", "ORDER_SUBMITTED", "FILL", "BALANCE", "PNL")


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class TradeLifecycleLedger:
    """Store immutable evidence while allowing idempotent event replay."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS trade_lifecycle_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL UNIQUE,
                    stage TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_lifecycle_correlation "
                "ON trade_lifecycle_events(correlation_id, sequence)"
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def append_event(
        self,
        *,
        correlation_id: str,
        event_id: str,
        stage: str,
        occurred_at: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        correlation = str(correlation_id or "").strip()
        identifier = str(event_id or "").strip()
        normalized_stage = str(stage or "").strip().upper()
        timestamp = str(occurred_at or "").strip()
        if not correlation or not identifier or not timestamp:
            raise ValueError("missing_trade_lifecycle_identity")
        if normalized_stage not in STAGES:
            raise ValueError("unsupported_trade_lifecycle_stage")
        payload_json = _canonical(payload)
        payload_sha256 = _hash(payload)
        with self.connect() as db:
            prior = db.execute(
                "SELECT * FROM trade_lifecycle_events WHERE event_id=?", (identifier,)
            ).fetchone()
            if prior is not None:
                unchanged = (
                    str(prior["correlation_id"]) == correlation
                    and str(prior["stage"]) == normalized_stage
                    and str(prior["occurred_at"]) == timestamp
                    and str(prior["payload_sha256"]) == payload_sha256
                )
                if not unchanged:
                    raise ValueError("trade_lifecycle_event_mutation_rejected")
                result = dict(prior)
                result["idempotent_replay"] = True
                return result
            db.execute(
                """INSERT INTO trade_lifecycle_events
                   (correlation_id,event_id,stage,occurred_at,payload_json,payload_sha256,recorded_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    correlation,
                    identifier,
                    normalized_stage,
                    timestamp,
                    payload_json,
                    payload_sha256,
                    _now(),
                ),
            )
            row = db.execute(
                "SELECT * FROM trade_lifecycle_events WHERE event_id=?", (identifier,)
            ).fetchone()
            result = dict(row)
            result["idempotent_replay"] = False
            return result

    def events(self, correlation_id: str) -> list[dict[str, object]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM trade_lifecycle_events WHERE correlation_id=? ORDER BY sequence",
                (str(correlation_id or "").strip(),),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(str(item.pop("payload_json")))
            result.append(item)
        return result

    def reconcile(self, correlation_id: str) -> dict[str, object]:
        events = self.events(correlation_id)
        by_stage = {stage: [] for stage in STAGES}
        for event in events:
            by_stage[str(event["stage"])].append(event)
        issues: list[str] = []
        submitted = sum(
            max(0.0, float(item["payload"].get("quantity") or 0))
            for item in by_stage["ORDER_SUBMITTED"]
        )
        filled = sum(
            max(0.0, float(item["payload"].get("quantity") or 0))
            for item in by_stage["FILL"]
        )
        if by_stage["ORDER_SUBMITTED"] and not by_stage["CANDIDATE"]:
            issues.append("order_without_candidate")
        if by_stage["FILL"] and not by_stage["ORDER_SUBMITTED"]:
            issues.append("fill_without_order")
        if filled > submitted + 0.000001:
            issues.append("filled_quantity_exceeds_submitted_quantity")
        if by_stage["BALANCE"] and not by_stage["FILL"]:
            issues.append("balance_without_fill")
        if by_stage["PNL"] and not by_stage["FILL"]:
            issues.append("pnl_without_fill")
        if filled > 0 and not by_stage["BALANCE"]:
            issues.append("post_fill_balance_missing")
        stage_counts = {stage: len(by_stage[stage]) for stage in STAGES}
        complete = bool(
            stage_counts["CANDIDATE"]
            and stage_counts["ORDER_SUBMITTED"]
            and stage_counts["FILL"]
            and stage_counts["BALANCE"]
            and not issues
        )
        return {
            "correlation_id": str(correlation_id or "").strip(),
            "event_count": len(events),
            "stage_counts": stage_counts,
            "submitted_quantity": round(submitted, 6),
            "filled_quantity": round(filled, 6),
            "unfilled_quantity": round(max(0.0, submitted - filled), 6),
            "issues": issues,
            "quarantined": bool(issues),
            "complete": complete,
            "official_performance_eligible": complete and bool(stage_counts["PNL"]),
        }


def trade_correlation_id(*, ticket_id: str = "", order_no: str = "", fallback: str = "") -> str:
    """Build a stable non-secret correlation key without storing approval tokens."""
    material = str(ticket_id or order_no or fallback or "").strip()
    if not material:
        raise ValueError("missing_trade_correlation_material")
    return "TRADE-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24].upper()
