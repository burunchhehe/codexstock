import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.stock_suite_app as stock_app
from stock_suite.trade_lifecycle_ledger import TradeLifecycleLedger, trade_correlation_id


class TradeLifecycleLedgerTests(unittest.TestCase):
    def ledger(self, directory: str) -> TradeLifecycleLedger:
        return TradeLifecycleLedger(Path(directory) / "lifecycle.sqlite3")

    def append(self, ledger, correlation, event_id, stage, quantity=1):
        return ledger.append_event(
            correlation_id=correlation,
            event_id=event_id,
            stage=stage,
            occurred_at="2026-07-20T09:00:00+09:00",
            payload={"quantity": quantity},
        )

    def test_complete_lifecycle_is_performance_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            correlation = trade_correlation_id(ticket_id="ticket-1")
            for event_id, stage in (
                ("candidate-1", "CANDIDATE"),
                ("order-1", "ORDER_SUBMITTED"),
                ("fill-1", "FILL"),
                ("balance-1", "BALANCE"),
                ("pnl-1", "PNL"),
            ):
                self.append(ledger, correlation, event_id, stage)
            audit = ledger.reconcile(correlation)
        self.assertTrue(audit["complete"])
        self.assertTrue(audit["official_performance_eligible"])
        self.assertEqual(audit["issues"], [])

    def test_exact_replay_is_idempotent_but_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            correlation = trade_correlation_id(order_no="order-1")
            first = self.append(ledger, correlation, "event-1", "CANDIDATE")
            replay = self.append(ledger, correlation, "event-1", "CANDIDATE")
            with self.assertRaisesRegex(ValueError, "mutation_rejected"):
                self.append(ledger, correlation, "event-1", "CANDIDATE", quantity=2)
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])

    def test_orphan_fill_and_overfill_are_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            orphan = trade_correlation_id(fallback="orphan")
            self.append(ledger, orphan, "fill-orphan", "FILL", quantity=2)
            orphan_audit = ledger.reconcile(orphan)
            overfill = trade_correlation_id(fallback="overfill")
            self.append(ledger, overfill, "candidate", "CANDIDATE", quantity=1)
            self.append(ledger, overfill, "order", "ORDER_SUBMITTED", quantity=1)
            self.append(ledger, overfill, "fill", "FILL", quantity=2)
            overfill_audit = ledger.reconcile(overfill)
        self.assertIn("fill_without_order", orphan_audit["issues"])
        self.assertIn("filled_quantity_exceeds_submitted_quantity", orphan_audit["issues"])
        self.assertIn("filled_quantity_exceeds_submitted_quantity", overfill_audit["issues"])
        self.assertTrue(overfill_audit["quarantined"])

    def test_fill_requires_post_fill_balance_and_pnl_requires_fill(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            correlation = trade_correlation_id(fallback="missing-balance")
            self.append(ledger, correlation, "candidate", "CANDIDATE")
            self.append(ledger, correlation, "order", "ORDER_SUBMITTED")
            self.append(ledger, correlation, "fill", "FILL")
            fill_audit = ledger.reconcile(correlation)
            pnl_only = trade_correlation_id(fallback="pnl-only")
            self.append(ledger, pnl_only, "pnl", "PNL")
            pnl_audit = ledger.reconcile(pnl_only)
        self.assertIn("post_fill_balance_missing", fill_audit["issues"])
        self.assertIn("pnl_without_fill", pnl_audit["issues"])

    def test_app_state_machine_persists_complete_unified_lifecycle(self):
        ticket = {
            "id": "ticket-1",
            "mode": "live_candidate",
            "approval_token": "token-1",
            "symbol": "005930",
            "side": "SELL",
            "quantity": 1,
            "price": 100,
            "created_at": "2026-07-20T09:00:00+09:00",
        }
        submit = {
            "status": "LIVE_SUBMITTED",
            "approval_token": "token-1",
            "ticket": ticket,
            "created_at": "2026-07-20T09:01:00+09:00",
            "kis_submit": {"order_no": "order-1"},
        }
        account = {
            "status": "matched",
            "post_snapshot_at": "2026-07-20T09:02:00+09:00",
            "position": {"before_quantity": 1, "after_quantity": 0},
            "cash": {"actual_delta": 110},
            "realized_pnl": {
                "eligible": True,
                "net_realized_pnl": 10,
                "net_realized_pnl_pct": 10,
                "source": "test-broker-evidence",
            },
        }
        reconciliation = {
            "status": "ready",
            "matched": [{
                "date": "2026-07-20",
                "order_no": "order-1",
                "symbol": "005930",
                "side": "SELL",
                "broker_quantity": 1,
                "avg_price": 110,
                "matching_basis": "order_number",
                "created_at": "2026-07-20T09:02:00+09:00",
                "account_ledger_reconciliation": account,
            }],
            "partial": [],
            "pending": [],
            "active_broker_without_local_submit_count": 0,
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "lifecycle.sqlite3"
            with (
                patch.object(stock_app, "TRADE_LIFECYCLE_LEDGER_FILE", ledger_path),
                patch.object(stock_app.OPS, "tickets", return_value=[ticket]),
                patch.object(stock_app.OPS, "approvals", return_value=[]),
                patch.object(stock_app.OPS, "live_dry_submits", return_value=[]),
                patch.object(stock_app, "_read_jsonl", return_value=[submit]),
                patch.object(stock_app, "build_live_reconciliation_audit", return_value=reconciliation),
                patch.object(stock_app, "_append_jsonl"),
                patch.object(stock_app, "_compact_jsonl"),
            ):
                result = stock_app.build_live_order_state_machine(persist=True)
            lifecycle = result["workflows"][0]["trade_lifecycle"]
        self.assertTrue(lifecycle["complete"])
        self.assertTrue(lifecycle["official_performance_eligible"])
        self.assertEqual(lifecycle["event_count"], 5)


if __name__ == "__main__":
    unittest.main()
