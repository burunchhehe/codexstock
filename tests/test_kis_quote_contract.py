import unittest

from app.integrations import _kis_previous_close, _kis_quote_contract_issues


class KisQuoteContractTests(unittest.TestCase):
    def test_stock_standard_price_is_primary_previous_close(self):
        output = {
            "stck_sdpr": "244000",
            "prdy_clpr": "0",
            "prdy_vrss": "15000",
            "prdy_ctrt": "6.15",
        }

        self.assertEqual(244_000, _kis_previous_close(output, 259_000))

    def test_signed_change_is_used_only_as_bounded_fallback(self):
        output = {"prdy_vrss": "-19000", "prdy_ctrt": "-5.30"}

        self.assertEqual(358_000, _kis_previous_close(output, 339_000))

    def test_consistent_official_price_bundle_passes(self):
        output = {
            "stck_sdpr": "244000",
            "stck_hgpr": "263500",
            "stck_lwpr": "243000",
            "stck_mxpr": "317000",
            "stck_llam": "171000",
            "prdy_ctrt": "6.15",
        }

        issues = _kis_quote_contract_issues(output, price=259_000, previous_close=244_000)

        self.assertEqual([], issues)

    def test_current_price_copied_as_previous_close_is_rejected(self):
        output = {
            "stck_hgpr": "263500",
            "stck_lwpr": "243000",
            "stck_mxpr": "317000",
            "stck_llam": "171000",
            "prdy_ctrt": "6.15",
        }

        issues = _kis_quote_contract_issues(output, price=259_000, previous_close=259_000)

        self.assertIn("change_pct_inconsistent", issues)


if __name__ == "__main__":
    unittest.main()
