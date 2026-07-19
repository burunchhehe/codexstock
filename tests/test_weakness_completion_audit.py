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
            "same_period_auto_judgement_due": False,
            "same_period_auto_judgement_status": "WAITING_FOR_LOCKED_PERIOD",
            "same_period_auto_judgement_target_start_date": "2026-07-20",
            "same_period_auto_judgement_target_end_date": "2026-09-18",
            "same_period_auto_judgement_first_eligible_run_date": "2026-09-21",
            "same_period_auto_judgement_days_until_due": 68,
            "same_period_auto_judgement_remaining_triplet_count": 2,
            "same_period_auto_judgement_required_action": "wait_for_locked_target_period_to_complete",
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
            "same_period_auto_judgement_due": False,
            "same_period_auto_judgement_status": "WAITING_FOR_LOCKED_PERIOD",
            "same_period_auto_judgement_target_start_date": "2026-07-20",
            "same_period_auto_judgement_target_end_date": "2026-09-18",
            "same_period_auto_judgement_first_eligible_run_date": "2026-09-21",
            "same_period_auto_judgement_days_until_due": 68,
            "same_period_auto_judgement_remaining_triplet_count": 2,
            "same_period_auto_judgement_required_action": "wait_for_locked_target_period_to_complete",
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
            "same_period_auto_judgement_due": False,
            "same_period_auto_judgement_status": "WAITING_FOR_LOCKED_PERIOD",
            "same_period_auto_judgement_target_start_date": "2026-07-20",
            "same_period_auto_judgement_target_end_date": "2026-09-18",
            "same_period_auto_judgement_first_eligible_run_date": "2026-09-21",
            "same_period_auto_judgement_days_until_due": 68,
            "same_period_auto_judgement_remaining_triplet_count": 2,
            "same_period_auto_judgement_required_action": "wait_for_locked_target_period_to_complete",
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
            patch.object(
                suite,
                "build_ai_staff_learning_decision_reflection_audit",
                return_value={
                    "schema": "codexstock_ai_staff_learning_decision_reflection_audit_v1",
                    "status": "decision_reflection_gap",
                    "staff_count": 0,
                    "prior_history_staff_count": 0,
                    "unsafe_known_regressed_repeat_count": 0,
                    "historical_repeat_guard_verified": False,
                    "next_decision_reflection_verified": False,
                    "performance_improvement_proven": False,
                    "effect_statistics": {"sample_count": 0},
                    "next_action": "repair_next_decision_feedback_path",
                    "paper_only": True,
                    "live_order_allowed": False,
                    "automatic_promotion": False,
                    "official_performance_claim_allowed": False,
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

    def test_durable_cache_rejects_old_weakness_evidence_contract(self):
        cached = {
            "schema": "codexstock_weakness_completion_audit_v1",
            "objective_scope": {
                "schema": "codexstock_remaining_weakness_objective_scope_v1"
            },
            "technical_review": {
                "schema": "codexstock_gpt_technical_review_status_v1"
            },
            "snapshot_id": "ops-old-cache",
            "sequence_number": 1,
            "summary": {
                "current_evidence_passed_count": 8,
            },
            "items": [],
            "live_order_allowed": False,
            "unverified_result_affects_score": False,
            "unverified_result_affects_live_candidate": False,
        }

        self.assertFalse(suite._weakness_completion_durable_cache_valid(cached))

    def test_durable_cache_accepts_current_period_cost_evidence_contract(self):
        cached = {
            "schema": "codexstock_weakness_completion_audit_v1",
            "evidence_contract_version": (
                suite.WEAKNESS_COMPLETION_AUDIT_EVIDENCE_CONTRACT_VERSION
            ),
            "objective_scope": {
                "schema": "codexstock_remaining_weakness_objective_scope_v1"
            },
            "technical_review": {
                "schema": "codexstock_gpt_technical_review_status_v1"
            },
            "snapshot_id": "ops-current-cache",
            "sequence_number": 2,
            "summary": {
                "current_evidence_passed_count": 8,
                "current_evidence_passed_pct": 80.0,
            },
            "items": [
                {
                    "id": "long_horizon_benchmark_costs",
                    "evidence": {
                        "benchmark_period_contract_ok": True,
                        "benchmark_cost_contract_ok": True,
                        "staff_market_cost_contract_ok": True,
                    },
                }
            ],
            "live_order_allowed": False,
            "unverified_result_affects_score": False,
            "unverified_result_affects_live_candidate": False,
        }

        self.assertTrue(suite._weakness_completion_durable_cache_valid(cached))

    def test_refresh_timeout_is_fail_closed_and_visible(self):
        cached = {
            "ok": True,
            "schema": "codexstock_weakness_completion_audit_v1",
            "status": "verification_pending",
            "refresh_timed_out": True,
            "official_completion_claim_allowed": True,
            "unverified_result_affects_score": True,
            "unverified_result_affects_live_candidate": True,
            "live_order_allowed": True,
        }
        with patch.object(
            suite.WEAKNESS_COMPLETION_STATUS_CACHE,
            "get",
            return_value=cached,
        ):
            result = suite.build_codexstock_weakness_completion_audit(force=False)

        self.assertFalse(result["ok"])
        self.assertEqual("refresh_timeout", result["status"])
        self.assertFalse(result["official_completion_claim_allowed"])
        self.assertFalse(result["unverified_result_affects_score"])
        self.assertFalse(result["unverified_result_affects_live_candidate"])
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

    def test_refresh_mode_requests_background_update_without_deep_blocking(self):
        cached = {
            "ok": True,
            "schema": "codexstock_weakness_completion_audit_v1",
            "status": "verification_pending",
            "official_completion_claim_allowed": False,
            "live_order_allowed": False,
        }
        with patch.object(
            suite.WEAKNESS_COMPLETION_STATUS_CACHE,
            "request_refresh",
            return_value=cached,
        ) as request_refresh, patch.object(
            suite,
            "_build_codexstock_weakness_completion_audit_uncached",
        ) as uncached:
            result = suite.build_codexstock_weakness_completion_audit(
                force=True,
                refresh=True,
            )

        self.assertTrue(result["refresh_requested"])
        self.assertFalse(result["official_completion_claim_allowed"])
        self.assertFalse(result["live_order_allowed"])
        request_refresh.assert_called_once_with()
        uncached.assert_not_called()

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

    def test_news_audit_accepts_event_level_independent_original_sources(self):
        news = {
            "schema": "codexstock_market_news_evidence_v1",
            "summary": {
                "news_count": 2,
                "verified_count": 0,
                "verified_article_claim_count": 0,
                "original_source_confirmed_count": 2,
                "multi_source_original_count": 0,
                "event_multi_source_original_count": 2,
                "official_disclosure_corroborated_count": 0,
                "official_disclosure_primary_count": 0,
                "official_disclosure_requirement_status": "not_applicable_no_dart_eligible_article",
                "max_independent_original_domain_count": 1,
                "missing_independent_original_domain_count": 1,
            },
            "policy": {
                "headline_only_is_verified": False,
                "unverified_news_affects_score": False,
            },
            "evidence_gap": {
                "independent_multi_source_requirement_satisfied": True,
                "next_actions": [
                    "do_not_allow_headline_only_news_to_affect_score_or_live_order"
                ],
            },
            "external_collection_response_evidence": {
                "enabled": True,
                "source_usable": True,
                "file_exists": True,
                "active_response_file": r"C:\external-search-mcp\codexstock_outbox\market_news_evidence_collection_response.json",
                "response_read_files": [
                    r"C:\Users\김진우\AppData\Local\CodexStock\data\market_news_evidence_collection_response.json",
                    r"C:\external-search-mcp\codexstock_outbox\market_news_evidence_collection_response.json",
                ],
                "response_write_file": r"C:\Users\김진우\AppData\Local\CodexStock\data\market_news_evidence_collection_response.json",
                "accepted_source_record_count": 2,
                "matched_event_count": 1,
                "blockers": [],
            },
            "rows": [
                {
                    "original_source_resolutions": [{"url": "https://news.example/a"}],
                    "independent_original_domain_count": 1,
                    "official_disclosure_matches": [],
                    "score_allowed": False,
                    "live_order_allowed": False,
                },
                {
                    "original_source_resolutions": [{"url": "https://press.example/b"}],
                    "independent_original_domain_count": 1,
                    "official_disclosure_matches": [],
                    "score_allowed": False,
                    "live_order_allowed": False,
                },
            ],
        }
        self._patch_common_success_dependencies()
        with patch.object(suite, "build_market_news_evidence", return_value=news):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        news_row = next(row for row in result["items"] if row["id"] == 2)
        self.assertEqual("passed", news_row["status"])
        self.assertTrue(news_row["current_evidence_passed"])
        self.assertEqual(
            "event_level",
            news_row["evidence"]["independent_multi_source_pass_basis"],
        )
        response_status = news_row["evidence"]["external_collection_response_status"]
        self.assertTrue(response_status["source_usable"])
        self.assertTrue(response_status["file_exists"])
        self.assertEqual(2, response_status["accepted_source_record_count"])
        self.assertEqual(
            "/api/market/news-evidence-collection-response-status",
            response_status["status_endpoint"],
        )
        self.assertFalse(response_status["score_allowed"])
        self.assertFalse(response_status["live_order_allowed"])
        self.assertEqual(0, news_row["evidence"]["verified_article_claim_count"])
        self.assertFalse(result["unverified_result_affects_score"])
        self.assertFalse(result["live_order_allowed"])

    def test_long_horizon_audit_exposes_period_and_market_cost_contract(self):
        cost_model = {
            "policy_version": suite.PAPER_COST_POLICY_VERSION,
            "base_currency": "KRW",
            "commission_bps_each_side": suite.DEFAULT_PAPER_COMMISSION_BPS,
            "slippage_bps_each_side": suite.DEFAULT_PAPER_SLIPPAGE_BPS,
            "fx_conversion_spread_bps_each_side": suite.DEFAULT_PAPER_FX_SPREAD_BPS,
            "us_regulatory_fee_policy_version": suite.PAPER_US_REGULATORY_POLICY_VERSION,
        }
        long_horizon = {
            "schema": "codexstock_ai_staff_long_horizon_v2",
            "start_date": "2000-01-03",
            "end_date": "2026-01-02",
            "benchmark_measurement_window": {
                "status": "common_staff_actual_window",
                "start_date": "2000-01-03",
                "end_date": "2026-01-02",
            },
            "benchmark": {
                "schema": "codexstock_long_horizon_benchmark_v3",
                "requested_start_date": "2000-01-03",
                "requested_end_date": "2026-01-02",
                "first_date": "2000-01-03",
                "last_date": "2026-01-02",
                "comparison_currency": "KRW",
                "krw_adjusted_cagr_pct": 9.37,
                "net_costed_krw_cagr_pct": 9.36,
                "currency_conversion_validated": True,
                "transaction_cost_validated": True,
                "transaction_cost_profile": {
                    **cost_model,
                    "application": "fractional_buy_and_hold_round_trip",
                },
                "fx_policy_version": "ecos-boundary-fallback.v1",
                "usdkrw_future_value_used": False,
                "input_data_hash": "benchmark-input-hash",
                "evidence_hash": "benchmark-evidence-hash",
            },
            "staff": [
                {
                    "cost_model": cost_model,
                    "performance_evidence": {
                        "schema": "codexstock_long_horizon_performance_evidence_v1",
                        "passed": True,
                    },
                }
                for _ in range(4)
            ],
        }

        self._patch_common_success_dependencies()
        with patch.object(suite, "load_ai_staff_long_horizon_benchmark", return_value=long_horizon):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        row = next(item for item in result["items"] if item["id"] == 3)
        evidence = row["evidence"]
        self.assertEqual("passed", row["status"])
        self.assertTrue(evidence["benchmark_period_contract_ok"])
        self.assertTrue(evidence["benchmark_cost_contract_ok"])
        self.assertTrue(evidence["staff_market_cost_contract_ok"])
        self.assertEqual(suite.PAPER_COST_POLICY_VERSION, evidence["cost_policy_version"])
        self.assertEqual("KRW", evidence["benchmark_cost_base_currency"])
        self.assertEqual("ecos-boundary-fallback.v1", evidence["benchmark_fx_policy_version"])
        self.assertFalse(evidence["benchmark_usdkrw_future_value_used"])
        self.assertEqual("benchmark-input-hash", evidence["benchmark_input_data_hash"])

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

    def test_objective_scope_reports_stale_ai_worker_evidence_ids(self):
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
        workers = [
            {
                "id": worker_id,
                "status_contract": suite.AI_WORKER_STATUS_CONTRACT_VERSION,
                "status_code": "stale" if worker_id == "operator" else "monitoring",
                "is_active": worker_id != "operator",
                "evidence_status": "stale" if worker_id == "operator" else "recent",
                "decision_role": worker_id in {"operator", "risk", "research_market", "research_strategy"},
                "decision_eligible": worker_id not in {"operator"},
            }
            for worker_id in suite.AI_RUNTIME_WORKER_IDS
        ]
        worker_board = {
            "schema": "codexstock_ai_worker_board_v3",
            "status_contract": suite.AI_WORKER_STATUS_CONTRACT_VERSION,
            "workers": workers,
            "status_counts": {"stale": 1, "monitoring": len(workers) - 1},
            "evidence_freshness": {
                "policy": "role_based_fail_closed",
                "all_active_statuses_truthful": True,
                "stale_worker_ids": ["operator"],
                "missing_required_worker_ids": [],
                "decision_ineligible_worker_ids": ["operator"],
            },
        }
        self._patch_common_success_dependencies()
        with patch.object(
            suite,
            "build_unified_market_context_snapshot",
            return_value=context,
        ), patch.object(
            suite.AI_DAEMON,
            "status",
            return_value={"worker_board": worker_board},
        ):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        objective_tracks = {
            row["id"]: row for row in result["objective_scope"]["tracks"]
        }
        worker_track = objective_tracks["ai_worker_freshness"]

        self.assertTrue(worker_track["system_ready"])
        self.assertFalse(worker_track["current_outcome_passed"])
        self.assertEqual(["operator"], worker_track["detail"]["stale_worker_ids"])
        self.assertEqual(
            ["operator"],
            worker_track["detail"]["decision_ineligible_worker_ids"],
        )
        self.assertEqual([], worker_track["detail"]["active_with_unusable_evidence_ids"])

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
            "next_decision_reflection_evidence_pending",
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

    def test_learning_growth_requires_decision_reflection_and_performance_audit(self):
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
        complete_preregistration = {
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
            "contract_id": "LCFPR-complete",
            "contract_hash": "prereg-hash",
            "contract_generated_at": "2026-07-17T19:06:53+09:00",
            "registered_plan_count": 2,
            "blocked_plan_count": 0,
            "registered_contestant_ids": ["operator", "researcher"],
            "contract_outcome_state": "COMPLETED",
            "contract_registered_triplet_count": 2,
            "contract_completed_triplet_count": 2,
            "contract_remaining_triplet_count": 0,
            "contract_missing_contestant_ids": [],
            "all_registered_plans_completed": True,
            "contract_result_evidence_ready": True,
            "contract_result_catch_up_after_restart": False,
            "strategy_lock_ready": True,
            "strategy_lock_plan_count": 2,
            "strategy_lock_signature_count": 4,
            "strategy_lock_digest": "b" * 64,
            "execution_strategy_revalidation_required": True,
            "full_strategy_payload_exposed": False,
            "generated_before_target_start": True,
            "blockers": [],
            "next_action": "review_completed_locked_forward_counterfactual_outcome",
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        reflection_pending = {
            "schema": "codexstock_ai_staff_learning_decision_reflection_audit_v1",
            "status": "decision_reflection_verified_performance_pending",
            "staff_count": 2,
            "prior_history_staff_count": 2,
            "unsafe_known_regressed_repeat_count": 0,
            "historical_repeat_guard_verified": True,
            "next_decision_reflection_verified": True,
            "performance_improvement_proven": False,
            "effect_statistics": {"sample_count": 2, "confidence_gate_passed": False},
            "next_action": "continue_new_independent_paper_periods_until_confidence_lower_bound_is_positive",
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
            "official_performance_claim_allowed": False,
        }
        reflection_passed = {
            **reflection_pending,
            "status": "decision_and_performance_verified",
            "performance_improvement_proven": True,
            "effect_statistics": {"sample_count": 6, "confidence_gate_passed": True},
            "next_action": "retain_verified_policy_and_monitor_forward_performance",
            "official_performance_claim_allowed": True,
        }

        self._patch_common_success_dependencies()
        with (
            patch.object(suite, "ai_staff_learning_audit", return_value=growth_proven_learning),
            patch.object(
                suite,
                "build_ai_staff_learning_counterfactual_preregistration_status",
                return_value=complete_preregistration,
            ),
            patch.object(
                suite,
                "build_ai_staff_learning_decision_reflection_audit",
                return_value=reflection_pending,
            ),
        ):
            pending_result = suite.build_codexstock_weakness_completion_audit(force=True)

        pending_row = next(row for row in pending_result["items"] if row["id"] == 5)
        self.assertFalse(pending_row["current_evidence_passed"])
        self.assertTrue(pending_row["evidence"]["learning_decision_reflection_verified"])
        self.assertFalse(
            pending_row["evidence"]["learning_decision_reflection_performance_verified"]
        )
        self.assertIn(
            "next_decision_reflection_performance_evidence_pending",
            pending_row["blockers"],
        )

        with (
            patch.object(suite, "ai_staff_learning_audit", return_value=growth_proven_learning),
            patch.object(
                suite,
                "build_ai_staff_learning_counterfactual_preregistration_status",
                return_value=complete_preregistration,
            ),
            patch.object(
                suite,
                "build_ai_staff_learning_decision_reflection_audit",
                return_value=reflection_passed,
            ),
        ):
            passed_result = suite.build_codexstock_weakness_completion_audit(force=True)

        passed_row = next(row for row in passed_result["items"] if row["id"] == 5)
        self.assertTrue(passed_row["current_evidence_passed"])
        self.assertTrue(
            passed_row["evidence"]["learning_decision_reflection_performance_verified"]
        )
        self.assertNotIn(
            "next_decision_reflection_performance_evidence_pending",
            passed_row["blockers"],
        )
        objective = next(
            row
            for row in passed_result["objective_scope"]["tracks"]
            if row["id"] == "same_period_counterfactual_learning"
        )
        self.assertTrue(objective["current_outcome_passed"])
        self.assertTrue(objective["detail"]["decision_and_performance_verified"])

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

    def test_forward_ab_overdue_today_is_promoted_to_weakness_blocker(self):
        self._patch_common_success_dependencies()
        overdue_status = {
            "ok": True,
            "schema": "codexstock_ai_staff_90_session_forward_ab_status_v1",
            "status": "FROZEN_FORWARD_PAPER_RUNNING",
            "contract_id": "FAB90-overdue",
            "completed_trading_sessions": 0,
            "required_trading_sessions": 90,
            "progress_pct": 0.0,
            "next_required_observation_date": "2026-07-20",
            "collection_health": "OVERDUE_TODAY",
            "current_session_observation_due": True,
            "current_session_observation_overdue": True,
            "missed_required_observation_count": 0,
            "missed_required_observation_dates": [],
            "evidence_blockers": ["forward_ab_required_session_evidence_overdue_today"],
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        with patch.object(
            suite,
            "build_ai_staff_90_session_forward_ab_status",
            return_value=overdue_status,
        ):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        learning_row = next(row for row in result["items"] if row["id"] == 5)
        self.assertIn(
            "forward_ab_90_session_observation_overdue_today",
            learning_row["blockers"],
        )
        self.assertEqual(
            "OVERDUE_TODAY",
            learning_row["evidence"]["forward_ab_90_session_collection_health"],
        )

    def test_forward_ab_final_evaluation_due_is_promoted_to_weakness_blocker(self):
        self._patch_common_success_dependencies()
        due_status = {
            "ok": True,
            "schema": "codexstock_ai_staff_90_session_forward_ab_status_v1",
            "status": "COMPLETED_PENDING_FINAL_AB_EVALUATION",
            "contract_id": "FAB90-final-due",
            "completed_trading_sessions": 90,
            "required_trading_sessions": 90,
            "progress_pct": 100.0,
            "first_eligible_evaluation_date": "2026-11-25",
            "days_until_final_ab_evaluation": 0,
            "next_required_observation_date": "",
            "collection_health": "HEALTHY",
            "current_session_observation_due": False,
            "current_session_observation_overdue": False,
            "missed_required_observation_count": 0,
            "missed_required_observation_dates": [],
            "final_ab_evaluation_status": "FINAL_AB_EVALUATION_DUE",
            "final_ab_evaluation_due": True,
            "automatic_final_ab_evaluation_required": True,
            "evidence_blockers": ["forward_ab_final_evaluation_due"],
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
        }
        with patch.object(
            suite,
            "build_ai_staff_90_session_forward_ab_status",
            return_value=due_status,
        ):
            result = suite.build_codexstock_weakness_completion_audit(force=True)

        learning_row = next(row for row in result["items"] if row["id"] == 5)
        self.assertIn(
            "forward_ab_90_session_final_evaluation_due",
            learning_row["blockers"],
        )
        self.assertEqual(
            "COMPLETED_PENDING_FINAL_AB_EVALUATION",
            learning_row["evidence"]["forward_ab_90_session_status"],
        )

    def test_same_period_auto_judgement_status_is_visible_in_learning_evidence(self):
        self._patch_common_success_dependencies()
        result = suite.build_codexstock_weakness_completion_audit(force=True)

        learning_row = next(row for row in result["items"] if row["id"] == 5)
        evidence = learning_row["evidence"]
        self.assertFalse(evidence["same_period_auto_judgement_due"])
        self.assertEqual(
            "WAITING_FOR_LOCKED_PERIOD",
            evidence["same_period_auto_judgement_status"],
        )
        self.assertEqual(
            "2026-09-21",
            evidence["same_period_auto_judgement_first_eligible_run_date"],
        )
        self.assertEqual(
            "2026-07-20",
            evidence["same_period_auto_judgement_target_start_date"],
        )
        self.assertEqual(
            "2026-09-18",
            evidence["same_period_auto_judgement_target_end_date"],
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
