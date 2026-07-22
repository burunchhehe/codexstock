"""Run the CodexStock Shadow execution sidecar against read-only KIS data."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
PACKAGES_ROOT = REPO_ROOT / "packages"
for path in (APP_ROOT, PACKAGES_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from integrations import IntegrationHub  # noqa: E402
from ops_core import HepiOpsCore  # noqa: E402
from stock_suite.execution_sidecar import (  # noqa: E402
    ExecutionSidecar,
    SignalLedger,
    process_signal_directory_once,
    single_instance_lock,
)
from stock_suite.execution_mode import build_execution_policy_contract  # noqa: E402
from stock_suite.snapshot_provider import KisShadowSnapshotProvider  # noqa: E402
from stock_suite.signal_bridge import load_or_create_signing_secret  # noqa: E402
from stock_suite.paper_lifecycle import PaperOrderLedger  # noqa: E402
from stock_suite.runtime_evidence import RuntimeEvidenceLedger  # noqa: E402
from stock_suite.pipeline_audit import audit_candidate_pipeline  # noqa: E402
from stock_suite.pipeline_drill import run_isolated_pipeline_drill  # noqa: E402
from stock_suite.sidecar_audit import audit_shadow_runtime  # noqa: E402


def live_mode_allowed(
    mode: str,
    policy: dict[str, object],
    *,
    live_executor_enabled: bool,
) -> tuple[bool, dict[str, object]]:
    execution_policy = build_execution_policy_contract(policy)
    allowed = bool(
        mode == "live"
        and live_executor_enabled
        and execution_policy.get("policy_consistent") is True
        and execution_policy.get("delegated") is True
        and execution_policy.get("authorization_valid") is True
        and execution_policy.get("live_switches_enabled") is True
        and execution_policy.get("safety_halt") is False
        and execution_policy.get("desired_sidecar_mode") == "live"
    )
    return allowed, execution_policy


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        for attempt in range(40):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _result_history(results_dir: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    if results_dir.exists():
        for path in sorted(results_dir.glob("*.json")):
            row = _read_json(path)
            if row:
                rows.append(row)
    return {
        "processed_total": len(rows),
        "accepted_total": sum(1 for row in rows if row.get("state") in {"SHADOW_ACCEPTED", "PAPER_FILLED", "LIVE_SUBMITTED"}),
        "rejected_total": sum(1 for row in rows if row.get("state") == "REJECTED"),
        "last_result": rows[-1] if rows else {},
    }


def validation_transition_alert(
    previous: dict[str, object], current: dict[str, object]
) -> dict[str, object] | None:
    """Return one alert only when the independent audit changes state."""
    previous_ok = previous.get("operational_ok")
    current_ok = current.get("operational_ok")
    if not isinstance(previous_ok, bool) or not isinstance(current_ok, bool):
        return None
    if previous_ok == current_ok:
        return None
    if current_ok:
        return {
            "kind": "recovery",
            "text": (
                "[외부 실행기 복구]\n"
                "독립 운영감사가 다시 정상으로 확인됐습니다.\n"
                "실계좌 주문 기능은 계속 비활성 상태입니다."
            ),
            "failed_checks": [],
        }
    checks = current.get("checks") if isinstance(current.get("checks"), dict) else {}
    failed_checks = sorted(str(name) for name, ok in checks.items() if ok is not True)
    failed_text = ", ".join(failed_checks[:8]) or "상세 감사 보고서 확인 필요"
    return {
        "kind": "failure",
        "text": (
            "[외부 실행기 이상]\n"
            f"독립 운영감사 실패: {failed_text}\n"
            "실계좌 주문 기능은 비활성 상태이며 Shadow 처리를 점검합니다."
        ),
        "failed_checks": failed_checks,
    }


class ShadowExecutionService:
    def __init__(self, repo_root: Path = REPO_ROOT, mode: str = "shadow") -> None:
        self.ops = HepiOpsCore(repo_root)
        self.hub = IntegrationHub(repo_root)
        root = self.ops.data_dir / "execution_sidecar"
        self.inbox = root / "inbox"
        self.processed = root / "processed"
        self.results = root / "results"
        self.status_file = root / "status.json"
        self.runtime_evidence = RuntimeEvidenceLedger(root / "runtime_evidence.sqlite3")
        self.process_started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        self._last_evidence_write = 0.0
        self._candidate_pipeline_status: dict[str, object] = {}
        try:
            self._pipeline_drill = run_isolated_pipeline_drill(root)
        except Exception as exc:
            self._pipeline_drill = {
                "ok": False,
                "mode": "shadow",
                "isolated": True,
                "real_order_allowed": False,
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }
        previous_status = _read_json(self.status_file)
        previous_proof = previous_status.get("validation_proof")
        self._validation_proof = previous_proof if isinstance(previous_proof, dict) else {}
        previous_alert = previous_status.get("validation_alert")
        self._validation_alert = previous_alert if isinstance(previous_alert, dict) else {}
        self.validation_file = root / "validation_proof.json"
        secret = load_or_create_signing_secret(self.ops.shadow_signal_secret_file)
        self.paper_ledger = PaperOrderLedger(root / "paper_orders.sqlite3") if mode == "paper" else None
        live_enabled, execution_policy = live_mode_allowed(
            mode,
            self.ops.autotrade_policy(),
            live_executor_enabled=(
                os.environ.get("CODEXSTOCK_ENABLE_EXTERNAL_LIVE_EXECUTOR") == "1"
            ),
        )
        self.execution_policy = execution_policy
        self.runtime_mode_ready = bool(mode != "live" or live_enabled)

        def live_submit(signal, snapshot):
            order_price = snapshot.ask_price if signal.side == "BUY" else snapshot.bid_price
            return self.hub.kis_cash_order(
                symbol=signal.symbol,
                side=signal.side,
                quantity=signal.quantity,
                price=order_price,
                order_type="limit",
            )

        self.sidecar = ExecutionSidecar(
            SignalLedger(root / "ledger.sqlite3"), secret, mode=mode,
            paper_order_ledger=self.paper_ledger,
            live_broker_submit=live_submit if live_enabled else None,
        )
        self.provider = KisShadowSnapshotProvider(
            quote=self.hub.kis_quote,
            orderbook=self.hub.kis_orderbook,
            account=self.hub.kis_account,
            executions=lambda symbol: self.hub.kis_daily_executions(symbol=symbol, filled="all"),
            emergency_halt=lambda: bool(self.ops.autotrade_policy().get("emergency_halt")),
        )

    def _advance_paper_orders(self) -> list[dict[str, object]]:
        if not self.paper_ledger:
            return []
        updates: list[dict[str, object]] = []
        initial_reconciliation = self.paper_ledger.reconcile()
        if initial_reconciliation.get("ok") is not True:
            raise RuntimeError("paper_ledger_reconciliation_failed_before_recovery")
        for signal, lifecycle in self.paper_ledger.recover_all_signals():
            recovered = self.sidecar.recover_paper_decision(signal, lifecycle)
            result_path = self.results / f"{signal.signal_id}.json"
            if recovered.get("idempotent_replay") is not True or not result_path.exists():
                _write_json(result_path, recovered)
                updates.append(recovered)
        for signal, before in self.paper_ledger.recover_open_signals():
            snapshot = self.provider(signal)
            lifecycle = self.paper_ledger.advance_resting_order(signal, snapshot)
            if int(lifecycle.get("version") or 0) == int(before.get("version") or 0):
                continue
            reason = str(lifecycle.get("match_reason") or "paper_lifecycle_advanced")
            transitioned = self.sidecar.ledger.transition_paper(
                signal.signal_id,
                str(lifecycle.get("state") or "PAPER_SUBMITTED"),
                reason,
                {"paper_lifecycle": lifecycle, "snapshot": snapshot.__dict__, "real_order_submitted": False},
            )
            result_path = self.results / f"{signal.signal_id}.json"
            result_document = _read_json(result_path)
            result_document.update(transitioned)
            _write_json(result_path, result_document)
            updates.append(transitioned)
        return updates

    def run_once(self) -> list[dict[str, object]]:
        previous = _read_json(self.status_file)
        baseline = _result_history(self.results) if "processed_total" not in previous else previous
        completed = process_signal_directory_once(
            self.inbox, self.processed, self.results, self.sidecar, self.provider
        )
        paper_updates = self._advance_paper_orders()
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        for result in completed:
            state = str(result.get("state") or "UNKNOWN")
            reason = str(result.get("reason") or "")
            mode_label = {"shadow": "Shadow", "paper": "Paper", "live": "실전"}.get(
                self.sidecar.mode, self.sidecar.mode
            )
            submitted = bool((result.get("result") or {}).get("real_order_submitted"))
            self.ops.queue_telegram(
                text=(
                    f"[{mode_label} 외부 실행기]\n"
                    f"신호: {result.get('signal_id', '-')}\n"
                    f"결과: {state}\n"
                    f"사유: {reason}\n"
                    f"실제 주문: {'전송 기록됨' if submitted else '전송하지 않음'}"
                ),
                message_type=f"{self.sidecar.mode}_execution",
                source="execution-sidecar",
                metadata={"signal_id": result.get("signal_id"), "state": state, "reason": reason},
            )
        paper_reconciliation = self.paper_ledger.reconcile() if self.paper_ledger else None
        evidence_due = time.monotonic() - self._last_evidence_write >= 30.0
        if evidence_due:
            self._candidate_pipeline_status = audit_candidate_pipeline(
                self.ops.ticket_file,
                self.inbox,
                self.processed,
                self.results,
                self.ops.data_dir.parent / "intraday_market_pulses.jsonl",
                self.ops.data_dir.parent / "intraday_minute_radar.jsonl",
                self.ops.data_dir.parent / "live_candidate_decisions.jsonl",
                service_mode=self.sidecar.mode,
                control_mode=str(self.execution_policy.get("control_mode") or ""),
            )
        history = _result_history(self.results)
        _write_json(
            self.status_file,
            {
                "ok": self.runtime_mode_ready,
                "state": "running" if self.runtime_mode_ready else "live_mode_policy_blocked",
                "mode": self.sidecar.mode,
                "started_at": previous.get("started_at") or now,
                "updated_at": now,
                "cycles": int(previous.get("cycles") or 0) + 1,
                "processed_this_cycle": len(completed),
                "paper_updates_this_cycle": len(paper_updates),
                "processed_total": int(history.get("processed_total") or 0),
                "accepted_total": int(history.get("accepted_total") or 0),
                "rejected_total": int(history.get("rejected_total") or 0),
                "last_activity_at": (
                    now if completed
                    else previous.get("last_activity_at")
                    or (baseline.get("last_result") or {}).get("updated_at")
                    or ""
                ),
                "last_result": completed[-1] if completed else previous.get("last_result") or baseline.get("last_result") or {},
                "inbox_pending": len(list(self.inbox.glob("*.json"))) if self.inbox.exists() else 0,
                "paper_reconciliation": paper_reconciliation,
                "paper_open_orders": paper_reconciliation.get("open_order_count", 0) if paper_reconciliation else 0,
                "runtime_session_id": self.runtime_evidence.session_id,
                "process_id": os.getpid(),
                "process_started_at": self.process_started_at,
                "candidate_pipeline": self._candidate_pipeline_status,
                "pipeline_drill": self._pipeline_drill,
                "validation_proof": self._validation_proof,
                "validation_alert": self._validation_alert,
                "real_order_supported": self.sidecar.mode == "live" and self.sidecar.live_broker_submit is not None,
                "execution_policy": {
                    "control_mode": self.execution_policy.get("control_mode"),
                    "policy_consistent": self.execution_policy.get("policy_consistent"),
                    "policy_conflicts": self.execution_policy.get("policy_conflicts"),
                    "authorization_valid": self.execution_policy.get("authorization_valid"),
                    "live_switches_enabled": self.execution_policy.get("live_switches_enabled"),
                    "safety_halt": self.execution_policy.get("safety_halt"),
                    "desired_sidecar_mode": self.execution_policy.get("desired_sidecar_mode"),
                },
            },
        )
        if evidence_due:
            self.runtime_evidence.heartbeat(
                mode=self.sidecar.mode,
                cycle=int(previous.get("cycles") or 0) + 1,
                ok=self.runtime_mode_ready,
            )
            self._last_evidence_write = time.monotonic()
            audit = audit_shadow_runtime(
                self.status_file.parent,
                min_observation_hours=24.0,
                min_result_count=10,
                min_symbol_count=2,
            )
            previous_proof = self._validation_proof
            self._validation_proof = {
                "operational_ok": audit.get("operational_ok"),
                "proof_complete": audit.get("proof_complete"),
                "observation_hours": audit.get("observation_hours"),
                "required_observation_hours": audit.get("required_observation_hours"),
                "coverage_complete": audit.get("coverage_complete"),
                "qualifying_result_count": (audit.get("evidence") or {}).get("qualifying_result_count"),
                "required_result_count": audit.get("required_result_count"),
                "observed_symbol_count": (audit.get("evidence") or {}).get("observed_symbol_count"),
                "required_symbol_count": audit.get("required_symbol_count"),
                "generated_at": audit.get("generated_at"),
            }
            transition = validation_transition_alert(previous_proof, audit)
            if transition:
                self._validation_alert = {
                    **transition,
                    "detected_at": self._validation_proof.get("generated_at"),
                }
                try:
                    self.ops.queue_telegram(
                        text=str(transition["text"]),
                        message_type="execution_sidecar_audit",
                        source="execution-sidecar",
                        metadata={
                            "kind": transition["kind"],
                            "failed_checks": transition["failed_checks"],
                        },
                    )
                except Exception as exc:
                    self._validation_alert["telegram_error"] = f"{type(exc).__name__}: {exc}"[:300]
            _write_json(self.validation_file, audit)
            current_status = _read_json(self.status_file)
            current_status["validation_proof"] = self._validation_proof
            current_status["validation_alert"] = self._validation_alert
            _write_json(self.status_file, current_status)
        return completed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CodexStock fail-closed external execution service")
    parser.add_argument("--mode", choices=("shadow", "paper", "live"), default="shadow")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    service = ShadowExecutionService(mode=args.mode)
    lock_path = service.ops.data_dir / "execution_sidecar" / "service.lock"
    with single_instance_lock(lock_path):
        while True:
            try:
                service.run_once()
            except Exception as exc:
                previous = _read_json(service.status_file)
                service.runtime_evidence.heartbeat(
                    mode=service.sidecar.mode,
                    cycle=int(previous.get("cycles") or 0) + 1,
                    ok=False,
                )
                _write_json(
                    service.status_file,
                    {
                        **previous,
                        "ok": False,
                        "mode": service.sidecar.mode,
                        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "error": f"{type(exc).__name__}: {exc}"[:500],
                        "state": "cycle_failed_service_alive",
                        "cycle_failures": int(previous.get("cycle_failures") or 0) + 1,
                        "real_order_supported": service.sidecar.mode == "live" and service.sidecar.live_broker_submit is not None,
                    },
                )
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(max(0.2, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
