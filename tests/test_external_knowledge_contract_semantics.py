import unittest

from app.external_knowledge.schema import (
    STAGE2_COST_POLICY_VERSION,
    market_specific_stage2_cost_model,
    package_status_semantics,
)


class ExternalKnowledgeContractSemanticsTests(unittest.TestCase):
    def test_backtest_ready_is_only_schema_validated(self):
        semantics = package_status_semantics("BACKTEST_READY")

        self.assertEqual("SCHEMA_VALIDATED", semantics["evidence_stage"])
        self.assertFalse(semantics["profitability_verified"])
        self.assertFalse(semantics["paper_eligible"])
        self.assertFalse(semantics["live_promotion_eligible"])

    def test_market_specific_stage2_costs_separate_kr_and_us(self):
        model = market_specific_stage2_cost_model("MIXED")

        self.assertEqual(STAGE2_COST_POLICY_VERSION, model["model_id"])
        self.assertTrue(model["mixed_market_requires_per_trade_profile"])
        self.assertEqual(18.0, model["market_profiles"]["KR"]["sell_tax_bps"])
        self.assertEqual(0.0, model["market_profiles"]["US"]["sell_tax_bps"])
        self.assertEqual(
            0.000195,
            model["market_profiles"]["US"]["finra_taf_2026_per_share_usd"],
        )
        self.assertEqual(
            10.0,
            model["market_profiles"]["US"]["fx_conversion_spread_bps_per_side"],
        )


if __name__ == "__main__":
    unittest.main()
