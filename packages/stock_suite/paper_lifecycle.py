"""Restart-safe Paper order lifecycle with idempotent fill and cancel events."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping

from .execution_sidecar import MarketSnapshot, OrderSignal


OPEN_STATES = {"PAPER_SUBMITTED", "PAPER_PARTIALLY_FILLED", "PAPER_CANCEL_PENDING"}
FINAL_STATES = {"PAPER_FILLED", "PAPER_CANCELED", "PAPER_REJECTED"}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PaperOrderLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS paper_orders (
                    signal_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    requested_quantity INTEGER NOT NULL,
                    filled_quantity INTEGER NOT NULL,
                    remaining_quantity INTEGER NOT NULL,
                    average_fill_price REAL NOT NULL,
                    state TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_order_events (
                    event_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(paper_orders)")}
            if "signal_json" not in columns:
                db.execute("ALTER TABLE paper_orders ADD COLUMN signal_json TEXT NOT NULL DEFAULT '{}'")

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

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, object] | None:
        return dict(row) if row else None

    def get(self, signal_id: str) -> dict[str, object] | None:
        with self.connect() as db:
            return self._row(db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone())

    def submit(self, signal: OrderSignal) -> dict[str, object]:
        with self.connect() as db:
            existing = db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal.signal_id,)).fetchone()
            if existing:
                row = dict(existing)
                same = (
                    row["symbol"] == signal.symbol and row["side"] == signal.side
                    and row["requested_quantity"] == signal.quantity
                )
                if not same:
                    raise ValueError("paper_order_signal_mismatch")
                return {**row, "idempotent_replay": True}
            now = _now()
            db.execute(
                """INSERT INTO paper_orders(
                    signal_id,symbol,side,requested_quantity,filled_quantity,remaining_quantity,
                    average_fill_price,state,version,created_at,updated_at,signal_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    signal.signal_id, signal.symbol, signal.side, signal.quantity, 0, signal.quantity,
                    0.0, "PAPER_SUBMITTED", 1, now, now,
                    json.dumps(signal.__dict__, ensure_ascii=False, sort_keys=True),
                ),
            )
            row = db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal.signal_id,)).fetchone()
            return dict(row)

    def apply_fill(self, signal_id: str, event_id: str, quantity: int, price: float) -> dict[str, object]:
        if quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be positive")
        payload = {"quantity": int(quantity), "price": float(price)}
        payload_hash = _hash(payload)
        with self.connect() as db:
            prior_event = db.execute("SELECT * FROM paper_order_events WHERE event_id=?", (event_id,)).fetchone()
            if prior_event:
                if prior_event["signal_id"] != signal_id or prior_event["payload_hash"] != payload_hash:
                    raise ValueError("paper_event_id_payload_mismatch")
                row = db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone()
                return {**dict(row), "idempotent_replay": True}
            order = db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone()
            if not order:
                raise ValueError("paper_order_not_found")
            if order["state"] in FINAL_STATES:
                raise ValueError("paper_order_already_final")
            new_filled = int(order["filled_quantity"]) + int(quantity)
            if new_filled > int(order["requested_quantity"]):
                raise ValueError("paper_overfill_blocked")
            old_notional = float(order["average_fill_price"]) * int(order["filled_quantity"])
            average = (old_notional + float(price) * int(quantity)) / new_filled
            remaining = int(order["requested_quantity"]) - new_filled
            state = "PAPER_FILLED" if remaining == 0 else "PAPER_PARTIALLY_FILLED"
            now = _now()
            db.execute(
                "UPDATE paper_orders SET filled_quantity=?,remaining_quantity=?,average_fill_price=?,state=?,version=version+1,updated_at=? WHERE signal_id=?",
                (new_filled, remaining, average, state, now, signal_id),
            )
            db.execute(
                "INSERT INTO paper_order_events VALUES (?,?,?,?,?,?)",
                (event_id, signal_id, "FILL", payload_hash, json.dumps(payload, sort_keys=True), now),
            )
            return dict(db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone())

    def request_cancel(self, signal_id: str, event_id: str) -> dict[str, object]:
        return self._cancel_transition(signal_id, event_id, "PAPER_CANCEL_PENDING", "CANCEL_REQUESTED")

    def confirm_cancel(self, signal_id: str, event_id: str) -> dict[str, object]:
        return self._cancel_transition(signal_id, event_id, "PAPER_CANCELED", "CANCELED")

    def _cancel_transition(self, signal_id: str, event_id: str, state: str, event_type: str) -> dict[str, object]:
        payload = {"state": state}
        payload_hash = _hash(payload)
        with self.connect() as db:
            prior = db.execute("SELECT * FROM paper_order_events WHERE event_id=?", (event_id,)).fetchone()
            if prior:
                if prior["signal_id"] != signal_id or prior["payload_hash"] != payload_hash:
                    raise ValueError("paper_event_id_payload_mismatch")
                row = db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone()
                return {**dict(row), "idempotent_replay": True}
            order = db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone()
            if not order:
                raise ValueError("paper_order_not_found")
            if order["state"] == "PAPER_FILLED":
                raise ValueError("filled_order_cannot_be_canceled")
            if order["state"] == "PAPER_CANCELED":
                raise ValueError("paper_order_already_final")
            if event_type == "CANCEL_REQUESTED" and order["state"] not in {
                "PAPER_SUBMITTED", "PAPER_PARTIALLY_FILLED",
            }:
                raise ValueError("paper_cancel_request_invalid_state")
            if event_type == "CANCELED" and order["state"] != "PAPER_CANCEL_PENDING":
                raise ValueError("paper_cancel_confirmation_without_pending_request")
            now = _now()
            db.execute(
                "UPDATE paper_orders SET state=?,version=version+1,updated_at=? WHERE signal_id=?",
                (state, now, signal_id),
            )
            db.execute(
                "INSERT INTO paper_order_events VALUES (?,?,?,?,?,?)",
                (event_id, signal_id, event_type, payload_hash, json.dumps(payload, sort_keys=True), now),
            )
            return dict(db.execute("SELECT * FROM paper_orders WHERE signal_id=?", (signal_id,)).fetchone())

    def open_orders(self) -> list[dict[str, object]]:
        placeholders = ",".join("?" for _ in OPEN_STATES)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT * FROM paper_orders WHERE state IN ({placeholders}) ORDER BY created_at",
                tuple(sorted(OPEN_STATES)),
            ).fetchall()
            return [dict(row) for row in rows]

    def recover_all_signals(self) -> list[tuple[OrderSignal, dict[str, object]]]:
        recovered: list[tuple[OrderSignal, dict[str, object]]] = []
        with self.connect() as db:
            orders = [dict(row) for row in db.execute("SELECT * FROM paper_orders ORDER BY created_at")]
        for order in orders:
            try:
                payload = json.loads(str(order.get("signal_json") or "{}"))
                signal = OrderSignal(**payload)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"paper_signal_recovery_failed:{order.get('signal_id')}") from exc
            if signal.signal_id != order.get("signal_id"):
                raise ValueError(f"paper_signal_recovery_mismatch:{order.get('signal_id')}")
            recovered.append((signal, order))
        return recovered

    def recover_open_signals(self) -> list[tuple[OrderSignal, dict[str, object]]]:
        return [
            (signal, order)
            for signal, order in self.recover_all_signals()
            if order.get("state") in OPEN_STATES
        ]

    def advance_resting_order(
        self, signal: OrderSignal, snapshot: MarketSnapshot, now: datetime | None = None
    ) -> dict[str, object]:
        """Advance a resting Paper order using only a fresh visible top-of-book snapshot."""
        current = self.get(signal.signal_id)
        if not current:
            raise ValueError("paper_order_not_found")
        if current["state"] in FINAL_STATES:
            return {**current, "match_reason": "paper_order_already_final"}
        observed_now = now or datetime.now().astimezone()
        expires_at = datetime.fromisoformat(signal.expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.astimezone()
        if observed_now >= expires_at:
            self.request_cancel(signal.signal_id, f"{signal.signal_id}:EXPIRE:CANCEL_REQUEST")
            current = self.confirm_cancel(signal.signal_id, f"{signal.signal_id}:EXPIRE:CANCELED")
            return {**current, "match_reason": "paper_order_expired_canceled"}
        try:
            snapshot_at = datetime.fromisoformat(snapshot.observed_at)
            if snapshot_at.tzinfo is None:
                snapshot_at = snapshot_at.astimezone()
            snapshot_age = (observed_now - snapshot_at).total_seconds()
        except ValueError:
            snapshot_age = 999.0
        if (
            not snapshot.account_ok or snapshot.snapshot_errors or snapshot_age < -1
            or snapshot_age > 5 or snapshot.emergency_halt or snapshot.market_halted or snapshot.vi_active
        ):
            return {**current, "match_reason": "paper_order_snapshot_blocked"}
        visible = snapshot.best_ask_quantity if signal.side == "BUY" else snapshot.best_bid_quantity
        price = snapshot.ask_price if signal.side == "BUY" else snapshot.bid_price
        marketable = (
            signal.side == "BUY" and price > 0 and price <= signal.max_price
        ) or (
            signal.side == "SELL" and price > 0 and price >= signal.min_price
        )
        if not marketable or visible <= 0:
            return {**current, "match_reason": "paper_order_waiting_liquidity"}
        quantity = min(int(current["remaining_quantity"]), max(0, int(visible)))
        stamp = str(snapshot.observed_at).replace(":", "").replace("+", "")[:40]
        current = self.apply_fill(
            signal.signal_id, f"{signal.signal_id}:REST:FILL:{stamp}", quantity, price
        )
        reason = "paper_resting_filled" if current["state"] == "PAPER_FILLED" else "paper_resting_partial"
        return {**current, "match_reason": reason}

    def match_ioc(self, signal: OrderSignal, snapshot: MarketSnapshot) -> dict[str, object]:
        """Apply only visible top-of-book liquidity, then cancel any IOC remainder."""
        order = self.submit(signal)
        if order["state"] in FINAL_STATES:
            return {**order, "match_reason": "paper_ioc_already_final"}
        visible = snapshot.best_ask_quantity if signal.side == "BUY" else snapshot.best_bid_quantity
        price = snapshot.ask_price if signal.side == "BUY" else snapshot.bid_price
        price_allowed = (
            signal.side == "BUY" and price > 0 and price <= signal.max_price
        ) or (
            signal.side == "SELL" and price > 0 and price >= signal.min_price
        )
        fill_quantity = (
            min(int(order["remaining_quantity"]), max(0, int(visible)))
            if price_allowed else 0
        )
        if fill_quantity > 0:
            order = self.apply_fill(
                signal.signal_id, f"{signal.signal_id}:IOC:FILL", fill_quantity, price
            )
        if int(order["remaining_quantity"]) > 0:
            self.request_cancel(signal.signal_id, f"{signal.signal_id}:IOC:CANCEL_REQUEST")
            order = self.confirm_cancel(signal.signal_id, f"{signal.signal_id}:IOC:CANCELED")
        if int(order["filled_quantity"]) == int(order["requested_quantity"]):
            reason = "paper_ioc_filled"
        elif int(order["filled_quantity"]) > 0:
            reason = "paper_ioc_partial_canceled"
        elif not price_allowed:
            reason = "paper_ioc_price_guard_canceled"
        else:
            reason = "paper_ioc_unfilled_canceled"
        return {**order, "match_reason": reason}

    def reconcile(self) -> dict[str, object]:
        errors: list[dict[str, object]] = []
        with self.connect() as db:
            orders = db.execute("SELECT * FROM paper_orders ORDER BY signal_id").fetchall()
            for order in orders:
                signal_id = str(order["signal_id"])
                events = db.execute(
                    "SELECT event_id,event_type,payload_hash,payload_json FROM paper_order_events WHERE signal_id=?",
                    (signal_id,),
                ).fetchall()
                event_types = [str(row["event_type"]) for row in events]
                row_errors: list[str] = []
                fill_rows: list[dict[str, object]] = []
                for event in events:
                    event_type = str(event["event_type"])
                    if event_type not in {"FILL", "CANCEL_REQUESTED", "CANCELED"}:
                        row_errors.append("unknown_paper_event_type")
                    try:
                        payload = json.loads(event["payload_json"])
                    except (TypeError, json.JSONDecodeError):
                        row_errors.append("invalid_event_payload")
                        continue
                    if not isinstance(payload, dict):
                        row_errors.append("invalid_event_payload")
                        continue
                    if _hash(payload) != str(event["payload_hash"]):
                        row_errors.append("event_payload_hash_mismatch")
                    if event_type == "FILL":
                        fill_rows.append(payload)
                event_quantity = sum(int(row.get("quantity") or 0) for row in fill_rows)
                event_notional = sum(int(row.get("quantity") or 0) * float(row.get("price") or 0) for row in fill_rows)
                expected_average = event_notional / event_quantity if event_quantity else 0.0
                requested = int(order["requested_quantity"])
                filled = int(order["filled_quantity"])
                remaining = int(order["remaining_quantity"])
                state = str(order["state"])
                if state not in OPEN_STATES | FINAL_STATES:
                    row_errors.append("unknown_paper_state")
                if requested != filled + remaining:
                    row_errors.append("quantity_conservation_failed")
                if event_quantity != filled:
                    row_errors.append("fill_event_quantity_mismatch")
                if abs(expected_average - float(order["average_fill_price"])) > 0.000001:
                    row_errors.append("average_fill_price_mismatch")
                if state == "PAPER_FILLED" and remaining != 0:
                    row_errors.append("filled_state_has_remaining_quantity")
                if state == "PAPER_PARTIALLY_FILLED" and not (0 < filled < requested):
                    row_errors.append("partial_state_quantity_invalid")
                if state == "PAPER_SUBMITTED" and filled != 0:
                    row_errors.append("submitted_state_has_fill")
                if state == "PAPER_CANCEL_PENDING" and "CANCEL_REQUESTED" not in event_types:
                    row_errors.append("cancel_pending_without_request_event")
                if state == "PAPER_CANCELED" and "CANCELED" not in event_types:
                    row_errors.append("canceled_state_without_event")
                if state == "PAPER_CANCELED" and "CANCEL_REQUESTED" not in event_types:
                    row_errors.append("canceled_state_without_request_event")
                if "CANCELED" in event_types and state != "PAPER_CANCELED":
                    row_errors.append("cancel_event_state_mismatch")
                if state == "PAPER_FILLED" and filled != requested:
                    row_errors.append("filled_state_quantity_mismatch")
                if row_errors:
                    errors.append({"signal_id": signal_id, "errors": row_errors})
            orphan_events = db.execute(
                "SELECT e.event_id,e.signal_id FROM paper_order_events e LEFT JOIN paper_orders o ON o.signal_id=e.signal_id WHERE o.signal_id IS NULL"
            ).fetchall()
            for event in orphan_events:
                errors.append({"event_id": event["event_id"], "signal_id": event["signal_id"], "errors": ["orphan_event"]})
        return {
            "ok": not errors,
            "order_count": len(orders),
            "open_order_count": sum(1 for row in orders if row["state"] in OPEN_STATES),
            "final_order_count": sum(1 for row in orders if row["state"] in FINAL_STATES),
            "error_count": len(errors),
            "errors": errors,
        }
