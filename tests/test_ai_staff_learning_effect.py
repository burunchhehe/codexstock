import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import app.stock_suite_app as stock_app

from app.stock_suite_app import (
    AI_INTERNAL_LEAGUE_REJECTION_BACKOFF_SECONDS,
    AI_STAFF_OPEN_STRATEGY_MODES,
    AI_STAFF_SYMBOL_SELECTION_LENSES,
    HEAVY_RESEARCH_JOB_LOCK,
    LONG_HORIZON_FIXED_ETF_UNIVERSE,
    LONG_HORIZON_FIXED_ETF_UNIVERSE_ID,
    REPLAY_STRATEGY_PROFILES,
    _ai_internal_league_strict_verification,
    _ai_staff_learning_source_hash,
    _ai_staff_learning_counterfactual_period_plan,
    _ai_staff_learning_counterfactual_due_preregistration_status,
    _ai_staff_learning_counterfactual_preregistration_status,
    _ai_staff_learning_transition_status,
    _ai_staff_monte_carlo_retraining_trial_configs,
    _ai_staff_certified_learning_observation,
    _ai_staff_counterfactual_ledger_summary,
    _ai_staff_counterfactual_rejected_strategy_ids,
    _ai_staff_counterfactual_execution_contract_hash,
    _merge_ai_staff_counterfactual_learning_pairs,
    _ai_staff_capital_goal_progress,
    _ai_staff_replay_journal_diagnosis,
    _ai_staff_adaptation_changes_signature,
    _ai_staff_counterfactual_adaptation_history,
    _ai_staff_role_generated_strategy_configs,
    _ai_tournament_challenge_configs,
    _ai_staff_symbol_selection_lens,
    _ai_staff_training_arena,
    _ai_staff_verified_strategy_memory_configs,
    _ai_tournament_monte_carlo_failure_reasons,
    _ai_tournament_monte_carlo_stress,
    _ai_tournament_stress_retraining_plan,
    _ai_tournament_stress_retraining_plan_valid,
    _maturity_verified_monte_carlo_evidence,
    _replay_data_bundle_slice_manifest_hash,
    _find_ai_staff_learning_counterfactual_preregistration,
    _maybe_preregister_ai_staff_learning_counterfactual,
    _maybe_schedule_ai_staff_learning_counterfactual,
    _run_ai_staff_learning_counterfactual_jobs,
    _apply_ai_staff_verified_learning,
    _build_ai_staff_learning_counterfactual_control,
    _build_ai_staff_causal_learning_transition,
    _ai_tournament_challenge_configs,
    ai_staff_learning_audit,
    ai_tournament_contestants,
    build_ai_tournament_monte_carlo_evidence_audit,
    build_ai_staff_learning_adaptation_preparation,
    build_ai_staff_learning_decision_reflection_audit,
    build_ai_staff_learning_counterfactual_queue,
    build_ai_staff_learning_counterfactual_preregistration_status,
    build_ai_staff_learning_counterfactual_scheduler_status,
    build_ai_staff_learning_experiment_status,
    build_ai_staff_indicator_catalog,
    build_live_candidate_decision_report,
    build_live_learning_evidence_gate,
    ensure_ai_staff_learning_counterfactual_preregistration,
    format_live_candidate_decision_reply,
    load_ai_internal_league_state,
    run_autonomous_ai_internal_league_if_due,
    run_ai_staff_learning_counterfactual_sample,
    run_ai_staff_learning_counterfactual_triplet,
    run_ai_staff_learning_counterfactual_triplet_batch,
    run_ai_mini_league,
)


class AiStaffLearningEffectTests(unittest.TestCase):
    @staticmethod
    def _certified_observation_fixture() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        source_id = "HREPLAY-100"
        certified_id = "HREPLAY-200"
        row = {
            "contestant_id": "operator",
            "replay_id": source_id,
            "strategy_mode": "ma_cross",
            "total_return_pct": 999.0,
        }
        record = {
            "id": "AITOUR-SOURCE",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "symbols": ["005930"],
            "rankings": [row],
        }
        replay = {
            "id": certified_id,
            "source": f"tournament-regeneration:{source_id}",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "actual_start_date": "2024-01-02",
            "actual_end_date": "2024-03-29",
            "strategy_mode": "ma_cross",
            "strategy_config": {
                "fast": 12,
                "slow": 32,
                "allocation_pct": 30.0,
                "max_positions": 3,
                "stop_loss_pct": 8.0,
                "take_profit_pct": 12.0,
                "holding_limit_days": 10,
                "cycles_per_day": 24,
            },
            "symbols": ["005930"],
            "total_return_pct": 4.25,
            "max_drawdown_pct": -3.5,
            "win_rate_pct": 55.0,
            "trade_count": 20,
            "closed_trade_count": 10,
            "average_win_pct": 2.0,
            "average_loss_pct": -1.0,
            "cost_model": {"enabled": True},
            "transaction_cost_audit": {"passed": True},
            "execution_timing_model": {"lookahead_safe_required": True},
            "data_coverage": {"portfolio_boundary_coverage_passed": True},
            "price_currency_unit_audit": {"passed": True},
            "data_mode": "real",
        }
        ledger = {
            "source_replay_id": source_id,
            "new_replay_id": certified_id,
            "paper_only": True,
            "live_order_allowed": False,
            "automatic_promotion": False,
            "official_return_claim_allowed": True,
            "contract_hash": "contract-hash",
            "source_comparison": {
                "schema": "codexstock_replay_source_comparison_v1",
                "status": "new_result_valid_source_equivalence_unproven",
                "new_result_return_claim_is_separate": True,
                "source_equivalence_claim_allowed": False,
            },
        }
        index = {
            "ok": True,
            "replacements": {
                source_id: {
                    "new_replay_id": certified_id,
                    "replay": replay,
                    "ledger": ledger,
                    "reconciliation": {"official_return_claim_allowed": True},
                    "official_verdict": {"official_return_claim_allowed": True},
                    "milestone": 757,
                    "evidence_bundle_hash": "bundle-hash",
                }
            },
        }
        return record, row, index

    def test_certified_replacement_becomes_separate_paper_learning_observation(self):
        record, row, index = self._certified_observation_fixture()
        with patch(
            "app.stock_suite_app._ai_tournament_bias_audit",
            return_value={"passed": True, "universe_dataset_id": "krx-history"},
        ):
            result = _ai_staff_certified_learning_observation(
                record,
                row,
                certified_index=index,
            )

        self.assertTrue(result["eligible"])
        projected = result["row"]
        self.assertEqual(4.25, projected["total_return_pct"])
        self.assertEqual(999.0, row["total_return_pct"])
        self.assertEqual("HREPLAY-200", projected["certified_replay_id"])
        provenance = projected["learning_observation_provenance"]
        self.assertFalse(provenance["legacy_result_equivalence_claim_allowed"])
        self.assertTrue(provenance["new_result_return_claim_is_separate"])
        self.assertTrue(projected["paper_only"])
        self.assertFalse(projected["promotion_allowed"])
        self.assertFalse(projected["live_order_allowed"])

    def test_certified_learning_observation_blocks_strategy_identity_mismatch(self):
        record, row, index = self._certified_observation_fixture()
        row["strategy_mode"] = "breakout"
        result = _ai_staff_certified_learning_observation(
            record,
            row,
            certified_index=index,
        )
        self.assertFalse(result["eligible"])
        self.assertIn("certified_replacement_strategy_mode_mismatch", result["blockers"])

    def test_certified_learning_observation_blocks_unverified_point_in_time_universe(self):
        record, row, index = self._certified_observation_fixture()
        with patch(
            "app.stock_suite_app._ai_tournament_bias_audit",
            return_value={"passed": False, "blockers": ["point_in_time_universe_dataset_missing"]},
        ):
            result = _ai_staff_certified_learning_observation(
                record,
                row,
                certified_index=index,
            )
        self.assertFalse(result["eligible"])
        self.assertIn(
            "certified_replacement_point_in_time_universe_not_validated",
            result["blockers"],
        )

    @staticmethod
    def _causal_context(contestant_id: str = "operator", index: int = 0) -> dict[str, object]:
        return {
            "source_record_id": f"AITOUR-CAUSAL-SOURCE-{contestant_id}",
            "source_start_date": "2023-01-03",
            "source_end_date": "2023-12-28",
            "source_contestant_id": contestant_id,
            "source_strategy": {
                "strategy": "ma_cross",
                "fast": 12 + index,
                "slow": 32 + index,
                "stop": 8.0,
                "take": 12.0,
                "hold": 10,
                "allocation": 30.0,
                "max_positions": 3,
            },
            "source_metrics": {"valid": True},
            "source_raw_metrics": {
                "total_return_pct": -2.0,
                "max_drawdown_pct": -10.0,
                "win_rate_pct": 30.0,
                "trade_count": 20,
                "risk_limit_pct": 15.0,
            },
            "reason_codes": ["non_positive_net_return", "low_win_rate"],
            "journal_diagnosis": {"reason_codes": [], "metrics": {}},
            "journal_lessons": ["change the next Paper strategy before retesting"],
            "source_evidence_hash": hashlib.sha256(
                f"official-source-{contestant_id}-{index}".encode("utf-8")
            ).hexdigest(),
        }

    @classmethod
    def _causal_contexts(cls, *contestant_ids: str) -> dict[str, dict[str, object]]:
        selected = contestant_ids or tuple(str(row["id"]) for row in ai_tournament_contestants()[:4])
        return {
            contestant_id: cls._causal_context(contestant_id, index)
            for index, contestant_id in enumerate(selected)
        }

    @staticmethod
    def _counterfactual_execution_contract(
        symbols: list[str] | None = None,
        *,
        start_date: str = "2024-01-02",
        end_date: str = "2024-03-29",
        minimum_bars: int = 36,
    ) -> dict[str, object]:
        contract: dict[str, object] = {
            "schema": "codexstock_ai_staff_counterfactual_execution_contract_v1",
            "start_date": start_date,
            "end_date": end_date,
            "symbols": list(symbols or ["005930"]),
            "initial_cash": 100_000_000.0,
            "cycles_per_day": 24,
            "minimum_bars": minimum_bars,
            "shared_replay_data_bundle_required": True,
            "allow_simulated_fallback": False,
            "paper_only": True,
            "live_order_allowed": False,
        }
        contract["contract_hash"] = _ai_staff_counterfactual_execution_contract_hash(
            contract
        )
        return contract

    @staticmethod
    def _counterfactual_replay_bundle_evidence(
        symbols: list[str] | None = None,
        *,
        start_date: str = "2024-01-02",
        end_date: str = "2024-03-29",
    ) -> dict[str, object]:
        selected_symbols = list(symbols or ["005930"])
        row_count = 252
        evidence: dict[str, object] = {
            "schema": "codexstock_replay_data_bundle_slice_evidence_v3",
            "used": True,
            "passed": True,
            "bundle_content_hash": "sha256:" + "a" * 64,
            "slice_content_hash": "sha256:" + "b" * 64,
            "bundle_period": {"start_date": start_date, "end_date": end_date},
            "requested_period": {"start_date": start_date, "end_date": end_date},
            "symbols": selected_symbols,
            "symbol_count": len(selected_symbols),
            "symbol_row_counts": {symbol: row_count for symbol in selected_symbols},
            "symbol_row_bounds": {
                symbol: {
                    "first_date": start_date,
                    "last_date": end_date,
                    "row_count": row_count,
                }
                for symbol in selected_symbols
            },
            "symbol_calendar_adjacency_roots": {
                symbol: hashlib.sha256(symbol.encode("utf-8")).hexdigest()
                for symbol in selected_symbols
            },
            "symbol_calendar_pair_counts": {
                symbol: row_count - 1 for symbol in selected_symbols
            },
            "fx_row_count": 0,
            "excluded_before_row_count": 0,
            "excluded_future_row_count": 0,
            "future_rows_excluded_before_strategy": True,
            "no_rows_outside_requested_period": True,
            "source_fetch_reused": True,
            "live_order_allowed": False,
        }
        evidence["slice_manifest_hash"] = _replay_data_bundle_slice_manifest_hash(
            evidence
        )
        return evidence

    @classmethod
    def _causal_transition(
        cls,
        contestant_id: str = "operator",
        *,
        target_start_date: str = "2024-01-02",
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
        context = cls._causal_context(contestant_id)
        baseline = dict(context["source_strategy"])
        baseline["label"] = "verified prior baseline"
        adapted = _apply_ai_staff_verified_learning(
            baseline,
            context,
            current_start_date=target_start_date,
        )
        transition = _build_ai_staff_causal_learning_transition(
            context,
            baseline,
            adapted,
            target_start_date=target_start_date,
        )
        return context, baseline, adapted, transition

    @classmethod
    def _causal_ledger_triplet(
        cls,
        *,
        contestant_id: str = "operator",
        strategy_id: str = "S-CAUSAL",
        baseline_return: float = 1.0,
        adapted_return: float = 3.0,
        baseline_mdd: float = -1.0,
        adapted_mdd: float = -1.0,
    ) -> list[dict[str, object]]:
        context, baseline, adapted, transition = cls._causal_transition(contestant_id)
        execution_contract = cls._counterfactual_execution_contract()
        rows: list[dict[str, object]] = []
        for run_type, return_pct, mdd in (
            ("prior_official_source", -2.0, -10.0),
            ("same_period_baseline", baseline_return, baseline_mdd),
            ("same_period_adapted", adapted_return, adapted_mdd),
        ):
            row: dict[str, object] = {
                "schema": "codexstock_ai_staff_learning_counterfactual_ledger_v1",
                "contestant_id": contestant_id,
                "strategy_generation_id": strategy_id,
                "run_type": run_type,
                "status": "COMPLETED",
                "start_date": "2024-01-02",
                "end_date": "2024-03-29",
                "symbols": ["005930"],
                "initial_cash": 100_000_000.0,
                "cycles_per_day": 24,
                "shared_replay_min_bars": 36,
                "allow_simulated_fallback": False,
                "execution_comparison_contract": copy.deepcopy(execution_contract),
                "execution_comparison_contract_hash": execution_contract["contract_hash"],
                "total_return_pct": return_pct,
                "max_drawdown_pct": mdd,
                "learning_transition": transition,
                "learning_transition_hash": transition["transition_hash"],
                "learning_transition_hash_valid": True,
                "causal_learning_evidence_eligible": True,
                "executed_strategy": adapted if run_type == "same_period_adapted" else baseline,
                "paper_only": True,
                "official_learning_evidence": False,
                "live_order_allowed": False,
                "unverified_result_affects_score": False,
                "unverified_result_affects_live_candidate": False,
            }
            if run_type == "prior_official_source":
                row.update(
                    {
                        "evidence_role": "verified_prior_official_source_observation",
                        "source_record_id": context["source_record_id"],
                        "source_evidence_hash": context["source_evidence_hash"],
                        "actual_start_date": context["source_start_date"],
                        "actual_end_date": context["source_end_date"],
                    }
                )
            else:
                row.update(
                    {
                        "actual_start_date": "2024-01-02",
                        "actual_end_date": "2024-03-29",
                        "cost_model": {"commission_bps_each_side": 1.5, "slippage_bps_each_side": 5.0},
                        "transaction_cost_audit": {"passed": True},
                        "execution_timing_model": {
                            "lookahead_safe_required": True,
                            "same_bar_signal_execution_allowed": False,
                            "minimum_signal_lag_bars": 1,
                        },
                        "data_coverage": {"portfolio_boundary_coverage_passed": True},
                        "replay_data_bundle_evidence": cls._counterfactual_replay_bundle_evidence(),
                    }
                )
            row["ledger_hash"] = hashlib.sha256(
                json.dumps(row, ensure_ascii=True, sort_keys=True).encode("utf-8")
            ).hexdigest()
            rows.append(row)
        return rows

    @staticmethod
    def _counterfactual_summary_triplet(
        *,
        start_date: str,
        end_date: str,
        improvement: float,
        index: int,
    ) -> dict[str, object]:
        status = "improved" if improvement >= 1.0 else "regressed" if improvement <= -1.0 else "inconclusive"
        return {
            "contestant_id": "operator",
            "strategy_generation_id": f"S-LEDGER-{index}",
            "start_date": start_date,
            "end_date": end_date,
            "symbols": ["005930", "000660"],
            "risk_adjusted_improvement": improvement,
            "status": status,
            "causal_learning_evidence_eligible": True,
            "learning_transition_hash": f"{index:x}" * 64,
            "source_record_id": "AITOUR-VERIFIED-SOURCE",
            "source_period": {"start_date": "2024-01-02", "end_date": "2024-03-29"},
            "adaptation_changes": {"allocation": {"before": 20.0, "after": 22.0}},
            "replay_data_slice_hash": f"sha256:shared-{index}",
            "paper_only": True,
            "official_learning_evidence": False,
            "live_order_allowed": False,
        }

    @staticmethod
    def _row(
        *,
        total_return_pct: float,
        max_drawdown_pct: float,
        actual_start_date: str,
        actual_end_date: str,
        strategy: str = "ma_cross",
        fast: int = 12,
        slow: int = 32,
        allocation: float = 40.0,
        max_positions: int = 4,
        stop: float = 8.0,
        take: float = 12.0,
        hold: int = 10,
    ) -> dict[str, object]:
        trade_count = 20
        return {
            "contestant_id": "operator",
            "strategy_mode": strategy,
            "fast_window": fast,
            "slow_window": slow,
            "risk_limit_pct": 15.0,
            "actual_start_date": actual_start_date,
            "actual_end_date": actual_end_date,
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "win_rate_pct": 45.0,
            "trade_count": trade_count,
            "selected_symbols": ["005930"],
            "selected_challenge_config": {
                "strategy_mode": strategy,
                "allocation_pct": allocation,
                "max_positions": max_positions,
                "stop_loss_pct": stop,
                "take_profit_pct": take,
                "holding_limit_days": hold,
            },
            "transaction_cost_audit": {
                "schema": "codexstock_replay_transaction_cost_audit_v1",
                "passed": True,
                "applied_action_count": trade_count,
            },
            "execution_timing_model": {
                "lookahead_safe_required": True,
                "same_bar_signal_execution_allowed": False,
                "minimum_signal_lag_bars": 1,
            },
            "data_coverage": {"portfolio_boundary_coverage_passed": True},
            "cost_model": {
                "enabled": True,
                "commission_bps_each_side": 1.5,
                "slippage_bps_each_side": 5.0,
                "kr_sell_tax_bps": 18.0,
            },
            "return_reconciliation_summary": {
                "status": "passed",
                "checked_count": 10,
                "blocker_count": 0,
                "official_return_blocker_count": 0,
            },
        }

    def _records(self, *, target_return: float = 12.0, target_mdd: float = -6.0):
        source = {
            "id": "AITOUR-SOURCE",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
        }
        source_row = self._row(
            total_return_pct=-8.0,
            max_drawdown_pct=-22.0,
            actual_start_date="2024-01-02",
            actual_end_date="2024-06-28",
        )
        source["rankings"] = [source_row]
        context = {
            "source_record_id": source["id"],
            "source_start_date": source_row["actual_start_date"],
            "source_end_date": source_row["actual_end_date"],
            "source_contestant_id": "operator",
            "source_evidence_hash": _ai_staff_learning_source_hash(source, source_row),
            "source_metrics": {},
            "reason_codes": ["non_positive_net_return", "drawdown_above_role_limit"],
        }
        adapted = _apply_ai_staff_verified_learning(
            {
                "label": "operator baseline",
                "strategy": "ma_cross",
                "fast": 12,
                "slow": 32,
                "allocation": 40.0,
                "max_positions": 4,
                "stop": 8.0,
                "take": 12.0,
                "hold": 10,
            },
            context,
            current_start_date="2024-07-01",
        )
        target = {
            "id": "AITOUR-TARGET",
            "start_date": "2024-07-01",
            "end_date": "2024-12-31",
        }
        target_row = self._row(
            total_return_pct=target_return,
            max_drawdown_pct=target_mdd,
            actual_start_date="2024-07-01",
            actual_end_date="2024-12-30",
            strategy=str(adapted["strategy"]),
            fast=int(adapted["fast"]),
            slow=int(adapted["slow"]),
            allocation=float(adapted["allocation"]),
            max_positions=int(adapted["max_positions"]),
            stop=float(adapted["stop"]),
            take=float(adapted["take"]),
            hold=int(adapted["hold"]),
        )
        target_row["learning_provenance"] = adapted["_learning_provenance"]
        baseline_row = self._row(
            total_return_pct=-4.0,
            max_drawdown_pct=-14.0,
            actual_start_date="2024-07-01",
            actual_end_date="2024-12-30",
        )
        target_row["learning_counterfactual_control"] = _build_ai_staff_learning_counterfactual_control(
            source_record_id=str(source["id"]),
            baseline_row=baseline_row,
            target_row=target_row,
        )
        target["rankings"] = [target_row]
        return source, target

    def _three_pair_records(self):
        source, first_target = self._records()
        targets = [first_target]
        periods = [
            ("AITOUR-TARGET-2", "2025-01-01", "2025-06-30", "2025-01-02", "2025-06-30"),
            ("AITOUR-TARGET-3", "2025-07-01", "2025-12-31", "2025-07-01", "2025-12-30"),
        ]
        for record_id, start_date, end_date, actual_start, actual_end in periods:
            target = copy.deepcopy(first_target)
            target["id"] = record_id
            target["start_date"] = start_date
            target["end_date"] = end_date
            row = target["rankings"][0]
            row["actual_start_date"] = actual_start
            row["actual_end_date"] = actual_end
            row["learning_provenance"]["current_start_date"] = start_date
            baseline = copy.deepcopy(row["learning_counterfactual_control"]["baseline_result"])
            baseline["actual_start_date"] = actual_start
            baseline["actual_end_date"] = actual_end
            row["learning_counterfactual_control"] = _build_ai_staff_learning_counterfactual_control(
                source_record_id=str(source["id"]),
                baseline_row=baseline,
                target_row=row,
            )
            targets.append(target)
        return [source, *targets]

    @staticmethod
    def _operator(result: dict[str, object]) -> dict[str, object]:
        return next(row for row in result["staff"] if row["contestant_id"] == "operator")

    def test_one_verified_pair_is_not_enough_to_claim_growth(self):
        source, target = self._records()
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=[target, source]),
            patch("app.stock_suite_app._ai_tournament_official_claim_state", return_value={"eligible": True, "reasons": []}),
        ):
            result = ai_staff_learning_audit(limit=10)
        operator = self._operator(result)
        self.assertFalse(operator["growth_proven"])
        self.assertEqual(operator["validated_learning_pair_count"], 1)
        self.assertEqual(operator["improved_learning_pair_count"], 1)
        self.assertEqual(operator["invalid_provenance_count"], 0)
        self.assertEqual(operator["learning_pairs"][0]["status"], "improved")
        self.assertEqual(operator["growth_status_code"], "insufficient_independent_learning_pairs")
        self.assertEqual(operator["required_additional_validated_pair_count"], 2)
        self.assertEqual(result["schema"], "codexstock_ai_staff_learning_audit_v4")
        self.assertTrue(result["counterfactual_control_required"])
        self.assertTrue(result["effect_confidence_gate_required"])
        operator_queue = next(
            row for row in result["next_learning_validation_queue"] if row["contestant_id"] == "operator"
        )
        self.assertGreaterEqual(result["next_learning_validation_queue_count"], 1)
        self.assertEqual(
            ["prior_official_source", "same_period_baseline", "same_period_adapted"],
            operator_queue["next_required_runs"],
        )
        self.assertFalse(operator_queue["live_order_allowed"])
        self.assertTrue(operator_queue["ready_for_paired_replay"])
        self.assertFalse(operator_queue["adaptation_change_required"])
        self.assertEqual(operator_queue["next_action"], "run_paper_counterfactual_triplet")

    def test_learning_queue_blocks_replay_until_strategy_change_is_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch(
                    "app.stock_suite_app._historical_replay_certified_score_index",
                    return_value={"status": "ready", "verified_through_count": 100, "target_count": 757},
                ),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
            ):
                result = ai_staff_learning_audit(limit=10)

            self.assertGreaterEqual(result["next_learning_validation_queue_count"], 1)
            self.assertTrue(result["learning_experiment_contract_ready"])
            self.assertEqual(str(contract_path), result["learning_experiment_contract_path"])
            self.assertTrue(contract_path.exists())
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            self.assertEqual("codexstock_ai_staff_learning_experiment_queue_v1", contract["schema"])
            self.assertEqual(result["next_learning_validation_queue_count"], contract["queue_count"])
            self.assertFalse(contract["live_order_allowed"])
            self.assertFalse(contract["unverified_result_affects_score"])
            for row in result["next_learning_validation_queue"]:
                self.assertTrue(row["adaptation_change_required"])
                self.assertFalse(row["official_learning_source_ready"])
                self.assertFalse(row["ready_for_paired_replay"])
                self.assertEqual(row["queue_blockers"], ["official_learning_source_missing"])
                self.assertEqual(row["next_action"], "complete_official_replay_evidence_gate")
                self.assertEqual(row["next_required_runs"], [])
                self.assertEqual(
                    row["runs_after_precondition"],
                    ["prior_official_source", "same_period_baseline", "same_period_adapted"],
                )
                self.assertFalse(row["live_order_allowed"])

            readiness = result["official_learning_source_readiness"]
            self.assertEqual("codexstock_ai_staff_learning_source_readiness_v1", readiness["schema"])
            self.assertEqual(0, readiness["source_ready_staff_count"])
            self.assertEqual(4, readiness["source_blocked_staff_count"])
            self.assertTrue(readiness["historical_replay_dependency_active"])
            self.assertEqual("100/757", readiness["deep_progress_label"])
            self.assertEqual(
                "complete_historical_replay_and_bias_evidence_for_learning_sources",
                readiness["next_action"],
            )
            self.assertFalse(readiness["live_order_allowed"])
            self.assertFalse(readiness["unverified_result_affects_score"])

    def test_learning_experiment_status_verifies_contract_hash_and_safety(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
            ):
                status = build_ai_staff_learning_experiment_status(regenerate_if_missing=True)
                self.assertTrue(status["exists"])
                self.assertTrue(status["ready"])
                self.assertTrue(status["hash_valid"])
                self.assertTrue(status["paper_only"])
                self.assertFalse(status["live_order_allowed"])
                self.assertFalse(status["unverified_result_affects_score"])
                self.assertFalse(status["unverified_result_affects_live_candidate"])

                payload = json.loads(contract_path.read_text(encoding="utf-8"))
                payload["live_order_allowed"] = True
                contract_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

                tampered = build_ai_staff_learning_experiment_status(regenerate_if_missing=False)
                self.assertFalse(tampered["ready"])
                self.assertFalse(tampered["safe_to_execute_paper"])
                self.assertIn("learning_experiment_contract_live_order_not_blocked", tampered["blockers"])
                self.assertIn("learning_experiment_contract_hash_mismatch", tampered["blockers"])

    def test_learning_adaptation_preparation_blocks_random_variants_without_prior_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
            ):
                prepared = build_ai_staff_learning_adaptation_preparation()

            self.assertTrue(prepared["ok"])
            self.assertEqual("codexstock_ai_staff_learning_adaptation_preparation_v1", prepared["schema"])
            self.assertEqual(0, prepared["prepared_count"])
            self.assertEqual(prepared["blocked_count"], prepared["blocked_plan_count"])
            self.assertGreaterEqual(prepared["blocked_plan_count"], 4)
            self.assertTrue(prep_path.exists())
            self.assertFalse(prepared["safe_to_execute_paper"])
            self.assertFalse(prepared["live_order_allowed"])
            self.assertFalse(prepared["unverified_result_affects_score"])
            self.assertFalse(prepared["unverified_result_affects_live_candidate"])
            self.assertEqual([], prepared["plans"])
            self.assertTrue(
                all(
                    row["blockers"] == ["verified_prior_learning_source_missing"]
                    for row in prepared["blocked_plans"]
                )
            )

    def test_learning_adaptation_preparation_builds_hashed_causal_transition(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            contexts = self._causal_contexts("operator")
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
            ):
                prepared = build_ai_staff_learning_adaptation_preparation()

            self.assertEqual(1, prepared["prepared_count"])
            self.assertEqual(1, prepared["causal_transition_count"])
            self.assertTrue(prepared["safe_to_execute_paper"])
            plan = prepared["plans"][0]
            self.assertTrue(plan["causal_learning_evidence_eligible"])
            self.assertEqual("verified_learning_adaptation", plan["candidate_strategies"][0]["candidate_origin"])
            self.assertTrue(_ai_staff_learning_transition_status(plan["learning_transition"])["valid"])
            self.assertNotEqual(plan["source_strategy"], plan["candidate_strategies"][0])
            self.assertFalse(plan["live_order_allowed"])

    def test_learning_adaptation_preparation_keeps_already_runnable_staff(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prep_path = Path(temp_dir) / "learning-prep.json"
            status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": "C:/tmp/contract.json",
                "contract_hash": "contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [
                            "prior_official_source",
                            "same_period_baseline",
                            "same_period_adapted",
                        ],
                    }
                ],
            }
            with (
                patch("app.stock_suite_app.build_ai_staff_learning_experiment_status", return_value=status),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
            ):
                prepared = build_ai_staff_learning_adaptation_preparation()

            self.assertEqual(1, prepared["source_runnable_count"])
            self.assertEqual(1, prepared["source_queue_count"])
            self.assertEqual(1, prepared["prepared_count"])
            self.assertEqual("operator", prepared["plans"][0]["contestant_id"])

    def test_learning_counterfactual_queue_expands_preparation_into_paper_only_triplets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            queue_path = Path(temp_dir) / "learning-queue.json"
            contexts = self._causal_contexts()
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
            ):
                queue = build_ai_staff_learning_counterfactual_queue()

            self.assertTrue(queue["ok"])
            self.assertEqual("codexstock_ai_staff_learning_counterfactual_queue_v1", queue["schema"])
            self.assertEqual(3, queue["expected_runs_per_strategy"])
            self.assertEqual(len(contexts) * 3, queue["job_count"])
            self.assertEqual(queue["job_count"] // 3, queue["strategy_triplet_count"])
            self.assertEqual(queue["job_count"], queue["ready_job_count"])
            self.assertTrue(queue["safe_to_execute_paper"])
            self.assertEqual("run_paper_counterfactual_triplet_batch", queue["next_action"])
            self.assertTrue(queue_path.exists())
            self.assertFalse(queue["live_order_allowed"])
            self.assertFalse(queue["unverified_result_affects_score"])
            run_types = {job["run_type"] for job in queue["jobs"]}
            self.assertEqual(
                {"prior_official_source", "same_period_baseline", "same_period_adapted"},
                run_types,
            )
            for job in queue["jobs"]:
                self.assertTrue(job["paper_only"])
                self.assertFalse(job["live_order_allowed"])
                self.assertFalse(job["unverified_result_affects_score"])
                self.assertFalse(job["unverified_result_affects_live_candidate"])
                self.assertTrue(job["causal_learning_evidence_eligible"])
                self.assertTrue(_ai_staff_learning_transition_status(job["learning_transition"])["valid"])
                self.assertEqual("QUEUED", job["status"])
                self.assertTrue(job["requires_post_run_audit"])
                self.assertFalse(job["persist_result_as_official_learning_evidence"])

    def test_forward_counterfactual_preregistration_locks_before_target_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preregistration_path = root / "learning-preregistrations.jsonl"
            prep_path = root / "learning-prep.json"
            experiment_status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": str(root / "learning-contract.json"),
                "contract_hash": "source-contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [
                            "prior_official_source",
                            "same_period_baseline",
                            "same_period_adapted",
                        ],
                    }
                ],
            }
            with (
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_experiment_status",
                    return_value=experiment_status,
                ),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE",
                    prep_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                    preregistration_path,
                ),
            ):
                first = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
                )
                second = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-18T10:00:00+09:00"),
                )

            self.assertTrue(first["ok"])
            self.assertTrue(first["created"])
            self.assertEqual("REGISTERED", first["status"])
            self.assertTrue(first["generated_before_target_start"])
            self.assertEqual(1, first["registered_plan_count"])
            self.assertTrue(first["strategy_lock_ready"])
            self.assertEqual(1, first["strategy_lock_plan_count"])
            self.assertEqual(2, first["strategy_lock_signature_count"])
            self.assertEqual(64, len(first["strategy_lock_digest"]))
            self.assertFalse(first["live_order_allowed"])
            self.assertFalse(second["created"])
            self.assertEqual(
                first["contract"]["contract_hash"],
                second["contract"]["contract_hash"],
            )
            self.assertEqual(1, len(preregistration_path.read_text(encoding="utf-8").splitlines()))

    def test_forward_counterfactual_preregistration_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preregistration_path = root / "learning-preregistrations.jsonl"
            prep_path = root / "learning-prep.json"
            experiment_status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": str(root / "learning-contract.json"),
                "contract_hash": "source-contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [],
                    }
                ],
            }
            with (
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_experiment_status",
                    return_value=experiment_status,
                ),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE",
                    prep_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                    preregistration_path,
                ),
            ):
                created = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
                )
                contract = dict(created["contract"])
                contract["symbols"] = [*contract["symbols"], "035720"]
                preregistration_path.write_text(
                    json.dumps(contract, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                lookup = _find_ai_staff_learning_counterfactual_preregistration(
                    "2026-07-20",
                    target_end_date="2026-09-18",
                )

            self.assertTrue(lookup["found"])
            self.assertFalse(lookup["valid"])
            self.assertIn(
                "learning_preregistration_contract_hash_mismatch",
                lookup["blockers"],
            )
            self.assertFalse(lookup["live_order_allowed"])

    def test_counterfactual_queue_uses_locked_preregistration_not_later_strategy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preregistration_path = root / "learning-preregistrations.jsonl"
            prep_path = root / "learning-prep.json"
            queue_path = root / "learning-queue.json"
            experiment_status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": str(root / "learning-contract.json"),
                "contract_hash": "source-contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [],
                    }
                ],
            }
            with (
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_experiment_status",
                    return_value=experiment_status,
                ),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE",
                    prep_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                    preregistration_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE",
                    queue_path,
                ),
            ):
                registered = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
                )
                with patch(
                    "app.stock_suite_app.build_ai_staff_learning_adaptation_preparation",
                    side_effect=AssertionError("must use immutable preregistration"),
                ):
                    queue = build_ai_staff_learning_counterfactual_queue(
                        target_start_date="2026-07-20",
                    )

            self.assertTrue(registered["valid"])
            self.assertTrue(queue["safe_to_execute_paper"])
            self.assertEqual("immutable_forward_preregistration", queue["preparation_source"])
            self.assertTrue(queue["preregistered_forward_test"])
            self.assertEqual("2026-09-18", queue["learning_preregistration_target_end_date"])
            self.assertEqual(3, queue["job_count"])
            self.assertTrue(all(job["preregistered_forward_test"] for job in queue["jobs"]))
            self.assertTrue(all(job["strategy_signature"] for job in queue["jobs"]))
            self.assertTrue(all(job["source_strategy_signature"] for job in queue["jobs"]))
            self.assertTrue(all(job["adapted_strategy_signature"] for job in queue["jobs"]))
            self.assertTrue(queue["learning_preregistration_strategy_lock_digest"])
            self.assertTrue(
                all(
                    job["learning_preregistration_strategy_lock_digest"]
                    == registered["strategy_lock_digest"]
                    for job in queue["jobs"]
                )
            )
            self.assertTrue(
                all(
                    job["learning_preregistration_hash"]
                    == registered["contract"]["contract_hash"]
                    for job in queue["jobs"]
                )
            )
            self.assertFalse(queue["live_order_allowed"])

    def test_forward_counterfactual_execution_rejects_tampered_locked_strategy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preregistration_path = root / "learning-preregistrations.jsonl"
            prep_path = root / "learning-prep.json"
            queue_path = root / "learning-queue.json"
            ledger_path = root / "learning-ledger.jsonl"
            experiment_status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": str(root / "learning-contract.json"),
                "contract_hash": "source-contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [],
                    }
                ],
            }
            with (
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_experiment_status",
                    return_value=experiment_status,
                ),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE",
                    prep_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                    preregistration_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE",
                    queue_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE",
                    ledger_path,
                ),
            ):
                registered = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2024-01-02",
                    target_end_date="2024-03-29",
                    first_eligible_run_date="2024-04-01",
                    now=datetime.fromisoformat("2023-12-20T18:00:00+09:00"),
                )
                queue = build_ai_staff_learning_counterfactual_queue(
                    target_start_date="2024-01-02",
                )
                tampered = copy.deepcopy(
                    next(
                        job
                        for job in queue["jobs"]
                        if job["run_type"] == "same_period_adapted"
                    )
                )
                tampered["strategy"]["fast"] = int(tampered["strategy"]["fast"]) + 1
                with (
                    patch(
                        "app.stock_suite_app.build_operating_focus",
                        return_value={"market_priority_active": False, "market_open": False},
                    ),
                    patch(
                        "app.stock_suite_app._build_historical_replay_data_bundle",
                        return_value={"ok": True, "symbols": ["005930"]},
                    ),
                    patch(
                        "app.stock_suite_app.run_historical_paper_replay"
                    ) as replay,
                ):
                    result = _run_ai_staff_learning_counterfactual_jobs(
                        [tampered],
                        queue_hash=queue["queue_hash"],
                        symbols=registered["contract"]["symbols"],
                        start_date="2024-01-02",
                        end_date="2024-03-29",
                        allow_simulated_fallback=False,
                    )

            self.assertEqual(0, result["completed_count"])
            self.assertEqual(1, result["failed_count"])
            row = result["rows"][0]
            self.assertFalse(row["preregistered_forward_evidence_eligible"])
            self.assertFalse(row["learning_preregistration_strategy_match"])
            self.assertIn(
                "learning_preregistration_executed_strategy_mismatch",
                row["learning_preregistration_execution_blockers"],
            )
            self.assertEqual("invalid_forward_preregistration", row["failure_kind"])
            replay.assert_not_called()

    def test_forward_counterfactual_preregistration_cannot_be_created_after_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            preregistration_path = Path(temp_dir) / "learning-preregistrations.jsonl"
            with patch(
                "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                preregistration_path,
            ):
                result = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-20T08:00:00+09:00"),
                )

            self.assertFalse(result["ok"])
            self.assertEqual("TOO_LATE_TO_PREREGISTER", result["status"])
            self.assertFalse(preregistration_path.exists())
            self.assertFalse(result["live_order_allowed"])

    def test_scheduler_registers_the_reported_future_window(self):
        schedule = {
            "ready_to_run": False,
            "next_candidate_start_date": "2026-07-20",
            "minimum_candidate_end_date": "2026-09-18",
            "next_eligible_date": "2026-09-21",
        }
        expected = {
            "ok": True,
            "status": "REGISTERED",
            "created": True,
            "paper_only": True,
            "live_order_allowed": False,
        }
        with patch(
            "app.stock_suite_app.ensure_ai_staff_learning_counterfactual_preregistration",
            return_value=expected,
        ) as ensure:
            result = _maybe_preregister_ai_staff_learning_counterfactual(
                schedule,
                now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
            )

        ensure.assert_called_once_with(
            target_start_date="2026-07-20",
            target_end_date="2026-09-18",
            first_eligible_run_date="2026-09-21",
            symbols=["005930", "000660", "035420"],
            now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
        )
        self.assertEqual("REGISTERED", result["status"])
        self.assertFalse(result["live_order_allowed"])

    def test_matured_preregistration_due_status_requires_matching_contract_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preregistration_path = root / "learning-preregistrations.jsonl"
            prep_path = root / "learning-prep.json"
            experiment_status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": str(root / "learning-contract.json"),
                "contract_hash": "source-contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [
                            "prior_official_source",
                            "same_period_baseline",
                            "same_period_adapted",
                        ],
                    }
                ],
            }
            with (
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_experiment_status",
                    return_value=experiment_status,
                ),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE",
                    prep_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                    preregistration_path,
                ),
            ):
                registered = ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
                )
                waiting = _ai_staff_learning_counterfactual_due_preregistration_status(
                    now=datetime.fromisoformat("2026-09-20T18:00:00+09:00"),
                    ledger_summary={"causal_completed_triplet_keys": []},
                )
                due = _ai_staff_learning_counterfactual_due_preregistration_status(
                    now=datetime.fromisoformat("2026-09-21T18:00:00+09:00"),
                    ledger_summary={"causal_completed_triplet_keys": []},
                )
                contract = registered["contract"]
                strategy_id = contract["plans"][0]["candidate_strategies"][0][
                    "strategy_generation_id"
                ]
                completed = _ai_staff_learning_counterfactual_due_preregistration_status(
                    now=datetime.fromisoformat("2026-09-22T18:00:00+09:00"),
                    ledger_summary={
                        "causal_completed_triplet_keys": [
                            {
                                "contestant_id": "operator",
                                "strategy_generation_id": strategy_id,
                                "start_date": "2026-07-20",
                                "end_date": "2026-09-18",
                                "preregistered_forward_evidence_eligible": True,
                                "learning_preregistration_id": contract["contract_id"],
                                "learning_preregistration_hash": contract["contract_hash"],
                            }
                        ]
                    },
                )

            self.assertEqual("WAITING_FOR_PREREGISTERED_PERIOD", waiting["status"])
            self.assertEqual(0, waiting["due_count"])
            self.assertEqual("MATURED_PREREGISTRATION_DUE", due["status"])
            self.assertEqual(1, due["due_count"])
            self.assertEqual(contract["contract_id"], due["selected_due_contract"]["contract_id"])
            self.assertEqual(1, due["selected_due_contract"]["remaining_triplet_count"])
            self.assertTrue(due["same_period_auto_judgement_due"])
            self.assertEqual("DUE_NOW", due["same_period_auto_judgement_status"])
            self.assertEqual("2026-07-20", due["same_period_auto_judgement_target_start_date"])
            self.assertEqual("2026-09-18", due["same_period_auto_judgement_target_end_date"])
            self.assertEqual("2026-09-21", due["same_period_auto_judgement_first_eligible_run_date"])
            self.assertEqual(0, due["same_period_auto_judgement_days_until_due"])
            self.assertEqual(1, due["same_period_auto_judgement_remaining_triplet_count"])
            self.assertEqual(
                "run_oldest_matured_preregistered_paper_triplet",
                due["same_period_auto_judgement_required_action"],
            )
            runbook = due["same_period_auto_judgement_runbook"]
            self.assertEqual(
                "_maybe_schedule_ai_staff_learning_counterfactual",
                runbook["execution_function"],
            )
            self.assertIn(
                "app-startup-learning-proof-catch-up",
                runbook["trigger_sources"],
            )
            self.assertEqual(
                "run_ai_staff_learning_counterfactual_triplet_batch",
                runbook["batch_function"],
            )
            self.assertTrue(runbook["catch_up_after_restart"])
            self.assertFalse(runbook["live_order_allowed"])
            self.assertTrue(due["catch_up_after_restart"])
            self.assertEqual("NO_INCOMPLETE_PREREGISTRATION", completed["status"])
            self.assertEqual(1, completed["completed_count"])
            self.assertEqual(0, completed["due_count"])
            self.assertFalse(completed["live_order_allowed"])

    def test_same_period_collection_monitor_flags_missing_forward_sessions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            preregistration_path = root / "learning-preregistrations.jsonl"
            prep_path = root / "learning-prep.json"
            forward_contract_path = root / "forward-ab-contract.json"
            forward_ledger_path = root / "forward-ab-ledger.jsonl"
            experiment_status = {
                "ready": True,
                "hash_valid": True,
                "safe_to_execute_paper": True,
                "path": str(root / "learning-contract.json"),
                "contract_hash": "source-contract-hash",
                "blocked_count": 0,
                "blocked": [],
                "runnable": [
                    {
                        "contestant_id": "operator",
                        "display_name": "operator",
                        "runs_after_precondition": [
                            "prior_official_source",
                            "same_period_baseline",
                            "same_period_adapted",
                        ],
                    }
                ],
            }
            with (
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_experiment_status",
                    return_value=experiment_status,
                ),
                patch(
                    "app.stock_suite_app._ai_staff_verified_learning_contexts",
                    return_value=self._causal_contexts("operator"),
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE",
                    prep_path,
                ),
                patch(
                    "app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_PREREGISTRATION_FILE",
                    preregistration_path,
                ),
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_CONTRACT_FILE",
                    forward_contract_path,
                ),
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_FILE",
                    forward_ledger_path,
                ),
            ):
                ensure_ai_staff_learning_counterfactual_preregistration(
                    target_start_date="2026-07-20",
                    target_end_date="2026-09-18",
                    first_eligible_run_date="2026-09-21",
                    now=datetime.fromisoformat("2026-07-17T18:00:00+09:00"),
                )
                sessions = stock_app._ai_staff_same_period_session_dates(
                    "2026-07-20",
                    "2026-09-18",
                )
                contract_hash = "forward-contract-hash"
                forward_contract_path.write_text(
                    json.dumps(
                        {
                            "schema": stock_app.AI_STAFF_90_SESSION_FORWARD_AB_CONTRACT_SCHEMA,
                            "contract_hash": contract_hash,
                            "planned_session_dates": sessions,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                forward_ledger_path.write_text(
                    json.dumps(
                        {
                            "schema": stock_app.AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_SCHEMA,
                            "event_type": "SESSION_CAPTURED",
                            "contract_hash": contract_hash,
                            "session_date": "2026-07-20",
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                result = _ai_staff_learning_counterfactual_due_preregistration_status(
                    now=datetime.fromisoformat("2026-07-22T18:00:00+09:00"),
                    ledger_summary={"causal_completed_triplet_keys": []},
                )

            monitor = result["same_period_collection_monitor"]
            self.assertEqual("COLLECTION_GAP", monitor["status"])
            self.assertEqual(len(sessions), monitor["expected_session_count"])
            self.assertEqual(1, monitor["observed_session_count"])
            self.assertEqual(2, monitor["missing_session_count"])
            self.assertEqual(
                ["2026-07-21", "2026-07-22"],
                monitor["missing_session_dates"],
            )
            preflight = monitor["collection_preflight"]
            self.assertEqual(
                "capture_missing_after_close",
                preflight["observer_evidence_status"],
            )
            self.assertFalse(preflight["today_capture_recorded"])
            self.assertTrue(preflight["route_ready_is_not_capture_proof"])
            self.assertEqual(
                "run_current_session_forward_ab_observer",
                preflight["required_recovery_action"],
            )
            self.assertEqual(
                "/api/ai-tournament/staff-learning-90-session-forward-ab-observer?run=1",
                preflight["manual_recovery_endpoint"],
            )
            self.assertIn(
                "forward_ab_observer_capture_missing_after_close",
                preflight["blockers"],
            )
            self.assertEqual("EVIDENCE_GAP", result["same_period_collection_health"])
            self.assertFalse(monitor["live_order_allowed"])

    def test_public_preregistration_status_reconciles_the_entire_locked_contract(self):
        contract = {
            "contract_id": "LCFPR-coverage",
            "contract_hash": "locked-contract-hash",
            "generated_at": "2026-07-17T18:00:00+09:00",
            "registered_plan_count": 2,
            "blocked_plan_count": 2,
            "first_eligible_run_date": "2026-09-21",
            "symbols": ["005930", "000660", "035420"],
        }
        lookup = {
            "found": True,
            "valid": True,
            "hash_valid": True,
            "ready_for_future_execution": True,
            "generated_before_target_start": True,
            "registered_contestant_ids": ["operator", "researcher"],
            "strategy_lock_ready": True,
            "strategy_lock_plan_count": 2,
            "strategy_lock_signature_count": 4,
            "strategy_lock_digest": "a" * 64,
            "blockers": [],
            "contract": contract,
        }
        schedule = {
            "preregistered_forward_test": True,
            "target_start_date": "2026-07-20",
            "learning_preregistration_target_end_date": "2026-09-18",
            "learning_preregistration_first_eligible_run_date": "2026-09-21",
        }
        base_entry = {
            "contract_id": contract["contract_id"],
            "contract_hash": contract["contract_hash"],
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "ready_for_future_execution": True,
            "registered_plan_count": 2,
            "registered_contestant_ids": ["operator", "researcher"],
        }
        waiting_due = {
            "entries": [
                {
                    **base_entry,
                    "state": "FUTURE_LOCKED",
                    "completed_triplet_count": 0,
                    "remaining_triplet_count": 2,
                    "missing_contestant_ids": ["operator", "researcher"],
                }
            ],
            "catch_up_after_restart": True,
        }
        completed_due = {
            "entries": [
                {
                    **base_entry,
                    "state": "COMPLETED",
                    "completed_triplet_count": 2,
                    "remaining_triplet_count": 0,
                    "missing_contestant_ids": [],
                }
            ],
            "catch_up_after_restart": True,
        }
        with patch(
            "app.stock_suite_app._find_ai_staff_learning_counterfactual_preregistration",
            return_value=lookup,
        ), patch(
            "app.stock_suite_app._ai_staff_learning_counterfactual_due_preregistration_status",
            side_effect=[waiting_due, completed_due],
        ):
            waiting = build_ai_staff_learning_counterfactual_preregistration_status(
                schedule
            )
            completed = build_ai_staff_learning_counterfactual_preregistration_status(
                schedule
            )

        self.assertEqual("FUTURE_LOCKED", waiting["contract_outcome_state"])
        self.assertEqual(2, waiting["contract_registered_triplet_count"])
        self.assertEqual(0, waiting["contract_completed_triplet_count"])
        self.assertEqual(2, waiting["contract_remaining_triplet_count"])
        self.assertFalse(waiting["all_registered_plans_completed"])
        self.assertFalse(waiting["contract_result_evidence_ready"])
        self.assertTrue(waiting["contract_result_catch_up_after_restart"])
        self.assertFalse(waiting["full_strategy_payload_exposed"])
        self.assertFalse(waiting["live_order_allowed"])

        self.assertEqual("COMPLETED", completed["contract_outcome_state"])
        self.assertEqual(2, completed["contract_completed_triplet_count"])
        self.assertEqual(0, completed["contract_remaining_triplet_count"])
        self.assertTrue(completed["all_registered_plans_completed"])
        self.assertTrue(completed["contract_result_evidence_ready"])
        self.assertEqual(
            "review_completed_locked_forward_counterfactual_outcome",
            completed["next_action"],
        )

    def test_public_preregistration_status_prefers_future_ledger_lock_over_stale_schedule(self):
        contract = {
            "contract_id": "LCFPR-future",
            "contract_hash": "future-contract-hash",
            "generated_at": "2026-07-17T18:00:00+09:00",
            "registered_plan_count": 2,
            "blocked_plan_count": 0,
            "first_eligible_run_date": "2026-09-21",
            "symbols": ["005930", "000660", "035420"],
        }
        lookup = {
            "found": True,
            "valid": True,
            "hash_valid": True,
            "ready_for_future_execution": True,
            "generated_before_target_start": True,
            "registered_contestant_ids": ["operator", "researcher"],
            "strategy_lock_ready": True,
            "strategy_lock_plan_count": 2,
            "strategy_lock_signature_count": 4,
            "strategy_lock_digest": "a" * 64,
            "blockers": [],
            "contract": contract,
        }
        future_entry = {
            "contract_id": contract["contract_id"],
            "contract_hash": contract["contract_hash"],
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "first_eligible_run_date": "2026-09-21",
            "state": "FUTURE_LOCKED",
            "valid": True,
            "ready_for_future_execution": True,
            "registered_plan_count": 2,
            "completed_triplet_count": 0,
            "remaining_triplet_count": 2,
            "missing_contestant_ids": ["operator", "researcher"],
        }
        stale_schedule = {
            "preregistered_forward_test": False,
            "target_start_date": "2024-04-01",
            "target_end_date": "2026-07-16",
            "next_candidate_start_date": "2024-04-01",
            "minimum_candidate_end_date": "2026-07-16",
            "next_eligible_date": "",
        }
        due_status = {
            "entries": [future_entry],
            "selected_due_contract": {},
            "catch_up_after_restart": True,
        }
        with patch(
            "app.stock_suite_app._ai_staff_learning_counterfactual_due_preregistration_status",
            return_value=due_status,
        ), patch(
            "app.stock_suite_app._find_ai_staff_learning_counterfactual_preregistration",
            return_value=lookup,
        ) as find_contract:
            result = build_ai_staff_learning_counterfactual_preregistration_status(
                stale_schedule
            )

        find_contract.assert_called_once_with(
            "2026-07-20",
            target_end_date="2026-09-18",
        )
        self.assertEqual("REGISTERED", result["status"])
        self.assertEqual("2026-07-20", result["target_start_date"])
        self.assertEqual("2026-09-18", result["target_end_date"])
        self.assertEqual("2026-09-21", result["first_eligible_run_date"])
        self.assertEqual(
            "future_preregistration_ledger",
            result["target_selection_source"],
        )
        self.assertEqual("FUTURE_LOCKED", result["contract_outcome_state"])
        self.assertFalse(result["live_order_allowed"])

    def test_scheduler_prioritizes_matured_preregistration_over_historical_gap(self):
        due_status = {
            "ok": True,
            "status": "MATURED_PREREGISTRATION_DUE",
            "due_count": 1,
            "catch_up_after_restart": True,
            "selected_due_contract": {
                "contract_id": "LCFPR-priority",
                "contract_hash": "locked-hash",
                "target_start_date": "2026-07-20",
                "target_end_date": "2026-09-18",
                "first_eligible_run_date": "2026-09-21",
                "remaining_triplet_count": 1,
                "missing_contestant_ids": ["operator"],
                "symbols": ["005930", "000660"],
            },
        }
        historical_plan = {
            "ok": True,
            "start_date": "2025-05-01",
            "end_date": "2025-08-01",
            "missing_staff_ids": ["researcher"],
        }
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 3,
            "strategy_triplet_count": 1,
            "queue_hash": "queue-hash",
            "target_start_date": "2026-07-20",
            "preregistered_forward_test": True,
            "learning_preregistration_found": True,
            "learning_preregistration_valid": True,
            "learning_preregistration_id": "LCFPR-priority",
            "learning_preregistration_hash": "locked-hash",
            "learning_preregistration_target_end_date": "2026-09-18",
            "learning_preregistration_first_eligible_run_date": "2026-09-21",
            "jobs": [
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "operator-forward",
                    "run_type": run_type,
                }
                for run_type in (
                    "prior_official_source",
                    "same_period_baseline",
                    "same_period_adapted",
                )
            ],
        }
        focus = {
            "large_batch_jobs_allowed": False,
            "market_priority_active": False,
            "market_open": False,
            "market_phase": "closed",
        }
        with (
            patch(
                "app.stock_suite_app._ai_staff_learning_counterfactual_due_preregistration_status",
                return_value=due_status,
            ),
            patch(
                "app.stock_suite_app._ai_staff_learning_counterfactual_period_plan",
                return_value=historical_plan,
            ),
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_queue",
                return_value=queue,
            ) as queue_builder,
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
        ):
            result = build_ai_staff_learning_counterfactual_scheduler_status(
                max_triplets=1,
                now=datetime.fromisoformat("2026-09-21T18:00:00+09:00"),
            )

        self.assertTrue(result["ready_to_run"])
        self.assertTrue(result["matured_preregistration_priority_active"])
        self.assertTrue(result["matured_forward_contract_override"])
        self.assertTrue(result["large_batch_jobs_allowed"])
        self.assertEqual("2026-07-20", result["target_start_date"])
        self.assertEqual("2026-09-18", result["target_end_date"])
        self.assertEqual(["005930", "000660"], result["target_symbols"])
        self.assertEqual("LCFPR-priority", result["selected_due_preregistration_id"])
        self.assertEqual(1, result["selected_due_preregistration_remaining_triplet_count"])
        queue_builder.assert_called_once_with(
            regenerate_preparation_if_missing=True,
            target_start_date="2026-07-20",
        )
        self.assertFalse(result["live_order_allowed"])

    def test_scheduler_reports_future_locked_contract_even_before_queue_is_runnable(self):
        due_status = {
            "status": "WAITING_FOR_PREREGISTERED_PERIOD",
            "entries": [
                {
                    "valid": True,
                    "state": "FUTURE_LOCKED",
                    "contract_id": "LCFPR-future",
                    "contract_hash": "future-hash",
                    "target_start_date": "2026-07-20",
                    "target_end_date": "2026-09-18",
                    "first_eligible_run_date": "2026-09-21",
                }
            ],
            "selected_due_contract": {},
        }
        period_plan = {
            "ok": False,
            "status": "waiting_for_completed_target_period",
            "start_date": "",
            "end_date": "",
            "next_candidate_start_date": "2026-07-20",
            "minimum_candidate_end_date": "2026-09-18",
            "next_eligible_date": "2026-09-21",
            "blockers": ["no_completed_non_overlapping_target_period_available"],
        }
        queue = {
            "ok": False,
            "safe_to_execute_paper": False,
            "job_count": 0,
            "strategy_triplet_count": 0,
            "jobs": [],
            "queue_hash": "empty-queue",
            "preregistered_forward_test": False,
            "learning_preregistration_found": False,
            "learning_preregistration_valid": False,
        }
        focus = {
            "large_batch_jobs_allowed": False,
            "market_priority_active": False,
            "market_open": False,
            "market_phase": "closed",
            "large_batch_schedule": "weekend",
        }
        with (
            patch(
                "app.stock_suite_app._ai_staff_learning_counterfactual_due_preregistration_status",
                return_value=due_status,
            ),
            patch(
                "app.stock_suite_app._ai_staff_learning_counterfactual_period_plan",
                return_value=period_plan,
            ),
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_queue",
                return_value=queue,
            ),
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
        ):
            result = build_ai_staff_learning_counterfactual_scheduler_status(
                max_triplets=1,
                now=datetime.fromisoformat("2026-07-21T19:00:00+09:00"),
            )

        self.assertFalse(result["ready_to_run"])
        self.assertTrue(result["preregistered_forward_test"])
        self.assertTrue(result["learning_preregistration_found"])
        self.assertTrue(result["learning_preregistration_valid"])
        self.assertEqual("LCFPR-future", result["learning_preregistration_id"])
        self.assertEqual("future-hash", result["learning_preregistration_hash"])

    def test_daily_execution_guard_still_checks_future_preregistration_first(self):
        now = datetime.fromisoformat("2026-07-17T20:00:00+09:00")
        runtime = {
            "ok": True,
            "running": False,
            "status": "COMPLETED",
            "state": {
                "status": "COMPLETED",
                "started_at": "2026-07-17T18:00:00+09:00",
            },
            "paper_only": True,
            "live_order_allowed": False,
        }
        schedule = {
            "ok": True,
            "ready_to_run": False,
            "next_candidate_start_date": "2026-07-20",
            "minimum_candidate_end_date": "2026-09-18",
            "next_eligible_date": "2026-09-21",
        }
        preregistration = {
            "ok": True,
            "status": "REGISTERED",
            "created": True,
            "paper_only": True,
            "live_order_allowed": False,
        }
        with (
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_runtime_status",
                return_value=runtime,
            ),
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_scheduler_status",
                return_value=schedule,
            ) as schedule_builder,
            patch(
                "app.stock_suite_app._maybe_preregister_ai_staff_learning_counterfactual",
                return_value=preregistration,
            ) as preregister,
        ):
            result = _maybe_schedule_ai_staff_learning_counterfactual(
                "test-daily-guard",
                now=now,
            )

        self.assertEqual("DAILY_COUNTERFACTUAL_ALREADY_ATTEMPTED", result["status"])
        self.assertFalse(result["scheduled"])
        self.assertEqual("REGISTERED", result["preregistration"]["status"])
        schedule_builder.assert_called_once_with(max_triplets=2, now=now)
        preregister.assert_called_once_with(schedule, now=now)
        self.assertFalse(result["live_order_allowed"])

    def test_learning_counterfactual_sample_run_writes_non_promoting_paper_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            queue_path = Path(temp_dir) / "learning-queue.json"
            ledger_path = Path(temp_dir) / "learning-ledger.jsonl"
            replay = {
                "id": "REPLAY-SAMPLE",
                "actual_start_date": "2024-01-02",
                "actual_end_date": "2024-03-29",
                "total_return_pct": 3.2,
                "max_drawdown_pct": -2.1,
                "trade_count": 4,
                "cost_model": {"commission_bps": 1.5},
                "transaction_cost_audit": {"passed": True},
                "execution_timing_model": {
                    "lookahead_safe_required": True,
                    "same_bar_signal_execution_allowed": False,
                    "minimum_signal_lag_bars": 1,
                },
                "data_coverage": {"portfolio_boundary_coverage_passed": True},
                "replay_data_bundle_evidence": self._counterfactual_replay_bundle_evidence(),
            }
            contexts = self._causal_contexts("operator")
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={
                        "large_batch_jobs_allowed": True,
                        "market_priority_active": False,
                        "market_open": False,
                        "market_phase": "closed",
                    },
                ),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path),
                patch(
                    "app.stock_suite_app._build_historical_replay_data_bundle",
                    return_value={"schema": "codexstock_replay_data_bundle_v1", "content_hash": "sha256:bundle"},
                ) as build_bundle,
                patch("app.stock_suite_app.run_historical_paper_replay", return_value=replay) as run_replay,
            ):
                result = run_ai_staff_learning_counterfactual_sample(max_jobs=2, symbols=["005930"])

            self.assertTrue(result["ok"])
            self.assertEqual(2, result["completed_count"])
            self.assertEqual(0, result["failed_count"])
            self.assertTrue(ledger_path.exists())
            self.assertFalse(result["live_order_allowed"])
            self.assertFalse(result["automatic_promotion"])
            self.assertFalse(result["official_learning_evidence"])
            self.assertFalse(result["unverified_result_affects_score"])
            source_row, replay_row = result["rows"]
            self.assertEqual("verified_prior_official_source_observation", source_row["evidence_role"])
            self.assertEqual("existing_official_source_observation_reused_by_hash", source_row["replay_skipped_reason"])
            self.assertEqual("COMPLETED", replay_row["status"])
            self.assertEqual("REPLAY-SAMPLE", replay_row["replay_id"])
            self.assertFalse(replay_row["live_order_allowed"])
            self.assertFalse(replay_row["official_learning_evidence"])
            self.assertRegex(replay_row["ledger_hash"], r"^[0-9a-f]{64}$")
            run_replay.assert_called_once()
            build_bundle.assert_called_once()
            self.assertIsNotNone(run_replay.call_args.kwargs["replay_data_bundle"])

    def test_learning_counterfactual_sample_defers_during_market_priority(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "queue_hash": "queue-hash",
            "jobs": [{"job_id": "sample-job", "run_type": "same_period_baseline", "strategy": {}}],
        }
        focus = {
            "large_batch_jobs_allowed": False,
            "market_priority_active": True,
            "market_open": False,
            "market_phase": "premarket",
            "mode": "MARKET_PREPARATION_FOCUS",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch("app.stock_suite_app.build_ai_staff_learning_counterfactual_queue", return_value=queue),
            patch("app.stock_suite_app.run_historical_paper_replay") as run_replay,
        ):
            result = run_ai_staff_learning_counterfactual_sample(max_jobs=1, symbols=["005930"])

        run_replay.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual("deferred_to_market_closed_window", result["status"])
        self.assertEqual(1, result["requested_job_count"])
        self.assertEqual(0, result["completed_count"])
        self.assertEqual([], result["rows"])
        self.assertEqual("MARKET_PREPARATION_FOCUS", result["current_focus_mode"])
        self.assertIn("직원 학습 직접 실행 보류", result["operator_message"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["unverified_result_affects_score"])

    def test_learning_counterfactual_triplet_runs_one_complete_strategy_set_without_promotion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            queue_path = Path(temp_dir) / "learning-queue.json"
            ledger_path = Path(temp_dir) / "learning-ledger.jsonl"

            def fake_replay(**kwargs):
                return {
                    "id": f"REPLAY-{kwargs['source'][-8:]}",
                    "actual_start_date": kwargs["start_date"],
                    "actual_end_date": kwargs["end_date"],
                    "total_return_pct": 1.0,
                    "max_drawdown_pct": -0.5,
                    "trade_count": 2,
                    "cost_model": {"commission_bps": 1.5},
                    "transaction_cost_audit": {"passed": True},
                    "execution_timing_model": {
                        "lookahead_safe_required": True,
                        "same_bar_signal_execution_allowed": False,
                        "minimum_signal_lag_bars": 1,
                    },
                    "data_coverage": {"portfolio_boundary_coverage_passed": True},
                    "replay_data_bundle_evidence": self._counterfactual_replay_bundle_evidence(),
                }

            contexts = self._causal_contexts("operator")
            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={
                        "large_batch_jobs_allowed": True,
                        "market_priority_active": False,
                        "market_open": False,
                        "market_phase": "closed",
                    },
                ),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path),
                patch(
                    "app.stock_suite_app._build_historical_replay_data_bundle",
                    return_value={"schema": "codexstock_replay_data_bundle_v1", "content_hash": "sha256:bundle"},
                ) as build_bundle,
                patch("app.stock_suite_app.run_historical_paper_replay", side_effect=fake_replay) as run_replay,
            ):
                result = run_ai_staff_learning_counterfactual_triplet(symbols=["005930"])

            self.assertTrue(result["ok"])
            self.assertTrue(result["triplet_complete"])
            self.assertEqual(3, result["completed_count"])
            self.assertEqual(0, result["failed_count"])
            self.assertEqual(
                ["prior_official_source", "same_period_adapted", "same_period_baseline"],
                result["completed_run_types"],
            )
            self.assertFalse(result["official_learning_evidence"])
            self.assertFalse(result["promotion_allowed"])
            self.assertFalse(result["live_order_allowed"])
            self.assertEqual(2, run_replay.call_count)
            self.assertEqual(1, build_bundle.call_count)
            bundle_ids = {
                id(call.kwargs["replay_data_bundle"])
                for call in run_replay.call_args_list
            }
            self.assertEqual(1, len(bundle_ids))
            strategy_ids = {row["strategy_generation_id"] for row in result["rows"]}
            self.assertEqual(1, len(strategy_ids))
            self.assertTrue(ledger_path.exists())

    def test_learning_counterfactual_triplet_defers_during_market_priority(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "queue_hash": "queue-hash",
            "jobs": [
                {
                    "job_id": f"job-{run_type}",
                    "contestant_id": "operator",
                    "strategy_generation_id": "S1",
                    "run_type": run_type,
                    "strategy": {},
                }
                for run_type in ("prior_official_source", "same_period_baseline", "same_period_adapted")
            ],
        }
        focus = {
            "large_batch_jobs_allowed": False,
            "market_priority_active": True,
            "market_open": False,
            "market_phase": "premarket",
            "mode": "MARKET_PREPARATION_FOCUS",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch("app.stock_suite_app.build_ai_staff_learning_counterfactual_queue", return_value=queue),
            patch("app.stock_suite_app._ai_staff_counterfactual_ledger_summary", return_value={"completed_triplet_keys": []}),
            patch("app.stock_suite_app.run_historical_paper_replay") as run_replay,
        ):
            result = run_ai_staff_learning_counterfactual_triplet(symbols=["005930"])

        run_replay.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual("deferred_to_market_closed_window", result["status"])
        self.assertFalse(result["triplet_complete"])
        self.assertEqual(0, result["completed_count"])
        self.assertEqual([], result["rows"])
        self.assertEqual("MARKET_PREPARATION_FOCUS", result["current_focus_mode"])
        self.assertFalse(result["live_order_allowed"])

    def test_learning_counterfactual_queue_separates_baseline_and_adapted_strategy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            queue_path = Path(temp_dir) / "learning-queue.json"
            ledger_path = Path(temp_dir) / "learning-ledger.jsonl"
            contexts = self._causal_contexts("operator")

            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path),
            ):
                queue = build_ai_staff_learning_counterfactual_queue()

            first_jobs = queue["jobs"][:3]
            by_type = {job["run_type"]: job for job in first_jobs}
            self.assertEqual(
                by_type["prior_official_source"]["strategy"],
                by_type["same_period_baseline"]["strategy"],
            )
            self.assertNotEqual(
                by_type["same_period_baseline"]["strategy"],
                by_type["same_period_adapted"]["strategy"],
            )
            self.assertEqual(
                by_type["same_period_baseline"]["source_strategy"],
                by_type["same_period_baseline"]["strategy"],
            )
            self.assertEqual(
                by_type["same_period_adapted"]["adapted_strategy"],
                by_type["same_period_adapted"]["strategy"],
            )
            self.assertFalse(queue["live_order_allowed"])
            self.assertFalse(queue["unverified_result_affects_score"])

    def test_counterfactual_ledger_summary_groups_completed_triplets_without_promotion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.jsonl"
            rows = self._causal_ledger_triplet(strategy_id="S1")
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            with patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path):
                summary = _ai_staff_counterfactual_ledger_summary()

            self.assertEqual(3, summary["ledger_row_count"])
            self.assertEqual(1, summary["completed_triplet_count"])
            self.assertEqual(1, summary["diagnostic_completed_triplet_count"])
            self.assertEqual(0, summary["excluded_noncausal_triplet_count"])
            self.assertEqual(1, summary["improved_triplet_count"])
            self.assertEqual(1, summary["directionally_improved_triplet_count"])
            self.assertEqual(0, summary["directionally_regressed_triplet_count"])
            self.assertEqual(3, summary["required_improved_triplet_count_for_official_evidence"])
            self.assertEqual(2, summary["additional_improved_triplet_count_needed"])
            self.assertEqual("run_more_paper_counterfactual_triplets", summary["next_verification_action"])
            self.assertFalse(summary["counterfactual_confidence_gate_passed"])
            self.assertFalse(summary["counterfactual_effect_statistics"]["confidence_gate_passed"])
            self.assertIn(
                "validated_pair_count_below_minimum",
                summary["counterfactual_confidence_gate_blockers"],
            )
            self.assertEqual(
                2,
                summary["counterfactual_effect_statistics"]["additional_validated_pair_count_needed"],
            )
            self.assertEqual(
                1,
                summary["counterfactual_effect_statistics"]["additional_improved_pair_count_needed"],
            )
            self.assertIn("개선 트리플릿 2개 추가 필요", summary["operator_message"])
            self.assertFalse(summary["official_counterfactual_promotion_ready"])
            self.assertFalse(summary["official_learning_evidence"])
            self.assertFalse(summary["live_order_allowed"])
            self.assertFalse(summary["unverified_result_affects_score"])
            self.assertEqual("improved", summary["triplet_preview"][0]["status"])
            self.assertTrue(summary["triplet_preview"][0]["causal_learning_evidence_eligible"])

    def test_counterfactual_learning_merge_counts_only_independent_paper_triplets(self):
        entry = {
            "validated_learning_pair_count": 0,
            "improved_learning_pair_count": 0,
            "regressed_learning_pair_count": 0,
            "inconclusive_learning_pair_count": 0,
            "causal_learning_link_count": 0,
            "counterfactual_learning_pair_count": 0,
            "counterfactual_learning_pair_excluded_count": 0,
            "verified_source_record_ids": [],
            "learning_pairs": [],
            "risk_adjusted_improvements": [],
            "_validated_pair_keys": set(),
            "_validated_target_periods": [],
            "_counterfactual_transition_hashes": set(),
        }
        triplets = [
            self._counterfactual_summary_triplet(
                start_date="2024-05-13",
                end_date="2024-07-05",
                improvement=2.0,
                index=1,
            ),
            self._counterfactual_summary_triplet(
                start_date="2024-08-05",
                end_date="2024-10-04",
                improvement=1.5,
                index=2,
            ),
            self._counterfactual_summary_triplet(
                start_date="2024-11-04",
                end_date="2025-01-03",
                improvement=0.5,
                index=3,
            ),
        ]

        merged = _merge_ai_staff_counterfactual_learning_pairs({"operator": entry}, triplets)

        self.assertEqual({"merged_count": 3, "excluded_count": 0}, merged)
        self.assertEqual(3, entry["validated_learning_pair_count"])
        self.assertEqual(2, entry["improved_learning_pair_count"])
        self.assertEqual(1, entry["inconclusive_learning_pair_count"])
        self.assertEqual(3, len(entry["_validated_target_periods"]))
        self.assertEqual(3, len(entry["_counterfactual_transition_hashes"]))
        self.assertTrue(all(pair["paper_only"] for pair in entry["learning_pairs"]))
        self.assertTrue(all(pair["live_order_allowed"] is False for pair in entry["learning_pairs"]))

        overlapping = self._counterfactual_summary_triplet(
            start_date="2024-06-03",
            end_date="2024-06-28",
            improvement=9.0,
            index=4,
        )
        rejected = _merge_ai_staff_counterfactual_learning_pairs({"operator": entry}, [overlapping])
        self.assertEqual({"merged_count": 0, "excluded_count": 1}, rejected)
        self.assertEqual(3, entry["validated_learning_pair_count"])
        self.assertIn("target_period_overlaps_prior_learning_pair", entry["learning_pairs"][-1]["blockers"])

    def test_learning_audit_consumes_full_counterfactual_ledger_without_exposing_bulk_rows(self):
        triplets = [
            self._counterfactual_summary_triplet(
                start_date="2024-05-13",
                end_date="2024-07-05",
                improvement=2.0,
                index=1,
            ),
            self._counterfactual_summary_triplet(
                start_date="2024-08-05",
                end_date="2024-10-04",
                improvement=1.5,
                index=2,
            ),
            self._counterfactual_summary_triplet(
                start_date="2024-11-04",
                end_date="2025-01-03",
                improvement=0.5,
                index=3,
            ),
        ]
        ledger_summary = {
            "completed_triplet_count": 3,
            "diagnostic_completed_triplet_count": 3,
            "excluded_noncausal_triplet_count": 0,
            "causal_completed_triplets": triplets,
        }
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=[]),
            patch("app.stock_suite_app._historical_replay_certified_score_index", return_value={"ok": True}),
            patch("app.stock_suite_app._ai_staff_counterfactual_ledger_summary", return_value=ledger_summary),
            patch(
                "app.stock_suite_app._write_ai_staff_learning_experiment_contract",
                return_value={"queue_count": 4, "path": "test", "contract_hash": "test"},
            ),
        ):
            result = ai_staff_learning_audit(limit=10)

        operator = self._operator(result)
        self.assertEqual(3, operator["validated_learning_pair_count"])
        self.assertEqual(3, operator["counterfactual_learning_pair_count"])
        self.assertEqual(3, operator["verified_counterfactual_transition_count"])
        self.assertEqual({"merged_count": 3, "excluded_count": 0}, result["counterfactual_learning_pair_merge"])
        self.assertNotIn("causal_completed_triplets", result["counterfactual_ledger_summary"])
        self.assertFalse(operator["growth_proven"])

    def test_counterfactual_ledger_summary_rejects_directionally_regressed_strategy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.jsonl"
            rows = []
            for run_type, return_pct, mdd in (
                ("prior_official_source", 2.0, -1.0),
                ("same_period_baseline", 2.0, -1.0),
                ("same_period_adapted", 0.5, -2.0),
            ):
                rows.append(
                    {
                        "schema": "codexstock_ai_staff_learning_counterfactual_ledger_v1",
                        "contestant_id": "risk_manager",
                        "strategy_generation_id": "S-REGRESS",
                        "run_type": run_type,
                        "status": "COMPLETED",
                        "start_date": "2024-01-02",
                        "end_date": "2024-03-29",
                        "symbols": ["005930"],
                        "total_return_pct": return_pct,
                        "max_drawdown_pct": mdd,
                        "paper_only": True,
                        "official_learning_evidence": False,
                        "live_order_allowed": False,
                    }
                )
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            with patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path):
                summary = _ai_staff_counterfactual_ledger_summary()

            self.assertEqual(0, summary["completed_triplet_count"])
            self.assertEqual(1, summary["diagnostic_completed_triplet_count"])
            self.assertEqual(1, summary["excluded_noncausal_triplet_count"])
            self.assertEqual(0, summary["directionally_regressed_triplet_count"])
            self.assertEqual(1, summary["diagnostic_directionally_regressed_triplet_count"])
            self.assertEqual(1, summary["reject_from_live_candidate_count"])
            self.assertEqual(["S-REGRESS"], summary["rejected_strategy_ids"])
            self.assertEqual("S-REGRESS", summary["rejected_strategy_records"][0]["strategy_generation_id"])
            verdict = summary["strategy_verdicts"][0]
            self.assertEqual("reject_from_live_candidate", verdict["verdict"])
            self.assertFalse(verdict["live_candidate_allowed"])
            self.assertFalse(verdict["score_promotion_allowed"])
            self.assertFalse(verdict["official_learning_evidence"])
            self.assertFalse(verdict["causal_learning_evidence_eligible"])

    def test_counterfactual_ledger_summary_quarantines_mismatched_transition_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.jsonl"
            rows = self._causal_ledger_triplet(strategy_id="S-TAMPERED")
            rows[-1]["learning_transition_hash"] = "0" * 64
            tampered_material = dict(rows[-1])
            tampered_material.pop("ledger_hash", None)
            rows[-1]["ledger_hash"] = hashlib.sha256(
                json.dumps(tampered_material, ensure_ascii=True, sort_keys=True).encode("utf-8")
            ).hexdigest()
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            with patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path):
                summary = _ai_staff_counterfactual_ledger_summary()

            self.assertEqual(0, summary["causal_completed_triplet_count"])
            self.assertEqual(1, summary["diagnostic_completed_triplet_count"])
            self.assertEqual(1, summary["excluded_noncausal_triplet_count"])
            blockers = summary["diagnostic_triplet_preview"][0]["causal_learning_evidence_blockers"]
            self.assertIn("same_period_adapted:ledger_transition_hash_mismatch", blockers)
            self.assertEqual(0, summary["counterfactual_effect_statistics"]["sample_count"])
            self.assertFalse(summary["official_counterfactual_promotion_ready"])

    def test_counterfactual_ledger_rejects_different_execution_contracts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.jsonl"
            rows = self._causal_ledger_triplet(strategy_id="S-CONTRACT-MISMATCH")
            adapted = rows[-1]
            contract = adapted["execution_comparison_contract"]
            contract["initial_cash"] = 50_000_000.0
            contract["contract_hash"] = _ai_staff_counterfactual_execution_contract_hash(
                contract
            )
            adapted["execution_comparison_contract_hash"] = contract["contract_hash"]
            adapted["initial_cash"] = 50_000_000.0
            adapted_material = dict(adapted)
            adapted_material.pop("ledger_hash", None)
            adapted["ledger_hash"] = hashlib.sha256(
                json.dumps(adapted_material, ensure_ascii=True, sort_keys=True).encode("utf-8")
            ).hexdigest()
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            with patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path):
                summary = _ai_staff_counterfactual_ledger_summary()

        self.assertEqual(0, summary["causal_completed_triplet_count"])
        blockers = summary["diagnostic_triplet_preview"][0]["causal_learning_evidence_blockers"]
        self.assertIn("same_period_execution_contract_hash_mismatch", blockers)
        self.assertFalse(summary["official_counterfactual_promotion_ready"])

    def test_counterfactual_ledger_rejects_simulated_fallback_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.jsonl"
            rows = self._causal_ledger_triplet(strategy_id="S-SIMULATED-FALLBACK")
            for row in rows[1:]:
                contract = row["execution_comparison_contract"]
                contract["allow_simulated_fallback"] = True
                contract["contract_hash"] = _ai_staff_counterfactual_execution_contract_hash(
                    contract
                )
                row["execution_comparison_contract_hash"] = contract["contract_hash"]
                row["allow_simulated_fallback"] = True
                material = dict(row)
                material.pop("ledger_hash", None)
                row["ledger_hash"] = hashlib.sha256(
                    json.dumps(material, ensure_ascii=True, sort_keys=True).encode("utf-8")
                ).hexdigest()
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            with patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path):
                summary = _ai_staff_counterfactual_ledger_summary()

        self.assertEqual(0, summary["causal_completed_triplet_count"])
        blockers = summary["diagnostic_triplet_preview"][0]["causal_learning_evidence_blockers"]
        self.assertIn(
            "same_period_baseline:execution_contract_simulated_fallback_not_blocked",
            blockers,
        )
        self.assertFalse(summary["official_counterfactual_promotion_ready"])

    def test_counterfactual_ledger_rejects_different_replay_data_slice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "ledger.jsonl"
            rows = self._causal_ledger_triplet(strategy_id="S-DATA-MISMATCH")
            adapted = rows[-1]
            evidence = adapted["replay_data_bundle_evidence"]
            evidence["slice_content_hash"] = "sha256:" + "c" * 64
            evidence["slice_manifest_hash"] = _replay_data_bundle_slice_manifest_hash(
                evidence
            )
            material = dict(adapted)
            material.pop("ledger_hash", None)
            adapted["ledger_hash"] = hashlib.sha256(
                json.dumps(material, ensure_ascii=True, sort_keys=True).encode("utf-8")
            ).hexdigest()
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            with patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path):
                summary = _ai_staff_counterfactual_ledger_summary()

        self.assertEqual(0, summary["causal_completed_triplet_count"])
        blockers = summary["diagnostic_triplet_preview"][0]["causal_learning_evidence_blockers"]
        self.assertIn("same_period_replay_data_bundle_hash_mismatch", blockers)
        self.assertFalse(summary["official_counterfactual_promotion_ready"])

    def test_counterfactual_rejection_filter_uses_full_records_not_truncated_preview(self):
        summary = {
            "strategy_verdicts": [],
            "rejected_strategy_records": [
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "OLD-REJECT",
                    "reason": "directionally_regressed_in_same_period_counterfactual",
                    "risk_adjusted_improvement": -3.2,
                }
            ],
        }

        rejected = _ai_staff_counterfactual_rejected_strategy_ids("operator", summary=summary)

        self.assertIn("OLD-REJECT", rejected)
        self.assertFalse(rejected["OLD-REJECT"]["live_candidate_allowed"])
        self.assertFalse(rejected["OLD-REJECT"]["score_promotion_allowed"])
        self.assertFalse(rejected["OLD-REJECT"]["official_learning_evidence"])

    def test_counterfactual_rejected_generated_strategy_is_excluded_from_next_draft(self):
        contestant = {
            "id": "operator",
            "strategy_mode": "ma_cross",
            "strategy_name": "operator baseline",
            "fast": 12,
            "slow": 32,
            "allocation_pct": 25,
            "max_positions": 3,
            "stop_loss_pct": 8,
            "take_profit_pct": 0,
            "holding_limit_days": 0,
        }
        generated = _ai_staff_role_generated_strategy_configs(contestant, season_index=0)
        rejected_id = str(generated[0]["strategy_generation_id"])
        ledger_rows = []
        for run_type, return_pct, mdd in (
            ("prior_official_source", 2.0, -1.0),
            ("same_period_baseline", 2.0, -1.0),
            ("same_period_adapted", 0.0, -6.0),
        ):
            ledger_rows.append(
                {
                    "schema": "codexstock_ai_staff_learning_counterfactual_ledger_v1",
                    "contestant_id": "operator",
                    "strategy_generation_id": rejected_id,
                    "run_type": run_type,
                    "status": "COMPLETED",
                    "start_date": "2024-01-02",
                    "end_date": "2024-03-29",
                    "symbols": ["005930"],
                    "total_return_pct": return_pct,
                    "max_drawdown_pct": mdd,
                    "paper_only": True,
                    "official_learning_evidence": False,
                    "live_order_allowed": False,
                }
            )

        with patch("app.stock_suite_app._read_jsonl", return_value=ledger_rows):
            configs = _ai_tournament_challenge_configs(
                contestant,
                trial_budget=12,
                before_date="2024-04-01",
                end_date="2024-06-28",
                season_index=0,
            )

        selected_ids = {str(config.get("strategy_generation_id") or "") for config in configs}
        self.assertNotIn(rejected_id, selected_ids)
        self.assertTrue(any(config.get("counterfactual_rejection_filter") for config in configs))
        for config in configs:
            filter_info = config.get("counterfactual_rejection_filter")
            if isinstance(filter_info, dict):
                self.assertEqual(1, filter_info["blocked_strategy_count"])
                self.assertIn(rejected_id, filter_info["blocked_strategy_ids"])
                self.assertFalse(filter_info["live_candidate_allowed"])
                self.assertFalse(filter_info["score_promotion_allowed"])

    def test_learning_counterfactual_triplet_does_not_skip_uncertified_completed_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            queue_path = Path(temp_dir) / "learning-queue.json"
            ledger_path = Path(temp_dir) / "learning-ledger.jsonl"
            contexts = self._causal_contexts("operator", "researcher")

            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path),
            ):
                queue = build_ai_staff_learning_counterfactual_queue()
            first_strategy = queue["jobs"][0]["strategy_generation_id"]
            completed_rows = []
            for job in queue["jobs"][:3]:
                completed_rows.append(
                    {
                        "schema": "codexstock_ai_staff_learning_counterfactual_ledger_v1",
                        "contestant_id": job["contestant_id"],
                        "strategy_generation_id": job["strategy_generation_id"],
                        "run_type": job["run_type"],
                        "status": "COMPLETED",
                        "start_date": "2024-01-02",
                        "end_date": "2024-03-29",
                        "symbols": ["005930"],
                        "total_return_pct": 0.0,
                        "max_drawdown_pct": 0.0,
                        "paper_only": True,
                        "official_learning_evidence": False,
                        "live_order_allowed": False,
                    }
                )
            ledger_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in completed_rows) + "\n",
                encoding="utf-8",
            )

            def fake_replay(**kwargs):
                return {
                    "id": f"REPLAY-{kwargs['source'][-8:]}",
                    "actual_start_date": kwargs["start_date"],
                    "actual_end_date": kwargs["end_date"],
                    "total_return_pct": 1.0,
                    "max_drawdown_pct": -0.5,
                    "trade_count": 2,
                    "cost_model": {"commission_bps": 1.5},
                    "transaction_cost_audit": {"passed": True},
                    "execution_timing_model": {
                        "lookahead_safe_required": True,
                        "same_bar_signal_execution_allowed": False,
                        "minimum_signal_lag_bars": 1,
                    },
                    "data_coverage": {"portfolio_boundary_coverage_passed": True},
                    "replay_data_bundle_evidence": self._counterfactual_replay_bundle_evidence(),
                }

            with (
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={
                        "large_batch_jobs_allowed": True,
                        "market_priority_active": False,
                        "market_open": False,
                        "market_phase": "closed",
                    },
                ),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path),
                patch(
                    "app.stock_suite_app._build_historical_replay_data_bundle",
                    return_value={"schema": "codexstock_replay_data_bundle_v1", "content_hash": "sha256:bundle"},
                ),
                patch("app.stock_suite_app.run_historical_paper_replay", side_effect=fake_replay),
            ):
                result = run_ai_staff_learning_counterfactual_triplet(symbols=["005930"])

            self.assertTrue(result["triplet_complete"])
            self.assertEqual(first_strategy, result["triplet_key"]["strategy_generation_id"])
            self.assertEqual(3, result["completed_count"])
            self.assertFalse(result["official_learning_evidence"])

    def test_learning_counterfactual_triplet_batch_runs_multiple_uncompleted_sets_safely(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "learning-contract.json"
            prep_path = Path(temp_dir) / "learning-prep.json"
            queue_path = Path(temp_dir) / "learning-queue.json"
            ledger_path = Path(temp_dir) / "learning-ledger.jsonl"
            contexts = self._causal_contexts("operator", "researcher")

            def fake_replay(**kwargs):
                return {
                    "id": f"REPLAY-{kwargs['source'][-8:]}",
                    "actual_start_date": kwargs["start_date"],
                    "actual_end_date": kwargs["end_date"],
                    "total_return_pct": 1.0,
                    "max_drawdown_pct": -0.5,
                    "trade_count": 2,
                    "cost_model": {"commission_bps": 1.5},
                    "transaction_cost_audit": {"passed": True},
                    "execution_timing_model": {
                        "lookahead_safe_required": True,
                        "same_bar_signal_execution_allowed": False,
                        "minimum_signal_lag_bars": 1,
                    },
                    "data_coverage": {"portfolio_boundary_coverage_passed": True},
                }

            with (
                patch("app.stock_suite_app._read_jsonl", return_value=[]),
                patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value=contexts),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={
                        "large_batch_jobs_allowed": True,
                        "large_batch_schedule": "weekend",
                        "market_priority_active": False,
                        "market_open": False,
                        "market_phase": "closed",
                    },
                ),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_EXPERIMENT_FILE", contract_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_ADAPTATION_PREP_FILE", prep_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_QUEUE_FILE", queue_path),
                patch("app.stock_suite_app.AI_STAFF_LEARNING_COUNTERFACTUAL_LEDGER_FILE", ledger_path),
                patch("app.stock_suite_app.run_historical_paper_replay", side_effect=fake_replay) as run_replay,
            ):
                result = run_ai_staff_learning_counterfactual_triplet_batch(
                    max_triplets=2,
                    symbols=["005930"],
                    start_date="2024-01-02",
                    end_date="2024-03-29",
                )

            self.assertTrue(result["ok"])
            self.assertEqual(2, result["executed_triplet_count"])
            self.assertEqual(2, result["completed_triplet_count"])
            self.assertEqual(0, result["failed_triplet_count"])
            self.assertEqual(4, run_replay.call_count)
            self.assertFalse(result["official_learning_evidence"])
            self.assertFalse(result["promotion_allowed"])
            self.assertFalse(result["live_order_allowed"])
            self.assertFalse(result["unverified_result_affects_score"])
            strategy_ids = {
                row["strategy_generation_id"]
                for triplet in result["results"]
                for row in triplet["rows"]
            }
            self.assertEqual(2, len(strategy_ids))

    def test_learning_counterfactual_triplet_batch_uses_scheduler_period_when_dates_omitted(self):
        schedule = {
            "ok": True,
            "ready_to_run": True,
            "status": "ready_to_run",
            "target_start_date": "2025-05-01",
            "target_end_date": "2025-08-01",
        }
        triplet = {
            "ok": True,
            "triplet_complete": True,
            "selected_existing_triplet_was_skipped": False,
            "triplet_key": {
                "contestant_id": "operator",
                "strategy_generation_id": "operator-gap-strategy",
            },
            "rows": [],
        }
        with (
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_scheduler_status",
                return_value=schedule,
            ) as scheduler,
            patch(
                "app.stock_suite_app.run_ai_staff_learning_counterfactual_triplet",
                return_value=triplet,
            ) as run_triplet,
            patch(
                "app.stock_suite_app._ai_staff_counterfactual_ledger_summary",
                return_value={"causal_completed_triplet_count": 1},
            ),
        ):
            result = run_ai_staff_learning_counterfactual_triplet_batch(
                max_triplets=1,
                symbols=["005930"],
            )

        scheduler.assert_called_once_with(
            max_triplets=1,
            target_start_date="",
            heavy_slot_reserved=False,
        )
        self.assertEqual("2025-05-01", run_triplet.call_args.kwargs["start_date"])
        self.assertEqual("2025-08-01", run_triplet.call_args.kwargs["end_date"])
        self.assertEqual("2025-05-01", result["target_start_date"])
        self.assertEqual("2025-08-01", result["target_end_date"])
        self.assertEqual(1, result["completed_triplet_count"])
        self.assertFalse(result["live_order_allowed"])

    def test_learning_counterfactual_triplet_batch_defers_during_market_priority(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 36,
            "strategy_triplet_count": 12,
            "path": "C:/tmp/queue.json",
            "queue_hash": "queue-hash",
            "jobs": [{"job_id": "should-not-run"}],
        }
        focus = {
            "large_batch_jobs_allowed": False,
            "large_batch_schedule": "weekend",
            "market_priority_active": True,
            "market_open": False,
            "market_phase": "premarket",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch("app.stock_suite_app.build_ai_staff_learning_counterfactual_queue", return_value=queue),
            patch("app.stock_suite_app.run_ai_staff_learning_counterfactual_triplet") as run_triplet,
        ):
            result = run_ai_staff_learning_counterfactual_triplet_batch(max_triplets=2, symbols=["005930"])

        run_triplet.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertEqual("deferred_to_market_closed_window", result["status"])
        self.assertEqual(0, result["executed_triplet_count"])
        self.assertEqual(0, result["completed_triplet_count"])
        self.assertEqual("defer_staff_learning_counterfactual_triplets", result["stopped_reason"])
        self.assertIn("장마감/주말 슬롯", result["operator_message"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["unverified_result_affects_score"])

    def test_learning_counterfactual_scheduler_defers_during_market_priority(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 36,
            "strategy_triplet_count": 12,
            "path": "C:/tmp/queue.json",
            "queue_hash": "queue-hash",
        }
        focus = {
            "large_batch_jobs_allowed": False,
            "large_batch_schedule": "weekend",
            "market_priority_active": True,
            "market_open": False,
            "market_phase": "premarket",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch("app.stock_suite_app.build_ai_staff_learning_counterfactual_queue", return_value=queue),
        ):
            result = build_ai_staff_learning_counterfactual_scheduler_status(max_triplets=2)

        self.assertEqual("deferred_to_market_closed_window", result["status"])
        self.assertFalse(result["ready_to_run"])
        self.assertIn("large_batch_window_not_allowed", result["blockers"])
        self.assertIn("market_priority_active", result["blockers"])
        self.assertIn("직원 학습 검증 보류", result["operator_message"])
        self.assertIn("장마감/주말 슬롯", result["operator_message"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["automatic_promotion"])
        self.assertFalse(result["unverified_result_affects_score"])

    def test_learning_counterfactual_scheduler_allows_market_closed_large_batch_window(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 36,
            "strategy_triplet_count": 12,
            "path": "C:/tmp/queue.json",
            "queue_hash": "queue-hash",
        }
        focus = {
            "large_batch_jobs_allowed": True,
            "large_batch_schedule": "weekend",
            "market_priority_active": False,
            "market_open": False,
            "market_phase": "closed",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_queue",
                return_value=queue,
            ) as queue_builder,
        ):
            result = build_ai_staff_learning_counterfactual_scheduler_status(
                max_triplets=2,
                target_start_date="2025-01-06",
            )

        self.assertEqual("ready_to_run", result["status"])
        self.assertTrue(result["ready_to_run"])
        self.assertEqual("2025-01-06", result["target_start_date"])
        queue_builder.assert_called_once_with(
            regenerate_preparation_if_missing=True,
            target_start_date="2025-01-06",
        )
        self.assertEqual([], result["blockers"])
        self.assertEqual("run_ai_staff_learning_counterfactual_triplet_batch", result["next_action"])
        self.assertIn("직원 학습 검증 준비 완료", result["operator_message"])
        self.assertEqual(12, result["queue_triplet_count"])
        self.assertFalse(result["live_order_allowed"])

    def test_learning_counterfactual_scheduler_does_not_requeue_completed_staff(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 3,
            "strategy_triplet_count": 1,
            "path": "C:/tmp/queue.json",
            "queue_hash": "queue-hash",
            "jobs": [
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "operator-completed",
                    "run_type": run_type,
                }
                for run_type in (
                    "prior_official_source",
                    "same_period_baseline",
                    "same_period_adapted",
                )
            ],
        }
        period_plan = {
            "ok": True,
            "start_date": "2025-05-01",
            "end_date": "2025-08-01",
            "missing_staff_ids": ["researcher", "risk_manager", "strategy_researcher"],
        }
        focus = {
            "large_batch_jobs_allowed": True,
            "large_batch_schedule": "weekend",
            "market_priority_active": False,
            "market_open": False,
            "market_phase": "closed",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app._ai_staff_learning_counterfactual_period_plan",
                return_value=period_plan,
            ),
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_queue",
                return_value=queue,
            ),
        ):
            result = build_ai_staff_learning_counterfactual_scheduler_status(max_triplets=2)

        self.assertEqual("waiting", result["status"])
        self.assertFalse(result["ready_to_run"])
        self.assertEqual(3, result["queue_total_job_count"])
        self.assertEqual(1, result["queue_total_triplet_count"])
        self.assertEqual(0, result["queue_job_count"])
        self.assertEqual(0, result["queue_triplet_count"])
        self.assertTrue(result["queue_filtered_to_missing_staff"])
        self.assertIn("missing_staff_have_no_runnable_causal_transition", result["blockers"])
        self.assertIn("임의 Paper 실험을 만들지 않습니다", result["operator_message"])
        self.assertFalse(result["live_order_allowed"])

    def test_counterfactual_period_plan_fills_missing_staff_before_opening_new_period(self):
        contexts = self._causal_contexts()
        contestant_ids = sorted(contexts)
        summary = {
            "causal_completed_triplet_keys": [
                {
                    "contestant_id": contestant_ids[0],
                    "start_date": "2024-04-01",
                    "end_date": "2024-06-28",
                }
            ]
        }

        result = _ai_staff_learning_counterfactual_period_plan(
            now=datetime.fromisoformat("2026-07-17T16:00:00+09:00"),
            contexts=contexts,
            ledger_summary=summary,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("2024-04-01", result["start_date"])
        self.assertEqual("2024-06-28", result["end_date"])
        self.assertEqual(contestant_ids[1:], result["missing_staff_ids"])
        self.assertEqual(3, result["missing_staff_count"])
        self.assertFalse(result["live_order_allowed"])

    def test_counterfactual_period_plan_opens_latest_completed_60_day_window(self):
        contexts = self._causal_contexts()
        summary = {
            "causal_completed_triplet_keys": [
                {
                    "contestant_id": contestant_id,
                    "start_date": "2026-01-05",
                    "end_date": "2026-04-30",
                }
                for contestant_id in sorted(contexts)
            ]
        }

        result = _ai_staff_learning_counterfactual_period_plan(
            now=datetime.fromisoformat("2026-07-17T16:00:00+09:00"),
            contexts=contexts,
            ledger_summary=summary,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("2026-05-04", result["start_date"])
        self.assertEqual("2026-07-16", result["end_date"])
        self.assertEqual(73, result["selected_target_span_days"])
        self.assertEqual(60, result["minimum_target_span_days"])
        self.assertEqual(sorted(contexts), result["missing_staff_ids"])
        self.assertEqual("latest_completed_weekday_before_today", result["target_end_policy"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_order_allowed"])

    def test_counterfactual_period_plan_backfills_completed_gap_before_waiting(self):
        contexts = self._causal_contexts()
        summary = {
            "causal_completed_triplet_keys": [
                {
                    "contestant_id": contestant_id,
                    "start_date": start_date,
                    "end_date": end_date,
                }
                for start_date, end_date in (
                    ("2025-01-06", "2025-04-30"),
                    ("2025-08-04", "2025-11-28"),
                )
                for contestant_id in sorted(contexts)
            ]
        }

        result = _ai_staff_learning_counterfactual_period_plan(
            now=datetime.fromisoformat("2026-07-17T16:00:00+09:00"),
            contexts=contexts,
            ledger_summary=summary,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("2025-05-01", result["start_date"])
        self.assertEqual("2025-08-01", result["end_date"])
        self.assertEqual(92, result["selected_target_span_days"])
        self.assertTrue(result["selected_from_historical_gap"])
        self.assertEqual(1, result["historical_gap_candidate_count"])
        self.assertEqual(sorted(contexts), result["missing_staff_ids"])
        self.assertFalse(result["live_order_allowed"])

    def test_counterfactual_period_plan_reports_exact_next_eligible_date(self):
        contexts = self._causal_contexts()
        summary = {
            "causal_completed_triplet_keys": [
                {
                    "contestant_id": contestant_id,
                    "start_date": "2026-01-05",
                    "end_date": "2026-04-30",
                }
                for contestant_id in sorted(contexts)
            ]
        }

        result = _ai_staff_learning_counterfactual_period_plan(
            now=datetime.fromisoformat("2026-06-15T16:00:00+09:00"),
            contexts=contexts,
            ledger_summary=summary,
        )

        self.assertFalse(result["ok"])
        self.assertEqual("2026-05-04", result["next_candidate_start_date"])
        self.assertEqual("2026-07-03", result["minimum_candidate_end_date"])
        self.assertEqual("2026-07-06", result["next_eligible_date"])
        self.assertEqual(21, result["days_until_next_eligible"])
        self.assertFalse(result["live_order_allowed"])

    def test_counterfactual_period_plan_skips_non_runnable_gap_and_krx_holiday(self):
        contexts = self._causal_contexts()
        contestant_ids = sorted(contexts)
        complete_periods = (
            ("2024-08-05", "2024-11-29"),
            ("2025-01-06", "2025-04-30"),
            ("2025-08-04", "2025-11-28"),
            ("2026-01-05", "2026-04-30"),
            ("2026-05-01", "2026-07-16"),
        )
        completed = [
            {
                "contestant_id": contestant_id,
                "start_date": start_date,
                "end_date": end_date,
            }
            for start_date, end_date in complete_periods
            for contestant_id in contestant_ids
        ]
        completed.append(
            {
                "contestant_id": "operator",
                "start_date": "2025-05-01",
                "end_date": "2025-08-01",
            }
        )

        result = _ai_staff_learning_counterfactual_period_plan(
            now=datetime.fromisoformat("2026-07-17T16:00:00+09:00"),
            contexts=contexts,
            ledger_summary={"causal_completed_triplet_keys": completed},
            excluded_periods={("2025-05-01", "2025-08-01")},
        )

        self.assertFalse(result["ok"])
        self.assertEqual("2026-07-20", result["next_candidate_start_date"])
        self.assertEqual("2026-09-18", result["minimum_candidate_end_date"])
        self.assertEqual("2026-09-21", result["next_eligible_date"])
        self.assertEqual(
            [{"start_date": "2025-05-01", "end_date": "2025-08-01"}],
            result["excluded_non_runnable_periods"],
        )
        self.assertFalse(result["live_order_allowed"])

    def test_scheduler_reports_next_window_after_non_runnable_gap(self):
        current_plan = {
            "ok": True,
            "start_date": "2025-05-01",
            "end_date": "2025-08-01",
            "missing_staff_ids": ["researcher", "risk_manager", "strategy_researcher"],
        }
        next_plan = {
            "ok": False,
            "start_date": "",
            "end_date": "",
            "next_candidate_start_date": "2026-07-20",
            "minimum_candidate_end_date": "2026-09-18",
            "next_eligible_date": "2026-09-21",
            "days_until_next_eligible": 66,
            "blockers": ["no_completed_non_overlapping_target_period_available"],
        }
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 3,
            "strategy_triplet_count": 1,
            "jobs": [
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "operator-completed",
                    "run_type": run_type,
                }
                for run_type in (
                    "prior_official_source",
                    "same_period_baseline",
                    "same_period_adapted",
                )
            ],
        }
        focus = {
            "large_batch_jobs_allowed": True,
            "market_priority_active": False,
            "market_open": False,
            "market_phase": "closed",
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app._ai_staff_learning_counterfactual_period_plan",
                side_effect=[current_plan, next_plan],
            ),
            patch(
                "app.stock_suite_app.build_ai_staff_learning_counterfactual_queue",
                return_value=queue,
            ),
        ):
            result = build_ai_staff_learning_counterfactual_scheduler_status(max_triplets=2)

        self.assertFalse(result["ready_to_run"])
        self.assertEqual("2026-07-20", result["next_candidate_start_date"])
        self.assertEqual("2026-09-18", result["minimum_candidate_end_date"])
        self.assertEqual("2026-09-21", result["next_eligible_date"])
        self.assertEqual(66, result["days_until_next_eligible"])
        self.assertIn("non_runnable_causal_transition_period_deferred", result["blockers"])
        self.assertIn("2026-09-21", result["operator_message"])
        self.assertFalse(result["live_order_allowed"])

    def test_replay_journal_diagnosis_changes_the_next_strategy(self):
        row = self._row(
            total_return_pct=-1.0,
            max_drawdown_pct=-9.0,
            actual_start_date="2024-01-02",
            actual_end_date="2024-12-30",
            strategy="intraday_theme_leader",
            fast=3,
            slow=8,
            stop=3.0,
            take=4.0,
            hold=2,
        )
        row.update(
            {
                "closed_trade_count": 10,
                "average_win_pct": 1.0,
                "average_loss_pct": -3.0,
                "transaction_cost_pct_of_initial_cash": 2.0,
                "trade_journal_bottom10": [
                    {"exit_reason": "stop loss"},
                    {"exit_reason": "defensive stop"},
                    {"exit_reason": "stop loss"},
                ],
            }
        )
        record = {"start_date": "2024-01-01", "end_date": "2024-12-31"}
        diagnosis = _ai_staff_replay_journal_diagnosis(record, row)
        self.assertIn("unfavorable_payoff_ratio", diagnosis["reason_codes"])
        self.assertIn("transaction_cost_drag", diagnosis["reason_codes"])
        self.assertIn("stop_loss_concentration", diagnosis["reason_codes"])

        context = {
            "source_record_id": "AITOUR-JOURNAL",
            "source_contestant_id": "operator",
            "source_start_date": "2024-01-01",
            "source_end_date": "2024-12-31",
            "source_evidence_hash": "hash",
            "reason_codes": diagnosis["reason_codes"],
            "journal_diagnosis": diagnosis,
            "journal_lessons": diagnosis["lessons"],
        }
        adapted = _apply_ai_staff_verified_learning(
            {
                "strategy": "intraday_theme_leader",
                "fast": 3,
                "slow": 8,
                "allocation": 35.0,
                "max_positions": 2,
                "stop": 3.0,
                "take": 4.0,
                "hold": 2,
            },
            context,
            current_start_date="2025-01-01",
        )
        self.assertLess(adapted["stop"], 3.0)
        self.assertGreater(adapted["take"], 4.0)
        self.assertGreater(adapted["slow"], 8)
        self.assertLess(adapted["allocation"], 35.0)
        self.assertTrue(adapted["_learning_provenance"]["journal_lessons_applied"])

    def test_replay_journal_diagnosis_flags_sparse_quarterly_exit_evidence(self):
        row = self._row(
            total_return_pct=4.0,
            max_drawdown_pct=-2.0,
            actual_start_date="2024-01-02",
            actual_end_date="2024-03-29",
        )
        row.update(
            {
                "trade_count": 4,
                "closed_trade_count": 1,
                "average_win_pct": 2.0,
                "average_loss_pct": -1.0,
            }
        )
        diagnosis = _ai_staff_replay_journal_diagnosis(
            {"start_date": "2024-01-01", "end_date": "2024-03-31"},
            row,
        )

        self.assertIn("too_few_closed_trades", diagnosis["reason_codes"])
        self.assertGreater(diagnosis["metrics"]["horizon_years"], 0.2)
        self.assertEqual(3, diagnosis["metrics"]["minimum_closed_trade_count"])

    def test_risk_budget_opportunity_waits_for_confidence_and_stress_gate(self):
        context = {
            "source_record_id": "AITOUR-RISK-BUDGET",
            "source_contestant_id": "risk_manager",
            "source_start_date": "2024-01-02",
            "source_end_date": "2024-03-29",
            "source_evidence_hash": "verified-hash",
            "reason_codes": ["risk_budget_underutilized"],
            "journal_diagnosis": {"reason_codes": [], "lessons": []},
            "journal_lessons": [],
        }
        adapted = _apply_ai_staff_verified_learning(
            {
                "strategy": "protected_ma",
                "fast": 8,
                "slow": 24,
                "allocation": 20.0,
                "max_positions": 2,
                "stop": 4.0,
                "take": 8.0,
                "hold": 8,
            },
            context,
            current_start_date="2024-05-13",
        )

        self.assertEqual(20.0, adapted["allocation"])
        self.assertEqual(2, adapted["max_positions"])
        self.assertFalse(adapted["_learning_provenance"]["adaptive"])
        self.assertIn(
            "risk_scale_confidence_and_stress_gate_not_passed",
            adapted["_learning_provenance"]["adaptation_blockers"],
        )
        self.assertFalse(adapted["_learning_provenance"]["live_order_allowed"])

    def test_risk_budget_opportunity_uses_small_paper_step_after_full_gate(self):
        context = {
            "source_record_id": "AITOUR-RISK-BUDGET-PASSED",
            "source_contestant_id": "risk_manager",
            "source_start_date": "2024-01-02",
            "source_end_date": "2024-03-29",
            "source_evidence_hash": "verified-hash",
            "reason_codes": ["risk_budget_underutilized"],
            "risk_budget_scale_up_gate": {
                "passed": True,
                "independent_period_count": 3,
                "official_monte_carlo_passed": True,
                "blockers": [],
            },
            "journal_diagnosis": {"reason_codes": [], "lessons": []},
            "journal_lessons": [],
        }
        adapted = _apply_ai_staff_verified_learning(
            {
                "strategy": "protected_ma",
                "fast": 8,
                "slow": 24,
                "allocation": 20.0,
                "max_positions": 2,
                "stop": 4.0,
                "take": 8.0,
                "hold": 8,
            },
            context,
            current_start_date="2024-05-13",
        )

        self.assertEqual(21.0, adapted["allocation"])
        self.assertEqual(2, adapted["max_positions"])
        self.assertTrue(adapted["_learning_provenance"]["adaptive"])
        self.assertEqual(
            ["risk_budget_underutilized"],
            adapted["_learning_provenance"]["actionable_reason_codes"],
        )
        self.assertFalse(adapted["_learning_provenance"]["live_order_allowed"])

    def test_sparse_trade_evidence_expands_sample_instead_of_speeding_signal(self):
        context = {
            "source_record_id": "AITOUR-SPARSE",
            "source_contestant_id": "strategy_researcher",
            "source_start_date": "2024-01-02",
            "source_end_date": "2024-03-29",
            "source_evidence_hash": "verified-hash",
            "reason_codes": ["too_few_closed_trades"],
            "journal_diagnosis": {"reason_codes": ["too_few_closed_trades"], "lessons": []},
            "journal_lessons": [],
        }
        adapted = _apply_ai_staff_verified_learning(
            {
                "strategy": "breakout",
                "fast": 8,
                "slow": 24,
                "allocation": 28.0,
                "max_positions": 3,
                "stop": 5.0,
                "take": 12.0,
                "hold": 12,
            },
            context,
            current_start_date="2024-05-13",
        )

        self.assertEqual(8, adapted["fast"])
        self.assertEqual(24, adapted["slow"])
        self.assertFalse(adapted["_learning_provenance"]["adaptive"])
        self.assertEqual(
            "expand_universe_or_target_period",
            adapted["_learning_provenance"]["next_learning_action"],
        )
        self.assertFalse(adapted["_learning_provenance"]["live_order_allowed"])

    def test_counterfactual_adaptation_history_excludes_future_and_groups_changes(self):
        changes = {
            "allocation": {"before": 40.0, "after": 32.0},
            "max_positions": {"before": 4, "after": 3},
            "stop": {"before": 8.0, "after": 4.0},
        }
        summary = {
            "causal_completed_triplets": [
                {
                    "contestant_id": "operator",
                    "end_date": "2024-03-29",
                    "adaptation_changes": changes,
                    "risk_adjusted_improvement": -1.0,
                    "strategy_generation_id": "past-1",
                },
                {
                    "contestant_id": "operator",
                    "end_date": "2024-06-28",
                    "adaptation_changes": changes,
                    "risk_adjusted_improvement": -2.0,
                    "strategy_generation_id": "past-2",
                },
                {
                    "contestant_id": "operator",
                    "end_date": "2025-03-31",
                    "adaptation_changes": changes,
                    "risk_adjusted_improvement": 9.0,
                    "strategy_generation_id": "future",
                },
            ]
        }

        history = _ai_staff_counterfactual_adaptation_history(
            "operator",
            before_date="2025-01-01",
            summary=summary,
        )

        self.assertTrue(history["ok"])
        self.assertTrue(history["point_in_time_cutoff_enforced"])
        self.assertEqual(1, history["history_count"])
        self.assertEqual(2, history["prior_triplet_count"])
        self.assertEqual(1, history["excluded_future_or_same_period_count"])
        self.assertEqual("reject_repeat_and_pivot", history["items"][0]["decision"])
        self.assertEqual(-1.5, history["items"][0]["mean_risk_adjusted_improvement"])

    def test_regressed_parameter_change_is_pivoted_before_next_paper_decision(self):
        base = {
            "strategy": "ma_cross",
            "label": "baseline",
            "fast": 12,
            "slow": 32,
            "allocation": 40.0,
            "max_positions": 4,
            "stop": 8.0,
            "take": 12.0,
            "hold": 10,
        }
        rejected_changes = {
            "allocation": {"before": 40.0, "after": 32.0},
            "max_positions": {"before": 4, "after": 3},
            "stop": {"before": 8.0, "after": 4.0},
        }
        rejected_signature = _ai_staff_adaptation_changes_signature(rejected_changes)
        context = {
            "source_record_id": "AITOUR-SOURCE",
            "source_contestant_id": "operator",
            "source_start_date": "2024-01-02",
            "source_end_date": "2024-03-29",
            "source_evidence_hash": "source-hash",
            "source_metrics": {},
            "reason_codes": ["drawdown_above_role_limit"],
            "journal_diagnosis": {},
            "counterfactual_adaptation_history": {
                "point_in_time_cutoff_enforced": True,
                "items": [
                    {
                        "change_signature": rejected_signature,
                        "decision": "reject_repeat_and_pivot",
                        "sample_count": 3,
                        "mean_risk_adjusted_improvement": -1.5,
                        "effect_statistics": {"confidence_gate_passed": False},
                    }
                ],
            },
        }

        adapted = _apply_ai_staff_verified_learning(
            base,
            context,
            current_start_date="2025-01-02",
        )
        provenance = adapted["_learning_provenance"]
        feedback = provenance["counterfactual_next_decision_feedback"]

        self.assertEqual("reject_repeat_and_pivot", feedback["decision"])
        self.assertTrue(feedback["known_regressed_repeat_blocked"])
        self.assertTrue(feedback["pivot_applied"])
        self.assertNotEqual(rejected_signature, feedback["final_change_signature"])
        self.assertGreater(adapted["slow"], base["slow"])
        self.assertLess(adapted["allocation"], base["allocation"])
        self.assertFalse(provenance["live_order_allowed"])

    def test_decision_reflection_audit_separates_feedback_from_profit_proof(self):
        base = {
            "strategy": "ma_cross",
            "fast": 12,
            "slow": 32,
            "allocation": 40.0,
            "max_positions": 4,
            "stop": 8.0,
            "take": 12.0,
            "hold": 10,
        }
        rejected_changes = {
            "allocation": {"before": 40.0, "after": 32.0},
            "max_positions": {"before": 4, "after": 3},
            "stop": {"before": 8.0, "after": 4.0},
        }
        history = {
            "history_count": 1,
            "prior_triplet_count": 3,
            "rejected_signature_count": 1,
            "supported_signature_count": 0,
            "point_in_time_cutoff_enforced": True,
            "items": [
                {
                    "change_signature": _ai_staff_adaptation_changes_signature(rejected_changes),
                    "decision": "reject_repeat_and_pivot",
                    "sample_count": 3,
                    "mean_risk_adjusted_improvement": -1.5,
                    "effect_statistics": {"confidence_gate_passed": False},
                }
            ],
        }
        context = {
            "source_record_id": "AITOUR-SOURCE",
            "source_contestant_id": "operator",
            "source_start_date": "2024-01-02",
            "source_end_date": "2024-03-29",
            "source_evidence_hash": "source-hash",
            "source_strategy": base,
            "source_metrics": {},
            "reason_codes": ["drawdown_above_role_limit"],
            "journal_diagnosis": {},
            "counterfactual_adaptation_history": history,
        }
        summary = {
            "causal_completed_triplet_count": 2,
            "improved_triplet_count": 0,
            "regressed_triplet_count": 2,
            "inconclusive_triplet_count": 0,
            "counterfactual_confidence_gate_passed": False,
            "counterfactual_effect_statistics": {
                "sample_count": 2,
                "confidence_gate_passed": False,
            },
            "causal_completed_triplets": [
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "repeat-1",
                    "start_date": "2024-01-02",
                    "end_date": "2024-03-29",
                    "adaptation_changes": rejected_changes,
                    "risk_adjusted_improvement": -1.0,
                },
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "repeat-2",
                    "start_date": "2024-04-01",
                    "end_date": "2024-06-28",
                    "adaptation_changes": rejected_changes,
                    "risk_adjusted_improvement": -2.0,
                },
            ],
        }
        with (
            patch(
                "app.stock_suite_app._ai_staff_counterfactual_ledger_summary",
                return_value=summary,
            ),
            patch(
                "app.stock_suite_app._ai_staff_verified_learning_contexts",
                return_value={"operator": context},
            ),
            patch(
                "app.stock_suite_app.ai_tournament_contestants",
                return_value=[
                    {
                        "id": "operator",
                        "display_name": "self",
                        "strategy_mode": "ma_cross",
                    }
                ],
            ),
        ):
            audit = build_ai_staff_learning_decision_reflection_audit(
                as_of_date="2025-01-02"
            )

        self.assertTrue(audit["next_decision_reflection_verified"])
        self.assertFalse(audit["performance_improvement_proven"])
        self.assertEqual(
            "decision_reflection_verified_performance_pending",
            audit["status"],
        )
        self.assertEqual(0, audit["unsafe_known_regressed_repeat_count"])
        self.assertTrue(audit["historical_repeat_guard_verified"])
        self.assertEqual(1, audit["historical_regressed_repeat_opportunity_count"])
        self.assertFalse(audit["live_order_allowed"])

    def test_monte_carlo_synthetic_aggregate_is_diagnostic_only(self):
        stress = _ai_tournament_monte_carlo_stress(
            {
                "id": "SYNTHETIC-STRESS",
                "initial_cash": 1_000_000,
                "total_return_pct": 30.0,
                "closed_trade_count": 30,
                "trade_count": 30,
                "trade_journal_sample": [],
                "trade_journal_reconciliation_summary": {
                    "checked_count": 30,
                    "blocker_count": 0,
                    "official_return_blocker_count": 0,
                },
            },
            iterations=100,
            seed="synthetic-diagnostic",
        )

        self.assertTrue(stress["synthetic_sample_used"])
        self.assertFalse(stress["actual_sample_sufficient"])
        self.assertFalse(stress["official_evidence"])
        self.assertFalse(stress["passed"])
        self.assertIn("monte_carlo_actual_sample_insufficient", stress["blockers"])

    def test_monte_carlo_requires_reconciled_actual_trade_sample(self):
        trades = [
            {"pnl_pct": 5.0, "notional": 100_000.0}
            for _ in range(25)
        ]
        stress = _ai_tournament_monte_carlo_stress(
            {
                "id": "ACTUAL-STRESS",
                "initial_cash": 1_000_000,
                "trade_journal_sample": trades,
                "trade_journal_reconciliation_summary": {
                    "checked_count": 25,
                    "blocker_count": 0,
                    "official_return_blocker_count": 0,
                },
            },
            iterations=100,
            seed="actual-reconciled",
        )

        self.assertEqual("loss-cluster-tail-shock-v2", stress["model_version"])
        self.assertEqual("replay_trade_journal_sample", stress["sample_source"])
        self.assertTrue(stress["actual_sample_sufficient"])
        self.assertTrue(stress["reconciliation_validated"])
        self.assertTrue(stress["raw_path_gate_passed"])
        self.assertTrue(stress["passed"])

    def test_maturity_recomputes_legacy_monte_carlo_from_source_replay(self):
        trades = [{"pnl_pct": 5.0, "notional": 100_000.0} for _ in range(25)]
        evidence = {
            "stress": {"ok": True, "status": "legacy", "trades_used": 25},
            "champion": {},
            "reference": {"replay_id": "HREPLAY-SOURCE"},
        }
        result = _maturity_verified_monte_carlo_evidence(
            evidence,
            replay_rows=[
                {
                    "id": "HREPLAY-SOURCE",
                    "initial_cash": 1_000_000,
                    "trade_journal_sample": trades,
                    "trade_journal_reconciliation_summary": {
                        "checked_count": 25,
                        "blocker_count": 0,
                        "official_return_blocker_count": 0,
                    },
                }
            ],
        )

        self.assertEqual("loss-cluster-tail-shock-v2", result["model_version"])
        self.assertTrue(result["recomputed_for_maturity"])
        self.assertTrue(result["legacy_result_replaced"])
        self.assertEqual("HREPLAY-SOURCE", result["source_replay_id"])
        self.assertTrue(result["actual_sample_sufficient"])
        self.assertTrue(result["reconciliation_validated"])
        self.assertTrue(result["passed"])
        self.assertFalse(result["live_order_allowed"])

    def test_maturity_blocks_legacy_monte_carlo_without_source_replay(self):
        result = _maturity_verified_monte_carlo_evidence(
            {
                "stress": {"ok": True, "passed": True, "status": "legacy"},
                "champion": {},
                "reference": {"replay_id": "MISSING"},
            },
            replay_rows=[],
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["passed"])
        self.assertFalse(result["official_evidence"])
        self.assertIn("monte_carlo_v2_source_replay_unavailable", result["blockers"])

    def test_monte_carlo_failure_drives_paper_only_risk_retraining(self):
        stress = {
            "ok": True,
            "passed": False,
            "actual_sample_sufficient": True,
            "reconciliation_validated": True,
            "positive_rate_pct": 42.0,
            "p10_return_pct": -18.0,
            "ruin_rate_pct": 14.0,
            "p90_mdd_pct": 28.0,
        }
        reasons = _ai_tournament_monte_carlo_failure_reasons(stress)
        self.assertIn("monte_carlo_ruin_risk", reasons)
        self.assertIn("monte_carlo_tail_drawdown", reasons)

        base = {
            "strategy": "ma_cross",
            "fast": 12,
            "slow": 32,
            "allocation": 40.0,
            "max_positions": 4,
            "stop": 8.0,
            "take": 12.0,
            "hold": 10,
        }
        plan = _ai_tournament_stress_retraining_plan(base, stress)
        self.assertTrue(plan["required"])
        self.assertTrue(plan["paper_only"])
        self.assertFalse(plan["live_order_allowed"])
        self.assertFalse(plan["automatic_promotion"])
        self.assertEqual(2, len(plan["candidate_configs"]))
        self.assertTrue(_ai_tournament_stress_retraining_plan_valid(plan))
        self.assertTrue(str(plan["plan_id"]).startswith("MCRP-"))
        self.assertEqual(64, len(str(plan["plan_hash"])))
        self.assertEqual(base, plan["source_config"])
        for candidate in plan["candidate_configs"]:
            self.assertTrue(str(candidate["retraining_candidate_id"]).startswith("MCRC-"))
            self.assertEqual(64, len(str(candidate["candidate_config_hash"])))

        adapted = _apply_ai_staff_verified_learning(
            base,
            {
                "source_record_id": "AITOUR-STRESS",
                "source_contestant_id": "operator",
                "source_start_date": "2024-01-01",
                "source_end_date": "2024-03-31",
                "source_evidence_hash": "stress-hash",
                "source_metrics": {},
                "reason_codes": reasons,
                "monte_carlo_reason_codes": reasons,
                "stress_retraining_plan": plan,
                "journal_diagnosis": {"reason_codes": [], "metrics": {}},
                "journal_lessons": [],
            },
            current_start_date="2024-04-01",
        )
        self.assertLess(adapted["allocation"], base["allocation"])
        self.assertLess(adapted["max_positions"], base["max_positions"])
        self.assertLess(adapted["stop"], base["stop"])
        self.assertGreater(adapted["slow"], base["slow"])
        self.assertFalse(adapted["_learning_provenance"]["live_order_allowed"])

    def test_monte_carlo_retraining_candidates_enter_bounded_paper_trials_with_controls(self):
        base = {
            "strategy": "ma_cross",
            "fast": 12,
            "slow": 32,
            "allocation": 40.0,
            "max_positions": 4,
            "stop": 8.0,
            "take": 12.0,
            "hold": 10,
            "label": "ordinary challenge",
        }
        stress = {
            "ok": True,
            "passed": False,
            "actual_sample_sufficient": True,
            "reconciliation_validated": True,
            "positive_rate_pct": 42.0,
            "p10_return_pct": -18.0,
            "ruin_rate_pct": 14.0,
            "p90_mdd_pct": 28.0,
        }
        plan = _ai_tournament_stress_retraining_plan(base, stress)
        context = {
            "source_record_id": "AITOUR-STRESS",
            "source_contestant_id": "operator",
            "source_start_date": "2024-01-01",
            "source_end_date": "2024-03-31",
            "source_evidence_hash": "stress-hash",
            "source_metrics": {},
            "reason_codes": plan["reason_codes"],
            "monte_carlo_reason_codes": plan["reason_codes"],
            "stress_retraining_plan": plan,
            "journal_diagnosis": {"reason_codes": [], "metrics": {}},
            "journal_lessons": [],
        }

        trials, controls = _ai_staff_monte_carlo_retraining_trial_configs(
            [base],
            context,
            trial_budget=2,
            season_index=0,
        )
        self.assertEqual(2, len(trials))
        self.assertEqual(2, len(controls))
        self.assertEqual(
            [row["retraining_candidate_id"] for row in plan["candidate_configs"]],
            [row["retraining_candidate_id"] for row in trials],
        )
        self.assertTrue(all(row["candidate_origin"] == "monte_carlo_stress_source_control" for row in controls))
        self.assertTrue(all(row["strategy"] == base["strategy"] for row in controls))
        self.assertTrue(all(row["allocation"] == base["allocation"] for row in controls))
        self.assertTrue(all(row["_monte_carlo_retraining_contract"]["paper_only"] for row in trials))
        self.assertTrue(all(not row["_monte_carlo_retraining_contract"]["live_order_allowed"] for row in trials))

        rotated, _ = _ai_staff_monte_carlo_retraining_trial_configs(
            [base],
            context,
            trial_budget=1,
            season_index=1,
        )
        self.assertEqual(
            plan["candidate_configs"][1]["retraining_candidate_id"],
            rotated[0]["retraining_candidate_id"],
        )

        tampered_context = copy.deepcopy(context)
        tampered_context["stress_retraining_plan"]["plan_hash"] = "0" * 64
        rejected, rejected_controls = _ai_staff_monte_carlo_retraining_trial_configs(
            [base],
            tampered_context,
            trial_budget=2,
            season_index=0,
        )
        self.assertEqual([base], rejected)
        self.assertEqual([base], rejected_controls)

        adapted = _apply_ai_staff_verified_learning(
            trials[0],
            context,
            current_start_date="2024-04-01",
        )
        expected = plan["candidate_configs"][0]
        self.assertEqual(expected["allocation"], adapted["allocation"])
        self.assertEqual(expected["max_positions"], adapted["max_positions"])
        self.assertEqual(expected["stop"], adapted["stop"])
        self.assertEqual(expected["slow"], adapted["slow"])
        provenance = adapted["_learning_provenance"]
        self.assertTrue(provenance["adaptive"])
        retraining = provenance["monte_carlo_retraining"]
        self.assertTrue(retraining["applied"])
        self.assertTrue(retraining["exact_candidate_tested"])
        self.assertEqual(plan["plan_id"], retraining["plan_id"])
        self.assertEqual(expected["retraining_candidate_id"], retraining["candidate_id"])
        self.assertFalse(retraining["live_order_allowed"])
        self.assertFalse(retraining["automatic_promotion"])
        self.assertNotIn("_monte_carlo_retraining_contract", adapted)

    def test_monte_carlo_evidence_audit_exposes_paper_only_retraining(self):
        tournament = {
            "id": "AITOUR-AUDIT",
            "generated_at": "2026-07-17T01:00:00+09:00",
            "monte_carlo_stress": {"ok": True, "status": "legacy"},
            "rankings": [
                {
                    "replay_id": "HREPLAY-LOSS",
                    "strategy_mode": "ma_cross",
                    "fast_window": 12,
                    "slow_window": 32,
                    "selected_challenge_config": {
                        "allocation_pct": 40.0,
                        "max_positions": 4,
                        "stop_loss_pct": 8.0,
                        "take_profit_pct": 12.0,
                        "holding_limit_days": 10,
                    },
                }
            ],
        }
        audit = build_ai_tournament_monte_carlo_evidence_audit(
            tournament,
            replay_rows=[
                {
                    "id": "HREPLAY-LOSS",
                    "initial_cash": 1_000_000,
                    "trade_journal_sample": [
                        {"pnl_pct": -4.0, "notional": 100_000.0}
                        for _ in range(25)
                    ],
                    "trade_journal_reconciliation_summary": {
                        "checked_count": 25,
                        "blocker_count": 0,
                        "official_return_blocker_count": 0,
                    },
                }
            ],
        )

        self.assertTrue(audit["ok"])
        self.assertFalse(audit["passed"])
        self.assertEqual("paper_retraining_required", audit["status"])
        self.assertEqual(25, audit["actual_trade_sample_count"])
        self.assertTrue(audit["actual_sample_sufficient"])
        self.assertTrue(audit["reconciliation_validated"])
        self.assertTrue(audit["retraining_plan"]["required"])
        self.assertGreaterEqual(len(audit["retraining_plan"]["candidate_configs"]), 2)
        self.assertEqual("official_sample_failed_stress_gate", audit["evidence_quality_tier"])
        self.assertFalse(audit["promotion_gate"]["official_performance_claim_allowed"])
        self.assertFalse(audit["promotion_gate"]["live_candidate_promotion_allowed"])
        self.assertTrue(audit["promotion_gate"]["paper_retraining_only"])
        self.assertTrue(audit["paper_only"])
        self.assertFalse(audit["live_order_allowed"])
        self.assertFalse(audit["automatic_promotion"])

    def test_monte_carlo_audit_preserves_stronger_recent_risk_anchor(self):
        latest = {
            "id": "AITOUR-LATEST-SMALL",
            "generated_at": "2026-07-17T17:43:00+09:00",
            "rankings": [{"replay_id": "HREPLAY-SMALL", "strategy_mode": "ma_cross"}],
        }
        stronger = {
            "id": "AITOUR-STRONGER-RISK",
            "generated_at": "2026-07-17T17:19:00+09:00",
            "rankings": [
                {
                    "replay_id": "HREPLAY-STRONGER",
                    "strategy_mode": "ma_cross",
                    "selected_challenge_config": {
                        "allocation_pct": 40.0,
                        "max_positions": 4,
                        "stop_loss_pct": 8.0,
                    },
                }
            ],
        }
        replay_rows = [
            {
                "id": "HREPLAY-SMALL",
                "initial_cash": 1_000_000,
                "closed_trade_count": 4,
                "trade_journal_sample": [
                    {"pnl_pct": 1.0, "notional": 100_000.0} for _ in range(4)
                ],
                "trade_journal_reconciliation_summary": {
                    "checked_count": 4,
                    "blocker_count": 0,
                    "official_return_blocker_count": 0,
                },
            },
            {
                "id": "HREPLAY-STRONGER",
                "initial_cash": 1_000_000,
                "closed_trade_count": 25,
                "trade_journal_sample": [
                    {"pnl_pct": -4.0, "notional": 100_000.0} for _ in range(25)
                ],
                "trade_journal_reconciliation_summary": {
                    "checked_count": 25,
                    "blocker_count": 0,
                    "official_return_blocker_count": 0,
                },
            },
        ]
        with patch(
            "app.stock_suite_app.latest_ai_tournaments",
            return_value=[latest, stronger],
        ):
            audit = build_ai_tournament_monte_carlo_evidence_audit(
                replay_rows=replay_rows,
            )

        self.assertTrue(audit["historical_risk_anchor_used"])
        self.assertEqual("AITOUR-STRONGER-RISK", audit["source_tournament_id"])
        self.assertEqual("AITOUR-LATEST-SMALL", audit["latest_tournament_id"])
        self.assertEqual(25, audit["actual_trade_sample_count"])
        self.assertEqual(4, audit["latest_strategy_evidence"]["actual_trade_sample_count"])
        self.assertFalse(audit["outcome_metrics_used_for_selection"])
        self.assertEqual(
            "historical_anchor_only_latest_unproven",
            audit["evidence_quality_tier"],
        )
        self.assertTrue(audit["evidence_quality"]["historical_anchor_used"])
        self.assertTrue(audit["evidence_quality"]["selected_official_sample_ready"])
        self.assertFalse(audit["evidence_quality"]["latest_strategy_official_sample_ready"])
        self.assertIn(
            "latest_strategy_evidence_not_yet_official",
            audit["evidence_quality"]["quality_reasons"],
        )
        self.assertFalse(audit["promotion_gate"]["official_performance_claim_allowed"])
        self.assertFalse(audit["promotion_gate"]["live_candidate_promotion_allowed"])
        self.assertTrue(audit["promotion_gate"]["paper_retraining_only"])
        self.assertEqual("paper_retraining_required", audit["status"])
        self.assertIn("latest_strategy_monte_carlo_evidence_insufficient", audit["blockers"])
        self.assertFalse(audit["passed"])
        self.assertFalse(audit["live_order_allowed"])

    def test_three_independent_positive_pairs_prove_effect_with_confidence(self):
        records = self._three_pair_records()
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=list(reversed(records))),
            patch("app.stock_suite_app._ai_tournament_official_claim_state", return_value={"eligible": True, "reasons": []}),
        ):
            result = ai_staff_learning_audit(limit=10)
        operator = self._operator(result)
        self.assertTrue(operator["growth_proven"])
        self.assertEqual(operator["validated_learning_pair_count"], 3)
        self.assertEqual(operator["independent_target_period_count"], 3)
        self.assertTrue(operator["effect_confidence_gate_passed"])
        self.assertGreater(operator["effect_statistics"]["confidence_interval_low"], 0)
        self.assertNotIn(
            "operator",
            {row["contestant_id"] for row in result["next_learning_validation_queue"]},
        )

    def test_overlapping_target_period_cannot_inflate_learning_sample(self):
        records = self._three_pair_records()
        duplicate = copy.deepcopy(records[-1])
        duplicate["id"] = "AITOUR-TARGET-OVERLAP"
        duplicate["rankings"][0]["learning_provenance"]["current_start_date"] = duplicate["start_date"]
        records.append(duplicate)
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=records),
            patch("app.stock_suite_app._ai_tournament_official_claim_state", return_value={"eligible": True, "reasons": []}),
        ):
            result = ai_staff_learning_audit(limit=10)
        operator = self._operator(result)
        self.assertEqual(operator["validated_learning_pair_count"], 3)
        self.assertEqual(operator["invalid_provenance_count"], 1)
        self.assertIn(
            "target_period_overlaps_prior_learning_pair",
            operator["learning_pairs"][-1]["blockers"],
        )

    def test_tampered_source_hash_cannot_prove_learning(self):
        source, target = self._records()
        target = copy.deepcopy(target)
        provenance = target["rankings"][0]["learning_provenance"]
        provenance["source_evidence_hashes"][source["id"]] = "tampered"
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=[source, target]),
            patch("app.stock_suite_app._ai_tournament_official_claim_state", return_value={"eligible": True, "reasons": []}),
        ):
            result = ai_staff_learning_audit(limit=10)
        operator = self._operator(result)
        self.assertFalse(operator["growth_proven"])
        self.assertEqual(operator["validated_learning_pair_count"], 0)
        self.assertEqual(operator["invalid_provenance_count"], 1)
        self.assertIn("source_evidence_hash_mismatch", operator["learning_pairs"][0]["blockers"])

    def test_tampered_counterfactual_hash_cannot_prove_learning(self):
        source, target = self._records()
        target = copy.deepcopy(target)
        target["rankings"][0]["learning_counterfactual_control"]["evidence_hash"] = "tampered"
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=[source, target]),
            patch("app.stock_suite_app._ai_tournament_official_claim_state", return_value={"eligible": True, "reasons": []}),
        ):
            result = ai_staff_learning_audit(limit=10)
        operator = self._operator(result)
        self.assertFalse(operator["growth_proven"])
        self.assertEqual(operator["validated_learning_pair_count"], 0)
        self.assertIn("counterfactual_evidence_hash_mismatch", operator["learning_pairs"][0]["blockers"])

    def test_valid_adaptation_without_improvement_is_not_growth(self):
        source, target = self._records(target_return=-15.0, target_mdd=-28.0)
        with (
            patch("app.stock_suite_app._read_jsonl", return_value=[source, target]),
            patch("app.stock_suite_app._ai_tournament_official_claim_state", return_value={"eligible": True, "reasons": []}),
        ):
            result = ai_staff_learning_audit(limit=10)
        operator = self._operator(result)
        self.assertFalse(operator["growth_proven"])
        self.assertEqual(operator["validated_learning_pair_count"], 1)
        self.assertEqual(operator["regressed_learning_pair_count"], 1)
        self.assertEqual(operator["growth_status_code"], "adapted_but_improvement_not_proven")

    def test_mini_league_applies_verified_learning_before_replay(self):
        context = {
            "source_record_id": "AITOUR-SOURCE",
            "source_start_date": "2024-01-02",
            "source_end_date": "2024-06-28",
            "source_contestant_id": "operator",
            "source_evidence_hash": "verified-hash",
            "source_metrics": {},
            "reason_codes": ["non_positive_net_return", "drawdown_above_role_limit"],
        }
        contestant = {
            "id": "operator",
            "name": "operator",
            "role": "trader",
            "strategy_mode": "ma_cross",
            "strategy_name": "baseline",
            "fast": 12,
            "slow": 32,
            "allocation_pct": 40.0,
            "max_positions": 4,
            "stop_loss_pct": 8.0,
            "take_profit_pct": 12.0,
            "holding_limit_days": 10,
            "risk_limit_pct": 15.0,
        }
        replay = {
            "id": "REPLAY-TARGET",
            "initial_cash": 100_000_000.0,
            "final_equity": 110_000_000.0,
            "total_return_pct": 10.0,
            "max_drawdown_pct": -5.0,
            "win_rate_pct": 50.0,
            "trade_count": 20,
            "closed_trade_count": 10,
            "average_win_pct": 3.0,
            "average_loss_pct": -1.0,
            "trade_journal_top10": [],
            "trade_journal_bottom10": [],
            "trade_journal_reconciliation_summary": {},
            "price_currency_unit_audit": {"passed": True},
            "summary": "paper replay",
        }
        base_config = {
            "label": "baseline",
            "strategy": "ma_cross",
            "fast": 12,
            "slow": 32,
            "allocation": 40.0,
            "max_positions": 4,
            "stop": 8.0,
            "take": 12.0,
            "hold": 10,
        }
        with (
            patch("app.stock_suite_app.ai_tournament_contestants", return_value=[contestant]),
            patch("app.stock_suite_app._ai_tournament_personal_bests", return_value={}),
            patch("app.stock_suite_app._ai_staff_verified_learning_contexts", return_value={"operator": context}),
            patch("app.stock_suite_app._ai_tournament_challenge_configs", return_value=[base_config]),
            patch("app.stock_suite_app.run_historical_paper_replay", return_value=replay) as replay_mock,
            patch("app.stock_suite_app._ai_tournament_score", return_value={"score": 10.0}),
            patch("app.stock_suite_app._ai_tournament_monte_carlo_stress", return_value={}),
            patch("app.stock_suite_app._ai_tournament_bias_audit", return_value={"passed": False, "status": "test"}),
            patch("app.stock_suite_app._ai_tournament_competition_gate", return_value={"confidence_score": 100, "failed_checks": [], "status": "test", "grade": "A"}),
            patch("app.stock_suite_app._ai_tournament_shadow_validation", return_value={}),
            patch("app.stock_suite_app.JOURNAL.add"),
        ):
            result = run_ai_mini_league(
                start_date="2024-07-01",
                end_date="2024-12-31",
                symbols=["005930"],
                symbol_selection_mode="common",
                challenge_mode=False,
                persist_replay_detail=False,
                persist_tournament_record=False,
                source="learning-wiring-test",
            )
        ranking = result["rankings"][0]
        self.assertTrue(ranking["learning_provenance"]["adaptive"])
        self.assertTrue(ranking["learning_provenance"]["applied_before_replay"])
        self.assertNotEqual(ranking["strategy_mode"], "ma_cross")
        self.assertEqual(replay_mock.call_count, 2)
        adapted_kwargs = replay_mock.call_args_list[0].kwargs
        baseline_kwargs = replay_mock.call_args_list[1].kwargs
        self.assertEqual(adapted_kwargs["strategy_mode"], ranking["strategy_mode"])
        self.assertEqual(adapted_kwargs["allocation_pct"], 32.0)
        self.assertEqual(adapted_kwargs["max_positions"], 3)
        self.assertEqual(baseline_kwargs["strategy_mode"], "ma_cross")
        self.assertFalse(baseline_kwargs["persist_detail"])
        self.assertEqual(
            ranking["learning_counterfactual_control"]["schema"],
            "codexstock_ai_staff_learning_counterfactual_v1",
        )

    def test_autonomous_learning_league_uses_fixed_common_universe(self):
        state = {
            "ok": True,
            "enabled": True,
            "interval_seconds": 3600,
            "initial_cash": 10_000_000,
            "start_year": 2000,
            "run_count": 17,
            "verified_learning_run_count": 0,
            "last_status": "READY",
        }
        league_result = {
            "ok": True,
            "id": "AITOUR-VERIFIED-1",
            "league_name": "verified",
            "start_date": "2000-01-01",
            "end_date": "2002-12-31",
            "champion": {},
            "rankings": [
                {"contestant_id": contestant_id}
                for contestant_id in ("operator", "researcher", "risk_manager", "strategy_researcher")
            ],
        }
        with (
            patch("app.stock_suite_app.load_ai_internal_league_state", return_value=state),
            patch("app.stock_suite_app.save_ai_internal_league_state", side_effect=lambda payload: payload),
            patch("app.stock_suite_app.build_operating_focus", return_value={"large_batch_jobs_allowed": True}),
            patch(
                "app.stock_suite_app._ensure_long_horizon_fixed_etf_universe",
                return_value={"validation": {"passed": True}},
            ),
            patch("app.stock_suite_app.run_ai_mini_league", return_value=league_result) as run_mock,
            patch(
                "app.stock_suite_app._ai_internal_league_strict_verification",
                return_value={
                    "passed": True,
                    "eligible_staff_count": 4,
                    "expected_staff_count": 4,
                    "blocker_counts": {},
                },
            ),
            patch(
                "app.stock_suite_app.ai_staff_learning_audit",
                return_value={
                    "schema": "codexstock_ai_staff_learning_audit_v4",
                    "records_checked": 1,
                    "staff_count": 4,
                    "growth_proven_staff_count": 0,
                    "staff": [],
                },
            ),
        ):
            result = run_autonomous_ai_internal_league_if_due(force=True)
        self.assertEqual(result["status"], "RAN_VERIFIED")
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs["symbol_selection_mode"], "common")
        self.assertEqual(kwargs["universe_dataset_id"], LONG_HORIZON_FIXED_ETF_UNIVERSE_ID)
        self.assertEqual(
            kwargs["symbols"],
            [str(row["symbol"]) for row in LONG_HORIZON_FIXED_ETF_UNIVERSE],
        )
        self.assertTrue(kwargs["source"].endswith("-verified-learning"))
        self.assertTrue(kwargs["challenge_mode"])
        self.assertEqual(kwargs["challenge_trials"], 6)
        self.assertEqual(state["verified_learning_run_count"], 1)

    def test_agent_strategy_library_generates_many_candidates_and_reuses_memory(self):
        contestant = {
            "id": "operator",
            "strategy_mode": "intraday_theme_leader",
            "strategy_name": "operator baseline",
            "fast": 3,
            "slow": 8,
            "allocation_pct": 35.0,
            "max_positions": 2,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
            "holding_limit_days": 2,
        }
        remembered = {
            "label": "verified memory",
            "strategy": "breakout",
            "fast": 4,
            "slow": 14,
            "allocation": 30.0,
            "max_positions": 2,
            "stop": 3.0,
            "take": 10.0,
            "hold": 4,
            "candidate_origin": "verified_strategy_memory",
            "strategy_memory_source_record_id": "AITOUR-PAST",
        }
        with patch(
            "app.stock_suite_app._ai_staff_verified_strategy_memory_configs",
            return_value=[remembered],
        ):
            free_seasons = [
                season
                for season in range(100)
                if _ai_staff_training_arena("2025-01-01", "2025-12-31", season)["id"] == "free_play"
            ]
            self.assertGreaterEqual(len(free_seasons), 2)
            first = _ai_tournament_challenge_configs(
                contestant,
                trial_budget=6,
                before_date="2025-01-01",
                end_date="2025-12-31",
                season_index=free_seasons[0],
            )
            second = _ai_tournament_challenge_configs(
                contestant,
                trial_budget=6,
                before_date="2025-01-01",
                end_date="2025-12-31",
                season_index=free_seasons[1],
            )

        self.assertEqual(len(first), 6)
        self.assertGreaterEqual(first[0]["strategy_library_candidate_count"], 12)
        self.assertIn("verified_strategy_memory", first[0]["strategy_library_origins"])
        self.assertIn("role_generated", first[0]["strategy_library_origins"])
        self.assertTrue(any(row.get("strategy_memory_source_record_id") == "AITOUR-PAST" for row in first))
        self.assertTrue(any(row.get("strategy_generation_id") for row in first))
        self.assertTrue(all(row.get("agent_strategy_autonomy") is True for row in first))
        self.assertTrue(all(row.get("role_strategy_restriction") is False for row in first))
        self.assertNotEqual(
            [row["label"] for row in first[2:]],
            [row["label"] for row in second[2:]],
        )

    def test_strategy_generation_is_open_ended_and_indicator_aware(self):
        contestant = {
            "id": "operator",
            "strategy_mode": "intraday_theme_leader",
            "allocation_pct": 35.0,
            "max_positions": 2,
        }
        season_zero = _ai_staff_role_generated_strategy_configs(contestant, season_index=0)
        season_one = _ai_staff_role_generated_strategy_configs(contestant, season_index=1)
        self.assertGreaterEqual(len(season_zero), 12)
        self.assertTrue(all(row.get("open_ended_generation") is True for row in season_zero))
        self.assertTrue(all(row.get("indicator_recipe") for row in season_zero))
        self.assertNotEqual(
            {row.get("strategy_generation_id") for row in season_zero},
            {row.get("strategy_generation_id") for row in season_one},
        )

    def test_all_staff_can_generate_every_strategy_without_role_quota(self):
        master_modes = {
            "buffett_quality_proxy",
            "graham_defensive_proxy",
            "lynch_growth_proxy",
            "turtle_55",
            "minervini_proxy",
            "canslim_proxy",
        }
        self.assertTrue(master_modes.issubset(REPLAY_STRATEGY_PROFILES))
        self.assertTrue(all(REPLAY_STRATEGY_PROFILES[mode].get("master_proxy") for mode in master_modes))
        self.assertEqual(set(AI_STAFF_OPEN_STRATEGY_MODES), set(REPLAY_STRATEGY_PROFILES))
        for contestant in ai_tournament_contestants():
            generated = _ai_staff_role_generated_strategy_configs(contestant, season_index=3)
            self.assertEqual({row["strategy"] for row in generated}, set(REPLAY_STRATEGY_PROFILES))
            self.assertEqual(len(generated), len(REPLAY_STRATEGY_PROFILES) * 6)

    def test_shared_arena_can_stage_intraday_longterm_and_master_competitions(self):
        periods = {
            "intraday_sprint": ("2025-01-01", "2025-03-01"),
            "long_compound": ("2000-01-01", "2026-12-31"),
            "master_open": ("2000-01-01", "2026-12-31"),
        }
        selected_seasons = {}
        for arena_id, (start_date, end_date) in periods.items():
            selected_seasons[arena_id] = next(
                season
                for season in range(256)
                if _ai_staff_training_arena(start_date, end_date, season)["id"] == arena_id
            )
        with patch("app.stock_suite_app._ai_staff_verified_strategy_memory_configs", return_value=[]):
            for arena_id, (start_date, end_date) in periods.items():
                expected_horizons = {
                    "intraday_sprint": {"daytrade"},
                    "long_compound": {"long_term"},
                    "master_open": {"mid_term", "long_term"},
                }[arena_id]
                for contestant in ai_tournament_contestants():
                    configs = _ai_tournament_challenge_configs(
                        contestant,
                        trial_budget=6,
                        before_date=start_date,
                        end_date=end_date,
                        season_index=selected_seasons[arena_id],
                    )
                    self.assertEqual(len(configs), 6)
                    self.assertTrue(all(row["training_arena"]["id"] == arena_id for row in configs))
                    self.assertTrue({row["strategy_horizon"] for row in configs}.issubset(expected_horizons))
                    expected_mode_count = {
                        "intraday_sprint": 4,
                        "long_compound": 3,
                        "master_open": 6,
                    }[arena_id]
                    self.assertEqual(len({row["strategy"] for row in configs}), expected_mode_count)
                    if arena_id == "master_open":
                        self.assertTrue(all(row.get("master_strategy_proxy") for row in configs))

    def test_capital_goal_tracks_paper_progress_without_relaxing_safety(self):
        progress = _ai_staff_capital_goal_progress(100.0)
        self.assertEqual(progress["target_multiple"], 1000.0)
        self.assertEqual(progress["realized_multiple"], 2.0)
        self.assertEqual(progress["current_capital_krw"], 20_000_000.0)
        self.assertFalse(progress["goal_reached"])
        self.assertIn("Paper", progress["objective"])

    def test_short_free_play_does_not_waste_trials_on_unavailable_history(self):
        start_date = "2024-01-02"
        end_date = "2024-03-29"
        season = next(
            index
            for index in range(128)
            if _ai_staff_training_arena(start_date, end_date, index)["id"] == "free_play"
        )
        arena = _ai_staff_training_arena(start_date, end_date, season)
        with patch("app.stock_suite_app._ai_staff_verified_strategy_memory_configs", return_value=[]):
            for contestant in ai_tournament_contestants():
                configs = _ai_tournament_challenge_configs(
                    contestant,
                    trial_budget=6,
                    before_date=start_date,
                    end_date=end_date,
                    season_index=season,
                )
                self.assertEqual(len(configs), 6)
                self.assertTrue(
                    all(
                        int(row.get("minimum_history_bars") or 0) <= arena["estimated_business_bars"]
                        for row in configs
                    )
                )

    def test_personality_does_not_lock_staff_to_one_symbol_lens(self):
        expected = set(AI_STAFF_SYMBOL_SELECTION_LENSES)
        self.assertEqual(len(expected), 4)
        for contestant in ai_tournament_contestants():
            lenses = {
                _ai_staff_symbol_selection_lens(str(contestant["id"]), season)["id"]
                for season in range(128)
            }
            self.assertEqual(lenses, expected)
            sample = _ai_staff_symbol_selection_lens(str(contestant["id"]), 0)
            self.assertFalse(sample["role_restriction"])
            self.assertTrue(sample["all_lenses_open_to_all_staff"])

    def test_all_staff_share_the_full_indicator_catalog(self):
        catalog = build_ai_staff_indicator_catalog()
        names = {row["name"] for row in catalog["technical_indicators"]}
        self.assertEqual(catalog["technical_indicator_count"], 16)
        self.assertEqual(
            names,
            {
                "SMA", "EMA", "RSI", "BOLLINGER", "ENVELOPE", "ATR", "WMA", "MACD",
                "ROC", "OBV", "VWAP", "STOCHASTIC", "WILLIAMS_R", "MFI", "CCI", "ADX",
            },
        )
        self.assertTrue(catalog["all_staff_can_read"])
        self.assertEqual(catalog["native_replay_direct_technical_count"], 3)
        self.assertEqual(set(catalog["role_focus"]), set(catalog["staff_ids"]))

    def test_strategy_memory_rejects_future_records(self):
        past_row = self._row(
            total_return_pct=12.0,
            max_drawdown_pct=-5.0,
            actual_start_date="2024-01-02",
            actual_end_date="2024-12-30",
            strategy="breakout",
        )
        future_row = copy.deepcopy(past_row)
        future_row["actual_start_date"] = "2026-01-02"
        future_row["actual_end_date"] = "2026-12-30"
        records = [
            {"id": "AITOUR-PAST", "end_date": "2024-12-31", "rankings": [past_row]},
            {"id": "AITOUR-FUTURE", "end_date": "2026-12-31", "rankings": [future_row]},
        ]
        with patch("app.stock_suite_app._ai_staff_learning_claim_state", return_value={"eligible": True}):
            memory = _ai_staff_verified_strategy_memory_configs(
                "operator",
                before_date="2025-01-01",
                records=records,
            )
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0]["strategy_memory_source_record_id"], "AITOUR-PAST")
        self.assertEqual(memory[0]["strategy"], "breakout")

    def test_autonomous_learning_league_does_not_advance_rejected_evidence(self):
        state = {
            "ok": True,
            "enabled": True,
            "interval_seconds": 3600,
            "initial_cash": 10_000_000,
            "start_year": 2000,
            "run_count": 106,
            "verified_learning_run_count": 0,
        }
        league_result = {
            "ok": True,
            "id": "AITOUR-REJECTED-1",
            "league_name": "rejected",
            "start_date": "2000-01-01",
            "end_date": "2002-12-31",
            "champion": {},
            "rankings": [],
        }
        rejected = {
            "passed": False,
            "eligible_staff_count": 3,
            "expected_staff_count": 4,
            "blocker_counts": {"staff_result_missing": 1},
        }
        with (
            patch("app.stock_suite_app.load_ai_internal_league_state", return_value=state),
            patch("app.stock_suite_app.save_ai_internal_league_state", side_effect=lambda payload: payload),
            patch("app.stock_suite_app.build_operating_focus", return_value={"large_batch_jobs_allowed": True}),
            patch(
                "app.stock_suite_app._ensure_long_horizon_fixed_etf_universe",
                return_value={"validation": {"passed": True}},
            ),
            patch("app.stock_suite_app.run_ai_mini_league", return_value=league_result),
            patch("app.stock_suite_app._ai_internal_league_strict_verification", return_value=rejected),
        ):
            result = run_autonomous_ai_internal_league_if_due(force=True)
        self.assertEqual(result["status"], "EVIDENCE_REJECTED")
        self.assertFalse(result["ok"])
        self.assertEqual(state["run_count"], 107)
        self.assertEqual(state["verified_learning_run_count"], 0)
        self.assertEqual(state["last_phase"], "CRASH-2000")

    def test_live_candidate_report_carries_staff_learning_evidence_gate(self):
        contract = {
            "ready": True,
            "hash_valid": True,
            "safe_to_execute_paper": True,
            "runnable_count": 0,
            "blocked_count": 4,
        }
        ledger = {
            "counterfactual_confidence_gate_passed": False,
            "official_counterfactual_promotion_ready": False,
            "next_verification_action": "run_independent_period_confidence_check",
            "watch_more_paper_evidence_count": 2,
            "reject_from_live_candidate_count": 1,
            "rejected_strategy_ids": ["BAD-STRATEGY"],
            "counterfactual_confidence_gate_blockers": [
                "confidence_interval_low_not_positive",
                "mean_risk_adjusted_improvement_not_positive",
            ],
            "operator_message": "직원 학습 효과 보류: 평균 개선은 보일 수 있으나 95% 신뢰구간 하단이 아직 0 이하입니다.",
            "strategy_verdicts": [
                {
                    "contestant_id": "operator",
                    "strategy_generation_id": "BAD-STRATEGY",
                    "verdict": "reject_from_live_candidate",
                    "live_candidate_allowed": False,
                    "score_promotion_allowed": False,
                }
            ],
            "counterfactual_effect_statistics": {
                "sample_count": 5,
                "confidence_gate_passed": False,
            },
        }
        plan = {
            "generated_at": "2026-07-15T09:10:00+09:00",
            "side": "BUY",
            "symbol": "005930",
            "name": "삼성전자",
            "selection_mode": "ai_screener",
            "selection_reason": "test candidate",
            "candidate_ready": True,
            "broker_submit_ready": False,
            "notional": 75000,
            "checks": [],
            "buy_theme_peer_gate": {},
            "live_trade_learning_rules": [{"rule": "cut weak bounces", "source_trade": "old trade"}],
            "selection": {
                "symbol": "005930",
                "name": "삼성전자",
                "score": 72.5,
                "candidate_pool": [
                    {"symbol": "005930", "name": "삼성전자", "score": 72.5, "reasons": ["liquidity"]},
                ],
            },
        }
        with (
            patch("app.stock_suite_app.build_ai_staff_learning_experiment_status", return_value=contract),
            patch("app.stock_suite_app._ai_staff_counterfactual_ledger_summary", return_value=ledger),
        ):
            gate = build_live_learning_evidence_gate()
            report = build_live_candidate_decision_report({**plan, "learning_evidence_gate": gate})

        self.assertEqual(gate["schema"], "codexstock_live_learning_evidence_gate_v1")
        self.assertFalse(gate["live_candidate_score_effect_allowed"])
        self.assertFalse(gate["unverified_result_affects_score"])
        self.assertFalse(gate["unverified_result_affects_live_candidate"])
        self.assertEqual("staff_learning_not_officially_promoted", gate["score_effect_block_reason"])
        self.assertIn("confidence_interval_low_not_positive", gate["confidence_gate_blockers"])
        self.assertIn("평균 개선은 보일 수 있으나", gate["operator_message"])
        self.assertEqual(gate["rejected_strategy_ids"], ["BAD-STRATEGY"])
        self.assertEqual(report["learning_evidence_gate"]["next_verification_action"], "run_independent_period_confidence_check")
        self.assertFalse(report["learning_evidence_gate"]["live_candidate_score_effect_allowed"])
        self.assertIn("mean_risk_adjusted_improvement_not_positive", report["learning_evidence_gate"]["confidence_gate_blockers"])
        reply = format_live_candidate_decision_reply(report)
        self.assertIn("staff_learning_not_officially_promoted", reply)
        self.assertIn("confidence_interval_low_not_positive", reply)
        self.assertIn("평균 개선은 보일 수 있으나", reply)

    def test_strict_learning_verification_requires_every_staff_claim(self):
        rankings = [
            {"contestant_id": contestant_id, "eligible": contestant_id != "risk_manager"}
            for contestant_id in ("operator", "researcher", "risk_manager", "strategy_researcher")
        ]

        def claim(row):
            eligible = bool(row.get("eligible"))
            return {
                "eligible": eligible,
                "status": "official_learning_evidence" if eligible else "reference_only",
                "reasons": [] if eligible else ["lookahead_safe_timing_not_validated"],
            }

        with patch("app.stock_suite_app._ai_staff_learning_claim_state", side_effect=claim):
            result = _ai_internal_league_strict_verification({"ok": True, "rankings": rankings, "errors": []})
        self.assertFalse(result["passed"])
        self.assertEqual(result["eligible_staff_count"], 3)
        self.assertEqual(result["blocker_counts"]["lookahead_safe_timing_not_validated"], 1)

    def test_autonomous_learning_league_persists_weekend_deferral(self):
        state = {
            "ok": True,
            "enabled": True,
            "interval_seconds": 3600,
            "initial_cash": 10_000_000,
            "run_count": 106,
            "verified_learning_run_count": 0,
        }
        saved = []
        with (
            patch("app.stock_suite_app.load_ai_internal_league_state", return_value=state),
            patch("app.stock_suite_app.save_ai_internal_league_state", side_effect=lambda payload: saved.append(dict(payload)) or payload),
            patch(
                "app.stock_suite_app.build_operating_focus",
                return_value={"large_batch_jobs_allowed": False, "large_batch_schedule": "weekend"},
            ),
        ):
            result = run_autonomous_ai_internal_league_if_due()
        self.assertEqual(result["status"], "DEFERRED_TO_MARKET_CLOSED_DAY")
        self.assertEqual(saved[-1]["last_status"], "DEFERRED_TO_MARKET_CLOSED_DAY")
        self.assertEqual(saved[-1]["strict_learning_evidence_status"], "awaiting_first_verified_run")
        self.assertGreaterEqual(saved[-1]["seconds_until_due"], 0)

    def test_autonomous_learning_league_backs_off_identical_rejected_evidence(self):
        state = {
            "ok": True,
            "enabled": True,
            "interval_seconds": 3600,
            "initial_cash": 10_000_000,
            "start_year": 2000,
            "run_count": 128,
            "verified_learning_run_count": 0,
            "last_status": "EVIDENCE_REJECTED",
            "last_run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "last_rejection_blocker_fingerprint": "same-blockers",
        }
        saved = []
        with (
            patch("app.stock_suite_app.load_ai_internal_league_state", return_value=state),
            patch(
                "app.stock_suite_app.save_ai_internal_league_state",
                side_effect=lambda payload: saved.append(dict(payload)) or payload,
            ),
            patch(
                "app.stock_suite_app.build_operating_focus",
                return_value={"large_batch_jobs_allowed": True},
            ),
            patch("app.stock_suite_app.run_ai_mini_league") as run_mock,
        ):
            result = run_autonomous_ai_internal_league_if_due()

        self.assertEqual("WAITING_FOR_EVIDENCE_CHANGE", result["status"])
        self.assertLessEqual(
            result["retry_after_seconds"],
            AI_INTERNAL_LEAGUE_REJECTION_BACKOFF_SECONDS,
        )
        self.assertEqual("WAITING_FOR_EVIDENCE_CHANGE", saved[-1]["scheduler_status"])
        run_mock.assert_not_called()

    def test_loaded_deferred_state_keeps_next_market_closed_window(self):
        state_file = MagicMock()
        state_file.exists.return_value = True
        state_file.read_text.return_value = json.dumps(
            {
                "enabled": True,
                "run_count": 106,
                "verified_learning_run_count": 0,
                "last_status": "DEFERRED_TO_MARKET_CLOSED_DAY",
                "last_run_at": "2026-07-14T11:49:41+09:00",
                "next_due_at": "2026-07-14T12:49:41+09:00",
            }
        )
        next_window = datetime.fromisoformat("2026-07-18T00:00:00+09:00")
        with (
            patch("app.stock_suite_app.AI_INTERNAL_LEAGUE_STATE_FILE", state_file),
            patch("app.stock_suite_app._next_ai_internal_league_window_at", return_value=next_window),
        ):
            state = load_ai_internal_league_state()
        self.assertEqual(state["next_due_at"], "2026-07-18T00:00:00+09:00")
        self.assertEqual(state["strict_learning_evidence_status"], "awaiting_first_verified_run")
        self.assertEqual(state["strict_learning_progress_label"], "0 verified / 106 attempts")

    def test_autonomous_learning_league_waits_for_single_heavy_slot(self):
        state = {
            "ok": True,
            "enabled": True,
            "interval_seconds": 3600,
            "initial_cash": 10_000_000,
            "start_year": 2000,
            "run_count": 0,
            "verified_learning_run_count": 0,
        }
        HEAVY_RESEARCH_JOB_LOCK.acquire()
        try:
            with (
                patch("app.stock_suite_app.load_ai_internal_league_state", return_value=state),
                patch("app.stock_suite_app.save_ai_internal_league_state", side_effect=lambda payload: payload),
                patch("app.stock_suite_app.build_operating_focus", return_value={"large_batch_jobs_allowed": True}),
                patch(
                    "app.stock_suite_app._ensure_long_horizon_fixed_etf_universe",
                    return_value={"validation": {"passed": True}},
                ),
                patch("app.stock_suite_app.run_ai_mini_league") as run_mock,
            ):
                result = run_autonomous_ai_internal_league_if_due(force=True)
        finally:
            HEAVY_RESEARCH_JOB_LOCK.release()
        self.assertEqual(result["status"], "WAITING_FOR_HEAVY_RESEARCH_SLOT")
        self.assertEqual(result["retry_after_seconds"], 60)
        self.assertFalse(result["live_order_allowed"])
        run_mock.assert_not_called()

    def test_90_session_forward_ab_contract_freezes_pairs_timestamp_and_ledger(self):
        source_contract = {
            "contract_id": "LCFPR-source",
            "contract_hash": "a" * 64,
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "plans": [
                {
                    "contestant_id": "self",
                    "source_strategy": {
                        "strategy_generation_id": "baseline-v1",
                        "strategy_mode": "ma_cross",
                        "fast": 10,
                        "slow": 30,
                    },
                    "candidate_strategies": [
                        {
                            "strategy_generation_id": "improved-v2",
                            "strategy_mode": "ma_cross",
                            "fast": 8,
                            "slow": 26,
                        }
                    ],
                    "learning_transition": {"transition_hash": "b" * 64},
                }
            ],
        }
        source_status = {
            "valid": True,
            "hash_valid": True,
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
        }
        source_lookup = {"found": True, "valid": True, "contract": source_contract}
        timestamp_evidence = {
            "schema": "codexstock_official_external_timestamp_evidence_v1",
            "status": "VERIFIED",
            "captured_at": "2026-07-18T07:00:00+00:00",
            "required_source_count": 2,
            "verified_source_count": 2,
            "source_spread_seconds": 1.0,
            "sources": [
                {"source_id": "kis_openapi", "status": "VERIFIED"},
                {"source_id": "krx_global", "status": "VERIFIED"},
            ],
        }
        timestamp_evidence["evidence_sha256"] = stock_app._hash_without_fields(
            timestamp_evidence,
            "evidence_sha256",
        )
        now = datetime.fromisoformat("2026-07-18T16:00:00+09:00")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_path = root / "forward-ab.json"
            ledger_path = root / "forward-ab.jsonl"
            with (
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_CONTRACT_FILE",
                    contract_path,
                ),
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_FILE",
                    ledger_path,
                ),
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_counterfactual_preregistration_status",
                    return_value=source_status,
                ),
                patch(
                    "app.stock_suite_app._find_ai_staff_learning_counterfactual_preregistration",
                    return_value=source_lookup,
                ),
                patch.object(
                    stock_app.AI_DAEMON,
                    "status",
                    return_value={"running": True, "thread_alive": True},
                ),
                patch.object(
                    stock_app.AUTOPILOT_SCHEDULER,
                    "status",
                    return_value={"running": False, "thread_alive": False},
                ),
            ):
                first = stock_app.ensure_ai_staff_90_session_forward_ab_contract(
                    now=now,
                    external_timestamp_evidence=timestamp_evidence,
                )
                second = stock_app.ensure_ai_staff_90_session_forward_ab_contract(
                    now=now,
                    external_timestamp_evidence=timestamp_evidence,
                )
                status = stock_app.build_ai_staff_90_session_forward_ab_status(now=now)
                overdue_before_capture = stock_app.build_ai_staff_90_session_forward_ab_status(
                    now=datetime.fromisoformat("2026-07-20T16:00:00+09:00")
                )
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                ledger = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
                focus = {
                    "mode": "DAILY_REVIEW_FOCUS",
                    "market_open": False,
                    "market_priority_active": False,
                    "market_closed_day": False,
                }
                with patch(
                    "app.stock_suite_app._build_official_external_timestamp_evidence",
                    return_value=timestamp_evidence,
                ):
                    captured = stock_app.run_ai_staff_90_session_forward_ab_observer_tick(
                        result={"status": "no_due_candidate", "results": []},
                        now=datetime.fromisoformat("2026-07-20T16:00:00+09:00"),
                        operating_focus=focus,
                    )
                    duplicate = stock_app.run_ai_staff_90_session_forward_ab_observer_tick(
                        result={"status": "no_due_candidate", "results": []},
                        now=datetime.fromisoformat("2026-07-20T16:05:00+09:00"),
                        operating_focus=focus,
                    )
                captured_status = stock_app.build_ai_staff_90_session_forward_ab_status(
                    now=datetime.fromisoformat("2026-07-21T09:00:00+09:00")
                )
                ledger_path.write_text(
                    json.dumps(ledger, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                missed_status = stock_app.build_ai_staff_90_session_forward_ab_status(
                    now=datetime.fromisoformat("2026-07-21T09:00:00+09:00")
                )

        self.assertTrue(first["ok"])
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual("FROZEN_FORWARD_PAPER_RUNNING", status["status"])
        self.assertEqual(90, status["required_trading_sessions"])
        self.assertEqual(0, status["completed_trading_sessions"])
        self.assertTrue(status["collection_route_ready"])
        self.assertTrue(status["collection_preflight"]["preflight_ok"])
        self.assertEqual("OVERDUE_TODAY", overdue_before_capture["collection_health"])
        self.assertTrue(overdue_before_capture["current_session_observation_overdue"])
        self.assertIn(
            "forward_ab_required_session_evidence_overdue_today",
            overdue_before_capture["evidence_blockers"],
        )
        self.assertEqual(90, len(contract["planned_session_dates"]))
        self.assertEqual("2026-07-20", contract["target_start_date"])
        self.assertEqual(1, len(contract["strategy_pairs"]))
        self.assertEqual("VERIFIED", contract["external_timestamp_evidence"]["status"])
        self.assertRegex(contract["contract_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual("CONTRACT_FROZEN", ledger["event_type"])
        self.assertRegex(ledger["ledger_hash"], r"^[0-9a-f]{64}$")
        self.assertTrue(captured["recorded"])
        self.assertEqual("independent_daily_forward_ab_observer", captured["collector"])
        self.assertTrue(captured["scheduler_independent_of_candidate_creation"])
        self.assertFalse(duplicate["recorded"])
        self.assertEqual("ALREADY_CAPTURED", duplicate["status"])
        self.assertEqual(1, captured_status["completed_trading_sessions"])
        self.assertEqual([], captured_status["missed_required_observation_dates"])
        self.assertEqual("DUE_TODAY", captured_status["collection_health"])
        self.assertTrue(captured_status["current_session_observation_due"])
        self.assertTrue(missed_status["ok"])
        self.assertEqual(
            "EVIDENCE_GAP_QUARANTINED_CONTINUING_COLLECTION",
            missed_status["status"],
        )
        self.assertEqual(["2026-07-20"], missed_status["missed_required_observation_dates"])
        self.assertIn(
            "forward_ab_required_session_evidence_missing",
            missed_status["evidence_blockers"],
        )
        self.assertFalse(status["live_order_allowed"])

    def test_90_session_forward_ab_preflight_blocks_overdue_when_collectors_are_down(self):
        source_contract = {
            "contract_id": "LCFPR-source",
            "contract_hash": "a" * 64,
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "plans": [
                {
                    "contestant_id": "self",
                    "source_strategy": {"strategy_generation_id": "baseline-v1"},
                    "candidate_strategies": [{"strategy_generation_id": "improved-v2"}],
                    "learning_transition": {"transition_hash": "b" * 64},
                }
            ],
        }
        timestamp_evidence = {
            "schema": "codexstock_official_external_timestamp_evidence_v1",
            "status": "VERIFIED",
            "captured_at": "2026-07-18T07:00:00+00:00",
            "required_source_count": 2,
            "verified_source_count": 2,
            "source_spread_seconds": 1.0,
            "sources": [{"source_id": "kis_openapi"}, {"source_id": "krx_global"}],
        }
        timestamp_evidence["evidence_sha256"] = stock_app._hash_without_fields(
            timestamp_evidence,
            "evidence_sha256",
        )
        source_lookup = {"found": True, "valid": True, "contract": source_contract}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_CONTRACT_FILE",
                    root / "forward-ab.json",
                ),
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_FILE",
                    root / "forward-ab.jsonl",
                ),
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_counterfactual_preregistration_status",
                    return_value={"valid": True, "hash_valid": True},
                ),
                patch(
                    "app.stock_suite_app._find_ai_staff_learning_counterfactual_preregistration",
                    return_value=source_lookup,
                ),
                patch.object(
                    stock_app.AI_DAEMON,
                    "status",
                    return_value={"running": False, "thread_alive": False},
                ),
                patch.object(
                    stock_app.AUTOPILOT_SCHEDULER,
                    "status",
                    return_value={"running": False, "thread_alive": False},
                ),
            ):
                stock_app.ensure_ai_staff_90_session_forward_ab_contract(
                    now=datetime.fromisoformat("2026-07-18T16:00:00+09:00"),
                    external_timestamp_evidence=timestamp_evidence,
                )
                status = stock_app.build_ai_staff_90_session_forward_ab_status(
                    now=datetime.fromisoformat("2026-07-20T16:00:00+09:00")
                )

        self.assertFalse(status["collection_route_ready"])
        self.assertEqual("COLLECTOR_DOWN_OVERDUE", status["collection_health"])
        self.assertFalse(status["collection_preflight"]["preflight_ok"])
        self.assertIn(
            "forward_ab_collection_route_not_running",
            status["evidence_blockers"],
        )

    def test_90_session_forward_ab_flags_final_evaluation_due_on_first_eligible_date(self):
        source_contract = {
            "contract_id": "LCFPR-source",
            "contract_hash": "a" * 64,
            "target_start_date": "2026-07-20",
            "target_end_date": "2026-09-18",
            "plans": [
                {
                    "contestant_id": "self",
                    "source_strategy": {"strategy_generation_id": "baseline-v1"},
                    "candidate_strategies": [{"strategy_generation_id": "improved-v2"}],
                    "learning_transition": {"transition_hash": "b" * 64},
                }
            ],
        }
        timestamp_evidence = {
            "schema": "codexstock_official_external_timestamp_evidence_v1",
            "status": "VERIFIED",
            "captured_at": "2026-07-18T07:00:00+00:00",
            "required_source_count": 2,
            "verified_source_count": 2,
            "source_spread_seconds": 1.0,
            "sources": [{"source_id": "kis_openapi"}, {"source_id": "krx_global"}],
        }
        timestamp_evidence["evidence_sha256"] = stock_app._hash_without_fields(
            timestamp_evidence,
            "evidence_sha256",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_path = root / "forward-ab.json"
            ledger_path = root / "forward-ab.jsonl"
            with (
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_CONTRACT_FILE",
                    contract_path,
                ),
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_FILE",
                    ledger_path,
                ),
                patch(
                    "app.stock_suite_app.build_ai_staff_learning_counterfactual_preregistration_status",
                    return_value={"valid": True, "hash_valid": True},
                ),
                patch(
                    "app.stock_suite_app._find_ai_staff_learning_counterfactual_preregistration",
                    return_value={"found": True, "valid": True, "contract": source_contract},
                ),
                patch.object(
                    stock_app.AI_DAEMON,
                    "status",
                    return_value={"running": True, "thread_alive": True},
                ),
                patch.object(
                    stock_app.AUTOPILOT_SCHEDULER,
                    "status",
                    return_value={"running": True, "thread_alive": True},
                ),
            ):
                stock_app.ensure_ai_staff_90_session_forward_ab_contract(
                    now=datetime.fromisoformat("2026-07-18T16:00:00+09:00"),
                    external_timestamp_evidence=timestamp_evidence,
                )
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                rows = [
                    json.loads(line)
                    for line in ledger_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                previous_hash = rows[-1]["ledger_hash"]
                for sequence, session_date in enumerate(contract["planned_session_dates"], start=1):
                    row = {
                        "schema": stock_app.AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_SCHEMA,
                        "event_type": "SESSION_CAPTURED",
                        "sequence": sequence,
                        "observed_at": f"{session_date}T15:40:00+09:00",
                        "session_date": session_date,
                        "contract_id": contract["contract_id"],
                        "contract_hash": contract["contract_hash"],
                        "external_timestamp_evidence": timestamp_evidence,
                        "market_input_witness_sha256": "c" * 64,
                        "strategy_pairs_digest": contract["strategy_pairs_digest"],
                        "evaluation_status": "LOCKED_INPUT_CAPTURED_PENDING_FINAL_PAPER_REPLAY",
                        "previous_ledger_hash": previous_hash,
                        "paper_only": True,
                        "live_order_allowed": False,
                    }
                    row["ledger_hash"] = stock_app._ai_staff_90_session_forward_ab_ledger_hash(row)
                    previous_hash = row["ledger_hash"]
                    stock_app._append_jsonl(ledger_path, row)
                status = stock_app.build_ai_staff_90_session_forward_ab_status(
                    now=datetime.fromisoformat(
                        f"{contract['first_eligible_evaluation_date']}T18:00:00+09:00"
                    )
                )

        self.assertEqual(90, status["completed_trading_sessions"])
        self.assertEqual("COMPLETED_PENDING_FINAL_AB_EVALUATION", status["status"])
        self.assertEqual("FINAL_AB_EVALUATION_DUE", status["final_ab_evaluation_status"])
        self.assertTrue(status["final_ab_evaluation_due"])
        self.assertTrue(status["automatic_final_ab_evaluation_required"])
        self.assertIn("forward_ab_final_evaluation_due", status["evidence_blockers"])

    def test_90_session_forward_ab_final_evaluation_persists_hashed_paper_result(self):
        baseline = {
            "strategy_generation_id": "baseline-v1",
            "strategy": "ma_cross",
            "fast": 10,
            "slow": 30,
        }
        adapted = {
            "strategy_generation_id": "improved-v2",
            "strategy": "ma_cross",
            "fast": 8,
            "slow": 26,
        }
        pair = {
            "contestant_id": "self",
            "strategy_a_id": "baseline-v1",
            "strategy_a_signature": stock_app._ai_staff_strategy_signature(baseline),
            "strategy_b_id": "improved-v2",
            "strategy_b_signature": stock_app._ai_staff_strategy_signature(adapted),
            "learning_transition_hash": "b" * 64,
        }
        pair["pair_hash"] = stock_app._hash_without_fields(pair, "pair_hash")
        contract = {
            "contract_id": "FAB90-test",
            "contract_hash": "a" * 64,
            "source_target_start_date": "2026-07-20",
            "source_target_end_date": "2026-09-18",
            "strategy_pairs": [pair],
            "planned_session_dates": ["2026-07-20", "2026-11-30"],
            "planned_session_dates_sha256": "c" * 64,
        }
        source_contract = {
            "symbols": ["005930"],
            "plans": [{
                "contestant_id": "self",
                "display_name": "self",
                "source_strategy": baseline,
                "candidate_strategies": [adapted],
                "learning_transition": {"transition_hash": "b" * 64},
            }],
        }
        replay_rows = [
            {
                "contestant_id": "self",
                "run_type": "same_period_baseline",
                "status": "COMPLETED",
                "total_return_pct": 5.0,
                "max_drawdown_pct": 10.0,
                "execution_comparison_contract_hash": "d" * 64,
                "replay_data_bundle_evidence": {"slice_content_hash": "e" * 64},
            },
            {
                "contestant_id": "self",
                "run_type": "same_period_adapted",
                "status": "COMPLETED",
                "total_return_pct": 9.0,
                "max_drawdown_pct": 8.0,
                "execution_comparison_contract_hash": "d" * 64,
                "replay_data_bundle_evidence": {"slice_content_hash": "e" * 64},
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger_path = root / "forward-ab-ledger.jsonl"
            result_path = root / "forward-ab-result.json"
            ledger_path.write_text(
                json.dumps({
                    "schema": stock_app.AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_SCHEMA,
                    "event_type": "CONTRACT_FROZEN",
                    "ledger_hash": "f" * 64,
                }) + "\n",
                encoding="utf-8",
            )
            with (
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_LEDGER_FILE",
                    ledger_path,
                ),
                patch.object(
                    stock_app,
                    "AI_STAFF_90_SESSION_FORWARD_AB_RESULT_FILE",
                    result_path,
                ),
                patch(
                    "app.stock_suite_app.build_ai_staff_90_session_forward_ab_status",
                    return_value={
                        "final_ab_evaluation_complete": False,
                        "final_ab_evaluation_due": True,
                        "evidence_blockers": ["forward_ab_final_evaluation_due"],
                    },
                ),
                patch(
                    "app.stock_suite_app._load_ai_staff_90_session_forward_ab_contract",
                    return_value=contract,
                ),
                patch(
                    "app.stock_suite_app._find_ai_staff_learning_counterfactual_preregistration",
                    return_value={"valid": True, "contract": source_contract},
                ),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={"market_priority_active": False, "market_open": False},
                ),
                patch(
                    "app.stock_suite_app._run_ai_staff_learning_counterfactual_jobs",
                    return_value={"rows": replay_rows},
                ),
            ):
                result = stock_app.run_ai_staff_90_session_forward_ab_final_evaluation(
                    now=datetime.fromisoformat("2026-12-01T18:00:00+09:00")
                )
                persisted = stock_app._load_ai_staff_90_session_forward_ab_result(
                    contract["contract_hash"]
                )
                ledger_rows = [
                    json.loads(line)
                    for line in ledger_path.read_text(encoding="utf-8").splitlines()
                ]

        self.assertTrue(result["ok"])
        self.assertEqual("COMPLETED", result["status"])
        self.assertEqual("IMPROVED", result["pair_results"][0]["verdict"])
        self.assertEqual(5.0, result["pair_results"][0]["risk_adjusted_improvement"])
        self.assertEqual(result["result_hash"], persisted["result_hash"])
        self.assertTrue(result["official_learning_evidence"])
        self.assertFalse(result["official_performance_claim_allowed"])
        self.assertFalse(result["automatic_promotion"])
        self.assertEqual("FINAL_AB_EVALUATION", ledger_rows[-1]["event_type"])
        self.assertEqual(result["result_hash"], ledger_rows[-1]["result_hash"])


if __name__ == "__main__":
    unittest.main()
