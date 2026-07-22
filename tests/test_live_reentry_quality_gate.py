import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app import stock_suite_app as suite


class LiveReentryQualityGateTests(unittest.TestCase):
    def test_medium_context_is_blocked_for_automated_live_buy(self):
        snapshot = {
            "quality": {
                "level": "medium",
                "gaps": ["news missing"],
                "message": "news missing",
            }
        }

        manual = suite.live_context_snapshot_gate(snapshot)
        automated = suite.live_context_snapshot_gate(snapshot, require_high_quality=True)

        self.assertEqual("warning", manual["status"])
        self.assertEqual("blocked", automated["status"])

    def test_same_symbol_buy_is_blocked_during_post_sell_cooldown(self):
        now = datetime(2026, 7, 22, 14, 43, tzinfo=ZoneInfo("Asia/Seoul"))
        rows = [
            {
                "id": "sell-1",
                "status": "LIVE_SUBMITTED",
                "created_at": "2026-07-22T13:44:00+09:00",
                "ticket": {"symbol": "006360", "side": "SELL"},
            }
        ]

        guard = suite._live_buy_reentry_cooldown_guard(
            "006360",
            "BUY",
            {"delegated_live_reentry_cooldown_minutes": 90},
            now=now,
            submitted_rows=rows,
        )

        self.assertFalse(guard["ok"])
        self.assertEqual("COOLDOWN_ACTIVE", guard["state"])
        self.assertEqual(31 * 60, guard["remaining_seconds"])

    def test_reentry_is_ready_after_cooldown(self):
        now = datetime(2026, 7, 22, 15, 15, tzinfo=ZoneInfo("Asia/Seoul"))
        rows = [
            {
                "created_at": "2026-07-22T13:44:00+09:00",
                "symbol": "006360",
                "side": "SELL",
            }
        ]

        guard = suite._live_buy_reentry_cooldown_guard(
            "006360",
            "BUY",
            {"delegated_live_reentry_cooldown_minutes": 90},
            now=now,
            submitted_rows=rows,
        )

        self.assertTrue(guard["ok"])
        self.assertEqual("READY", guard["state"])


if __name__ == "__main__":
    unittest.main()
