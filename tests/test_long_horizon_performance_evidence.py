import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.stock_suite_app import (
    LONG_HORIZON_VERIFICATION_CONTRACT_VERSION,
    LONG_HORIZON_FIXED_ETF_UNIVERSE_ID,
    PointInTimeUniverseHistory,
    UniverseStore,
    _ai_tournament_bias_audit,
    _build_point_in_time_universe_coverage_certificate,
    _ensure_long_horizon_fixed_etf_universe,
    _long_horizon_fixed_etf_universe_status,
    _long_horizon_performance_evidence,
    _long_horizon_benchmark_cost_policy_current,
    _long_horizon_spy_benchmark,
    _refresh_ai_staff_long_horizon_benchmark,
)


class LongHorizonPerformanceEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start_date = "2000-01-03"
        self.end_date = "2026-01-02"
        years = (
            datetime.fromisoformat(self.end_date).date()
            - datetime.fromisoformat(self.start_date).date()
        ).days / 365.25
        initial_cash = 100_000_000.0
        final_equity = 400_000_000.0
        total_return = (final_equity / initial_cash - 1.0) * 100.0
        cagr = ((final_equity / initial_cash) ** (1.0 / years) - 1.0) * 100.0
        self.staff = {
            "contestant_id": "staff-1",
            "actual_start_date": self.start_date,
            "actual_end_date": self.end_date,
            "data_coverage": {
                "schema": "codexstock_replay_data_coverage_v1",
                "actual_start_date": self.start_date,
                "actual_end_date": self.end_date,
                "portfolio_boundary_coverage_passed": True,
            },
            "initial_cash": initial_cash,
            "final_equity": final_equity,
            "total_return_pct": round(total_return, 2),
            "cagr_pct": round(cagr, 2),
            "trade_count": 100,
            "total_transaction_cost": 12_345.0,
            "cost_model": {
                "enabled": True,
                "base_currency": "KRW",
                "commission_bps_each_side": 1.5,
                "slippage_bps_each_side": 5.0,
                "us_sell_tax_bps": 0.0,
                "fx_conversion_spread_bps_each_side": 10.0,
                "us_regulatory_fee_policy_version": "us-sec-finra-date-aware.v1",
            },
            "transaction_cost_audit": {
                "schema": "codexstock_replay_transaction_cost_audit_v1",
                "passed": True,
                "applied_action_count": 100,
                "recorded_total_transaction_cost": 12_345.0,
                "ledger_hash": "cost-ledger-hash",
            },
            "return_claim_status": "passed",
            "return_claim_blocked": False,
            "price_currency_unit_audit": {"passed": True, "base_currency": "KRW"},
            "execution_timing_model": {
                "version": "prior-bar-signal-next-close.v1",
                "lookahead_safe_required": True,
                "same_bar_signal_execution_allowed": False,
                "minimum_signal_lag_bars": 1,
            },
            "bias_audit": {"passed": True, "universe_dataset_id": "pit-universe-v1"},
            "walk_forward": {"passed": True, "status": "passed"},
        }
        self.benchmark = {
            "schema": "codexstock_long_horizon_benchmark_v3",
            "first_date": self.start_date,
            "last_date": self.end_date,
            "adjusted_row_count": 6_500,
            "comparison_currency": "KRW",
            "currency_conversion_validated": True,
            "dividends_reinvested": True,
            "krw_adjusted_cagr_pct": 8.0,
            "net_costed_krw_cagr_pct": 7.99,
            "transaction_cost_profile": {
                "policy_version": "mandatory-market-specific-paper-costs.v2",
                "commission_bps_each_side": 1.5,
                "slippage_bps_each_side": 5.0,
                "us_sell_tax_bps": 0.0,
                "fx_conversion_spread_bps_each_side": 10.0,
                "us_regulatory_fee_policy_version": "us-sec-finra-date-aware.v1",
                "base_currency": "KRW",
            },
            "transaction_cost_validated": True,
            "input_data_hash": "input-data-hash",
            "evidence_hash": "benchmark-hash",
        }

    def test_benchmark_cost_policy_requires_current_market_specific_contract(self):
        self.assertTrue(_long_horizon_benchmark_cost_policy_current(self.benchmark))
        legacy = copy.deepcopy(self.benchmark)
        legacy["transaction_cost_profile"].pop("policy_version")
        self.assertFalse(_long_horizon_benchmark_cost_policy_current(legacy))

    def evidence(self, staff=None, benchmark=None):
        return _long_horizon_performance_evidence(
            staff or self.staff,
            benchmark or self.benchmark,
            requested_start_date=self.start_date,
            requested_end_date=self.end_date,
        )

    def test_complete_exact_period_krw_evidence_is_official(self):
        evidence = self.evidence()
        self.assertTrue(evidence["passed"])
        self.assertEqual("official", evidence["status"])
        self.assertEqual(100.0, evidence["confidence_score"])
        self.assertIsNotNone(evidence["official_cagr_pct"])
        self.assertIsNotNone(evidence["excess_cagr_pctp"])

    def test_usd_benchmark_cannot_validate_krw_strategy(self):
        benchmark = copy.deepcopy(self.benchmark)
        benchmark.update(
            {
                "comparison_currency": "USD",
                "currency_conversion_validated": False,
                "krw_adjusted_cagr_pct": None,
            }
        )
        evidence = self.evidence(benchmark=benchmark)
        self.assertFalse(evidence["passed"])
        self.assertIn("benchmark_total_return_or_currency_evidence_invalid", evidence["blockers"])
        self.assertIsNone(evidence["official_cagr_pct"])

    def test_requested_period_label_cannot_hide_short_actual_history(self):
        staff = copy.deepcopy(self.staff)
        staff["actual_start_date"] = "2015-01-02"
        staff["data_coverage"]["actual_start_date"] = "2015-01-02"
        staff["data_coverage"]["portfolio_boundary_coverage_passed"] = False
        evidence = self.evidence(staff=staff)
        self.assertFalse(evidence["passed"])
        self.assertIn("actual_data_boundary_evidence_missing_or_incomplete", evidence["blockers"])
        self.assertIn("actual_horizon_below_20_years", evidence["blockers"])

    def test_cost_ledger_mismatch_blocks_official_claim(self):
        staff = copy.deepcopy(self.staff)
        staff["transaction_cost_audit"]["recorded_total_transaction_cost"] = 99.0
        evidence = self.evidence(staff=staff)
        self.assertFalse(evidence["passed"])
        self.assertIn("transaction_cost_ledger_not_reconciled", evidence["blockers"])

    def test_uncosted_benchmark_cannot_validate_net_strategy(self):
        benchmark = copy.deepcopy(self.benchmark)
        benchmark["transaction_cost_validated"] = False
        benchmark["net_costed_krw_cagr_pct"] = None
        evidence = self.evidence(benchmark=benchmark)
        self.assertFalse(evidence["passed"])
        self.assertIn("benchmark_total_return_or_currency_evidence_invalid", evidence["blockers"])
        self.assertIn("benchmark_transaction_cost_contract_mismatch", evidence["blockers"])
        self.assertIsNone(evidence["official_cagr_pct"])

    def test_benchmark_cost_profile_must_match_strategy(self):
        benchmark = copy.deepcopy(self.benchmark)
        benchmark["transaction_cost_profile"]["slippage_bps_each_side"] = 1.0
        evidence = self.evidence(benchmark=benchmark)
        self.assertFalse(evidence["passed"])
        self.assertIn("benchmark_transaction_cost_contract_mismatch", evidence["blockers"])

    def test_benchmark_boundary_must_exactly_match_strategy(self):
        benchmark = copy.deepcopy(self.benchmark)
        benchmark["last_date"] = "2026-01-01"
        evidence = self.evidence(benchmark=benchmark)
        self.assertFalse(evidence["passed"])
        self.assertIn("benchmark_period_not_aligned_with_strategy", evidence["blockers"])

    def test_verified_negative_oos_strategy_remains_official_measurement_but_not_promotable(self):
        staff = copy.deepcopy(self.staff)
        staff["walk_forward"] = {
            "passed": False,
            "status": "retraining_required",
            "checks": {
                "training_return_positive": False,
                "out_of_sample_return_positive": False,
                "out_of_sample_mdd_within_limit": True,
                "out_of_sample_trade_sample": True,
                "training_evidence_passed": True,
                "out_of_sample_cost_ledger_passed": True,
                "out_of_sample_price_currency_unit_passed": True,
                "out_of_sample_lookahead_safe_execution_passed": True,
                "same_cost_profile": True,
                "selection_leakage_free": True,
            },
        }
        evidence = self.evidence(staff=staff)
        self.assertTrue(evidence["passed"])
        self.assertTrue(evidence["walk_forward_measurement_evidence_validated"])
        self.assertFalse(evidence["strategy_walk_forward_passed"])
        self.assertFalse(evidence["strategy_promotion_allowed"])
        self.assertIsNotNone(evidence["official_cagr_pct"])

    def test_spy_benchmark_fills_missing_2000_fx_boundary_from_official_ecos(self):
        spy_rows = [
            {"date": "2000-01-03", "close": 145.44, "adjusted_close": 93.19},
            {"date": "2026-01-02", "close": 690.0, "adjusted_close": 690.0},
        ]
        yahoo_fx_rows = [
            {"date": "2026-01-02", "close": 1470.0, "adjusted_close": 1470.0},
        ]

        def yahoo(symbol, *_args, **_kwargs):
            return {"rows": spy_rows if symbol == "SPY" else yahoo_fx_rows}

        with (
            patch("app.stock_suite_app._fetch_yahoo_chart_range", side_effect=yahoo),
            patch(
                "app.stock_suite_app.INTEGRATIONS.ecos_series",
                return_value={
                    "ok": True,
                    "configured": True,
                    "message": "ok",
                    "rows": [
                        {
                            "time": "19991231",
                            "value": 1138.0,
                            "unit": "KRW",
                            "stat_name": "USD/KRW",
                            "item_name1": "reference rate",
                        },
                        {
                            "time": "20000103",
                            "value": 1122.5,
                            "unit": "KRW",
                            "stat_name": "USD/KRW",
                            "item_name1": "reference rate",
                        },
                    ],
                },
            ) as ecos_series,
        ):
            benchmark = _long_horizon_spy_benchmark("2000-01-03", "2026-01-02")

        self.assertEqual("KRW", benchmark["comparison_currency"])
        self.assertTrue(benchmark["currency_conversion_validated"])
        self.assertEqual("codexstock_long_horizon_benchmark_v3", benchmark["schema"])
        self.assertTrue(benchmark["transaction_cost_validated"])
        self.assertLess(
            benchmark["net_costed_krw_cagr_pct"],
            benchmark["krw_adjusted_cagr_pct"],
        )
        self.assertTrue(benchmark["input_data_hash"])
        self.assertEqual(1122.5, benchmark["usdkrw_first"])
        self.assertEqual(1470.0, benchmark["usdkrw_last"])
        self.assertIn("BOK ECOS", benchmark["usdkrw_source"])
        self.assertFalse(benchmark["usdkrw_future_value_used"])
        self.assertTrue(benchmark["usdkrw_boundary_evidence"]["first"]["ok"])
        called = ecos_series.call_args.kwargs
        self.assertEqual("20000103", called["end"])
        self.assertEqual("731Y001", called["stat_code"])

    def test_stored_usd_benchmark_retries_after_ecos_fallback_upgrade(self):
        payload = {
            "schema": "codexstock_ai_staff_long_horizon_v1",
            "start_date": "2000-01-03",
            "end_date": "2026-01-02",
            "claim_policy_version": "strict-long-horizon-evidence.v1",
            "benchmark": {
                "dividend_adjusted_cagr_pct": 8.0,
                "krw_adjusted_cagr_pct": None,
                "currency_conversion_validated": False,
                "fx_error": "USD/KRW does not cover the benchmark boundary dates",
            },
            "staff": [],
        }
        upgraded = {
            "schema": "codexstock_long_horizon_benchmark_v3",
            "dividend_adjusted_cagr_pct": 8.0,
            "krw_adjusted_cagr_pct": 9.1,
            "net_costed_krw_cagr_pct": 9.09,
            "currency_conversion_validated": True,
            "transaction_cost_validated": True,
            "fx_policy_version": "ecos-boundary-fallback.v1",
        }
        with (
            patch("app.stock_suite_app._long_horizon_spy_benchmark", return_value=upgraded) as rebuild,
            patch("app.stock_suite_app._save_ai_staff_long_horizon_benchmark") as save,
        ):
            result = _refresh_ai_staff_long_horizon_benchmark(payload)

        rebuild.assert_called_once_with("2000-01-03", "2026-01-02")
        save.assert_called_once()
        self.assertEqual("ecos-boundary-fallback.v1", result["benchmark"]["fx_policy_version"])
        self.assertTrue(result["benchmark"]["currency_conversion_validated"])
        self.assertEqual("codexstock_ai_staff_long_horizon_v2", result["schema"])
        self.assertEqual("fixed_strategy_durability", result["benchmark_type"])
        self.assertFalse(result["learning_career_simulation"])
        self.assertFalse(result["learning_claim_allowed"])
        self.assertTrue(result["adaptive_training_system"]["challenge_mode"])
        self.assertEqual(6, result["adaptive_training_system"]["strategy_trials_per_staff_per_season"])

    def test_legacy_staff_rows_require_rerun_and_get_explicit_walk_forward_blocker(self):
        payload = {
            "ok": True,
            "schema": "codexstock_ai_staff_long_horizon_v2",
            "run_once_key": "ai-staff-2000-2026-costed-v3-krw-adjusted",
            "claim_policy_version": "strict-long-horizon-evidence.v1",
            "start_date": self.start_date,
            "end_date": self.end_date,
            "benchmark": copy.deepcopy(self.benchmark),
            "staff": [{"contestant_id": "staff-1"}, {"contestant_id": "staff-2"}],
        }
        with patch("app.stock_suite_app._save_ai_staff_long_horizon_benchmark") as save:
            result = _refresh_ai_staff_long_horizon_benchmark(payload)

        self.assertTrue(result["rerun_required"])
        self.assertEqual(
            LONG_HORIZON_VERIFICATION_CONTRACT_VERSION,
            result["verification_contract_version"],
        )
        self.assertEqual("재검증 필요", result["staff"][0]["walk_forward"]["status"])
        self.assertIn(
            "legacy_per_staff_walk_forward_missing",
            result["staff"][1]["walk_forward"]["blockers"],
        )
        save.assert_called_once()

    def test_fixed_pre2000_etf_universe_is_official_but_timing_scope_only(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UniverseStore(Path(directory))
            contract = _ensure_long_horizon_fixed_etf_universe(
                coverage_end=self.end_date,
                store=store,
            )
            audit = _ai_tournament_bias_audit(
                symbols=contract["symbols"],
                start_date=self.start_date,
                end_date=self.end_date,
                symbol_selection_mode="common",
                universe_dataset_id=LONG_HORIZON_FIXED_ETF_UNIVERSE_ID,
                store=store,
            )
            status = _long_horizon_fixed_etf_universe_status(
                coverage_end=self.end_date,
                store=store,
            )

        self.assertEqual(12, len(contract["symbols"]))
        self.assertTrue(contract["validation"]["passed"])
        self.assertTrue(audit["passed"])
        self.assertEqual("official_fixed_pre_start_instruments", audit["universe_grade"])
        self.assertEqual("timing_exit_and_risk_management_only", audit["claim_scope"])
        self.assertFalse(audit["stock_selection_claim_allowed"])
        self.assertFalse(audit["promotion_allowed"])
        self.assertTrue(status["ok"])
        self.assertEqual(contract["content_hash"], status["content_hash"])

    def test_bias_audit_automatically_selects_best_official_covering_universe(self):
        records = [
            {
                "symbol": "005930",
                "name": "Samsung Electronics",
                "market": "KOSPI",
                "security_type": "COMMON",
                "listing_date": "1975-06-11",
                "delisting_date": None,
            },
            {
                "symbol": "000660",
                "name": "SK hynix",
                "market": "KOSPI",
                "security_type": "COMMON",
                "listing_date": "1996-12-26",
                "delisting_date": None,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            store = UniverseStore(Path(directory))
            store.register(
                "current-snapshot",
                records,
                "official current snapshot",
                {
                    "grade": "official_snapshot",
                    "official": True,
                    "coverage_start": "2026-01-01",
                    "coverage_end": "2026-12-31",
                },
            )
            store.register(
                "official-history",
                records,
                "official listing history",
                {
                    "grade": "official_listing_interval_history",
                    "official": True,
                    "historical_query_allowed": True,
                    "includes_delisted": True,
                    "complete_daily_history": True,
                    "coverage_start": "2016-01-01",
                    "coverage_end": "2026-12-31",
                    "precoverage_listing_dates_clipped": 0,
                },
            )
            audit = _ai_tournament_bias_audit(
                symbols=["005930", "000660"],
                start_date="2024-01-02",
                end_date="2024-03-29",
                symbol_selection_mode="common",
                universe_dataset_id=None,
                store=store,
            )

        self.assertTrue(audit["passed"])
        self.assertEqual("official-history", audit["universe_dataset_id"])
        resolution = audit["universe_dataset_resolution"]
        self.assertEqual("automatic", resolution["mode"])
        self.assertEqual(2, resolution["candidate_count"])

    def test_partial_official_history_is_research_only_for_stock_selection(self):
        records = [{
            "symbol": "005930",
            "name": "Samsung Electronics",
            "market": "KOSPI",
            "security_type": "COMMON",
            "listing_date": "1975-06-11",
            "delisting_date": None,
        }]
        with tempfile.TemporaryDirectory() as directory:
            store = UniverseStore(Path(directory))
            store.register(
                "partial-official-history",
                records,
                "official listing history",
                {
                    "grade": "official_listing_interval_history",
                    "official": True,
                    "historical_query_allowed": True,
                    "includes_delisted": True,
                    "complete_daily_history": False,
                    "coverage_start": "2016-01-01",
                    "coverage_end": "2026-12-31",
                    "precoverage_listing_dates_clipped": 542,
                },
            )
            audit = _ai_tournament_bias_audit(
                symbols=["005930"],
                start_date="2024-01-02",
                end_date="2024-03-29",
                symbol_selection_mode="common",
                universe_dataset_id="partial-official-history",
                store=store,
            )

        self.assertFalse(audit["passed"])
        self.assertTrue(audit["research_only"])
        self.assertTrue(audit["research_claim_allowed"])
        self.assertFalse(audit["official_performance_claim_allowed"])
        self.assertIn(
            "official_universe_history_incomplete_for_stock_selection",
            audit["blockers"],
        )
        self.assertEqual(
            "OFFICIAL_PARTIAL_RESEARCH_ONLY",
            audit["claim_classification"]["classification"],
        )

    def test_coverage_certificate_expands_only_with_gap_free_official_snapshots(self):
        records = [{
            "symbol": "005930",
            "name": "Samsung Electronics",
            "market": "KOSPI",
            "security_type": "COMMON",
            "listing_date": "1975-06-11",
            "delisting_date": None,
        }]
        source_hash = "sha256:" + "1" * 64
        normalized_hash = "sha256:" + "2" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = UniverseStore(root)
            store.register(
                "partial-official-history",
                records,
                "official listing history",
                {
                    "grade": "official_listing_interval_history",
                    "official": True,
                    "historical_query_allowed": True,
                    "includes_delisted": True,
                    "complete_daily_history": False,
                    "coverage_start": "2016-07-06",
                    "coverage_end": "2026-07-13",
                    "precoverage_listing_dates_clipped": 542,
                },
            )
            history = PointInTimeUniverseHistory(root)
            baseline = {
                "as_of": "2026-07-13",
                "source": "KRX KIND official snapshot",
                "source_hash": source_hash,
                "normalized_hash": normalized_hash,
                "records": records,
                "evidence": {
                    "grade": "official_snapshot",
                    "official": True,
                    "coverage_start": "2026-07-13",
                    "coverage_end": "2026-07-13",
                },
            }
            history.create_baseline("kind-official-daily", baseline)
            one_day = _build_point_in_time_universe_coverage_certificate(
                store=store,
                history_store=history,
                as_of_date="2026-07-14",
            )
            history.append_snapshot(
                "kind-official-daily",
                {
                    **baseline,
                    "as_of": "2026-07-14",
                },
            )
            two_days = _build_point_in_time_universe_coverage_certificate(
                store=store,
                history_store=history,
                as_of_date="2026-07-14",
            )

        self.assertEqual("2016-07-06", one_day["official_stock_history_available_from"])
        self.assertEqual("2026-07-13", one_day["official_forward_capture_certified_start"])
        self.assertEqual("2026-07-13", one_day["official_forward_capture_certified_through"])
        self.assertFalse(one_day["official_performance_range_ready"])
        self.assertEqual(
            "OFFICIAL_PARTIAL_RESEARCH_ONLY",
            one_day["datasets"][0]["claim_classification"]["classification"],
        )
        self.assertTrue(
            any(
                row["classification"] == "RESEARCH_ONLY_FORWARD_CAPTURE_GAP"
                for row in one_day["research_only_ranges"]
            )
        )
        self.assertTrue(two_days["official_performance_range_ready"])
        self.assertEqual("2026-07-14", two_days["official_performance_certified_through"])

    def test_bias_audit_does_not_auto_promote_unofficial_declared_intervals(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UniverseStore(Path(directory))
            store.register(
                "unofficial-history",
                [{
                    "symbol": "005930",
                    "name": "Samsung Electronics",
                    "market": "KOSPI",
                    "security_type": "COMMON",
                    "listing_date": "1975-06-11",
                    "delisting_date": None,
                }],
                "user declared intervals",
                {
                    "grade": "declared_intervals",
                    "coverage_start": "2000-01-01",
                    "coverage_end": "2026-12-31",
                },
            )
            audit = _ai_tournament_bias_audit(
                symbols=["005930"],
                start_date="2024-01-02",
                end_date="2024-03-29",
                symbol_selection_mode="common",
                universe_dataset_id=None,
                store=store,
            )

        self.assertFalse(audit["passed"])
        self.assertIsNone(audit["universe_dataset_id"])
        self.assertEqual(
            "no_official_period_covering_dataset",
            audit["universe_dataset_resolution"]["blocker"],
        )

    def test_fixed_universe_rejects_symbol_added_after_test_start(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UniverseStore(Path(directory))
            contract = _ensure_long_horizon_fixed_etf_universe(
                coverage_end=self.end_date,
                store=store,
            )
            payload = store.get(LONG_HORIZON_FIXED_ETF_UNIVERSE_ID)
            payload["records"][0]["listing_date"] = "2001-01-01"
            evidence = payload["evidence"]
            store.register(
                "late-instrument",
                payload["records"],
                payload["source"],
                evidence,
            )
            validation = store.validate_period(
                "late-instrument",
                contract["symbols"],
                self.start_date,
                self.end_date,
            )

        self.assertFalse(validation["passed"])
        self.assertIn("SPY", validation["uncovered_symbols"])

    def test_fixed_universe_rejects_nonofficial_source_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UniverseStore(Path(directory))
            _ensure_long_horizon_fixed_etf_universe(coverage_end=self.end_date, store=store)
            payload = store.get(LONG_HORIZON_FIXED_ETF_UNIVERSE_ID)
            payload["evidence"]["official_source_urls"] = ["https://example.invalid/etf"]
            store.register("unofficial-fixed", payload["records"], payload["source"], payload["evidence"])
            validation = store.validate_period(
                "unofficial-fixed",
                [row["symbol"] for row in payload["records"]],
                self.start_date,
                self.end_date,
            )

        self.assertFalse(validation["passed"])
        self.assertIn("evidence_grade", validation["uncovered_symbols"])


if __name__ == "__main__":
    unittest.main()
