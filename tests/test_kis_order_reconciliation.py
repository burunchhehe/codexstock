import unittest

from app.kis_order_reconciliation import (
    allocate_primary_executions,
    reconcile_account_ledger,
    reconcile_order_snapshots,
)


class KisOrderReconciliationTests(unittest.TestCase):
    def test_account_ledger_reconciles_new_buy_position(self) -> None:
        result = reconcile_account_ledger(
            {"order_no": "B-1", "symbol": "005930", "side": "BUY"},
            {"allocated_quantity": 2, "avg_price": 71000},
            {"available_cash": 200000, "positions": []},
            {
                "available_cash": 58000,
                "positions": [{"symbol": "005930", "quantity": 2, "avg_price": 71000}],
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "matched")
        self.assertTrue(result["position"]["quantity_matched"])
        self.assertTrue(result["official_trade_eligible"])
        self.assertFalse(result["official_performance_eligible"])

    def test_account_ledger_reconciles_sell_and_derives_net_pnl(self) -> None:
        result = reconcile_account_ledger(
            {"order_no": "S-1", "symbol": "001440", "side": "SELL"},
            {"allocated_quantity": 3, "avg_price": 29050},
            {
                "current": {
                    "available_cash": 211096,
                    "positions": [{"symbol": "001440", "quantity": 3, "avg_price": 29550}],
                }
            },
            {"available_cash": 297635, "positions": []},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["cash"]["actual_delta"], 86539)
        self.assertEqual(result["realized_pnl"]["transaction_cost_and_tax"], 611)
        self.assertEqual(result["realized_pnl"]["net_realized_pnl"], -2111)
        self.assertTrue(result["official_performance_eligible"])
        self.assertTrue(result["learning_eligible"])

    def test_account_ledger_checks_weighted_average_on_added_buy(self) -> None:
        result = reconcile_account_ledger(
            {"symbol": "005930", "side": "BUY"},
            {"allocated_quantity": 1, "avg_price": 73000},
            {"available_cash": 200000, "positions": [{"symbol": "005930", "quantity": 1, "avg_price": 71000}]},
            {"available_cash": 127000, "positions": [{"symbol": "005930", "quantity": 2, "avg_price": 72000}]},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["average_price"]["expected_after"], 72000)

    def test_account_ledger_position_contradiction_hard_blocks(self) -> None:
        result = reconcile_account_ledger(
            {"symbol": "005930", "side": "BUY"},
            {"allocated_quantity": 2, "avg_price": 71000},
            {"available_cash": 200000, "positions": []},
            {"available_cash": 58000, "positions": [{"symbol": "005930", "quantity": 1, "avg_price": 71000}]},
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result["hard_block"])
        self.assertFalse(result["next_order_allowed"])
        self.assertEqual(result["mismatches"][0]["field"], "position_quantity")

    def test_account_ledger_missing_post_snapshot_is_quarantined(self) -> None:
        result = reconcile_account_ledger(
            {"symbol": "005930", "side": "BUY"},
            {"allocated_quantity": 1, "avg_price": 71000},
            {"available_cash": 100000, "positions": []},
            None,
        )
        self.assertEqual(result["status"], "incomplete_evidence")
        self.assertFalse(result["official_trade_eligible"])
        self.assertFalse(result["learning_eligible"])

    def test_primary_allocation_never_cross_matches_different_order_numbers(self) -> None:
        result = allocate_primary_executions(
            [{"date": "2026-07-14", "order_no": "A-1", "symbol": "005930", "side": "BUY", "quantity": 2}],
            [{"date": "2026-07-14", "order_no": "A-2", "symbol": "005930", "side": "BUY", "quantity": 2, "price": 71000}],
        )
        self.assertEqual(result["allocations"][0]["allocated_quantity"], 0)
        self.assertEqual(result["order_number_mismatch_count"], 1)
        self.assertEqual(result["remaining_executions"][0]["remaining_quantity"], 2)

    def test_primary_allocation_matches_exact_order_before_same_symbol_fills(self) -> None:
        result = allocate_primary_executions(
            [{"date": "2026-07-14", "order_no": "A-1", "symbol": "005930", "side": "BUY", "quantity": 1}],
            [
                {"date": "2026-07-14", "order_no": "A-2", "symbol": "005930", "side": "BUY", "quantity": 1, "price": 72000},
                {"date": "2026-07-14", "order_no": "A-1", "symbol": "005930", "side": "BUY", "quantity": 1, "price": 71000},
            ],
        )
        allocation = result["allocations"][0]
        self.assertEqual(allocation["allocated_quantity"], 1)
        self.assertEqual(allocation["avg_price"], 71000)
        self.assertEqual(allocation["matching_basis"], "order_no")
        self.assertEqual(result["remaining_executions"][0]["order_no"], "A-2")

    def test_legacy_fallback_requires_both_sides_to_lack_order_number(self) -> None:
        result = allocate_primary_executions(
            [{"date": "2026-07-14", "symbol": "005930", "side": "BUY", "quantity": 1}],
            [{"date": "2026-07-14", "symbol": "005930", "side": "BUY", "quantity": 1, "price": 70000}],
        )
        self.assertEqual(result["allocations"][0]["allocated_quantity"], 1)
        self.assertEqual(result["allocations"][0]["matching_basis"], "legacy_unnumbered_fallback")

    def test_disconnected_secondary_uses_primary_fallback_without_false_match(self) -> None:
        result = reconcile_order_snapshots(
            [{"order_no": "101", "symbol": "005930", "side": "BUY", "quantity": 1}],
            None,
            secondary_connected=False,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "primary_only_fallback")
        self.assertFalse(result["hard_block"])

    def test_matching_independent_snapshot_allows_next_order(self) -> None:
        primary = [{"order_no": "101", "symbol": "005930", "side": "BUY", "ordered_qty": 2, "filled_qty": 2, "avg_price": 71000}]
        secondary = [{"ODNO": "101", "PDNO": "005930", "side": "BUY", "quantity": 2, "broker_quantity": 2, "price": 71000}]
        result = reconcile_order_snapshots(primary, secondary, secondary_connected=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "matched")
        self.assertTrue(result["next_order_allowed"])

    def test_quantity_or_price_mismatch_hard_blocks_followup_order(self) -> None:
        primary = [{"order_no": "101", "symbol": "005930", "side": "BUY", "ordered_qty": 2, "filled_qty": 2, "avg_price": 71000}]
        secondary = [{"order_no": "101", "symbol": "005930", "side": "BUY", "ordered_qty": 2, "filled_qty": 1, "avg_price": 71100}]
        result = reconcile_order_snapshots(primary, secondary, secondary_connected=True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["hard_block"])
        self.assertFalse(result["next_order_allowed"])
        self.assertEqual({row["field"] for row in result["mismatches"]}, {"filled_qty", "avg_price"})

    def test_connected_secondary_without_snapshot_blocks_after_primary_order(self) -> None:
        result = reconcile_order_snapshots(
            [{"order_no": "101", "symbol": "005930", "side": "BUY", "quantity": 1}],
            None,
            secondary_connected=True,
        )
        self.assertEqual(result["status"], "secondary_snapshot_pending")
        self.assertTrue(result["hard_block"])


if __name__ == "__main__":
    unittest.main()
