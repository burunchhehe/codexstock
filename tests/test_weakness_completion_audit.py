import unittest
from unittest.mock import patch

from app import stock_suite_app as suite


class WeaknessCompletionAuditTests(unittest.TestCase):
    def _patch_common_success_dependencies(self):
        news = {
            "schema": "codexstock_market_news_evidence_v1",
            "summary": {
                "news_count": 1,
                "verified_count": 1,
                "original_source_confirmed_count": 1,
                "multi_source_original_count": 1,
                "official_disclosure_corroborated_count": 1,
                "official_disclosure_primary_count": 0,
            },
            "policy": {
                "headline_only_is_verified": False,
                "unverified_news_affects_score": False,
            },
            "rows": [
                {
                    "original_source_resolutions": [],
                    "independent_original_domain_count": 1,
                    "official_disclosure_matches": [{}],
                    "score_allowed": True,
                    "live_order_allowed": False,
                }
            ],
        }
        long_horizon = {
            "schema": "codexstock_ai_staff_long_horizon_v2",
            "benchmark": {
                "schema": "codexstock_long_horizon_benchmark_v3",
                "comparison_currency": "KRW",
                "krw_adjusted_cagr_pct": 9.37,
                "net_costed_krw_cagr_pct": 9.36,
                "currency_conversion_validated": True,
                "transaction_cost_validated": True,
            },
            "staff": [
                {"performance_evidence": {"schema": "codexstock_long_horizon_performance_evidence_v1", "passed": True}}
                for _ in range(4)
            ],
        }
        replay = {
            "schema": "codexstock_historical_replay_completion_audit_v3",
            "paper_only": True,
            "automatic_promotion": False,
            "live_order_allowed": False,
            "completion_verified": False,
            "resolved_count": 159,
            "remaining_count": 598,
            "progress_label": "159/757",
            "blockers": ["replay_incomplete"],
            "completion_estimate": {
                "estimated_hours_remaining": 12.3,
                "conservative_hours_remaining": 15.6,
                "estimated_throughput_per_hour": 48.5,
                "schedule_mode": "market_priority_deferred",
                "next_due_at": "2026-07-15T21:00:00+09:00",
                "next_eligible_at": "2026-07-15T21:05:00+09:00",
            },
            "next_action": "defer_to_market_closed_window",
            "operator_message": "과거장 대사 159/757 / 남은 598건 / 다음 조치 defer_to_market_closed_window",
        }
        learning = {
            "schema": "codexstock_ai_staff_learning_audit_v4",
            "verification_capability_ready": True,
            "counterfactual_control_required": True,
            "effect_confidence_gate_required": True,
            "growth_outcome_proven": False,
            "verification_state": "verification_pending",
            "staff_count": 4,
            "growth_proven_staff_count": 0,
            "validated_learning_pair_count": 0,
            "improved_learning_pair_count": 0,
            "effect_confidence_proven_staff_count": 0,
            "learning_experiment_contract_ready": True,
            "learning_experiment_contract_path": "C:/tmp/ai_staff_learning_experiment_contract.json",
            "learning_experiment_contract_hash": "hash",
            "counterfactual_ledger_triplet_count": 1,
            "counterfactual_ledger_improved_triplet_count": 0,
            "official_learning_source_readiness": {
                "schema": "codexstock_ai_staff_learning_source_readiness_v1",
                "staff_count": 4,
                "source_ready_staff_count": 0,
                "source_blocked_staff_count": 4,
                "historical_replay_dependency_active": True,
                "deep_progress_label": "100/757",
                "dominant_blockers": [
                    {"reason": "source_replay_not_in_deep_verified_milestone", "count": 4}
                ],
                "next_action": "complete_historical_replay_and_bias_evidence_for_learning_sources",
                "operator_message": "직원 공식 학습 원천 0/4명 준비. 과거장 깊은 검증 100/757",
            },
            "policy": {"unverified_result_affects_score": False},
        }
        score = {
            "ok": True,
            "summary": {
                "dedup_policy_expected_version": suite.SCORE_DEDUP_POLICY_VERSION,
                "dedup_policy_missing_count": 0,
                "score_contract_failed_count": 0,
                "display_score_98_or_more_count": 0,
            },
        }
        pulse = {
            "schema": "codexstock_intraday_market_pulse_v1",
            "source_status": [
                {"source": source, "ok": True}
                for source in ("amount", "volume", "gainers", "losers", "foreign", "institution")
            ],
            "alerts": [],
        }
        live = {
            "ok": True,
            "summary": {
                "pending_reconciliation_count": 0,
                "partial_count": 0,
                "account_ledger_mismatch_count": 0,
                "active_account_ledger_mismatch_count": 0,
                "active_account_ledger_incomplete_count": 0,
                "dual_path_hard_block": False,
            },
        }
        sqlite = {
            "status": "ready",
            "summary": {"sqlite_file_count": 2, "problem_sqlite_count": 0, "max_query_ms": 2.0},
        }
        engines = {
            "on_demand_audit": {
                "schema": "codexstock_external_engine_on_demand_audit_v1",
                "status": "passed",
                "engine_count": 9,
                "persistent_heavy_engine_count": 0,
                "max_concurrent_external_jobs": 1,
                "blockers": [],
            }
        }
        health = {
            "checks": [
                {
                    "id": "ops_status",
                    "action": "none",
                    "operational_state": "normal",
                    "operational_state_label": "normal",
                    "operational_state_description": "ok",
                    "operational_severity": "ok",
                    "status_badge": "ok",
                    "last_checked_at": "2026-07-15T00:00:00+09:00",
                    "last_success_at": "2026-07-15T00:00:00+09:00",
                    "success_evidence_status": "verified",
                    "success_evidence_label": "success evidence available",
                }
            ],
            "lifecycle_contract": {"ok": True, "missing_field_count": 0, "invalid_state_ids": []},
        }
        surface = {
            "ok": True,
            "ui_button_count": 131,
            "ui_button_unbound_count": 0,
            "ui_api_missing_count": 0,
            "mcp_tool_count": 146,
            "mcp_tool_unhandled_count": 0,
        }
        learning_queue = {
            "ok": True,
            "job_count": 36,
            "strategy_triplet_count": 12,
            "safe_to_execute_paper": True,
            "next_action": "run_paper_counterfactual_triplet_batch",
            "path": "C:/tmp/ai_staff_learning_counterfactual_queue.json",
            "queue_hash": "queue-hash",
        }
        learning_schedule = {
            "status": "deferred_to_market_closed_window",
            "ready_to_run": False,
            "blockers": ["large_batch_window_not_allowed"],
            "next_action": "defer_staff_learning_counterfactual_triplets",
            "operator_message": "직원 학습 검증 보류: premarket 우선 모드라 Paper 트리플릿 12개를 장마감/주말 슬롯으로 미룹니다.",
            "large_batch_jobs_allowed": False,
            "market_priority_active": True,
            "heavy_slot_available": True,
        }
        learning_schedule = {
            "status": "deferred_to_market_closed_window",
            "ready_to_run": False,
            "blockers": ["large_batch_window_not_allowed"],
            "next_action": "defer_staff_learning_counterfactual_triplets",
            "operator_message": "직원 학습 검증 보류: premarket 우선 모드라 Paper 트리플릿 12개를 장마감/주말 슬롯으로 미룹니다.",
            "large_batch_jobs_allowed": False,
            "market_priority_active": True,
            "heavy_slot_available": True,
        }
        learning_preregistration = {
            "ok": True,
            "schema": "codexstock_ai_staff_learning_counterfactual_preregistration_status_v1",
            "status": "REGISTERED",
            "found": True,
            "valid": True,
            "hash_valid": True,
            "ready_for_future_execution": True,
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "first_eligible_run_date": "2026-09-21",
            "contract_id": "LCFPR-test",
            "contract_hash": "prereg-hash",
            "contract_generated_at": "2026-07-17T19:06:53+09:00",
            "registered_plan_count": 2,
            "blocked_plan_count": 2,
            "registered_contestant_ids": ["operator", "researcher"],
            "contract_outcome_state": "FUTURE_LOCKED",
            "contract_registered_triplet_count": 2,
            "contract_completed_triplet_count": 0,
            "contract_remaining_triplet_count": 2,
            "contract_missing_contestant_ids": ["operator", "researcher"],
            "all_registered_plans_completed": False,
            "contract_result_evidence_ready": False,
            "contract_result_catch_up_after_restart": True,
            "strategy_lock_ready": True,
            "strategy_lock_plan_count": 2,
            "strategy_lock_signature_count": 4,
            "strategy_lock_digest": "a" * 64,
            "execution_strategy_revalidation_required": True,
            "full_strategy_payload_exposed": False,
            "generated_before_target_start": True,
            "blockers": [],
            "next_action": "wait_for_locked_target_period_to_complete",
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        patches = (
            patch.object(suite, "build_market_news_evidence", return_value=news),
            patch.object(suite, "load_ai_staff_long_horizon_benchmark", return_value=long_horizon),
            patch.object(suite, "historical_replay_completion_audit", return_value=replay),
            patch.object(suite, "load_historical_replay_completion_certificate", return_value={"ok": False, "status": "missing"}),
            patch.object(suite, "ai_staff_learning_audit", return_value=learning),
            patch.object(suite, "build_ai_staff_learning_experiment_status", return_value={"ready": True, "hash_valid": True, "safe_to_execute_paper": True, "runnable_count": 0, "blocked_count": 4}),
            patch.object(suite, "build_ai_staff_learning_counterfactual_queue", return_value=learning_queue),
            patch.object(suite, "build_ai_staff_learning_counterfactual_scheduler_status", return_value=learning_schedule),
            patch.object(
                suite,
                "build_ai_staff_learning_counterfactual_preregistration_status",
                return_value=learning_preregistration,
            ),
            patch.object(suite, "_score_saturation_feature_probe", return_value=score),
            patch.object(suite, "build_intraday_market_pulse", return_value=pulse),
            patch.object(suite, "build_live_reconciliation_audit", return_value=live),
            patch.object(suite, "_sqlite_storage_feature_probe", return_value=sqlite),
            patch.object(suite, "build_external_engine_dashboard", return_value=engines),
            patch.object(suite.AI_DAEMON, "status", return_value={"worker_board": {}}),
            patch.object(
                suite,
                "build_ai_tournament_monte_carlo_evidence_audit",
                return_value={
                    "schema": "codexstock_monte_carlo_evidence_audit_v1",
                    "passed": False,
                    "outcome_metrics_used_for_selection": False,
                    "retraining_plan": {"schema": "codexstock_monte_carlo_stress_retraining_plan_v1"},
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "_promotion_candidate_evidence_audit",
                return_value={
                    "schema": "codexstock_promotion_candidate_evidence_audit_v1",
                    "raw_count": 0,
                    "verified_count": 0,
                    "quarantined_count": 0,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "_research_forge_candidate_discovery_audit",
                return_value={
                    "schema": "codexstock_research_forge_candidate_discovery_audit_v1",
                    "contract_ready": True,
                    "requires_manual_research_forge_nomination": True,
                    "requires_verified_historical_provider_evidence": True,
                    "requires_next_krx_session_cooling": True,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "_promotion_candidate_evidence_audit",
                return_value={
                    "schema": "codexstock_promotion_candidate_evidence_audit_v1",
                    "raw_count": 0,
                    "verified_count": 0,
                    "quarantined_count": 0,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "_research_forge_candidate_discovery_audit",
                return_value={
                    "schema": "codexstock_research_forge_candidate_discovery_audit_v1",
                    "contract_ready": True,
                    "requires_manual_research_forge_nomination": True,
                    "requires_verified_historical_provider_evidence": True,
                    "requires_next_krx_session_cooling": True,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "_promotion_rehearsal_evidence_audit",
                return_value={"schema": "codexstock_promotion_rehearsal_evidence_audit_v2"},
            ),
            patch.object(
                suite,
                "_promotion_rehearsal_readiness",
                return_value={
                    "schema": "codexstock_promotion_rehearsal_readiness_v1",
                    "ready": False,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "build_promotion_forward_observation_audit",
                return_value={
                    "schema": "codexstock_promotion_forward_observation_audit_v1",
                    "ready": False,
                    "required_calendar_days": 90,
                    "minimum_session_coverage_pct": 95.0,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(suite, "build_feature_health_board", return_value=health),
            patch.object(suite, "_feature_surface_contract_probe", return_value=surface),
        )
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_non_forced_audit_uses_immediate_status_cache(self):
        cached = {
            "ok": False,
            "schema": "codexstock_weakness_completion_audit_v1",
            "status": "refreshing",
            "official_completion_claim_allowed": False,
            "live_order_allowed": False,
        }
        with patch.object(
            suite.WEAKNESS_COMPLETION_STATUS_CACHE,
            "get",
            return_value=cached,
        ) as cache_get, patch.object(
            suite,
            "_build_codexstock_weakness_completion_audit_uncached",
        ) as uncached:
            result = suite.build_codexstock_weakness_completion_audit(force=False)

        self.assertEqual(cached, result)
        cache_get.assert_called_once_with()
        uncached.assert_not_called()
        self.assertFalse(result["official_completion_claim_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_forced_audit_remains_an_explicit_synchronous_diagnostic(self):
        fresh = {
            "ok": True,
            "schema": "codexstock_weakness_completion_audit_v1",
            "status": "verification_pending",
            "live_order_allowed": False,
        }
        with patch.object(
            suite,
            "_build_codexstock_weakness_completion_audit_uncached",
            return_value=fresh,
        ) as uncached, patch.object(
            suite.WEAKNESS_COMPLETION_STATUS_CACHE,
            "get",
        ) as cache_get:
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        self.assertEqual(fresh, result)
        uncached.assert_called_once_with(force=True)
        cache_get.assert_not_called()

    def test_market_context_retry_recovers_transient_economic_calendar_gap(self):
        first_context = {
            "schema": "codexstock_unified_market_context_v2",
            "coverage": {
                "total_count": 6,
                "covered_count": 5,
                "fresh_verified_count": 5,
                "decision_context_ready": False,
                "decision_context_blockers": ["economic_calendar"],
            },
        }
        second_context = {
            "schema": "codexstock_unified_market_context_v2",
            "coverage": {
                "total_count": 6,
                "covered_count": 6,
                "fresh_verified_count": 6,
                "decision_context_ready": True,
                "decision_context_blockers": [],
            },
        }
        self._patch_common_success_dependencies()
        with patch.object(
            suite,
            "build_unified_market_context_snapshot",
            side_effect=[first_context, second_context],
        ) as market_context:
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        self.assertEqual(2, market_context.call_count)
        context_row = next(row for row in result["items"] if row["id"] == 1)
        self.assertEqual("passed", context_row["status"])
        self.assertTrue(context_row["current_evidence_passed"])
        self.assertEqual(6, context_row["evidence"]["fresh_verified"])

    def test_intraday_pulse_retry_recovers_transient_source_gap(self):
        context = {
            "schema": "codexstock_unified_market_context_v2",
            "coverage": {
                "total_count": 6,
                "covered_count": 6,
                "fresh_verified_count": 6,
                "decision_context_ready": True,
                "decision_context_blockers": [],
            },
        }
        first_pulse = {
            "schema": "codexstock_intraday_market_pulse_v1",
            "source_status": [
                {"source": source, "ok": source != "losers"}
                for source in ("amount", "volume", "gainers", "losers", "foreign", "institution")
            ],
            "alerts": [],
        }
        second_pulse = {
            "schema": "codexstock_intraday_market_pulse_v1",
            "source_status": [
                {"source": source, "ok": True}
                for source in ("amount", "volume", "gainers", "losers", "foreign", "institution")
            ],
            "alerts": [],
        }
        self._patch_common_success_dependencies()
        with patch.object(suite, "build_unified_market_context_snapshot", return_value=context), patch.object(
            suite,
            "build_intraday_market_pulse",
            side_effect=[first_pulse, second_pulse],
        ) as pulse:
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        self.assertEqual(2, pulse.call_count)
        pulse_row = next(row for row in result["items"] if row["id"] == 7)
        self.assertEqual("passed", pulse_row["status"])
        self.assertEqual(6, pulse_row["evidence"]["successful_source_count"])

    def test_implementation_and_outcome_evidence_are_reported_separately(self):
        context = {
            "schema": "codexstock_unified_market_context_v2",
            "coverage": {
                "total_count": 6,
                "covered_count": 6,
                "fresh_verified_count": 5,
                "decision_context_ready": True,
                "decision_context_blockers": [],
            },
        }
        news = {
            "schema": "codexstock_market_news_evidence_v1",
            "summary": {"news_count": 1, "verified_count": 0},
            "policy": {
                "headline_only_is_verified": False,
                "unverified_news_affects_score": False,
            },
            "rows": [
                {
                    "original_source_resolutions": [],
                    "independent_original_domain_count": 0,
                    "official_disclosure_matches": [],
                    "score_allowed": False,
                    "live_order_allowed": False,
                }
            ],
        }
        staff_evidence = {
            "schema": "codexstock_long_horizon_performance_evidence_v1",
            "passed": False,
            "blockers": ["exact_staff_trade_ledger_missing"],
        }
        long_horizon = {
            "schema": "codexstock_ai_staff_long_horizon_v2",
            "benchmark": {
                "schema": "codexstock_long_horizon_benchmark_v3",
                "comparison_currency": "KRW",
                "krw_adjusted_cagr_pct": 9.37,
                "net_costed_krw_cagr_pct": 9.36,
                "currency_conversion_validated": True,
                "transaction_cost_validated": True,
                "input_data_hash": "benchmark-input-hash",
                "usdkrw_future_value_used": False,
            },
            "staff": [{"performance_evidence": staff_evidence}],
        }
        replay = {
            "schema": "codexstock_historical_replay_completion_audit_v3",
            "paper_only": True,
            "automatic_promotion": False,
            "live_order_allowed": False,
            "completion_verified": False,
            "resolved_count": 115,
            "remaining_count": 642,
            "progress_label": "115/757",
            "blockers": ["replay_incomplete"],
            "completion_estimate": {
                "estimated_hours_remaining": 18.5,
                "conservative_hours_remaining": 21.0,
                "estimated_throughput_per_hour": 34.7,
                "schedule_mode": "weekday_after_hours_bounded",
                "next_due_at": "2026-07-15T21:00:00+09:00",
                "next_eligible_at": "2026-07-15T21:05:00+09:00",
            },
            "next_action": "continue_bounded_paper_replay_reconciliation",
            "operator_message": "과거장 대사 115/757 / 남은 642건 / 다음 조치 continue_bounded_paper_replay_reconciliation",
        }
        learning = {
            "schema": "codexstock_ai_staff_learning_audit_v4",
            "verification_capability_ready": True,
            "counterfactual_control_required": True,
            "effect_confidence_gate_required": True,
            "growth_outcome_proven": False,
            "verification_state": "verification_pending",
            "staff_count": 4,
            "growth_proven_staff_count": 0,
            "validated_learning_pair_count": 0,
            "improved_learning_pair_count": 0,
            "effect_confidence_proven_staff_count": 0,
            "learning_experiment_contract_ready": True,
            "learning_experiment_contract_path": "C:/tmp/ai_staff_learning_experiment_contract.json",
            "learning_experiment_contract_hash": "hash",
            "counterfactual_ledger_triplet_count": 1,
            "counterfactual_ledger_improved_triplet_count": 0,
            "official_learning_source_readiness": {
                "schema": "codexstock_ai_staff_learning_source_readiness_v1",
                "staff_count": 4,
                "source_ready_staff_count": 0,
                "source_blocked_staff_count": 4,
                "historical_replay_dependency_active": True,
                "deep_progress_label": "100/757",
                "dominant_blockers": [
                    {"reason": "source_replay_not_in_deep_verified_milestone", "count": 4}
                ],
                "next_action": "complete_historical_replay_and_bias_evidence_for_learning_sources",
                "operator_message": "직원 공식 학습 원천 0/4명 준비. 과거장 깊은 검증 100/757",
            },
            "policy": {"unverified_result_affects_score": False},
        }
        learning_contract_status = {
            "ready": True,
            "hash_valid": True,
            "safe_to_execute_paper": True,
            "runnable_count": 0,
            "blocked_count": 4,
        }
        learning_queue = {
            "ok": True,
            "job_count": 36,
            "strategy_triplet_count": 12,
            "safe_to_execute_paper": True,
            "next_action": "run_paper_counterfactual_triplet_batch",
            "path": "C:/tmp/ai_staff_learning_counterfactual_queue.json",
            "queue_hash": "queue-hash",
        }
        learning_schedule = {
            "status": "deferred_to_market_closed_window",
            "ready_to_run": False,
            "blockers": ["large_batch_window_not_allowed"],
            "next_action": "defer_staff_learning_counterfactual_triplets",
            "operator_message": "직원 학습 검증 보류: premarket 우선 모드라 Paper 트리플릿 12개를 장마감/주말 슬롯으로 미룹니다.",
            "large_batch_jobs_allowed": False,
            "market_priority_active": True,
            "heavy_slot_available": True,
        }
        learning_preregistration = {
            "ok": True,
            "schema": "codexstock_ai_staff_learning_counterfactual_preregistration_status_v1",
            "status": "REGISTERED",
            "found": True,
            "valid": True,
            "hash_valid": True,
            "ready_for_future_execution": True,
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "first_eligible_run_date": "2026-09-21",
            "contract_id": "LCFPR-test",
            "contract_hash": "prereg-hash",
            "contract_generated_at": "2026-07-17T19:06:53+09:00",
            "registered_plan_count": 2,
            "blocked_plan_count": 2,
            "registered_contestant_ids": ["operator", "researcher"],
            "contract_outcome_state": "FUTURE_LOCKED",
            "contract_registered_triplet_count": 2,
            "contract_completed_triplet_count": 0,
            "contract_remaining_triplet_count": 2,
            "contract_missing_contestant_ids": ["operator", "researcher"],
            "all_registered_plans_completed": False,
            "contract_result_evidence_ready": False,
            "contract_result_catch_up_after_restart": True,
            "strategy_lock_ready": True,
            "strategy_lock_plan_count": 2,
            "strategy_lock_signature_count": 4,
            "strategy_lock_digest": "a" * 64,
            "execution_strategy_revalidation_required": True,
            "full_strategy_payload_exposed": False,
            "generated_before_target_start": True,
            "blockers": [],
            "next_action": "wait_for_locked_target_period_to_complete",
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        score = {
            "ok": True,
            "summary": {
                "dedup_policy_expected_version": suite.SCORE_DEDUP_POLICY_VERSION,
                "dedup_policy_missing_count": 0,
                "score_contract_failed_count": 0,
                "display_score_98_or_more_count": 0,
            },
        }
        pulse = {
            "schema": "codexstock_intraday_market_pulse_v1",
            "source_status": [
                {"source": source, "ok": True}
                for source in ("amount", "volume", "gainers", "losers", "foreign", "institution")
            ],
            "alerts": [],
        }
        live = {
            "ok": True,
            "summary": {
                "pending_reconciliation_count": 0,
                "partial_count": 0,
                "account_ledger_mismatch_count": 0,
                "active_account_ledger_mismatch_count": 0,
                "active_account_ledger_incomplete_count": 0,
                "dual_path_hard_block": False,
            },
        }
        sqlite = {
            "status": "ready",
            "summary": {"sqlite_file_count": 2, "problem_sqlite_count": 0, "max_query_ms": 2.0},
        }
        engines = {
            "on_demand_audit": {
                "schema": "codexstock_external_engine_on_demand_audit_v1",
                "status": "passed",
                "engine_count": 9,
                "persistent_heavy_engine_count": 0,
                "max_concurrent_external_jobs": 1,
                "blockers": [],
            }
        }
        health = {
            "checks": [
                {
                    "id": "ops_status",
                    "action": "none",
                    "operational_state": "normal",
                    "operational_state_label": "정상",
                    "operational_state_description": "마지막 점검과 성공 기록이 유효합니다.",
                    "operational_severity": "ok",
                    "status_badge": "정상",
                    "last_checked_at": "2026-07-15T00:00:00+09:00",
                    "last_success_at": "2026-07-15T00:00:00+09:00",
                    "success_evidence_status": "verified",
                    "success_evidence_label": "success evidence available",
                }
            ],
            "lifecycle_contract": {
                "ok": True,
                "missing_field_count": 0,
                "invalid_state_ids": [],
            },
        }
        surface = {
            "ok": True,
            "ui_button_count": 131,
            "ui_button_unbound_count": 0,
            "ui_api_missing_count": 0,
            "mcp_tool_count": 146,
            "mcp_tool_unhandled_count": 0,
        }

        patches = (
            patch.object(suite, "build_unified_market_context_snapshot", return_value=context),
            patch.object(suite, "build_market_news_evidence", return_value=news),
            patch.object(suite, "load_ai_staff_long_horizon_benchmark", return_value=long_horizon),
            patch.object(suite, "historical_replay_completion_audit", return_value=replay),
            patch.object(
                suite,
                "load_historical_replay_completion_certificate",
                return_value={"ok": False, "status": "missing"},
            ),
            patch.object(suite, "ai_staff_learning_audit", return_value=learning),
            patch.object(suite, "build_ai_staff_learning_experiment_status", return_value=learning_contract_status),
            patch.object(suite, "build_ai_staff_learning_counterfactual_queue", return_value=learning_queue),
            patch.object(suite, "build_ai_staff_learning_counterfactual_scheduler_status", return_value=learning_schedule),
            patch.object(
                suite,
                "build_ai_staff_learning_counterfactual_preregistration_status",
                return_value=learning_preregistration,
            ),
            patch.object(suite, "_score_saturation_feature_probe", return_value=score),
            patch.object(suite, "build_intraday_market_pulse", return_value=pulse),
            patch.object(suite, "build_live_reconciliation_audit", return_value=live),
            patch.object(suite, "_sqlite_storage_feature_probe", return_value=sqlite),
            patch.object(suite, "build_external_engine_dashboard", return_value=engines),
            patch.object(suite.AI_DAEMON, "status", return_value={"worker_board": {}}),
            patch.object(
                suite,
                "build_ai_tournament_monte_carlo_evidence_audit",
                return_value={
                    "schema": "codexstock_monte_carlo_evidence_audit_v1",
                    "passed": False,
                    "outcome_metrics_used_for_selection": False,
                    "retraining_plan": {"schema": "codexstock_monte_carlo_stress_retraining_plan_v1"},
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "_promotion_rehearsal_evidence_audit",
                return_value={"schema": "codexstock_promotion_rehearsal_evidence_audit_v2"},
            ),
            patch.object(
                suite,
                "_promotion_rehearsal_readiness",
                return_value={
                    "schema": "codexstock_promotion_rehearsal_readiness_v1",
                    "ready": False,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(
                suite,
                "build_promotion_forward_observation_audit",
                return_value={
                    "schema": "codexstock_promotion_forward_observation_audit_v1",
                    "ready": False,
                    "required_calendar_days": 90,
                    "minimum_session_coverage_pct": 95.0,
                    "paper_only": True,
                    "live_order_allowed": False,
                },
            ),
            patch.object(suite, "build_feature_health_board", return_value=health),
            patch.object(suite, "_feature_surface_contract_probe", return_value=surface),
        )
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

        result = suite.build_codexstock_weakness_completion_audit(force=True)

        self.assertEqual("codexstock_weakness_completion_audit_v1", result["schema"])
        self.assertEqual("10/10 (100%)", result["summary"]["implementation_label"])
        self.assertEqual("6/10 (60%)", result["summary"]["evidence_label"])
        objective_scope = result["objective_scope"]
        self.assertEqual("codexstock_remaining_weakness_objective_scope_v1", objective_scope["schema"])
        self.assertEqual(8, objective_scope["track_count"])
        objective_tracks = {row["id"]: row for row in objective_scope["tracks"]}
        self.assertTrue(
            objective_tracks["paper_candidate_provenance_and_discovery"]["system_ready"]
        )
        self.assertTrue(
            objective_tracks["paper_candidate_provenance_and_discovery"]["current_outcome_passed"]
        )
        self.assertTrue(objective_tracks["monte_carlo_stress_evidence"]["system_ready"])
        self.assertFalse(objective_tracks["monte_carlo_stress_evidence"]["current_outcome_passed"])
        self.assertTrue(objective_tracks["paper_rehearsal_evidence"]["system_ready"])
        self.assertFalse(objective_tracks["paper_rehearsal_evidence"]["current_outcome_passed"])
        self.assertTrue(objective_tracks["forward_90_day_evidence"]["system_ready"])
        self.assertFalse(objective_tracks["forward_90_day_evidence"]["current_outcome_passed"])
        self.assertEqual([2, 3, 4, 5], [row["id"] for row in result["items"] if row["status"] == "verification_pending"])
        replay_row = next(row for row in result["items"] if row["id"] == 4)
        self.assertEqual(18.5, replay_row["evidence"]["estimated_hours_remaining"])
        self.assertEqual("weekday_after_hours_bounded", replay_row["evidence"]["schedule_mode"])
        self.assertEqual(
            "continue_bounded_paper_replay_reconciliation",
            replay_row["evidence"]["next_action"],
        )
        self.assertIn("과거장 대사 115/757", replay_row["evidence"]["operator_message"])
        learning_row = next(row for row in result["items"] if row["id"] == 5)
        self.assertIn("official_learning_source_not_ready", learning_row["blockers"])
        self.assertEqual(0, learning_row["evidence"]["official_learning_source_ready_staff_count"])
        self.assertEqual(4, learning_row["evidence"]["official_learning_source_blocked_staff_count"])
        self.assertTrue(learning_row["evidence"]["official_learning_source_historical_dependency_active"])
        self.assertEqual("100/757", learning_row["evidence"]["official_learning_source_deep_progress_label"])
        self.assertEqual(
            "complete_historical_replay_and_bias_evidence_for_learning_sources",
            learning_row["evidence"]["official_learning_source_next_action"],
        )
        self.assertEqual(36, learning_row["evidence"]["learning_counterfactual_queue_job_count"])
        self.assertEqual(12, learning_row["evidence"]["learning_counterfactual_queue_triplet_count"])
        self.assertTrue(learning_row["evidence"]["learning_counterfactual_queue_safe_to_execute_paper"])
        self.assertEqual(
            "run_paper_counterfactual_triplet_batch",
            learning_row["evidence"]["learning_counterfactual_queue_next_action"],
        )
        self.assertEqual(
            "deferred_to_market_closed_window",
            learning_row["evidence"]["learning_counterfactual_schedule_status"],
        )
        self.assertFalse(learning_row["evidence"]["learning_counterfactual_schedule_ready_to_run"])
        self.assertEqual(
            "defer_staff_learning_counterfactual_triplets",
            learning_row["evidence"]["learning_counterfactual_schedule_next_action"],
        )
        self.assertIn(
            "직원 학습 검증 보류",
            learning_row["evidence"]["learning_counterfactual_schedule_operator_message"],
        )
        self.assertEqual(
            "preregistered_forward_contract_incomplete",
            learning_row["evidence"]["counterfactual_official_blocker"],
        )
        confidence_blockers = set(
            learning_row["evidence"]["counterfactual_confidence_gate_blockers"]
        )
        self.assertTrue(
            {"confidence_interval_not_available", "confidence_interval_low_not_positive"}
            & confidence_blockers
        )
        counterfactual_message = learning_row["evidence"]["counterfactual_operator_message"]
        self.assertTrue(counterfactual_message)
        self.assertTrue(
            "인과 근거" in counterfactual_message or "신뢰구간" in counterfactual_message
        )
        self.assertTrue(learning_row["evidence"]["learning_counterfactual_schedule_market_priority_active"])
        self.assertTrue(learning_row["evidence"]["future_counterfactual_preregistered"])
        self.assertEqual(
            "preregistration_complete_future_outcome_pending",
            learning_row["evidence"]["future_counterfactual_state"],
        )
        self.assertEqual("REGISTERED", learning_row["evidence"]["future_counterfactual_preregistration_status"])
        self.assertTrue(learning_row["evidence"]["future_counterfactual_preregistration_hash_valid"])
        self.assertTrue(learning_row["evidence"]["future_counterfactual_strategy_lock_ready"])
        self.assertEqual(
            4,
            learning_row["evidence"]["future_counterfactual_strategy_lock_signature_count"],
        )
        self.assertEqual(
            "a" * 64,
            learning_row["evidence"]["future_counterfactual_strategy_lock_digest"],
        )
        self.assertTrue(
            learning_row["evidence"][
                "future_counterfactual_execution_strategy_revalidation_required"
            ]
        )
        self.assertEqual("LCFPR-test", learning_row["evidence"]["future_counterfactual_contract_id"])
        self.assertEqual("2026-09-21", learning_row["evidence"]["future_counterfactual_first_eligible_run_date"])
        self.assertEqual(2, learning_row["evidence"]["future_counterfactual_registered_plan_count"])
        self.assertEqual(2, learning_row["evidence"]["future_counterfactual_blocked_plan_count"])
        self.assertEqual(
            "FUTURE_LOCKED",
            learning_row["evidence"]["future_counterfactual_contract_outcome_state"],
        )
        self.assertEqual(
            2,
            learning_row["evidence"][
                "future_counterfactual_contract_registered_triplet_count"
            ],
        )
        self.assertEqual(
            0,
            learning_row["evidence"][
                "future_counterfactual_contract_completed_triplet_count"
            ],
        )
        self.assertEqual(
            2,
            learning_row["evidence"][
                "future_counterfactual_contract_remaining_triplet_count"
            ],
        )
        self.assertFalse(
            learning_row["evidence"]["future_counterfactual_contract_complete"]
        )
        self.assertTrue(learning_row["evidence"]["future_counterfactual_generated_before_target_start"])
        self.assertTrue(learning_row["evidence"]["future_counterfactual_paper_only"])
        self.assertFalse(learning_row["evidence"]["future_counterfactual_live_order_allowed"])
        self.assertIn("same_period_counterfactual_growth_evidence_pending", learning_row["blockers"])
        self.assertIn("preregistered_forward_contract_outcome_pending", learning_row["blockers"])
        self.assertNotIn("future_counterfactual_preregistration_pending", learning_row["blockers"])
        self.assertFalse(result["official_completion_claim_allowed"])
        self.assertTrue(all(row["unverified_result_affects_score"] is False for row in result["items"]))
        self.assertTrue(all(row["unverified_result_affects_live_candidate"] is False for row in result["items"]))
        self.assertEqual("4/10 remaining", result["summary"]["remaining_evidence_label"])
        self.assertEqual([2, 3, 4, 5], [row["id"] for row in result["pending_evidence_summary"]])
        replay_pending = next(row for row in result["pending_evidence_summary"] if row["id"] == 4)
        self.assertEqual("continue_bounded_paper_replay_reconciliation", replay_pending["next_action"])
        self.assertEqual(642, replay_pending["remaining_count"])
        self.assertFalse(replay_pending["market_safe_now"])
        learning_pending = next(row for row in result["pending_evidence_summary"] if row["id"] == 5)
        self.assertEqual("defer_staff_learning_counterfactual_triplets", learning_pending["next_action"])
        self.assertFalse(learning_pending["ready_to_run"])
        self.assertEqual(
            "preregistered_forward_contract_incomplete",
            learning_pending["official_blocker"],
        )
        pending_confidence_blockers = set(learning_pending["confidence_gate_blockers"])
        self.assertTrue(
            {"confidence_interval_not_available", "confidence_interval_low_not_positive"}
            & pending_confidence_blockers
        )
        self.assertIn("sample_count", learning_pending["effect_statistics"])
        self.assertGreaterEqual(learning_pending["effect_statistics"]["sample_count"], 0)
        self.assertTrue(learning_pending["future_counterfactual_preregistered"])
        self.assertEqual(
            "preregistration_complete_future_outcome_pending",
            learning_pending["future_counterfactual_state"],
        )
        self.assertEqual("LCFPR-test", learning_pending["preregistration_contract_id"])
        self.assertEqual("2026-07-20", learning_pending["preregistration_target_start_date"])
        self.assertEqual("2026-09-18", learning_pending["preregistration_target_end_date"])
        self.assertEqual("2026-09-21", learning_pending["preregistration_first_eligible_run_date"])
        self.assertTrue(learning_pending["preregistration_strategy_lock_ready"])
        self.assertEqual(4, learning_pending["preregistration_strategy_lock_signature_count"])
        self.assertEqual("a" * 64, learning_pending["preregistration_strategy_lock_digest"])
        self.assertTrue(learning_pending["execution_strategy_revalidation_required"])
        self.assertEqual(
            "FUTURE_LOCKED",
            learning_pending["preregistration_contract_outcome_state"],
        )
        self.assertEqual(
            2,
            learning_pending["preregistration_contract_registered_triplet_count"],
        )
        self.assertEqual(
            0,
            learning_pending["preregistration_contract_completed_triplet_count"],
        )
        self.assertEqual(
            2,
            learning_pending["preregistration_contract_remaining_triplet_count"],
        )
        self.assertFalse(learning_pending["preregistration_contract_complete"])
        self.assertTrue(learning_pending["preregistration_generated_before_target_start"])
        self.assertTrue(learning_pending["preregistration_paper_only"])
        self.assertFalse(learning_pending["preregistration_live_order_allowed"])
        self.assertTrue(result["pending_evidence_operator_messages"])
        self.assertIn("미검증 결과", result["next_best_actions"][-1])

    def test_growth_signal_cannot_pass_before_every_locked_forward_plan_completes(self):
        growth_proven_learning = {
            "schema": "codexstock_ai_staff_learning_audit_v4",
            "verification_capability_ready": True,
            "counterfactual_control_required": True,
            "effect_confidence_gate_required": True,
            "growth_outcome_proven": True,
            "verification_state": "growth_outcome_proven",
            "staff_count": 2,
            "growth_proven_staff_count": 2,
            "validated_learning_pair_count": 6,
            "improved_learning_pair_count": 6,
            "effect_confidence_proven_staff_count": 2,
            "learning_experiment_contract_ready": True,
            "learning_experiment_contract_path": "C:/tmp/learning-contract.json",
            "learning_experiment_contract_hash": "hash",
            "official_learning_source_readiness": {
                "schema": "codexstock_ai_staff_learning_source_readiness_v1",
                "staff_count": 2,
                "source_ready_staff_count": 2,
                "source_blocked_staff_count": 0,
                "historical_replay_dependency_active": False,
                "dominant_blockers": [],
            },
            "policy": {"unverified_result_affects_score": False},
        }
        self._patch_common_success_dependencies()
        with patch.object(
            suite,
            "ai_staff_learning_audit",
            return_value=growth_proven_learning,
        ):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        learning_row = next(row for row in result["items"] if row["id"] == 5)
        self.assertTrue(learning_row["evidence"]["learning_growth_outcome_proven"])
        self.assertFalse(
            learning_row["evidence"]["future_counterfactual_contract_complete"]
        )
        self.assertFalse(learning_row["current_evidence_passed"])
        self.assertNotIn(
            "same_period_counterfactual_growth_evidence_pending",
            learning_row["blockers"],
        )
        self.assertIn(
            "preregistered_forward_contract_outcome_pending",
            learning_row["blockers"],
        )
        self.assertEqual(
            "preregistered_forward_contract_incomplete",
            learning_row["evidence"]["counterfactual_official_blocker"],
        )
        objective = next(
            row
            for row in result["objective_scope"]["tracks"]
            if row["id"] == "same_period_counterfactual_learning"
        )
        self.assertFalse(objective["current_outcome_passed"])
        self.assertFalse(result["official_completion_claim_allowed"])

    def test_invalid_future_preregistration_is_separate_from_outcome_pending(self):
        context = {
            "schema": "codexstock_unified_market_context_v2",
            "coverage": {
                "total_count": 6,
                "covered_count": 6,
                "fresh_verified_count": 6,
                "decision_context_ready": True,
                "decision_context_blockers": [],
            },
        }
        invalid_preregistration = {
            "ok": False,
            "schema": "codexstock_ai_staff_learning_counterfactual_preregistration_status_v1",
            "status": "INVALID",
            "found": True,
            "valid": False,
            "hash_valid": False,
            "ready_for_future_execution": False,
            "contract_id": "LCFPR-tampered",
            "contract_hash": "tampered-hash",
            "generated_before_target_start": True,
            "blockers": ["learning_preregistration_hash_mismatch"],
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        self._patch_common_success_dependencies()
        with patch.object(
            suite,
            "build_unified_market_context_snapshot",
            return_value=context,
        ), patch.object(
            suite,
            "build_ai_staff_learning_counterfactual_preregistration_status",
            return_value=invalid_preregistration,
        ):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        learning_row = next(row for row in result["items"] if row["id"] == 5)
        self.assertFalse(learning_row["evidence"]["future_counterfactual_preregistered"])
        self.assertEqual(
            "invalid_preregistration_quarantined",
            learning_row["evidence"]["future_counterfactual_state"],
        )
        self.assertIn("same_period_counterfactual_growth_evidence_pending", learning_row["blockers"])
        self.assertIn("future_counterfactual_preregistration_invalid", learning_row["blockers"])
        self.assertEqual(
            ["learning_preregistration_hash_mismatch"],
            learning_row["evidence"]["future_counterfactual_preregistration_blockers"],
        )


class GptTechnicalReviewStatusTests(unittest.TestCase):
    def test_review_separates_ready_systems_from_time_dependent_evidence(self):
        snapshot = {
            "recorded_at": "2026-07-18T09:00:00+09:00",
            "snapshot_id": "ops-1234567890abcdef1234",
            "source_component": "test",
            "sequence_number": 1,
            "expires_at": "2026-07-18T09:01:00+09:00",
        }
        dashboard = {
            "summary": {"round_trip_verified_count": 3},
            "sequential_execution_contract": {
                "mode": "one_heavy_engine_at_a_time",
                "configured_order": ["vectorbt", "nautilus", "lean"],
                "max_concurrent_heavy_jobs": 1,
                "latest_cycle": {"status": "COMPLETED"},
                "ledger_paths": {"jobs": "C:/tmp/jobs.jsonl"},
                "live_order_allowed": False,
            },
        }
        universe = {
            "contract_ready": True,
            "complete_history_ready": False,
            "blockers": ["official_point_in_time_history_not_complete_from_2000"],
        }
        forward = {
            "schema": "codexstock_promotion_forward_observation_audit_v1",
            "required_calendar_days": 90,
            "minimum_session_coverage_pct": 95.0,
            "ready": False,
            "verified_forward_days": 0,
            "session_coverage_pct": 0.0,
            "paper_only": True,
            "live_order_allowed": False,
        }
        mcp = {
            "ok": True,
            "tool_count": 161,
            "server_schema_sha256": "a" * 64,
            "client_exposure": {"status": "MATCHED", "schema_match": True},
        }
        reconciliation = {
            "ok": True,
            "summary": {
                "pending_reconciliation_count": 0,
                "unknown_submit_outcome_count": 0,
            },
        }

        result = suite._build_gpt_technical_review_status(
            state_snapshot=snapshot,
            engine_dashboard=dashboard,
            point_in_time_universe=universe,
            forward_observation=forward,
            learning_system_ready=True,
            learning_evidence_passed=False,
            mcp_manifest=mcp,
            live_reconciliation=reconciliation,
        )

        self.assertEqual(7, result["summary"]["axis_count"])
        self.assertEqual(7, result["summary"]["system_ready_count"])
        self.assertEqual(4, result["summary"]["evidence_passed_count"])
        self.assertEqual("verification_pending", result["status"])
        self.assertFalse(result["official_completion_claim_allowed"])
        universe_axis = next(
            row for row in result["axes"] if row["id"] == "point_in_time_universe"
        )
        self.assertTrue(universe_axis["system_ready"])
        self.assertFalse(universe_axis["current_evidence_passed"])
        self.assertEqual("verification_pending", universe_axis["status"])

    def test_review_reports_unobserved_mcp_client_without_claiming_sync(self):
        snapshot = suite._new_operational_snapshot("test", ttl_seconds=5)
        result = suite._build_gpt_technical_review_status(
            state_snapshot=snapshot,
            engine_dashboard={},
            point_in_time_universe={"contract_ready": True, "complete_history_ready": True},
            forward_observation={
                "schema": "codexstock_promotion_forward_observation_audit_v1",
                "required_calendar_days": 90,
                "minimum_session_coverage_pct": 95.0,
                "ready": True,
                "paper_only": True,
                "live_order_allowed": False,
            },
            learning_system_ready=True,
            learning_evidence_passed=True,
            mcp_manifest={
                "ok": True,
                "tool_count": 161,
                "server_schema_sha256": "a" * 64,
                "client_exposure": {
                    "status": "CLIENT_EXPOSURE_UNOBSERVED",
                    "schema_match": None,
                },
            },
            live_reconciliation={
                "ok": True,
                "summary": {
                    "pending_reconciliation_count": 0,
                    "unknown_submit_outcome_count": 0,
                },
            },
        )

        mcp_axis = next(row for row in result["axes"] if row["id"] == "mcp_schema_sync")
        self.assertTrue(mcp_axis["system_ready"])
        self.assertFalse(mcp_axis["current_evidence_passed"])
        self.assertIn("chatgpt_connector_observation_pending", mcp_axis["blockers"])
        self.assertTrue(mcp_axis["evidence"]["server_publish_complete"])
        self.assertTrue(mcp_axis["evidence"]["server_publication_evidence_passed"])
        self.assertFalse(mcp_axis["evidence"]["server_side_filter_active"])


if __name__ == "__main__":
    unittest.main()
