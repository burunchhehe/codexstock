import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations import KisReadonlyBridge
from app import stock_suite_app as suite


class MarketSupplyMissAuditTests(unittest.TestCase):
    def test_kis_investor_trend_maps_three_investor_groups(self):
        bridge = object.__new__(KisReadonlyBridge)
        bridge.settings = SimpleNamespace(kis_configured=True)
        bridge._get = lambda *args, **kwargs: {
            "rt_cd": "0",
            "msg1": "정상",
            "output": [
                {
                    "stck_bsop_date": "20260714",
                    "stck_clpr": "80000",
                    "prsn_ntby_qty": "-100",
                    "frgn_ntby_qty": "60",
                    "orgn_ntby_qty": "40",
                    "prsn_ntby_tr_pbmn": "-8000000",
                    "frgn_ntby_tr_pbmn": "4800000",
                    "orgn_ntby_tr_pbmn": "3200000",
                }
            ],
        }

        result = bridge.investor_trend("005930")

        self.assertTrue(result["ok"])
        self.assertEqual(result["latest"]["date"], "2026-07-14")
        self.assertEqual(result["latest"]["personal_net_qty"], -100)
        self.assertEqual(result["latest"]["foreign_net_qty"], 60)
        self.assertEqual(result["latest"]["institution_net_qty"], 40)
        self.assertEqual(result["latest"]["foreign_net_amount"], 4_800_000_000_000)
        self.assertEqual(result["latest"]["provider_amount_unit"], "million_KRW")

    @patch.object(suite.INTEGRATIONS, "kis_foreign_institution_rank")
    @patch.object(suite.INTEGRATIONS, "kis_investor_trend")
    def test_supply_audit_keeps_personal_rank_scope_explicit(self, investor_trend, investor_rank):
        investor_trend.side_effect = lambda symbol: {
            "ok": True,
            "source": "test",
            "latest": {
                "date": "2026-07-14",
                "personal_net_amount": 200 if symbol == "000001" else 100,
                "foreign_net_amount": 50,
                "institution_net_amount": -10,
            },
        }
        investor_rank.return_value = {"ok": True, "items": [{"symbol": "000001"}], "message": "정상"}
        rows = [
            {"symbol": "000001", "name": "A", "amount": 1_000, "volume": 100, "change_pct": 5},
            {"symbol": "000002", "name": "B", "amount": 900, "volume": 90, "change_pct": -3},
        ]

        audit = suite._build_market_supply_audit(rows, rows, rows, rows, "2026-07-14")

        self.assertTrue(audit["ok"])
        self.assertEqual(audit["personal_net_buy_top_in_opportunity_pool"][0]["symbol"], "000001")
        self.assertIn("기회군 내부 순위", audit["contract"])

    def test_intraday_detection_classifies_never_seen_as_search_miss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "radar.jsonl"
            path.write_text('', encoding="utf-8")
            with patch.object(suite, "INTRADAY_MINUTE_RADAR_FILE", path):
                result = suite._intraday_detection_evidence("005930", "2026-07-14")

        self.assertFalse(result["seen"])
        self.assertEqual(result["root_cause"], "탐색 누락")

    def test_no_trade_streak_escalates_without_forcing_order(self):
        rows = [{"status": "LIVE_SUBMITTED", "created_at": "2026-07-08T10:00:00+09:00"}]
        with patch.object(suite, "_read_jsonl", return_value=rows):
            audit = suite.build_no_trade_streak_audit("2026-07-13")

        self.assertEqual(audit["consecutive_no_trade_weekdays"], 3)
        self.assertEqual(audit["level"], "critical")
        self.assertTrue(audit["candidate_obligation"]["enabled"])
        self.assertFalse(audit["forced_order"])


if __name__ == "__main__":
    unittest.main()
