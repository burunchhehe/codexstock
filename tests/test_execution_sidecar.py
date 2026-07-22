import tempfile
import unittest
import os
import math
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_suite.execution_sidecar import (
    ExecutionSidecar,
    ExecutorPolicy,
    MarketSnapshot,
    OrderSignal,
    SignalLedger,
    process_is_alive,
    process_signal_directory_once,
)
from stock_suite.paper_lifecycle import PaperOrderLedger


NOW = datetime(2026, 7, 20, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
SECRET = b"test-secret"


def signal(signal_id="SIG-1", quantity=1):
    return OrderSignal(
        signal_id=signal_id,
        created_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(seconds=30)).isoformat(),
        symbol="005930",
        side="BUY",
        quantity=quantity,
        order_type="IOC_LIMIT",
        reference_price=100_000,
        max_price=100_300,
        stop_loss_pct=-2,
        take_profit_pct=3,
        strategy_id="momentum-v1",
        evidence_hash="a" * 64,
    ).sign(SECRET)


def snapshot(**changes):
    values = dict(
        observed_at=NOW.isoformat(), current_price=100_100, ask_price=100_100,
        bid_price=100_000, account_ok=True, available_cash=1_000_000,
        equity=10_000_000, total_exposure=1_000_000, symbol_exposure=0,
        daily_loss_pct=0, daily_order_count=0,
        data_source="KIS_READONLY_CALLS_TEST_PROFILE",
    )
    values.update(changes)
    return MarketSnapshot(**values)


class ExecutionSidecarTests(unittest.TestCase):
    def test_process_liveness_probe_distinguishes_current_and_missing_pid(self):
        self.assertTrue(process_is_alive(os.getpid()))
        self.assertFalse(process_is_alive(2_147_483_647))

    def make_sidecar(self, directory, mode="shadow"):
        return ExecutionSidecar(
            SignalLedger(Path(directory) / "ledger.sqlite3"), SECRET, mode=mode,
            policy=ExecutorPolicy(), clock=lambda: NOW + timedelta(seconds=1),
        )

    def test_shadow_accepts_valid_signal_without_real_order(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.make_sidecar(directory).evaluate(signal(), snapshot())
        self.assertEqual(result["state"], "SHADOW_ACCEPTED")
        self.assertFalse(result["result"]["real_order_submitted"])

    def test_executor_rejects_non_finite_or_unsafe_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "invalid executor policy number"):
                ExecutionSidecar(
                    SignalLedger(Path(directory) / "nan-policy.sqlite3"), SECRET,
                    policy=ExecutorPolicy(max_total_exposure_pct=math.nan),
                )
            with self.assertRaisesRegex(ValueError, "no larger than total exposure"):
                ExecutionSidecar(
                    SignalLedger(Path(directory) / "unsafe-policy.sqlite3"), SECRET,
                    policy=ExecutorPolicy(max_total_exposure_pct=10, max_symbol_exposure_pct=15),
                )

    def test_string_account_flag_and_untrusted_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.make_sidecar(directory).evaluate(
                signal(), snapshot(account_ok="false", data_source="manual-fixture"),
            )
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("snapshot_boolean_invalid:account_ok", result["result"]["blockers"])
        self.assertIn("snapshot_data_source_untrusted", result["result"]["blockers"])

    def test_duplicate_signal_is_idempotent_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.make_sidecar(directory).evaluate(signal(), snapshot())
            second = self.make_sidecar(directory).evaluate(signal(), snapshot())
        self.assertEqual(first["state"], "SHADOW_ACCEPTED")
        self.assertTrue(second["idempotent_replay"])

    def test_live_mode_reserves_signal_then_calls_broker_exactly_once(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def broker(order_signal, market_snapshot):
                calls.append((order_signal.signal_id, market_snapshot.ask_price))
                return {"ok": True, "order_no": "KIS-1"}

            ledger = SignalLedger(Path(directory) / "ledger.sqlite3")
            first_sidecar = ExecutionSidecar(
                ledger, SECRET, mode="live", clock=lambda: NOW + timedelta(seconds=1),
                live_broker_submit=broker,
            )
            first = first_sidecar.evaluate(signal(), snapshot())
            restarted = ExecutionSidecar(
                ledger, SECRET, mode="live", clock=lambda: NOW + timedelta(seconds=2),
                live_broker_submit=broker,
            ).evaluate(signal(), snapshot())
        self.assertEqual("LIVE_SUBMITTED", first["state"])
        self.assertEqual("KIS-1", first["result"]["order_no"])
        self.assertTrue(restarted["idempotent_replay"])
        self.assertEqual(1, len(calls))

    def test_live_mode_unknown_broker_outcome_never_retries_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def ambiguous_broker(*_):
                calls.append("called")
                raise TimeoutError("response lost after submit")

            ledger = SignalLedger(Path(directory) / "ledger.sqlite3")
            sidecar = ExecutionSidecar(
                ledger, SECRET, mode="live", clock=lambda: NOW + timedelta(seconds=1),
                live_broker_submit=ambiguous_broker,
            )
            first = sidecar.evaluate(signal(), snapshot())
            replay = sidecar.evaluate(signal(), snapshot())
        self.assertEqual("LIVE_RECONCILIATION_REQUIRED", first["state"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(1, len(calls))

    def test_same_id_with_changed_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sidecar = self.make_sidecar(directory)
            sidecar.evaluate(signal(), snapshot())
            changed = signal(quantity=2)
            result = sidecar.evaluate(changed, snapshot())
        self.assertEqual(result["reason"], "signal_id_payload_mismatch")

    def test_expired_signal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sidecar = ExecutionSidecar(
                SignalLedger(Path(directory) / "ledger.sqlite3"), SECRET,
                clock=lambda: NOW + timedelta(minutes=1),
            )
            result = sidecar.evaluate(signal(), snapshot())
        self.assertEqual(result["reason"], "signal_expired")

    def test_price_and_exposure_guards_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.make_sidecar(directory).evaluate(
                signal(), snapshot(ask_price=101_000, total_exposure=2_990_000)
            )
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("max_price_exceeded", result["result"]["blockers"])
        self.assertIn("total_exposure_limit", result["result"]["blockers"])

    def test_invalid_signature_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            unsigned = OrderSignal(**{**signal().unsigned(), "signature": "bad"})
            result = self.make_sidecar(directory).evaluate(unsigned, snapshot())
        self.assertEqual(result["reason"], "invalid_signature")

    def test_non_finite_signal_number_is_rejected_before_risk_math(self):
        with tempfile.TemporaryDirectory() as directory:
            malformed = OrderSignal(**{
                **signal().unsigned(), "reference_price": math.nan, "signature": "",
            }).sign(SECRET)
            result = self.make_sidecar(directory).evaluate(malformed, snapshot())
        self.assertEqual(result["state"], "REJECTED")
        self.assertEqual(result["reason"], "invalid_signal:non-finite numeric field: reference_price")

    def test_non_sha256_evidence_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            malformed = OrderSignal(**{
                **signal().unsigned(), "evidence_hash": "not-a-sha256-digest", "signature": "",
            }).sign(SECRET)
            result = self.make_sidecar(directory).evaluate(malformed, snapshot())
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("evidence_hash must be a SHA-256", result["reason"])

    def test_non_finite_snapshot_numbers_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.make_sidecar(directory).evaluate(
                signal(), snapshot(equity=math.nan, daily_loss_pct=math.inf),
            )
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("snapshot_numeric_invalid:equity", result["result"]["blockers"])
        self.assertIn("snapshot_numeric_invalid:daily_loss_pct", result["result"]["blockers"])

    def test_negative_snapshot_quantities_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.make_sidecar(directory).evaluate(
                signal(), snapshot(available_cash=-1, best_ask_quantity=-2),
            )
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("snapshot_numeric_negative:available_cash", result["result"]["blockers"])
        self.assertIn("snapshot_numeric_negative:best_ask_quantity", result["result"]["blockers"])

    def test_queue_persists_result_then_archives_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            signed = signal()
            (inbox / "SIG-1.json").write_text(
                __import__("json").dumps(signed.__dict__), encoding="utf-8"
            )
            completed = process_signal_directory_once(
                inbox, root / "processed", root / "results",
                self.make_sidecar(directory), lambda value: snapshot(),
            )
            self.assertEqual(completed[0]["state"], "SHADOW_ACCEPTED")
            self.assertFalse((inbox / "SIG-1.json").exists())
            self.assertTrue((root / "processed" / "SIG-1.json").exists())
            self.assertTrue((root / "results" / "SIG-1.json").exists())
            self.assertEqual(
                process_signal_directory_once(
                    inbox, root / "processed", root / "results",
                    self.make_sidecar(directory), lambda value: snapshot(),
                ),
                [],
            )

    def test_restart_recovers_ledger_decision_without_market_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            signed = signal()
            (inbox / "SIG-1.json").write_text(
                __import__("json").dumps(signed.__dict__), encoding="utf-8"
            )
            sidecar = self.make_sidecar(directory)
            expected = sidecar.evaluate(signed, snapshot())

            def unavailable(_signal):
                raise RuntimeError("market API must not be called during durable replay")

            completed = process_signal_directory_once(
                inbox, root / "processed", root / "results", sidecar, unavailable,
            )
        self.assertEqual(completed[0]["state"], expected["state"])
        self.assertEqual(completed[0]["reason"], expected["reason"])
        self.assertTrue(completed[0]["idempotent_replay"])

    def test_queue_retries_transient_windows_file_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            signed = signal()
            (inbox / "SIG-1.json").write_text(
                __import__("json").dumps(signed.__dict__), encoding="utf-8"
            )
            actual_replace = os.replace
            attempts = {"count": 0}

            def transient_lock(source, destination):
                attempts["count"] += 1
                if attempts["count"] <= 2:
                    raise PermissionError("simulated reader lock")
                return actual_replace(source, destination)

            with patch("stock_suite.execution_sidecar.os.replace", side_effect=transient_lock):
                completed = process_signal_directory_once(
                    inbox, root / "processed", root / "results",
                    self.make_sidecar(directory), lambda _signal: snapshot(),
                )
        self.assertEqual(completed[0]["state"], "SHADOW_ACCEPTED")
        self.assertGreaterEqual(attempts["count"], 4)

    def test_stale_halted_vi_slow_and_crossed_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = (NOW - timedelta(seconds=10)).isoformat()
            result = self.make_sidecar(directory).evaluate(
                signal(),
                snapshot(
                    observed_at=stale, ask_price=99_900, bid_price=100_000,
                    market_halted=True, vi_active=True, fetch_latency_seconds=6,
                ),
            )
        blockers = result["result"]["blockers"]
        self.assertIn("snapshot_stale", blockers)
        self.assertIn("snapshot_fetch_too_slow", blockers)
        self.assertIn("market_halted", blockers)
        self.assertIn("volatility_interruption", blockers)
        self.assertIn("crossed_orderbook", blockers)

    def test_sell_requires_available_position_quantity(self):
        with tempfile.TemporaryDirectory() as directory:
            sell = OrderSignal(**{
                **signal().unsigned(), "side": "SELL", "quantity": 2,
                "min_price": 99_600, "signature": "",
            }).sign(SECRET)
            result = self.make_sidecar(directory).evaluate(
                sell, snapshot(available_position_quantity=1),
            )
        self.assertIn("insufficient_position_quantity", result["result"]["blockers"])

    def test_risk_reducing_sell_is_not_blocked_by_entry_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            sell = OrderSignal(**{
                **signal().unsigned(), "side": "SELL", "quantity": 2,
                "min_price": 99_600, "signature": "",
            }).sign(SECRET)
            result = self.make_sidecar(directory).evaluate(
                sell,
                snapshot(
                    available_position_quantity=5,
                    total_exposure=4_000_000,
                    symbol_exposure=2_000_000,
                    daily_loss_pct=-5,
                    daily_order_count=99,
                ),
            )
        self.assertEqual(result["state"], "SHADOW_ACCEPTED")
        self.assertNotIn("total_exposure_limit", result.get("result", {}).get("blockers", []))
        self.assertNotIn("symbol_exposure_limit", result.get("result", {}).get("blockers", []))
        self.assertNotIn("daily_loss_limit", result.get("result", {}).get("blockers", []))
        self.assertNotIn("daily_order_limit", result.get("result", {}).get("blockers", []))

    def test_sell_below_signed_minimum_price_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sell = OrderSignal(**{
                **signal().unsigned(), "side": "SELL", "quantity": 1,
                "min_price": 99_600, "signature": "",
            }).sign(SECRET)
            result = self.make_sidecar(directory).evaluate(
                sell,
                snapshot(bid_price=99_500, available_position_quantity=1),
            )
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("min_price_breached", result["result"]["blockers"])

    def test_paper_mode_requires_lifecycle_and_starts_submitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            without_ledger = self.make_sidecar(directory, mode="paper").evaluate(signal(), snapshot())
            self.assertEqual(without_ledger["reason"], "paper_lifecycle_unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), SECRET, mode="paper",
                policy=ExecutorPolicy(), clock=lambda: NOW + timedelta(seconds=1),
                paper_order_ledger=PaperOrderLedger(root / "paper.sqlite3"),
            )
            result = sidecar.evaluate(signal(), snapshot())
            self.assertEqual(result["state"], "PAPER_SUBMITTED")
            self.assertEqual(result["result"]["paper_lifecycle"]["remaining_quantity"], 1)

    def test_paper_ioc_uses_visible_liquidity_and_cancels_remainder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), SECRET, mode="paper",
                policy=ExecutorPolicy(), clock=lambda: NOW + timedelta(seconds=1),
                paper_order_ledger=PaperOrderLedger(root / "paper.sqlite3"),
            )
            result = sidecar.evaluate(signal(quantity=3), snapshot(best_ask_quantity=2))
        self.assertEqual(result["state"], "PAPER_CANCELED")
        self.assertEqual(result["reason"], "paper_ioc_partial_canceled")
        lifecycle = result["result"]["paper_lifecycle"]
        self.assertEqual(lifecycle["filled_quantity"], 2)
        self.assertEqual(lifecycle["remaining_quantity"], 1)

    def test_paper_ioc_full_visible_liquidity_fills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), SECRET, mode="paper",
                policy=ExecutorPolicy(), clock=lambda: NOW + timedelta(seconds=1),
                paper_order_ledger=PaperOrderLedger(root / "paper.sqlite3"),
            )
            result = sidecar.evaluate(signal(quantity=2), snapshot(best_ask_quantity=5))
        self.assertEqual(result["state"], "PAPER_FILLED")
        self.assertEqual(result["reason"], "paper_ioc_filled")

    def test_signal_ledger_paper_transition_updates_result_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SignalLedger(root / "signals.sqlite3")
            sidecar = ExecutionSidecar(
                ledger, SECRET, mode="paper", policy=ExecutorPolicy(),
                clock=lambda: NOW + timedelta(seconds=1),
                paper_order_ledger=PaperOrderLedger(root / "paper.sqlite3"),
            )
            sidecar.evaluate(signal(), snapshot())
            updated = ledger.transition_paper(
                "SIG-1", "PAPER_CANCELED", "paper_order_expired_canceled",
                {"paper_lifecycle": {"state": "PAPER_CANCELED"}, "real_order_submitted": False},
            )
            restored = SignalLedger(root / "signals.sqlite3").get("SIG-1")
        self.assertEqual(updated["state"], "PAPER_CANCELED")
        self.assertEqual(restored["state"], "PAPER_CANCELED")
        self.assertFalse(restored["result"]["real_order_submitted"])

    def test_paper_ledger_first_commit_repairs_missing_signal_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper = PaperOrderLedger(root / "paper.sqlite3")
            signed = OrderSignal(**{
                **signal(quantity=2).unsigned(), "order_type": "LIMIT", "signature": "",
            }).sign(SECRET)
            lifecycle = paper.submit(signed)
            sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), SECRET, mode="paper",
                paper_order_ledger=paper, clock=lambda: NOW + timedelta(seconds=1),
            )
            recovered = sidecar.recover_paper_decision(signed, lifecycle)
            replayed = sidecar.recover_paper_decision(signed, lifecycle)
        self.assertEqual(recovered["state"], "PAPER_SUBMITTED")
        self.assertTrue(recovered["result"]["recovered_from_paper_ledger"])
        self.assertTrue(replayed["idempotent_replay"])

    def test_paper_recovery_reconciles_divergent_ledger_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper = PaperOrderLedger(root / "paper.sqlite3")
            signed = OrderSignal(**{
                **signal(quantity=2).unsigned(), "order_type": "LIMIT", "signature": "",
            }).sign(SECRET)
            sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), SECRET, mode="paper",
                paper_order_ledger=paper, clock=lambda: NOW + timedelta(seconds=1),
            )
            submitted = sidecar.evaluate(signed, snapshot(best_ask_quantity=0))
            self.assertEqual(submitted["state"], "PAPER_SUBMITTED")
            final = paper.apply_fill(signed.signal_id, "RECOVERY-FILL", 2, 100_000)
            recovered = sidecar.recover_paper_decision(signed, final)
            restored = sidecar.ledger.get(signed.signal_id)
        self.assertEqual(recovered["state"], "PAPER_FILLED")
        self.assertEqual(restored["state"], "PAPER_FILLED")
        self.assertTrue(restored["result"]["recovered_from_paper_ledger"])

    def test_paper_ledger_recovery_rejects_tampered_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sidecar = ExecutionSidecar(
                SignalLedger(root / "signals.sqlite3"), SECRET, mode="paper",
                paper_order_ledger=PaperOrderLedger(root / "paper.sqlite3"),
            )
            original = signal()
            tampered = OrderSignal(**{**original.unsigned(), "quantity": 2, "signature": original.signature})
            with self.assertRaisesRegex(ValueError, "paper_recovery_invalid_signature"):
                sidecar.recover_paper_decision(tampered, {"state": "PAPER_SUBMITTED"})


if __name__ == "__main__":
    unittest.main()
