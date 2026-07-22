"""Fail-closed order-signal executor for CodexStock Paper and Shadow modes."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Mapping


FINAL_STATES = {"REJECTED", "PAPER_FILLED", "PAPER_CANCELED", "SHADOW_ACCEPTED", "LIVE_SUBMITTED"}
ALLOWED_MODES = {"paper", "shadow", "live"}


def process_is_alive(process_id: int) -> bool:
    """Return whether a local process currently exists without modifying it."""
    if process_id <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, process_id)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
    except (OSError, ValueError, OverflowError):
        return False
    return True


def _canonical(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO string")
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("signal timestamps must include a timezone")
    return parsed


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _sha256_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _replace_with_retry(source: Path, destination: Path, attempts: int = 40) -> None:
    """Survive short Windows reader locks without hiding persistent failures."""
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05)


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    try:
        _replace_with_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class OrderSignal:
    signal_id: str
    created_at: str
    expires_at: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    reference_price: float
    max_price: float
    stop_loss_pct: float
    take_profit_pct: float
    strategy_id: str
    evidence_hash: str
    origin: str = "unknown"
    candidate_ticket_hash: str = ""
    min_price: float = 0.0
    execution_mode: str = "unspecified"
    signature: str = ""

    def unsigned(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("signature", None)
        return payload

    def validate(self) -> None:
        if not self.signal_id or len(self.signal_id) > 120:
            raise ValueError("invalid signal_id")
        if not self.symbol or len(self.symbol) > 16:
            raise ValueError("invalid symbol")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type not in {"LIMIT", "BEST_LIMIT", "IOC_LIMIT"}:
            raise ValueError("unsupported order_type")
        numeric_fields = {
            "reference_price": self.reference_price,
            "max_price": self.max_price,
            "min_price": self.min_price,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
        }
        invalid_numeric = [name for name, value in numeric_fields.items() if not _finite_number(value)]
        if invalid_numeric:
            raise ValueError(f"non-finite numeric field: {invalid_numeric[0]}")
        if self.reference_price <= 0 or self.max_price <= 0:
            raise ValueError("prices must be positive")
        if self.side == "BUY" and self.max_price < self.reference_price:
            raise ValueError("max_price cannot be below reference_price for BUY")
        if self.side == "SELL" and (self.min_price <= 0 or self.min_price > self.reference_price):
            raise ValueError("SELL requires a positive min_price at or below reference_price")
        if self.stop_loss_pct >= 0 or self.take_profit_pct <= 0:
            raise ValueError("invalid exit policy")
        if not self.strategy_id or len(self.strategy_id) > 120:
            raise ValueError("invalid strategy_id")
        if not _sha256_hex(self.evidence_hash):
            raise ValueError("evidence_hash must be a SHA-256 hex digest")
        if self.origin == "candidate_ledger" and not _sha256_hex(self.candidate_ticket_hash):
            raise ValueError("candidate-ledger signals require a SHA-256 ticket hash")
        if self.execution_mode not in {"unspecified", "delegated_auto", "manual_approval"}:
            raise ValueError("invalid execution_mode")
        if _parse_time(self.expires_at) <= _parse_time(self.created_at):
            raise ValueError("expires_at must be after created_at")

    def sign(self, secret: bytes) -> "OrderSignal":
        signature = hmac.new(secret, _canonical(self.unsigned()), hashlib.sha256).hexdigest()
        return OrderSignal(**{**asdict(self), "signature": signature})

    def verify(self, secret: bytes) -> bool:
        expected = hmac.new(secret, _canonical(self.unsigned()), hashlib.sha256).hexdigest()
        return bool(self.signature) and hmac.compare_digest(self.signature, expected)


@dataclass(frozen=True)
class ExecutorPolicy:
    max_total_exposure_pct: float = 30.0
    max_symbol_exposure_pct: float = 15.0
    max_daily_orders: int = 6
    max_daily_loss_pct: float = 2.0
    max_chase_pct: float = 0.4
    max_spread_pct: float = 0.5
    max_snapshot_age_seconds: float = 3.0
    max_snapshot_latency_seconds: float = 5.0
    require_account_ok: bool = True
    required_data_source_prefix: str = "KIS_READONLY"

    def validate(self) -> None:
        numeric = {
            "max_total_exposure_pct": self.max_total_exposure_pct,
            "max_symbol_exposure_pct": self.max_symbol_exposure_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_chase_pct": self.max_chase_pct,
            "max_spread_pct": self.max_spread_pct,
            "max_snapshot_age_seconds": self.max_snapshot_age_seconds,
            "max_snapshot_latency_seconds": self.max_snapshot_latency_seconds,
        }
        invalid = [name for name, value in numeric.items() if not _finite_number(value)]
        if invalid:
            raise ValueError(f"invalid executor policy number: {invalid[0]}")
        if not 0 < self.max_total_exposure_pct <= 100:
            raise ValueError("max_total_exposure_pct must be within (0, 100]")
        if not 0 < self.max_symbol_exposure_pct <= self.max_total_exposure_pct:
            raise ValueError("max_symbol_exposure_pct must be positive and no larger than total exposure")
        if not isinstance(self.max_daily_orders, int) or isinstance(self.max_daily_orders, bool) or self.max_daily_orders <= 0:
            raise ValueError("max_daily_orders must be a positive integer")
        if self.max_daily_loss_pct <= 0:
            raise ValueError("max_daily_loss_pct must be positive")
        if self.max_chase_pct < 0 or self.max_spread_pct < 0:
            raise ValueError("price tolerance policy cannot be negative")
        if self.max_snapshot_age_seconds <= 0 or self.max_snapshot_latency_seconds <= 0:
            raise ValueError("snapshot time limits must be positive")
        if not isinstance(self.require_account_ok, bool):
            raise ValueError("require_account_ok must be boolean")
        if not isinstance(self.required_data_source_prefix, str) or not self.required_data_source_prefix.strip():
            raise ValueError("required_data_source_prefix must be non-empty")


@dataclass(frozen=True)
class MarketSnapshot:
    observed_at: str
    current_price: float
    ask_price: float
    bid_price: float
    account_ok: bool
    available_cash: float
    equity: float
    total_exposure: float
    symbol_exposure: float
    daily_loss_pct: float
    daily_order_count: int
    already_held: bool = False
    emergency_halt: bool = False
    pending_same_symbol: bool = False
    data_source: str = ""
    snapshot_errors: tuple[str, ...] = ()
    available_position_quantity: float = 0.0
    market_halted: bool = False
    vi_active: bool = False
    fetch_latency_seconds: float = 0.0
    best_ask_quantity: float = 0.0
    best_bid_quantity: float = 0.0


class SignalLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    payload_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, signal_id: str) -> dict[str, object] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT signal_id,payload_hash,state,reason,result_json,updated_at FROM signals WHERE signal_id=?",
                (signal_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "signal_id": row[0], "payload_hash": row[1], "state": row[2],
            "reason": row[3], "result": json.loads(row[4]), "updated_at": row[5],
        }

    def record(self, signal: OrderSignal, state: str, reason: str, result: Mapping[str, object]) -> dict[str, object]:
        payload_hash = hashlib.sha256(_canonical(asdict(signal))).hexdigest()
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as db:
            existing = db.execute(
                "SELECT payload_hash,state,reason,result_json,updated_at FROM signals WHERE signal_id=?",
                (signal.signal_id,),
            ).fetchone()
            if existing:
                if existing[0] != payload_hash:
                    return {"signal_id": signal.signal_id, "state": "REJECTED", "reason": "signal_id_payload_mismatch"}
                return {
                    "signal_id": signal.signal_id, "payload_hash": existing[0], "state": existing[1],
                    "reason": existing[2], "result": json.loads(existing[3]), "updated_at": existing[4],
                    "idempotent_replay": True,
                }
            db.execute(
                "INSERT INTO signals VALUES (?,?,?,?,?,?)",
                (signal.signal_id, payload_hash, state, reason, json.dumps(dict(result), ensure_ascii=False), now),
            )
        return {"signal_id": signal.signal_id, "payload_hash": payload_hash, "state": state, "reason": reason, "result": dict(result), "updated_at": now}

    def transition_paper(
        self, signal_id: str, state: str, reason: str, result_patch: Mapping[str, object]
    ) -> dict[str, object]:
        if not state.startswith("PAPER_"):
            raise ValueError("paper_transition_requires_paper_state")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as db:
            row = db.execute(
                "SELECT payload_hash,state,result_json FROM signals WHERE signal_id=?", (signal_id,)
            ).fetchone()
            if not row:
                raise ValueError("signal_ledger_entry_not_found")
            if not str(row[1]).startswith("PAPER_"):
                raise ValueError("non_paper_signal_transition_blocked")
            result = json.loads(row[2])
            result.update(dict(result_patch))
            db.execute(
                "UPDATE signals SET state=?,reason=?,result_json=?,updated_at=? WHERE signal_id=?",
                (state, reason, json.dumps(result, ensure_ascii=False), now, signal_id),
            )
        return {
            "signal_id": signal_id, "payload_hash": row[0], "state": state,
            "reason": reason, "result": result, "updated_at": now,
        }

    def transition_live(
        self, signal_id: str, state: str, reason: str, result_patch: Mapping[str, object]
    ) -> dict[str, object]:
        if state not in {"LIVE_SUBMITTED", "LIVE_RECONCILIATION_REQUIRED", "LIVE_REJECTED"}:
            raise ValueError("invalid_live_transition_state")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as db:
            row = db.execute(
                "SELECT payload_hash,state,result_json FROM signals WHERE signal_id=?", (signal_id,)
            ).fetchone()
            if not row:
                raise ValueError("signal_ledger_entry_not_found")
            if str(row[1]) != "LIVE_SUBMITTING":
                raise ValueError("live_transition_requires_submitting_state")
            result = json.loads(row[2])
            result.update(dict(result_patch))
            db.execute(
                "UPDATE signals SET state=?,reason=?,result_json=?,updated_at=? WHERE signal_id=?",
                (state, reason, json.dumps(result, ensure_ascii=False), now, signal_id),
            )
        return {
            "signal_id": signal_id, "payload_hash": row[0], "state": state,
            "reason": reason, "result": result, "updated_at": now,
        }


class ExecutionSidecar:
    def __init__(
        self,
        ledger: SignalLedger,
        secret: bytes,
        mode: str = "shadow",
        policy: ExecutorPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        paper_order_ledger: object | None = None,
        live_broker_submit: Callable[[OrderSignal, MarketSnapshot], Mapping[str, object]] | None = None,
    ):
        if mode not in ALLOWED_MODES:
            raise ValueError("mode must be paper, shadow, or live")
        if not secret:
            raise ValueError("a signing secret is required")
        self.ledger = ledger
        self.secret = secret
        self.mode = mode
        self.policy = policy or ExecutorPolicy()
        self.policy.validate()
        self.clock = clock or (lambda: datetime.now().astimezone())
        self.paper_order_ledger = paper_order_ledger
        self.live_broker_submit = live_broker_submit

    def replay(self, signal: OrderSignal) -> dict[str, object] | None:
        """Return a durable prior decision without consulting market or account APIs."""
        existing = self.ledger.get(signal.signal_id)
        if not existing:
            return None
        payload_hash = hashlib.sha256(_canonical(asdict(signal))).hexdigest()
        if existing["payload_hash"] != payload_hash:
            return {"signal_id": signal.signal_id, "state": "REJECTED", "reason": "signal_id_payload_mismatch"}
        return {**existing, "idempotent_replay": True}

    def evaluate(self, signal: OrderSignal, snapshot: MarketSnapshot) -> dict[str, object]:
        replayed = self.replay(signal)
        if replayed is not None:
            return replayed

        try:
            signal.validate()
        except ValueError as exc:
            return self.ledger.record(signal, "REJECTED", f"invalid_signal:{exc}", {})
        if not signal.verify(self.secret):
            return self.ledger.record(signal, "REJECTED", "invalid_signature", {})

        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("executor clock must include a timezone")
        blockers = self._blockers(signal, snapshot, now)
        if blockers:
            return self.ledger.record(
                signal,
                "REJECTED",
                blockers[0],
                {
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "quantity": signal.quantity,
                    "blockers": blockers,
                    "snapshot": asdict(snapshot),
                    "real_order_submitted": False,
                },
            )

        if self.mode == "paper" and self.paper_order_ledger is None:
            return self.ledger.record(
                signal,
                "REJECTED",
                "paper_lifecycle_unavailable",
                {"symbol": signal.symbol, "real_order_submitted": False},
            )
        if self.mode == "live":
            if self.live_broker_submit is None:
                return self.ledger.record(
                    signal,
                    "REJECTED",
                    "live_broker_unavailable",
                    {"symbol": signal.symbol, "real_order_submitted": False},
                )
            reserved = self.ledger.record(
                signal,
                "LIVE_SUBMITTING",
                "durable_reservation_before_broker_call",
                {
                    "mode": "live",
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "quantity": signal.quantity,
                    "decision_price": snapshot.ask_price if signal.side == "BUY" else snapshot.bid_price,
                    "real_order_submitted": False,
                    "snapshot": asdict(snapshot),
                },
            )
            if reserved.get("idempotent_replay") is True:
                return reserved
            try:
                broker_result = dict(self.live_broker_submit(signal, snapshot))
            except Exception as exc:
                return self.ledger.transition_live(
                    signal.signal_id,
                    "LIVE_RECONCILIATION_REQUIRED",
                    "broker_call_outcome_unknown",
                    {"error": f"{type(exc).__name__}: {exc}"[:500]},
                )
            order_no = str(broker_result.get("order_no") or broker_result.get("ODNO") or "").strip()
            if broker_result.get("ok") is not True or not order_no:
                return self.ledger.transition_live(
                    signal.signal_id,
                    "LIVE_REJECTED",
                    "broker_rejected_or_missing_order_number",
                    {"broker_result": broker_result, "real_order_submitted": False},
                )
            return self.ledger.transition_live(
                signal.signal_id,
                "LIVE_SUBMITTED",
                "broker_order_number_recorded",
                {"broker_result": broker_result, "order_no": order_no, "real_order_submitted": True},
            )
        lifecycle = self.paper_order_ledger.submit(signal) if self.mode == "paper" else None
        reason = "all_guards_passed"
        if self.mode == "paper" and signal.order_type == "IOC_LIMIT":
            visible_quantity = snapshot.best_ask_quantity if signal.side == "BUY" else snapshot.best_bid_quantity
            if visible_quantity > 0:
                lifecycle = self.paper_order_ledger.match_ioc(signal, snapshot)
                reason = str(lifecycle.get("match_reason") or "paper_ioc_processed")
        state = str(lifecycle.get("state")) if lifecycle else "SHADOW_ACCEPTED"
        result = {
            "mode": self.mode,
            "symbol": signal.symbol,
            "side": signal.side,
            "quantity": signal.quantity,
            "decision_price": snapshot.ask_price if signal.side == "BUY" else snapshot.bid_price,
            "real_order_submitted": False,
            "snapshot": asdict(snapshot),
            "paper_lifecycle": lifecycle or {},
        }
        return self.ledger.record(signal, state, reason, result)

    def recover_paper_decision(
        self, signal: OrderSignal, lifecycle: Mapping[str, object]
    ) -> dict[str, object]:
        """Repair a Paper-ledger-first commit after an interrupted two-ledger write."""
        if self.mode != "paper":
            raise ValueError("paper_recovery_requires_paper_mode")
        signal.validate()
        if not signal.verify(self.secret):
            raise ValueError("paper_recovery_invalid_signature")
        state = str(lifecycle.get("state") or "")
        valid_states = {
            "PAPER_SUBMITTED", "PAPER_PARTIALLY_FILLED", "PAPER_CANCEL_PENDING",
            "PAPER_FILLED", "PAPER_CANCELED", "PAPER_REJECTED",
        }
        if state not in valid_states:
            raise ValueError("paper_recovery_invalid_state")
        replayed = self.replay(signal)
        if replayed is not None:
            if replayed.get("idempotent_replay") is not True:
                raise ValueError("paper_recovery_signal_payload_mismatch")
            if replayed.get("state") == state:
                return replayed
            return self.ledger.transition_paper(
                signal.signal_id,
                state,
                "paper_ledgers_state_reconciled_after_interrupted_commit",
                {
                    "paper_lifecycle": dict(lifecycle),
                    "real_order_submitted": False,
                    "recovered_from_paper_ledger": True,
                },
            )
        return self.ledger.record(
            signal,
            state,
            "paper_ledger_recovered_after_interrupted_commit",
            {
                "mode": "paper",
                "symbol": signal.symbol,
                "side": signal.side,
                "quantity": signal.quantity,
                "real_order_submitted": False,
                "paper_lifecycle": dict(lifecycle),
                "recovered_from_paper_ledger": True,
            },
        )

    def _blockers(self, signal: OrderSignal, snap: MarketSnapshot, now: datetime) -> list[str]:
        policy = self.policy
        blockers: list[str] = []
        if now > _parse_time(signal.expires_at):
            blockers.append("signal_expired")
        try:
            snapshot_age = (now - _parse_time(snap.observed_at)).total_seconds()
            if snapshot_age < -1.0:
                blockers.append("snapshot_from_future")
            elif snapshot_age > policy.max_snapshot_age_seconds:
                blockers.append("snapshot_stale")
        except (TypeError, ValueError):
            blockers.append("snapshot_timestamp_invalid")
        numeric_fields = {
            "current_price": snap.current_price,
            "ask_price": snap.ask_price,
            "bid_price": snap.bid_price,
            "available_cash": snap.available_cash,
            "equity": snap.equity,
            "total_exposure": snap.total_exposure,
            "symbol_exposure": snap.symbol_exposure,
            "daily_loss_pct": snap.daily_loss_pct,
            "daily_order_count": snap.daily_order_count,
            "available_position_quantity": snap.available_position_quantity,
            "fetch_latency_seconds": snap.fetch_latency_seconds,
            "best_ask_quantity": snap.best_ask_quantity,
            "best_bid_quantity": snap.best_bid_quantity,
        }
        invalid_numeric = [name for name, value in numeric_fields.items() if not _finite_number(value)]
        if invalid_numeric:
            return blockers + [f"snapshot_numeric_invalid:{name}" for name in invalid_numeric]
        if not isinstance(snap.daily_order_count, int) or isinstance(snap.daily_order_count, bool):
            return blockers + ["snapshot_numeric_invalid:daily_order_count"]
        nonnegative_fields = {
            "available_cash": snap.available_cash,
            "total_exposure": snap.total_exposure,
            "symbol_exposure": snap.symbol_exposure,
            "daily_order_count": snap.daily_order_count,
            "available_position_quantity": snap.available_position_quantity,
            "fetch_latency_seconds": snap.fetch_latency_seconds,
            "best_ask_quantity": snap.best_ask_quantity,
            "best_bid_quantity": snap.best_bid_quantity,
        }
        invalid_negative = [name for name, value in nonnegative_fields.items() if value < 0]
        if invalid_negative:
            return blockers + [f"snapshot_numeric_negative:{name}" for name in invalid_negative]
        boolean_fields = {
            "account_ok": snap.account_ok,
            "already_held": snap.already_held,
            "emergency_halt": snap.emergency_halt,
            "pending_same_symbol": snap.pending_same_symbol,
            "market_halted": snap.market_halted,
            "vi_active": snap.vi_active,
        }
        invalid_boolean = [name for name, value in boolean_fields.items() if not isinstance(value, bool)]
        snapshot_contract_blockers = [
            f"snapshot_boolean_invalid:{name}" for name in invalid_boolean
        ]
        if not isinstance(snap.data_source, str) or not snap.data_source.startswith(policy.required_data_source_prefix):
            snapshot_contract_blockers.append("snapshot_data_source_untrusted")
        if snapshot_contract_blockers:
            return blockers + snapshot_contract_blockers
        if snap.fetch_latency_seconds > policy.max_snapshot_latency_seconds:
            blockers.append("snapshot_fetch_too_slow")
        if snap.emergency_halt:
            blockers.append("emergency_halt")
        if snap.market_halted:
            blockers.append("market_halted")
        if snap.vi_active:
            blockers.append("volatility_interruption")
        if policy.require_account_ok and not snap.account_ok:
            blockers.append("account_unavailable")
        if snap.snapshot_errors:
            blockers.append("snapshot_incomplete")
        if snap.pending_same_symbol:
            blockers.append("pending_order_same_symbol")
        execution_price = snap.ask_price if signal.side == "BUY" else snap.bid_price
        if execution_price <= 0 or snap.current_price <= 0:
            blockers.append("invalid_market_price")
        if snap.ask_price > 0 and snap.bid_price > 0 and snap.ask_price < snap.bid_price:
            blockers.append("crossed_orderbook")
        if signal.side == "BUY" and execution_price > signal.max_price:
            blockers.append("max_price_exceeded")
        if signal.side == "SELL" and execution_price < signal.min_price:
            blockers.append("min_price_breached")
        chase_pct = ((execution_price / signal.reference_price) - 1.0) * 100 if signal.reference_price else 999.0
        if signal.side == "BUY" and chase_pct > policy.max_chase_pct:
            blockers.append("chase_limit_exceeded")
        spread_pct = ((snap.ask_price - snap.bid_price) / snap.current_price) * 100 if snap.current_price else 999.0
        if spread_pct > policy.max_spread_pct:
            blockers.append("spread_too_wide")
        notional = execution_price * signal.quantity
        if signal.side == "BUY" and notional > snap.available_cash:
            blockers.append("insufficient_cash")
        if signal.side == "SELL" and snap.available_position_quantity < signal.quantity:
            blockers.append("insufficient_position_quantity")
        if snap.equity <= 0:
            blockers.append("invalid_equity")
        else:
            exposure_delta = notional if signal.side == "BUY" else -notional
            total_after = max(0.0, snap.total_exposure + exposure_delta) / snap.equity * 100
            symbol_after = max(0.0, snap.symbol_exposure + exposure_delta) / snap.equity * 100
            # Entry limits must never prevent a valid risk-reducing exit.
            if signal.side == "BUY" and total_after > policy.max_total_exposure_pct:
                blockers.append("total_exposure_limit")
            if signal.side == "BUY" and symbol_after > policy.max_symbol_exposure_pct:
                blockers.append("symbol_exposure_limit")
        if signal.side == "BUY" and snap.daily_order_count >= policy.max_daily_orders:
            blockers.append("daily_order_limit")
        if signal.side == "BUY" and snap.daily_loss_pct <= -abs(policy.max_daily_loss_pct):
            blockers.append("daily_loss_limit")
        return blockers


@contextmanager
def single_instance_lock(path: Path) -> Iterator[None]:
    """Hold a non-blocking Windows lock so two sidecars cannot run together."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("execution sidecar is already running") from exc
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        handle.close()


def poll_signal_directory(
    inbox: Path,
    sidecar: ExecutionSidecar,
    snapshot_provider: Callable[[OrderSignal], MarketSnapshot],
    interval_seconds: float = 1.0,
) -> None:
    """Continuously consume JSON signals; this loop never submits a real order."""
    inbox.mkdir(parents=True, exist_ok=True)
    while True:
        for path in sorted(inbox.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            signal = OrderSignal(**payload)
            if sidecar.replay(signal) is None:
                sidecar.evaluate(signal, snapshot_provider(signal))
        time.sleep(max(0.1, interval_seconds))


def process_signal_directory_once(
    inbox: Path,
    processed: Path,
    results: Path,
    sidecar: ExecutionSidecar,
    snapshot_provider: Callable[[OrderSignal], MarketSnapshot],
) -> list[dict[str, object]]:
    """Consume each signal once, persist its result, then archive its source file."""
    inbox, processed, results = Path(inbox), Path(processed), Path(results)
    for directory in (inbox, processed, results):
        directory.mkdir(parents=True, exist_ok=True)
    completed: list[dict[str, object]] = []
    for path in sorted(inbox.glob("*.json")):
        try:
            signal = OrderSignal(**json.loads(path.read_text(encoding="utf-8")))
            result = sidecar.replay(signal)
            if result is None:
                result = sidecar.evaluate(signal, snapshot_provider(signal))
        except Exception as exc:
            result = {
                "signal_id": path.stem,
                "state": "REJECTED",
                "reason": "signal_processing_error",
                "result": {"error": f"{type(exc).__name__}: {exc}"[:500], "real_order_submitted": False},
            }
        result_text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        result_path = results / f"{path.stem}.json"
        _atomic_write_text(result_path, result_text)
        destination = processed / path.name
        if destination.exists():
            destination = processed / f"{path.stem}.{time.time_ns()}.json"
        _replace_with_retry(path, destination)
        completed.append({**result, "result_path": str(result_path), "source_archive": str(destination)})
    return completed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CodexStock fail-closed Paper/Shadow execution sidecar")
    parser.add_argument("--mode", choices=sorted(ALLOWED_MODES), default="shadow")
    parser.add_argument("--signal", type=Path, required=True, help="signed order signal JSON")
    parser.add_argument("--snapshot", type=Path, required=True, help="latest market/account snapshot JSON")
    parser.add_argument("--ledger", type=Path, required=True, help="SQLite idempotency ledger")
    parser.add_argument("--lock", type=Path, required=True, help="single-instance lock file")
    parser.add_argument("--secret-env", default="CODEXSTOCK_EXECUTOR_SECRET")
    parser.add_argument("--paper-ledger", type=Path, help="required Paper lifecycle SQLite ledger")
    args = parser.parse_args(argv)

    secret_text = os.environ.get(args.secret_env, "")
    if not secret_text:
        parser.error(f"required signing secret environment variable is missing: {args.secret_env}")

    signal = OrderSignal(**json.loads(args.signal.read_text(encoding="utf-8")))
    snapshot = MarketSnapshot(**json.loads(args.snapshot.read_text(encoding="utf-8")))
    if args.mode == "paper" and args.paper_ledger is None:
        parser.error("--paper-ledger is required in paper mode")
    paper_ledger = None
    if args.paper_ledger is not None:
        from .paper_lifecycle import PaperOrderLedger

        paper_ledger = PaperOrderLedger(args.paper_ledger)
    with single_instance_lock(args.lock):
        result = ExecutionSidecar(
            SignalLedger(args.ledger), secret_text.encode("utf-8"), mode=args.mode,
            paper_order_ledger=paper_ledger,
        ).evaluate(signal, snapshot)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state") != "REJECTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
