"""Isolated end-to-end execution drill that can never submit a real order."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from .execution_sidecar import ExecutionSidecar, MarketSnapshot, SignalLedger, process_signal_directory_once
from .signal_bridge import ShadowSignalPublisher, load_or_create_signing_secret


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def run_isolated_pipeline_drill(root: Path, *, now: datetime | None = None) -> dict[str, object]:
    """Prove candidate -> signed signal -> Shadow result using isolated ledgers."""
    observed_at = now or datetime.now().astimezone()
    if observed_at.tzinfo is None:
        raise ValueError("pipeline drill clock must include a timezone")
    latest_path = Path(root) / "pipeline_drill" / "latest.json"
    try:
        previous = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    if (
        isinstance(previous, dict)
        and previous.get("drill_date") == observed_at.date().isoformat()
        and previous.get("ok") is True
    ):
        return {**previous, "reused": True}
    drill_root = Path(root) / "pipeline_drill" / observed_at.date().isoformat()
    inbox = drill_root / "inbox"
    processed = drill_root / "processed"
    results = drill_root / "results"
    secret_path = drill_root / "signal_secret"
    signal_id = f"DRILL-{observed_at.strftime('%Y%m%d')}-005930"
    ticket = {
        "id": f"TICKET-{signal_id}",
        "created_at": observed_at.isoformat(timespec="seconds"),
        "symbol": "005930",
        "side": "BUY",
        "quantity": 1,
        "price": 100_000,
        "mode": "live_candidate",
        "risk_status": "PASSED",
        "source": "isolated-premarket-shadow-drill",
        "memo": "Synthetic diagnostic only; no real order is allowed.",
        "metadata": {"strategy_id": "diagnostic-drill", "drill": True, "signal_id": signal_id},
    }
    publisher = ShadowSignalPublisher(inbox, secret_path, ttl_seconds=60)
    publication = publisher.publish(ticket)
    ticket["shadow_signal"] = publication
    signal_path = Path(str(publication.get("path") or ""))
    signal_payload = json.loads(signal_path.read_text(encoding="utf-8"))
    execution_at = datetime.fromisoformat(str(signal_payload["created_at"])) + timedelta(seconds=1)
    secret = load_or_create_signing_secret(secret_path)
    executor = ExecutionSidecar(
        SignalLedger(drill_root / "ledger.sqlite3"),
        secret,
        mode="shadow",
        clock=lambda: execution_at,
    )
    snapshot = MarketSnapshot(
        observed_at=execution_at.isoformat(timespec="seconds"),
        current_price=100_000,
        ask_price=100_000,
        bid_price=99_900,
        account_ok=True,
        available_cash=1_000_000,
        equity=10_000_000,
        total_exposure=0,
        symbol_exposure=0,
        daily_loss_pct=0,
        daily_order_count=0,
        data_source="KIS_READONLY_SYNTHETIC_ISOLATED_DRILL",
    )
    completed = process_signal_directory_once(
        inbox, processed, results, executor, lambda _signal: snapshot
    )
    result = completed[0] if completed else {}
    result_payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    checks = {
        "signal_published": publication.get("published") is True,
        "executor_received": bool(completed),
        "shadow_accepted": result.get("state") == "SHADOW_ACCEPTED",
        "result_recorded": any(results.glob("*.json")),
        "real_order_blocked": result_payload.get("real_order_submitted") is False,
    }
    proof_source = json.dumps(
        {"ticket": ticket, "result": result, "checks": checks}, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    proof = {
        "schema": "codexstock.pipeline-drill.v1",
        "ok": all(checks.values()),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "drill_date": observed_at.date().isoformat(),
        "mode": "shadow",
        "isolated": True,
        "real_order_allowed": False,
        "checks": checks,
        "signal_id": signal_id,
        "result_state": result.get("state", ""),
        "evidence_hash": hashlib.sha256(proof_source).hexdigest(),
    }
    _atomic_write(latest_path, proof)
    return proof


__all__ = ["run_isolated_pipeline_drill"]
