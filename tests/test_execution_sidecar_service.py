import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.execution_sidecar_service import (
    ShadowExecutionService,
    _write_json,
    live_mode_allowed,
    validation_transition_alert,
)
from stock_suite.execution_sidecar import ExecutionSidecar, ExecutorPolicy, MarketSnapshot, OrderSignal, SignalLedger
from stock_suite.paper_lifecycle import PaperOrderLedger


class ExecutionSidecarServiceTests(unittest.TestCase):
    def test_live_mode_uses_canonical_policy_and_fails_closed(self):
        policy = {
            "live_execution_control_mode": "delegated_auto",
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_mode": "standing",
            "require_approval": False,
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
            "emergency_halt": False,
            "day_halted": False,
        }
        allowed, contract = live_mode_allowed(
            "live", policy, live_executor_enabled=True
        )
        self.assertTrue(allowed)
        self.assertTrue(contract["policy_consistent"])

        conflicted = dict(policy, require_approval=True)
        allowed, contract = live_mode_allowed(
            "live", conflicted, live_executor_enabled=True
        )
        self.assertFalse(allowed)
        self.assertFalse(contract["policy_consistent"])

        halted = dict(policy, emergency_halt=True)
        allowed, contract = live_mode_allowed(
            "live", halted, live_executor_enabled=True
        )
        self.assertFalse(allowed)
        self.assertTrue(contract["safety_halt"])

    def test_atomic_status_write_retries_transient_windows_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "status.json"
            real_replace = __import__("os").replace
            attempts = []

            def flaky_replace(source, destination):
                attempts.append(1)
                if len(attempts) == 1:
                    raise PermissionError("transient reader lock")
                return real_replace(source, destination)

            with patch("app.execution_sidecar_service.os.replace", side_effect=flaky_replace):
                _write_json(target, {"ok": True})
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(len(attempts), 2)

    def test_validation_transition_alert_only_reports_state_changes(self):
        failure = validation_transition_alert(
            {"operational_ok": True},
            {"operational_ok": False, "checks": {"ledger_ok": True, "hash_ok": False}},
        )
        recovery = validation_transition_alert(
            {"operational_ok": False}, {"operational_ok": True, "checks": {"hash_ok": True}}
        )

        self.assertEqual(failure["kind"], "failure")
        self.assertEqual(failure["failed_checks"], ["hash_ok"])
        self.assertEqual(recovery["kind"], "recovery")
        self.assertIsNone(validation_transition_alert({}, {"operational_ok": False}))
        self.assertIsNone(validation_transition_alert(
            {"operational_ok": True}, {"operational_ok": True}
        ))

    def test_paper_advance_synchronizes_three_ledgers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now(timezone.utc)
            secret = b"service-test-secret"
            signal = OrderSignal(
                signal_id="SERVICE-PAPER-1", created_at=now.isoformat(),
                expires_at=(now + timedelta(minutes=2)).isoformat(), symbol="005930", side="BUY",
                quantity=3, order_type="LIMIT", reference_price=100_000, max_price=100_300,
                stop_loss_pct=-2, take_profit_pct=3, strategy_id="candidate-ledger", evidence_hash="a" * 64,
            ).sign(secret)
            signal_ledger = SignalLedger(root / "signals.sqlite3")
            paper_ledger = PaperOrderLedger(root / "paper.sqlite3")
            sidecar = ExecutionSidecar(
                signal_ledger, secret, mode="paper", policy=ExecutorPolicy(),
                clock=lambda: now + timedelta(seconds=1), paper_order_ledger=paper_ledger,
            )
            submitted = sidecar.evaluate(signal, MarketSnapshot(
                observed_at=now.isoformat(), current_price=100_000, ask_price=100_000, bid_price=99_900,
                account_ok=True, available_cash=1_000_000, equity=10_000_000, total_exposure=0,
                symbol_exposure=0, daily_loss_pct=0, daily_order_count=0,
                data_source="KIS_READONLY_CALLS_TEST_PROFILE",
            ))
            results = root / "results"
            results.mkdir()
            (results / "SERVICE-PAPER-1.json").write_text(json.dumps(submitted), encoding="utf-8")

            service = ShadowExecutionService.__new__(ShadowExecutionService)
            service.paper_ledger = paper_ledger
            service.sidecar = sidecar
            service.results = results
            service.provider = lambda value: MarketSnapshot(
                observed_at=datetime.now(timezone.utc).isoformat(), current_price=100_000,
                ask_price=100_000, bid_price=99_900, account_ok=True, available_cash=1_000_000,
                equity=10_000_000, total_exposure=0, symbol_exposure=0, daily_loss_pct=0,
                daily_order_count=0, best_ask_quantity=1, best_bid_quantity=1,
                data_source="KIS_READONLY_CALLS_TEST_PROFILE",
            )
            updates = service._advance_paper_orders()
            result_file = json.loads((results / "SERVICE-PAPER-1.json").read_text(encoding="utf-8"))
            paper_state = paper_ledger.get("SERVICE-PAPER-1")["state"]
            signal_state = signal_ledger.get("SERVICE-PAPER-1")["state"]

            class AfterExpiry(datetime):
                @classmethod
                def now(cls, tz=None):
                    value = now + timedelta(minutes=3)
                    return value.astimezone(tz) if tz else value

            restarted = ShadowExecutionService.__new__(ShadowExecutionService)
            restarted.paper_ledger = PaperOrderLedger(root / "paper.sqlite3")
            restarted.sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), secret, mode="paper",
                paper_order_ledger=restarted.paper_ledger,
            )
            restarted.results = results
            restarted.provider = service.provider
            with patch("stock_suite.paper_lifecycle.datetime", AfterExpiry):
                restart_updates = restarted._advance_paper_orders()
            final_result = json.loads((results / "SERVICE-PAPER-1.json").read_text(encoding="utf-8"))
            final_paper = restarted.paper_ledger.get("SERVICE-PAPER-1")
            final_signal = restarted.sidecar.ledger.get("SERVICE-PAPER-1")
            reconciliation = restarted.paper_ledger.reconcile()

        self.assertEqual(len(updates), 1)
        self.assertEqual(paper_state, "PAPER_PARTIALLY_FILLED")
        self.assertEqual(signal_state, "PAPER_PARTIALLY_FILLED")
        self.assertEqual(result_file["state"], "PAPER_PARTIALLY_FILLED")
        self.assertFalse(result_file["result"]["real_order_submitted"])
        self.assertEqual(len(restart_updates), 1)
        self.assertEqual(final_paper["state"], "PAPER_CANCELED")
        self.assertEqual(final_signal["state"], "PAPER_CANCELED")
        self.assertEqual(final_result["state"], "PAPER_CANCELED")
        self.assertEqual(final_paper["filled_quantity"], 1)
        self.assertEqual(final_paper["remaining_quantity"], 2)
        self.assertTrue(reconciliation["ok"])


if __name__ == "__main__":
    unittest.main()
