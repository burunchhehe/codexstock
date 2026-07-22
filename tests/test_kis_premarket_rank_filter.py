from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from app.integrations import KisReadonlyBridge


class KisPremarketRankFilterTests(unittest.TestCase):
    @staticmethod
    def _bridge(payload):
        bridge = object.__new__(KisReadonlyBridge)
        bridge.settings = SimpleNamespace(kis_configured=True, kis_mode="mock")
        bridge._get = Mock(return_value=payload)
        return bridge

    @staticmethod
    def _row(symbol="000020", *, volume="0", amount="0", change="0", change_pct="0"):
        return {
            "data_rank": "1",
            "mksc_shrn_iscd": symbol,
            "stck_shrn_iscd": symbol,
            "hts_kor_isnm": "테스트종목",
            "stck_prpr": "5740",
            "acml_vol": volume,
            "acml_tr_pbmn": amount,
            "prdy_vrss": change,
            "prdy_ctrt": change_pct,
        }

    def test_volume_rank_filters_zero_activity_placeholder_rows(self):
        bridge = self._bridge({"rt_cd": "0", "msg1": "정상처리", "output": [self._row()]})

        result = bridge.volume_rank()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "no_active_market_data")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["raw_count"], 1)
        self.assertEqual(result["filtered_zero_activity_count"], 1)
        self.assertIn("장전", result["message"])

    def test_volume_rank_keeps_rows_with_real_turnover(self):
        active = self._row(volume="120000", amount="900000000", change="10", change_pct="0.2")
        bridge = self._bridge({"rt_cd": "0", "msg1": "정상처리", "output": [self._row(), active]})

        result = bridge.volume_rank()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["filtered_zero_activity_count"], 1)

    def test_fluctuation_rank_filters_zero_activity_placeholder_rows(self):
        bridge = self._bridge({"rt_cd": "0", "msg1": "정상처리", "output": [self._row()]})

        result = bridge.fluctuation_rank()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "no_active_market_data")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["filtered_zero_activity_count"], 1)
        self.assertIn("장전", result["message"])

    def test_fluctuation_rank_keeps_rows_with_market_activity(self):
        active = self._row(volume="50000", amount="300000000", change="200", change_pct="3.6")
        bridge = self._bridge({"rt_cd": "0", "msg1": "정상처리", "output": [active]})

        result = bridge.fluctuation_rank(direction="up")

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["items"][0]["change_pct"], 3.6)


if __name__ == "__main__":
    unittest.main()
