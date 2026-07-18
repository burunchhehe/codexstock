import copy
import unittest
from unittest.mock import patch

from app.stock_suite_app import (
    _ai_tournament_walk_forward_validation,
    _attach_ai_tournament_walk_forward_validations,
)


def _replay(cost_profile: dict[str, float] | None = None) -> dict[str, object]:
    profile = cost_profile or {
        "commission_bps": 2.0,
        "slippage_bps": 7.0,
        "kr_sell_tax_bps": 20.0,
        "fx_conversion_spread_bps": 10.0,
    }
    return {
        "total_return_pct": 5.0,
        "max_drawdown_pct": -4.0,
        "win_rate_pct": 60.0,
        "trade_count": 5,
        "total_transaction_cost": 123.0,
        "cost_model": {
            "enabled": True,
            "mandatory": True,
            "base_currency": "KRW",
            "commission_bps_each_side": profile["commission_bps"],
            "slippage_bps_each_side": profile["slippage_bps"],
            "kr_sell_tax_bps": profile["kr_sell_tax_bps"],
            "fx_conversion_spread_bps_each_side": profile.get(
                "fx_conversion_spread_bps",
                10.0,
            ),
            "us_regulatory_fee_policy_version": "us-sec-finra-date-aware.v1",
        },
        "transaction_cost_audit": {
            "schema": "codexstock_replay_transaction_cost_audit_v1",
            "passed": True,
            "applied_action_count": 5,
        },
        "price_currency_unit_audit": {"passed": True, "base_currency": "KRW"},
        "execution_timing_model": {
            "lookahead_safe_required": True,
            "same_bar_signal_execution_allowed": False,
            "minimum_signal_lag_bars": 1,
        },
    }


class AiTournamentWalkForwardEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = {
            "commission_bps": 2.0,
            "slippage_bps": 7.0,
            "kr_sell_tax_bps": 20.0,
            "fx_conversion_spread_bps": 10.0,
        }
        self.row = {
            "contestant_id": "staff-1",
            "risk_limit_pct": 15.0,
            **_replay(self.profile),
        }

    def test_walk_forward_uses_identical_cost_profile_and_strict_evidence(self) -> None:
        with (
            patch("app.stock_suite_app.ai_tournament_contestants", return_value=[{"id": "staff-1"}]),
            patch(
                "app.stock_suite_app._ai_tournament_challenge_configs",
                return_value=[{
                    "label": "fixture",
                    "strategy": "ma_cross",
                    "fast": 5,
                    "slow": 20,
                    "allocation": 25,
                    "max_positions": 3,
                    "stop": 8,
                    "take": 10,
                    "hold": 20,
                }],
            ),
            patch("app.stock_suite_app._ai_tournament_challenge_ranking_score", return_value=10.0),
            patch("app.stock_suite_app.run_historical_paper_replay", side_effect=[_replay(self.profile), _replay(self.profile)]) as replay,
        ):
            result = _ai_tournament_walk_forward_validation(
                self.row,
                start_date="2024-01-01",
                end_date="2025-12-31",
                initial_cash=100_000_000.0,
                base_symbols=["SPY", "QQQ", "DIA"],
                symbol_selection_mode="common",
                allow_simulated_fallback=False,
                replay_cost_profile=self.profile,
                source="test",
            )

        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["training_evidence_passed"])
        self.assertTrue(result["checks"]["out_of_sample_cost_ledger_passed"])
        self.assertTrue(result["checks"]["out_of_sample_lookahead_safe_execution_passed"])
        self.assertTrue(result["checks"]["same_cost_profile"])
        self.assertTrue(result["measurement_evidence_validated"])
        self.assertTrue(result["strategy_promotion_passed"])
        self.assertEqual(2, replay.call_count)
        for call in replay.call_args_list:
            self.assertEqual(2.0, call.kwargs["commission_bps"])
            self.assertEqual(7.0, call.kwargs["slippage_bps"])
            self.assertEqual(20.0, call.kwargs["kr_sell_tax_bps"])
            self.assertEqual(10.0, call.kwargs["fx_conversion_spread_bps"])

    def test_main_replay_cost_mismatch_blocks_walk_forward(self) -> None:
        row = copy.deepcopy(self.row)
        row["cost_model"]["commission_bps_each_side"] = 9.0
        with (
            patch("app.stock_suite_app.ai_tournament_contestants", return_value=[{"id": "staff-1"}]),
            patch(
                "app.stock_suite_app._ai_tournament_challenge_configs",
                return_value=[{
                    "label": "fixture",
                    "strategy": "ma_cross",
                    "fast": 5,
                    "slow": 20,
                    "allocation": 25,
                    "max_positions": 3,
                    "stop": 8,
                    "take": 10,
                    "hold": 20,
                }],
            ),
            patch("app.stock_suite_app._ai_tournament_challenge_ranking_score", return_value=10.0),
            patch("app.stock_suite_app.run_historical_paper_replay", side_effect=[_replay(self.profile), _replay(self.profile)]),
        ):
            result = _ai_tournament_walk_forward_validation(
                row,
                start_date="2024-01-01",
                end_date="2025-12-31",
                initial_cash=100_000_000.0,
                base_symbols=["SPY", "QQQ", "DIA"],
                symbol_selection_mode="common",
                allow_simulated_fallback=False,
                replay_cost_profile=self.profile,
                source="test",
            )

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["same_cost_profile"])
        self.assertIn("same_cost_profile", result["blockers"])
        self.assertIn("same_cost_profile", result["measurement_blockers"])
        self.assertEqual([], result["performance_blockers"])

    def test_every_staff_gets_independent_walk_forward_after_bias_passes(self) -> None:
        rows = [{"contestant_id": "staff-1"}, {"contestant_id": "staff-2"}]
        with patch(
            "app.stock_suite_app._ai_tournament_walk_forward_validation",
            side_effect=lambda row, **_kwargs: {
                "passed": True,
                "contestant_id": row["contestant_id"],
            },
        ) as validate:
            _attach_ai_tournament_walk_forward_validations(
                rows,
                bias_audit={"passed": True},
                start_date="2024-01-01",
                end_date="2025-12-31",
                initial_cash=100_000_000.0,
                base_symbols=["SPY", "QQQ", "DIA"],
                symbol_selection_mode="common",
                allow_simulated_fallback=False,
                replay_cost_profile=self.profile,
                source="test",
            )

        self.assertEqual(2, validate.call_count)
        self.assertEqual("staff-1", rows[0]["walk_forward"]["contestant_id"])
        self.assertEqual("staff-2", rows[1]["walk_forward"]["contestant_id"])

    def test_bias_failure_blocks_all_staff_without_expensive_replay(self) -> None:
        rows = [{"contestant_id": "staff-1"}, {"contestant_id": "staff-2"}]
        with patch("app.stock_suite_app._ai_tournament_walk_forward_validation") as validate:
            _attach_ai_tournament_walk_forward_validations(
                rows,
                bias_audit={"passed": False},
                start_date="2024-01-01",
                end_date="2025-12-31",
                initial_cash=100_000_000.0,
                base_symbols=["SPY", "QQQ", "DIA"],
                symbol_selection_mode="common",
                allow_simulated_fallback=False,
                replay_cost_profile=self.profile,
                source="test",
            )

        validate.assert_not_called()
        self.assertTrue(all(row["walk_forward"]["passed"] is False for row in rows))


if __name__ == "__main__":
    unittest.main()
