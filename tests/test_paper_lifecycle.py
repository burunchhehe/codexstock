import tempfile
import unittest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_suite.execution_sidecar import MarketSnapshot, OrderSignal
from stock_suite.paper_lifecycle import PaperOrderLedger, _hash


def signal(quantity=3, order_type="IOC_LIMIT", now=None):
    now = now or datetime.now(timezone.utc)
    return OrderSignal(
        signal_id="PAPER-1", created_at=now.isoformat(), expires_at=(now + timedelta(minutes=1)).isoformat(),
        symbol="005930", side="BUY", quantity=quantity, order_type=order_type,
        reference_price=100_000, max_price=100_300, stop_loss_pct=-2, take_profit_pct=3,
        strategy_id="paper-test", evidence_hash="a" * 64,
    )


def snapshot(now, ask_quantity=1, **changes):
    values = dict(
        observed_at=now.isoformat(), current_price=100_000, ask_price=100_000, bid_price=99_900,
        account_ok=True, available_cash=1_000_000, equity=10_000_000, total_exposure=0,
        symbol_exposure=0, daily_loss_pct=0, daily_order_count=0,
        best_ask_quantity=ask_quantity, best_bid_quantity=ask_quantity,
    )
    values.update(changes)
    return MarketSnapshot(**values)


class PaperOrderLedgerTests(unittest.TestCase):
    def test_ioc_buy_above_signed_max_price_is_canceled_unfilled(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            result = ledger.match_ioc(
                signal(quantity=1),
                snapshot(datetime.now(timezone.utc), ask_quantity=5, ask_price=100_400),
            )
        self.assertEqual(result["state"], "PAPER_CANCELED")
        self.assertEqual(result["filled_quantity"], 0)
        self.assertEqual(result["match_reason"], "paper_ioc_price_guard_canceled")

    def test_ioc_sell_below_signed_min_price_is_canceled_unfilled(self):
        now = datetime.now(timezone.utc)
        sell = OrderSignal(**{
            **signal(quantity=1, now=now).unsigned(),
            "side": "SELL", "min_price": 99_600, "signature": "",
        })
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            result = ledger.match_ioc(
                sell, snapshot(now, ask_quantity=5, bid_price=99_500),
            )
        self.assertEqual(result["state"], "PAPER_CANCELED")
        self.assertEqual(result["filled_quantity"], 0)
        self.assertEqual(result["match_reason"], "paper_ioc_price_guard_canceled")

    def test_partial_then_full_fill_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            ledger = PaperOrderLedger(path)
            self.assertEqual(ledger.submit(signal())["state"], "PAPER_SUBMITTED")
            partial = ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            self.assertEqual(partial["state"], "PAPER_PARTIALLY_FILLED")
            self.assertEqual(partial["remaining_quantity"], 2)
            restarted = PaperOrderLedger(path)
            filled = restarted.apply_fill("PAPER-1", "FILL-2", 2, 100_300)
            self.assertEqual(filled["state"], "PAPER_FILLED")
            self.assertEqual(filled["filled_quantity"], 3)
            self.assertAlmostEqual(filled["average_fill_price"], 100_200)

    def test_duplicate_fill_is_idempotent_and_changed_payload_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            replay = ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            self.assertTrue(replay["idempotent_replay"])
            self.assertEqual(replay["filled_quantity"], 1)
            with self.assertRaisesRegex(ValueError, "payload_mismatch"):
                ledger.apply_fill("PAPER-1", "FILL-1", 2, 100_000)

    def test_overfill_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal(quantity=1))
            with self.assertRaisesRegex(ValueError, "overfill"):
                ledger.apply_fill("PAPER-1", "FILL-1", 2, 100_000)

    def test_partial_order_can_be_canceled(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            self.assertEqual(ledger.request_cancel("PAPER-1", "CANCEL-1")["state"], "PAPER_CANCEL_PENDING")
            canceled = ledger.confirm_cancel("PAPER-1", "CANCEL-2")
            self.assertEqual(canceled["state"], "PAPER_CANCELED")
            self.assertEqual(canceled["remaining_quantity"], 2)
            self.assertTrue(ledger.reconcile()["ok"])

    def test_cancel_confirmation_requires_pending_request(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            with self.assertRaisesRegex(ValueError, "without_pending_request"):
                ledger.confirm_cancel("PAPER-1", "CANCEL-1")
            current = ledger.get("PAPER-1")
        self.assertEqual(current["state"], "PAPER_SUBMITTED")

    def test_duplicate_cancel_request_is_idempotent_but_new_request_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            ledger.request_cancel("PAPER-1", "CANCEL-1")
            replay = ledger.request_cancel("PAPER-1", "CANCEL-1")
            self.assertTrue(replay["idempotent_replay"])
            with self.assertRaisesRegex(ValueError, "invalid_state"):
                ledger.request_cancel("PAPER-1", "CANCEL-2")

    def test_reconciliation_detects_corrupted_quantity(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            with ledger.connect() as db:
                db.execute("UPDATE paper_orders SET remaining_quantity=99 WHERE signal_id='PAPER-1'")
            audit = ledger.reconcile()
        self.assertFalse(audit["ok"])
        self.assertIn("quantity_conservation_failed", audit["errors"][0]["errors"])

    def test_reconciliation_rejects_unknown_state(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            with ledger.connect() as db:
                db.execute("UPDATE paper_orders SET state='PAPER_IMPOSSIBLE' WHERE signal_id='PAPER-1'")
            audit = ledger.reconcile()
        self.assertFalse(audit["ok"])
        self.assertIn("unknown_paper_state", audit["errors"][0]["errors"])

    def test_reconciliation_requires_cancel_event_for_canceled_state(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            with ledger.connect() as db:
                db.execute("UPDATE paper_orders SET state='PAPER_CANCELED' WHERE signal_id='PAPER-1'")
            audit = ledger.reconcile()
        self.assertFalse(audit["ok"])
        self.assertIn("canceled_state_without_event", audit["errors"][0]["errors"])

    def test_reconciliation_detects_corrupt_fill_event_json(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            with ledger.connect() as db:
                db.execute("UPDATE paper_order_events SET payload_json='{' WHERE event_id='FILL-1'")
            audit = ledger.reconcile()
        self.assertFalse(audit["ok"])
        self.assertIn("invalid_event_payload", audit["errors"][0]["errors"])

    def test_reconciliation_detects_event_payload_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            ledger.apply_fill("PAPER-1", "FILL-1", 1, 100_000)
            with ledger.connect() as db:
                db.execute(
                    "UPDATE paper_order_events SET payload_json=? WHERE event_id='FILL-1'",
                    (json.dumps({"quantity": 1, "price": 100_100}),),
                )
            audit = ledger.reconcile()
        self.assertFalse(audit["ok"])
        self.assertIn("event_payload_hash_mismatch", audit["errors"][0]["errors"])

    def test_reconciliation_rejects_unknown_event_type(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            ledger.submit(signal())
            with ledger.connect() as db:
                now = datetime.now(timezone.utc).isoformat()
                payload = {"state": "PAPER_SUBMITTED"}
                db.execute(
                    "INSERT INTO paper_order_events VALUES(?,?,?,?,?,?)",
                    ("UNKNOWN-1", "PAPER-1", "MYSTERY", _hash(payload), json.dumps(payload), now),
                )
            audit = ledger.reconcile()
        self.assertFalse(audit["ok"])
        self.assertIn("unknown_paper_event_type", audit["errors"][0]["errors"])

    def test_open_signal_and_partial_fill_recover_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            now = datetime.now(timezone.utc)
            PaperOrderLedger(path).submit(signal(order_type="LIMIT", now=now))
            restarted = PaperOrderLedger(path)
            recovered = restarted.recover_open_signals()
            self.assertEqual(len(recovered), 1)
            restored_signal, _ = recovered[0]
            self.assertEqual(restored_signal.signal_id, "PAPER-1")
            partial = restarted.advance_resting_order(restored_signal, snapshot(now, ask_quantity=1), now=now)
            self.assertEqual(partial["state"], "PAPER_PARTIALLY_FILLED")
            self.assertEqual(partial["remaining_quantity"], 2)

    def test_resting_order_is_canceled_at_expiry_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            now = datetime.now(timezone.utc)
            PaperOrderLedger(path).submit(signal(order_type="LIMIT", now=now))
            restarted = PaperOrderLedger(path)
            restored_signal, _ = restarted.recover_open_signals()[0]
            canceled = restarted.advance_resting_order(
                restored_signal, snapshot(now + timedelta(minutes=2)), now=now + timedelta(minutes=2)
            )
            self.assertEqual(canceled["state"], "PAPER_CANCELED")
            self.assertEqual(canceled["match_reason"], "paper_order_expired_canceled")

    def test_all_signals_include_final_orders_for_two_ledger_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperOrderLedger(Path(directory) / "paper.sqlite3")
            now = datetime.now(timezone.utc)
            signed = signal(order_type="IOC_LIMIT", quantity=1, now=now)
            ledger.submit(signed)
            ledger.match_ioc(signed, snapshot(now, ask_quantity=1))
            recovered = ledger.recover_all_signals()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0][0].signal_id, signed.signal_id)
        self.assertEqual(recovered[0][1]["state"], "PAPER_FILLED")


if __name__ == "__main__":
    unittest.main()
