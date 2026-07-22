"""Restart-safe position exit planning for Shadow and delegated workflows."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class PositionExitLedger:
    """Track broker-observed quantity and high-watermark without assuming an order filled."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS position_exit_state (
                    position_key TEXT PRIMARY KEY,
                    original_quantity REAL NOT NULL,
                    last_quantity REAL NOT NULL,
                    high_watermark_pct REAL NOT NULL,
                    partial_stage INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
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

    def observe(self, position_key: str, quantity: float, pnl_pct: float) -> dict[str, object]:
        key = str(position_key or "").strip()
        if not key or quantity <= 0:
            raise ValueError("invalid_position_exit_observation")
        with self.connect() as db:
            prior = db.execute(
                "SELECT * FROM position_exit_state WHERE position_key=?", (key,)
            ).fetchone()
            now = _now()
            if prior is None:
                original = float(quantity)
                high = float(pnl_pct)
                stage = 0
                db.execute(
                    "INSERT INTO position_exit_state VALUES(?,?,?,?,?,?)",
                    (key, original, float(quantity), high, stage, now),
                )
            else:
                original = max(float(prior["original_quantity"]), float(quantity))
                high = max(float(prior["high_watermark_pct"]), float(pnl_pct))
                stage = max(
                    int(prior["partial_stage"]),
                    1 if float(quantity) < original - 0.000001 else 0,
                )
                db.execute(
                    """UPDATE position_exit_state
                       SET original_quantity=?,last_quantity=?,high_watermark_pct=?,partial_stage=?,updated_at=?
                       WHERE position_key=?""",
                    (original, float(quantity), high, stage, now, key),
                )
            row = db.execute(
                "SELECT * FROM position_exit_state WHERE position_key=?", (key,)
            ).fetchone()
            return dict(row)


def build_exit_plan(
    *,
    position_key: str,
    available_quantity: float,
    pnl_pct: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    state: dict[str, object],
    severe_risk: bool = False,
    intraday_close: bool = False,
    partial_exit_pct: float = 50.0,
    trailing_drawdown_pct: float = 1.0,
) -> dict[str, object]:
    """Return a deterministic exit plan; it never submits an order."""
    available = max(0.0, float(available_quantity))
    stop = abs(float(stop_loss_pct))
    target = abs(float(take_profit_pct))
    high = max(float(state.get("high_watermark_pct") or pnl_pct), float(pnl_pct))
    stage = max(0, int(state.get("partial_stage") or 0))
    action = "HOLD"
    urgency = "normal"
    reason_code = "inside_risk_band"
    quantity = 0.0

    if pnl_pct <= -stop:
        action, urgency, reason_code, quantity = "SELL", "risk_stop", "hard_stop", available
    elif severe_risk:
        action, urgency, reason_code, quantity = "SELL", "risk_event", "risk_event", available
    elif intraday_close:
        action, urgency, reason_code, quantity = "SELL", "intraday_close", "intraday_market_close", available
    elif stage == 0 and pnl_pct >= target:
        ratio = max(1.0, min(float(partial_exit_pct), 100.0)) / 100.0
        partial = max(1.0, float(int(available * ratio))) if available >= 2 else available
        quantity = min(available, partial)
        action = "SELL"
        urgency = "profit_partial" if quantity < available else "profit_protect"
        reason_code = "first_profit_target"
    elif stage >= 1 and high >= target:
        trailing_floor = max(target * 0.5, high - abs(float(trailing_drawdown_pct)))
        if pnl_pct <= trailing_floor:
            action, urgency, reason_code, quantity = (
                "SELL", "profit_trailing", "post_partial_trailing_stop", available
            )

    material = f"{position_key}|{stage}|{action}|{reason_code}|{quantity:.6f}"
    plan_id = "EXIT-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20].upper()
    return {
        "plan_id": plan_id,
        "position_key": position_key,
        "decision": action,
        "urgency": urgency,
        "reason_code": reason_code,
        "recommended_exit_quantity": round(quantity, 6),
        "exit_scope": (
            "partial_available_position" if 0 < quantity < available
            else "full_available_position" if quantity > 0
            else "hold_no_exit"
        ),
        "partial_stage": stage,
        "high_watermark_pct": round(high, 4),
        "trailing_floor_pct": round(max(target * 0.5, high - abs(float(trailing_drawdown_pct))), 4),
    }
