import copy
import unittest
from unittest.mock import patch

from app.stock_suite_app import (
    SCORE_DEDUP_POLICY_VERSION,
    _candidate_lane_summary,
    _candidate_score_cache_is_current,
    _candidate_score_contract,
    _candidate_sector_concentration_audit,
    _candidate_sector_promotion_board,
    _candidate_score_saturation_audit,
    _candidate_score_view_fields,
    _deduplicate_candidate_score_components,
    _desaturate_candidate_score,
    _next_session_candidate_row,
    _normalize_staff_meeting_score_views,
    _score_saturation_feature_probe,
    _staff_meeting_candidate_summaries,
)


class CandidateScoreIntegrityTests(unittest.TestCase):
    @staticmethod
    def _candidate() -> dict[str, object]:
        components = {
            "base": 12.0,
            "backtest": 24.0,
            "mdd": 12.0,
            "quality": 14.0,
            "financial": 20.0,
            "news": 10.0,
            "theme": 5.0,
            "sector_news": 8.0,
            "market": 10.0,
            "toss_public": 8.0,
        }
        dedup = _deduplicate_candidate_score_components(components)
        pre_dedup = float(dedup["original_component_total"])
        raw = float(dedup["effective_component_total"])
        removed = round(pre_dedup - raw, 2)
        return {
            "symbol": "TEST",
            "name": "Test Candidate",
            "score": _desaturate_candidate_score(raw),
            "raw_score": raw,
            "pre_dedup_raw_score": pre_dedup,
            "duplicate_bonus_removed": removed,
            "score_dedup_audit": dedup,
            "quality_score": 80.0,
            "financial_score": 80.0,
            "profit_factor": 1.5,
            "mdd_pct": -12.0,
        }

    def _scored_candidate(
        self,
        symbol: str,
        raw_score: float,
        sector_key: str | None = None,
    ) -> dict[str, object]:
        row = self._candidate()
        removed = float(row["duplicate_bonus_removed"])
        row.update({
            "symbol": symbol,
            "name": symbol,
            "score": _desaturate_candidate_score(raw_score),
            "raw_score": raw_score,
            "pre_dedup_raw_score": raw_score + removed,
            "strategy_mode": "quality_swing",
            "trade_mode": "스윙",
            "trade_horizon": {
                "strategy_mode": "quality_swing",
                "swing_score": 75.0,
                "daytrade_score": 25.0,
            },
        })
        if sector_key:
            row["sector_news_signal"] = {
                "matches": [{"id": sector_key, "name": sector_key}],
            }
        return row

    def test_same_backtest_outputs_share_one_evidence_budget(self):
        result = _deduplicate_candidate_score_components({
            "base": 12.0,
            "backtest": 24.0,
            "mdd": 12.0,
            "quality": 14.0,
            "financial": 20.0,
            "news": 0.0,
            "theme": 0.0,
            "sector_news": 0.0,
            "market": 0.0,
            "toss_public": 0.0,
        })
        family = result["groups"]["backtest_run"]
        self.assertEqual(result["policy_version"], SCORE_DEDUP_POLICY_VERSION)
        self.assertEqual(family["keys"], ["backtest", "mdd", "quality"])
        self.assertLessEqual(family["effective_total"], 30.0)
        self.assertGreater(family["removed_points"], 0.0)

    def test_soft_cap_is_monotonic_and_never_reaches_100(self):
        raw_scores = [88.0, 100.0, 150.0, 500.0]
        display_scores = [_desaturate_candidate_score(value) for value in raw_scores]
        self.assertEqual(display_scores, sorted(display_scores))
        self.assertEqual(len(display_scores), len(set(display_scores)))
        self.assertTrue(all(value < 100.0 for value in display_scores))
        self.assertLessEqual(max(display_scores), 98.7)

    def test_score_contract_reconciles_removed_and_display_scores(self):
        candidate = self._candidate()
        contract = _candidate_score_contract(candidate)
        self.assertTrue(contract["passed"])
        self.assertEqual(contract["blockers"], [])
        audit = _candidate_score_saturation_audit([candidate])
        self.assertEqual(audit["score_contract_passed_count"], 1)
        self.assertEqual(audit["score_contract_failed_count"], 0)
        self.assertTrue(_candidate_score_cache_is_current([candidate]))

    def test_saturation_audit_is_independent_of_candidate_input_order(self):
        rows = []
        for symbol, raw_score in (("LOW", 40.0), ("TOP", 92.0), ("MID", 70.0)):
            row = self._candidate()
            removed = float(row["duplicate_bonus_removed"])
            row.update({
                "symbol": symbol,
                "raw_score": raw_score,
                "pre_dedup_raw_score": raw_score + removed,
                "score": _desaturate_candidate_score(raw_score),
            })
            rows.append(row)

        audit = _candidate_score_saturation_audit(rows)

        self.assertEqual(audit["top_symbol"], "TOP")
        self.assertEqual(audit["top_score"], _desaturate_candidate_score(92.0))
        self.assertTrue(audit["audit_input_order_independent"])

    def test_resolved_display_ties_do_not_fail_feature_health(self):
        rows = []
        for index, raw_score in enumerate((90.0, 90.001, 90.002), start=1):
            row = self._candidate()
            removed = float(row["duplicate_bonus_removed"])
            row.update({
                "symbol": f"TIE{index}",
                "raw_score": raw_score,
                "pre_dedup_raw_score": raw_score + removed,
                "score": _desaturate_candidate_score(raw_score),
            })
            rows.append(row)

        with patch(
            "app.stock_suite_app._agent_cache_load",
            return_value={"payload": {"candidates": rows}},
        ):
            result = _score_saturation_feature_probe()

        self.assertEqual(result["top_score_tie_count"], 3)
        self.assertEqual(result["top_ranking_vector_tie_count"], 1)
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["ok"])

    def test_stale_policy_or_tampered_ledger_cannot_reenter_cache(self):
        candidate = self._candidate()
        stale = copy.deepcopy(candidate)
        stale["score_dedup_audit"]["policy_version"] = "correlated_evidence_decay_v2"
        self.assertFalse(_candidate_score_cache_is_current([stale]))
        stale_audit = _candidate_score_saturation_audit([stale])
        self.assertEqual(stale_audit["dedup_policy_stale_count"], 1)

        tampered = copy.deepcopy(candidate)
        tampered["duplicate_bonus_removed"] = 0.0
        contract = _candidate_score_contract(tampered)
        self.assertFalse(contract["passed"])
        self.assertIn("duplicate_removed_reconciliation_mismatch", contract["blockers"])
        self.assertFalse(_candidate_score_cache_is_current([tampered]))

    def test_staff_meeting_candidate_summaries_do_not_show_100_point_ties(self):
        meeting_rows = [
            {
                "symbol": "005930",
                "name": "Samsung Electronics",
                "score": 100.0,
                "raw_score": 142.0,
                "reason": "meeting candidate",
            },
            {
                "symbol": "000660",
                "name": "SK Hynix",
                "score": 100.0,
                "raw_score": 118.0,
                "reason": "meeting candidate",
            },
        ]

        summaries = _staff_meeting_candidate_summaries(meeting_rows)

        self.assertEqual(len(summaries), 2)
        self.assertTrue(all(row["score"] < 100.0 for row in summaries))
        self.assertGreater(summaries[0]["score"], summaries[1]["score"])
        self.assertEqual(summaries[0]["raw_score"], 142.0)
        self.assertEqual(summaries[0]["display_score"], summaries[0]["score"])
        self.assertEqual(summaries[0]["score_display_policy"], "desaturated_candidate_view_v2")
        self.assertEqual(summaries[0]["score_contract"]["status"], "normalized")
        self.assertTrue(summaries[0]["score_contract"]["saturated_100_blocked"])

    def test_legacy_score_is_desaturated_without_claiming_raw_precision(self):
        fields = _candidate_score_view_fields({"symbol": "LEGACY", "score": 100.0})

        self.assertLess(fields["score"], 100.0)
        self.assertEqual(fields["ranking_precision"], "legacy_display_only")
        self.assertFalse(fields["ranking_tie_break_allowed"])
        self.assertFalse(fields["score_contract"]["raw_score_proven"])
        self.assertEqual(fields["score_contract"]["status"], "legacy_score_normalized_precision_limited")
        self.assertEqual(_candidate_score_view_fields(fields)["score"], fields["score"])

    def test_staff_meeting_score_tree_repairs_nested_legacy_scores(self):
        meeting = {
            "top_candidate": {"symbol": "TOP", "score": 100.0},
            "investment_committee": {
                "sector_concentration_audit": {
                    "sectors": [
                        {
                            "label": "Technology",
                            "avg_score": 100.0,
                            "candidates": [
                                {"symbol": "A", "score": 100.0, "raw_score": 142.0},
                                {"symbol": "B", "score": 100.0, "raw_score": 118.0},
                            ],
                        }
                    ]
                },
                "debate": [
                    {"evidence": {"representatives": [{"symbol": "A", "score": 100.0, "raw_score": 142.0}]}}
                ],
            },
            "next_session_live_watch_plan": {"selected": {"symbol": "B", "score": 100.0, "raw_score": 118.0}},
        }

        normalized = _normalize_staff_meeting_score_views(meeting)
        sector = normalized["investment_committee"]["sector_concentration_audit"]["sectors"][0]

        self.assertLess(normalized["top_candidate"]["score"], 100.0)
        self.assertFalse(normalized["top_candidate"]["ranking_tie_break_allowed"])
        self.assertGreater(sector["candidates"][0]["score"], sector["candidates"][1]["score"])
        self.assertEqual(
            sector["avg_score"],
            round(sum(row["score"] for row in sector["candidates"]) / 2, 2),
        )
        representative = normalized["investment_committee"]["debate"][0]["evidence"]["representatives"][0]
        self.assertLess(representative["score"], 100.0)
        self.assertLess(normalized["next_session_live_watch_plan"]["selected"]["score"], 100.0)

    def test_next_session_candidate_keeps_raw_score_contract(self):
        row = _next_session_candidate_row(
            {
                "symbol": "005930",
                "name": "Samsung Electronics",
                "score": 100.0,
                "raw_score": 142.0,
                "risk_gate_status": "PASSED",
            },
            set(),
            1,
        )

        self.assertEqual(row["raw_score"], 142.0)
        self.assertLess(row["score"], 100.0)
        self.assertTrue(row["ranking_tie_break_allowed"])
        self.assertEqual(row["score_contract"]["status"], "normalized")

    def test_sector_copy_keeps_legacy_precision_and_does_not_double_compress(self):
        source = {"symbol": "LEGACY", "name": "Legacy Candidate", "score": 100.0}
        source.update(_candidate_score_view_fields(source))

        audit = _candidate_sector_concentration_audit([source])
        copied = audit["top_sector"]["candidates"][0]
        normalized = _normalize_staff_meeting_score_views({"candidate": copied})["candidate"]

        self.assertEqual(copied["score"], source["score"])
        self.assertEqual(copied["raw_score"], 100.0)
        self.assertFalse(copied["ranking_tie_break_allowed"])
        self.assertEqual(normalized["score"], source["score"])
        self.assertEqual(normalized["raw_score"], 100.0)
        self.assertFalse(normalized["score_contract"]["raw_score_proven"])

    def test_candidate_lane_keeps_best_duplicate_regardless_of_input_order(self):
        lower = self._scored_candidate("DUP", 50.0, "sector_a")
        higher = self._scored_candidate("DUP", 82.0, "sector_a")

        board = _candidate_lane_summary([lower, higher])
        long_term = next(row for row in board["lanes"] if row["key"] == "long_term")

        self.assertEqual(long_term["count"], 1)
        self.assertEqual(long_term["top"][0]["raw_score"], 82.0)
        self.assertEqual(board["assignment_audit"]["duplicate_symbol_rows_skipped"], 1)
        self.assertTrue(board["assignment_audit"]["input_order_independent"])

    def test_sector_audit_ranks_before_top_n_and_keeps_all_crowded_names(self):
        crowded = [
            self._scored_candidate(f"A{index}", 80.0 + index, "sector_a")
            for index in range(7)
        ]
        low_other = [
            self._scored_candidate(f"B{index}", 10.0 + index, "sector_b")
            for index in range(3)
        ]

        audit = _candidate_sector_concentration_audit(low_other + crowded, top_n=7)

        self.assertEqual(audit["top_sector"]["key"], "sector_a")
        self.assertEqual(audit["top_sector"]["count"], 7)
        self.assertEqual(len(audit["top_sector"]["candidates"]), 7)
        self.assertEqual(audit["trusted_classification_pct"], 100.0)
        self.assertTrue(audit["input_order_independent"])

    def test_sector_promotion_uses_best_unique_rows_before_applying_cap(self):
        rows = [
            self._scored_candidate("A_TOP", 40.0, "sector_a"),
            self._scored_candidate("A_LOW", 70.0, "sector_a"),
            self._scored_candidate("B_TOP", 75.0, "sector_b"),
            self._scored_candidate("A_MID", 80.0, "sector_a"),
            self._scored_candidate("A_TOP", 90.0, "sector_a"),
        ]
        _candidate_lane_summary(rows)

        board = _candidate_sector_promotion_board(rows, max_per_sector=2, limit=3)

        self.assertEqual(
            [row["symbol"] for row in board["selected"]],
            ["A_TOP", "A_MID", "B_TOP"],
        )
        self.assertEqual(board["duplicate_symbol_rows_skipped"], 1)
        self.assertTrue(board["cap_compliant"])
        self.assertTrue(board["input_order_independent"])

    def test_untrusted_market_bucket_cannot_claim_sector_diversification(self):
        row = self._scored_candidate("UNKNOWN", 82.0)
        row["market"] = "KR-KOSDAQ"
        _candidate_lane_summary([row])

        board = _candidate_sector_promotion_board([row], max_per_sector=2, limit=3)

        self.assertEqual(board["selected_count"], 0)
        self.assertEqual(board["eligibility_excluded_count"], 1)
        self.assertIn(
            "trusted_sector_classification",
            board["excluded"][0]["eligibility"]["failed_checks"],
        )


if __name__ == "__main__":
    unittest.main()
