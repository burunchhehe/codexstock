import tempfile
import unittest
from pathlib import Path

from stock_suite.position_exit_policy import PositionExitLedger, build_exit_plan


class PositionExitPolicyTests(unittest.TestCase):
    def test_first_profit_target_is_partial_and_plan_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PositionExitLedger(Path(directory) / "exit.sqlite3")
            state = ledger.observe("005930:100000", 10, 3.2)
            first = build_exit_plan(
                position_key="005930:100000", available_quantity=10, pnl_pct=3.2,
                stop_loss_pct=2, take_profit_pct=3, state=state,
            )
            replay = build_exit_plan(
                position_key="005930:100000", available_quantity=10, pnl_pct=3.4,
                stop_loss_pct=2, take_profit_pct=3, state=ledger.observe("005930:100000", 10, 3.4),
            )
        self.assertEqual(first["urgency"], "profit_partial")
        self.assertEqual(first["recommended_exit_quantity"], 5)
        self.assertEqual(first["plan_id"], replay["plan_id"])

    def test_broker_quantity_drop_advances_stage_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exit.sqlite3"
            PositionExitLedger(path).observe("005930:100000", 10, 3.5)
            state = PositionExitLedger(path).observe("005930:100000", 5, 3.1)
        self.assertEqual(state["partial_stage"], 1)
        self.assertEqual(state["original_quantity"], 10)

    def test_post_partial_high_watermark_trailing_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PositionExitLedger(Path(directory) / "exit.sqlite3")
            ledger.observe("005930:100000", 10, 5.0)
            state = ledger.observe("005930:100000", 5, 3.8)
            plan = build_exit_plan(
                position_key="005930:100000", available_quantity=5, pnl_pct=3.8,
                stop_loss_pct=2, take_profit_pct=3, state=state, trailing_drawdown_pct=1,
            )
        self.assertEqual(plan["urgency"], "profit_trailing")
        self.assertEqual(plan["recommended_exit_quantity"], 5)

    def test_hard_stop_and_intraday_close_are_full_exit(self):
        state = {"partial_stage": 0, "high_watermark_pct": 0}
        stop = build_exit_plan(
            position_key="A", available_quantity=7, pnl_pct=-2.1,
            stop_loss_pct=2, take_profit_pct=3, state=state,
        )
        close = build_exit_plan(
            position_key="B", available_quantity=7, pnl_pct=0.2,
            stop_loss_pct=2, take_profit_pct=3, state=state, intraday_close=True,
        )
        self.assertEqual(stop["recommended_exit_quantity"], 7)
        self.assertEqual(close["recommended_exit_quantity"], 7)


if __name__ == "__main__":
    unittest.main()
