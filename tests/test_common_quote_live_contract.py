import unittest
from unittest.mock import patch

import app.stock_suite_app as stock_app


class CommonQuoteLiveContractTests(unittest.TestCase):
    @staticmethod
    def _trusted_quote() -> dict[str, object]:
        return {
            "ok": True,
            "symbol": "005930",
            "name": "Samsung Electronics",
            "market": "KR",
            "currency": "KRW",
            "unit_scale": 1,
            "price": 259000,
            "previous_close": 244000,
            "open": 249000,
            "high": 262000,
            "low": 247000,
            "change_pct": 6.15,
            "upper_limit_price": 317000,
            "lower_limit_price": 171000,
            "source": "kis_readonly",
            "updated_at": "2026-07-21T12:00:00+09:00",
            "verified_quote_age_seconds": 0.0,
        }

    def test_provided_trusted_quote_becomes_single_official_contract_without_refetch(self):
        with patch("app.stock_suite_app.ops_quote", side_effect=AssertionError("unexpected refetch")):
            snapshot = stock_app.build_common_quote_snapshot(
                symbols=["005930"],
                prefer_live=True,
                allow_coherence_live_refresh=False,
                quote_overrides={"005930": self._trusted_quote()},
            )

        contract = stock_app._common_quote_contract_from_snapshot("005930", snapshot)

        self.assertEqual("provided", snapshot["quote_input_mode"])
        self.assertEqual(259000, snapshot["marks"]["005930"])
        self.assertTrue(contract["ok"])
        self.assertTrue(contract["official_mark_eligible"])
        self.assertEqual("KRW", contract["currency"])
        self.assertEqual(1, contract["unit_scale"])
        self.assertEqual(259000, contract["price"])
        self.assertFalse(contract["blockers"])

    def test_untrusted_quote_cannot_be_used_for_sizing_or_live_candidate(self):
        quote = self._trusted_quote()
        quote.update({"source": "MARKET_CACHE", "verified_quote_age_seconds": 0.0})

        snapshot = stock_app.build_common_quote_snapshot(
            symbols=["005930"],
            prefer_live=True,
            allow_coherence_live_refresh=False,
            quote_overrides={"005930": quote},
        )
        contract = stock_app._common_quote_contract_from_snapshot("005930", snapshot)

        self.assertNotIn("005930", snapshot["marks"])
        self.assertFalse(contract["ok"])
        self.assertFalse(contract["live_order_allowed"])
        self.assertIn("official_mark_not_eligible", contract["blockers"])
        self.assertIn("official_quote_price_missing", contract["blockers"])

    def test_snapshot_hash_tampering_blocks_live_contract(self):
        snapshot = stock_app.build_common_quote_snapshot(
            symbols=["005930"],
            prefer_live=True,
            allow_coherence_live_refresh=False,
            quote_overrides={"005930": self._trusted_quote()},
        )
        snapshot["rows"][0]["price"] = 1

        contract = stock_app._common_quote_contract_from_snapshot("005930", snapshot)

        self.assertFalse(contract["ok"])
        self.assertIn("snapshot_hash_mismatch", contract["blockers"])


if __name__ == "__main__":
    unittest.main()
