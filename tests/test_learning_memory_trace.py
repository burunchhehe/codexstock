from datetime import datetime
import time
import unittest
from unittest.mock import patch

from app.stock_suite_app import (
    LEARNING_MEMORY_POLICY_VERSION,
    MEMORY,
    _candidate_learning_cache_is_current,
    _deduplicate_candidate_score_components,
    _desaturate_candidate_score,
    _learning_bias_for_candidate,
    _learning_memory_feature_probe,
    _replay_symbol_learning_evidence,
    build_ai_learning_insights,
    build_ai_screener,
)


class LearningMemoryTraceTests(unittest.TestCase):
    @staticmethod
    def _live_memory() -> dict[str, object]:
        return {
            "account": {"positions": []},
            "realized_preview": {"realized": []},
            "counts": {},
            "net_pnl_reconciliation": {"status": "not_available"},
        }

    @staticmethod
    def _study() -> dict[str, object]:
        return {
            "study_score": 60,
            "source_count": 2,
            "distilled_rules": [],
            "rule_weights": {},
            "execution_checklist": [],
        }

    def _build(
        self,
        *,
        meetings: list[dict[str, object]] | None = None,
        memory: dict[str, object] | None = None,
        reflection: dict[str, object] | None = None,
        live_memory: dict[str, object] | None = None,
    ) -> dict[str, object]:
        memory_payload = {
            "historical_replay_contexts": [],
            "historical_replay_memory_count": 0,
            "historical_replay_unique_context_count": 0,
            "historical_replay_duplicate_context_count": 0,
            "market_reflection_memory_count": 0,
            **(memory or {}),
        }
        with (
            patch("app.stock_suite_app.recent_ai_staff_meetings", return_value=meetings or []),
            patch.object(MEMORY, "summary", return_value=memory_payload),
            patch("app.stock_suite_app.latest_market_reflection_journal", return_value=reflection or {}),
            patch("app.stock_suite_app.build_live_trade_memory_summary", return_value=live_memory or self._live_memory()),
            patch("app.stock_suite_app.build_daytrader_strategy_study", return_value=self._study()),
        ):
            return build_ai_learning_insights(force=True, persist=False)

    def test_committee_decision_is_advisory_not_circular_score_evidence(self):
        insight = self._build(meetings=[{
            "id": "MEETING-1",
            "work_date": "2026-07-17",
            "top_candidate": {"symbol": "AAA", "score": 92.0},
            "decision": {"label": "집중 연구"},
        }])

        evidence = insight["meeting_learning_evidence"][0]
        self.assertEqual(evidence["score_delta"], 0.0)
        self.assertFalse(evidence["score_eligible"])
        self.assertNotIn("AAA", insight["symbol_bias"])
        self.assertEqual(insight["meeting_score_eligible_count"], 0)
        self.assertEqual(insight["meeting_advisory_symbol_evidence_counts"]["AAA"], 1)

    def test_basket_replay_without_symbol_results_cannot_reward_every_symbol(self):
        context = {
            "context_id": "CTX-1",
            "replay_id": "REPLAY-1",
            "strategy_id": "ma_cross",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "symbols": ["AAA", "BBB"],
            "return_pct": 30.0,
            "max_drawdown_pct": -10.0,
            "trade_count": 20,
        }

        evidence = _replay_symbol_learning_evidence(context)
        insight = self._build(memory={
            "historical_replay_contexts": [context],
            "historical_replay_memory_count": 1,
            "historical_replay_unique_context_count": 1,
        })

        self.assertEqual(evidence[0]["attribution_status"], "basket_only_no_symbol_attribution")
        self.assertFalse(evidence[0]["score_applied"])
        self.assertEqual(insight["replay_symbol_bias"], {})
        self.assertEqual(insight["replay_unattributed_context_count"], 1)

    def test_symbol_attributed_replay_updates_only_proven_symbol_outcomes(self):
        context = {
            "context_id": "CTX-2",
            "replay_id": "REPLAY-2",
            "strategy_id": "ma_cross",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "symbols": ["AAA", "BBB"],
            "symbol_results": [
                {"symbol": "AAA", "return_pct": 10.0, "max_drawdown_pct": -10.0, "trade_count": 12},
                {"symbol": "BBB", "return_pct": -10.0, "max_drawdown_pct": -12.0, "trade_count": 8},
            ],
        }

        insight = self._build(memory={
            "historical_replay_contexts": [context],
            "historical_replay_memory_count": 1,
            "historical_replay_unique_context_count": 1,
        })

        self.assertEqual(insight["replay_symbol_bias"]["AAA"], 0.5)
        self.assertEqual(insight["replay_symbol_bias"]["BBB"], -1.0)
        self.assertEqual(insight["replay_score_eligible_evidence_count"], 2)
        self.assertTrue(all(row["attribution_status"] == "symbol_attributed" for row in insight["replay_bias_evidence"]))

    def test_candidate_learning_trace_reconciles_sources_and_excludes_advisory_meeting(self):
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        insight = {
            "generated_at": generated_at,
            "learning_score": 70.0,
            "learning_evidence_fingerprint": "global-evidence",
            "historical_replay_unique_context_count": 1,
            "symbol_bias": {"AAA": 1.25},
            "replay_symbol_bias": {"AAA": 0.5},
            "live_realized_symbol_bias": {"AAA": 0.25},
            "meeting_symbol_evidence_counts": {},
            "meeting_advisory_symbol_evidence_counts": {"AAA": 1},
            "reflection_symbol_evidence_counts": {"AAA": 1},
            "reflection_learning_evidence": [{"event_key": "R-1", "symbol": "AAA"}],
            "replay_bias_evidence": [{
                "context_id": "CTX-1",
                "symbols": ["AAA"],
                "score_applied": True,
                "attribution_status": "symbol_attributed",
            }],
            "live_realized_evidence": [{"event_key": "L-1", "symbol": "AAA"}],
        }

        trace = _learning_bias_for_candidate({"symbol": "AAA"}, insight)

        self.assertEqual(trace["score_delta"], 1.25)
        self.assertEqual(trace["meeting_evidence_count"], 0)
        self.assertEqual(trace["meeting_advisory_evidence_count"], 1)
        self.assertEqual(trace["total_evidence_count"], 3)
        self.assertEqual(trace["source_score_deltas"]["meeting_decision"], 0.0)
        self.assertTrue(trace["source_delta_reconciled"])
        self.assertEqual(trace["evidence_ids"], ["CTX-1", "L-1", "R-1"])
        self.assertEqual(len(trace["evidence_fingerprint"]), 64)

    def test_learning_cache_requires_trace_and_score_reconciliation(self):
        candidate = {
            "learning_bias": {
                "policy_version": LEARNING_MEMORY_POLICY_VERSION,
                "eligible_for_score": True,
                "evidence_fingerprint": "trace",
            },
            "learning_bias_applied_to_score": True,
            "learning_score_reconciliation": {
                "policy_version": LEARNING_MEMORY_POLICY_VERSION,
                "evidence_fingerprint": "trace",
                "passed": True,
            },
        }
        self.assertTrue(_candidate_learning_cache_is_current([candidate]))

        candidate["learning_score_reconciliation"]["passed"] = False
        self.assertFalse(_candidate_learning_cache_is_current([candidate]))

    def test_feature_probe_detects_same_version_but_stale_evidence_trace(self):
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        insight = {
            "generated_at": generated_at,
            "learning_memory_policy_version": LEARNING_MEMORY_POLICY_VERSION,
            "learning_score": 70.0,
            "learning_evidence_fingerprint": "global-evidence",
            "symbol_bias": {"AAA": -4.0},
            "replay_symbol_bias": {},
            "live_realized_symbol_bias": {},
            "meeting_symbol_evidence_counts": {},
            "meeting_advisory_symbol_evidence_counts": {},
            "reflection_symbol_evidence_counts": {"AAA": 1},
            "reflection_learning_evidence": [{"event_key": "R-NEW", "symbol": "AAA"}],
            "replay_bias_evidence": [],
            "live_realized_evidence": [],
            "meeting_learning_evidence": [],
            "score_eligible_evidence_count": 1,
            "meeting_count": 0,
            "meeting_learning_unique_event_count": 0,
            "meeting_learning_duplicate_event_count": 0,
            "historical_replay_unique_context_count": 0,
            "replay_unattributed_context_count": 0,
        }
        candidate = {
            "symbol": "AAA",
            "learning_bias": {
                "policy_version": LEARNING_MEMORY_POLICY_VERSION,
                "score_delta": 2.0,
                "total_evidence_count": 1,
                "evidence_fingerprint": "old-trace",
            },
            "learning_score_reconciliation": {
                "policy_version": LEARNING_MEMORY_POLICY_VERSION,
                "evidence_fingerprint": "old-trace",
                "passed": True,
            },
        }
        with (
            patch("app.stock_suite_app._agent_cache_load", return_value={"payload": {"candidates": [candidate]}}),
        ):
            result = _learning_memory_feature_probe(insight_override=insight)

        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["summary"]["trace_mismatch_count"], 1)
        self.assertEqual(result["summary"]["score_delta_mismatch_count"], 1)

    def test_feature_probe_returns_stale_snapshot_while_one_refresh_starts(self):
        insight = {
            "generated_at": "2026-07-01T00:00:00+09:00",
            "learning_memory_policy_version": LEARNING_MEMORY_POLICY_VERSION,
            "learning_score": 70.0,
            "learning_evidence_fingerprint": "global-evidence",
            "meeting_learning_evidence": [],
            "replay_bias_evidence": [],
            "reflection_learning_evidence": [],
            "live_realized_evidence": [],
            "score_eligible_evidence_count": 0,
        }
        with (
            patch("app.stock_suite_app._start_learning_memory_refresh", return_value=True) as refresh,
            patch("app.stock_suite_app._agent_cache_load", return_value={"payload": {"candidates": []}}),
        ):
            result = _learning_memory_feature_probe(insight_override=insight)

        self.assertTrue(result["ok"])
        self.assertTrue(result["learning_snapshot_stale"])
        self.assertTrue(result["background_refresh_started"])
        self.assertEqual("stale_while_revalidate", result["health_probe_mode"])
        refresh.assert_called_once_with()

    def test_screener_cache_refreshes_only_learning_trace_without_market_rebuild(self):
        components = {
            "base": 12.0,
            "backtest": 20.0,
            "mdd": 10.0,
            "quality": 8.0,
            "financial": 10.0,
            "news": 0.0,
            "theme": 0.0,
            "sector_news": 0.0,
            "market": 0.0,
            "toss_public": 0.0,
        }
        dedup = _deduplicate_candidate_score_components(components)
        base_raw = float(dedup["effective_component_total"])
        base_pre = float(dedup["original_component_total"])
        old_delta = 2.0
        candidate = {
            "symbol": "AAA",
            "name": "AAA",
            "score": _desaturate_candidate_score(base_raw + old_delta),
            "raw_score": base_raw + old_delta,
            "raw_score_before_learning": base_raw,
            "pre_dedup_raw_score": base_pre + old_delta,
            "duplicate_bonus_removed": round(base_pre - base_raw, 2),
            "score_dedup_audit": dedup,
            "quality_score": 60.0,
            "financial_score": 60.0,
            "profit_factor": 1.2,
            "mdd_pct": -10.0,
            "strategy_mode": "quality_swing",
            "trade_mode": "스윙",
            "trade_horizon": {"strategy_mode": "quality_swing", "swing_score": 70.0},
            "reasons": ["회의/복기 종목 보정 +2.0"],
            "risk_flags": [],
            "learning_bias": {
                "policy_version": "deduplicated_evidence_v2",
                "score_delta": old_delta,
                "eligible_for_score": True,
            },
            "learning_bias_applied_to_score": True,
        }
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        insight = {
            "generated_at": generated_at,
            "learning_memory_policy_version": LEARNING_MEMORY_POLICY_VERSION,
            "learning_score": 70.0,
            "learning_evidence_fingerprint": "global-evidence",
            "symbol_bias": {"AAA": -4.0},
            "replay_symbol_bias": {},
            "live_realized_symbol_bias": {},
            "meeting_symbol_evidence_counts": {},
            "meeting_advisory_symbol_evidence_counts": {},
            "reflection_symbol_evidence_counts": {"AAA": 1},
            "reflection_learning_evidence": [{"event_key": "R-NEW", "symbol": "AAA"}],
            "replay_bias_evidence": [],
            "live_realized_evidence": [],
        }
        cached = {
            "saved_at": time.time(),
            "payload": {"candidates": [candidate], "learning": {}},
        }
        with (
            patch("app.stock_suite_app._agent_cache_load", return_value=cached),
            patch("app.stock_suite_app.build_ai_learning_insights", return_value=insight),
            patch("app.stock_suite_app._agent_cache_save") as cache_save,
            patch("app.stock_suite_app._lookup_symbols") as market_rebuild,
        ):
            result = build_ai_screener(force=False)

        refreshed = result["candidates"][0]
        self.assertTrue(result["cached"])
        self.assertTrue(result["learning_trace_refreshed"])
        self.assertEqual(refreshed["raw_score"], round(base_raw - 4.0, 2))
        self.assertEqual(refreshed["learning_bias"]["policy_version"], LEARNING_MEMORY_POLICY_VERSION)
        self.assertTrue(refreshed["learning_score_reconciliation"]["passed"])
        market_rebuild.assert_not_called()
        cache_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
