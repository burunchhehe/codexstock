import unittest
from unittest.mock import patch

from app import stock_suite_app as suite


def _fake_replay(**kwargs):
    bundle = kwargs.get("replay_data_bundle")
    bundle_hash = str(bundle.get("content_hash") or "") if isinstance(bundle, dict) else ""
    return {
        "id": "HREPLAY-TEST",
        "symbols": list(kwargs.get("symbols", [])),
        "strategy_mode": kwargs.get("strategy_mode", "ma_cross"),
        "strategy_label": "test",
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "trade_count": 0,
        "win_rate_pct": 0.0,
        "final_equity": kwargs.get("initial_cash", 150_000.0),
        "replay_data_bundle_evidence": {
            "used": isinstance(bundle, dict),
            "passed": isinstance(bundle, dict),
            "bundle_content_hash": bundle_hash,
            "slice_content_hash": "sha256:" + "b" * 64 if bundle_hash else "",
            "source_fetch_reused": isinstance(bundle, dict),
            "future_rows_excluded_before_strategy": isinstance(bundle, dict),
            "no_rows_outside_requested_period": isinstance(bundle, dict),
        },
        "summary": "test replay",
    }


class DailyReplayGainerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.shared_bundle = {
            "content_hash": "sha256:" + "a" * 64,
            "symbols": ["111111", "222222", "005930", "000660"],
            "persistence_policy": "execution_scoped_memory_only",
            "live_order_allowed": False,
        }
        self.bundle_patcher = patch.object(
            suite,
            "_build_historical_replay_data_bundle",
            return_value=self.shared_bundle,
        )
        self.bundle_builder = self.bundle_patcher.start()
        self.addCleanup(self.bundle_patcher.stop)

    def test_today_gainers_are_prioritized_and_incomplete_rows_are_analysis_only(self):
        radar = {
            "ok": True,
            "items": [
                {
                    "symbol": "111111",
                    "name": "상승완료",
                    "change_pct": 18.5,
                    "amount_eok": 320.0,
                    "data_quality": "complete",
                    "turnover_source": "fluctuation_rank",
                    "live_candidate_eligible": True,
                },
                {
                    "symbol": "222222",
                    "name": "상승검증대기",
                    "change_pct": 15.0,
                    "amount_eok": 0.0,
                    "data_quality": "incomplete_turnover",
                    "turnover_source": "fluctuation_rank",
                    "live_candidate_eligible": False,
                },
            ],
        }
        with (
            patch.object(suite, "fetch_kr_market_rows", return_value=("2026-07-16", [])),
            patch.object(suite, "build_kis_fluctuation_radar", return_value=radar),
            patch.object(suite, "_daily_replay_drill_symbols", return_value=["005930", "000660"]),
            patch.object(suite, "run_historical_paper_replay", side_effect=_fake_replay) as replay,
            patch.object(suite, "_append_jsonl"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = suite.run_post_market_daily_replay_drill(
                target_date="2026-07-16",
                repeats=1,
                remember=False,
            )

        self.assertEqual(["111111", "222222", "005930", "000660"], result["symbols"])
        self.assertEqual(2, result["today_mover_count"])
        self.assertEqual(1, result["analysis_only_mover_count"])
        self.assertFalse(result["today_movers"][0]["analysis_only"])
        self.assertTrue(result["today_movers"][1]["analysis_only"])
        self.assertFalse(result["today_movers"][1]["replay_turnover_verified"])
        self.assertTrue(result["symbol_selection_contract"]["analysis_only_does_not_enable_live_order"])
        self.assertFalse(result["symbol_selection_contract"]["replay_selection_has_live_order_side_effect"])
        self.assertEqual(["111111", "222222", "005930", "000660"], replay.call_args.kwargs["symbols"])

    def test_same_day_krx_turnover_completes_replay_evidence_without_live_upgrade(self):
        radar = {
            "ok": True,
            "items": [
                {
                    "symbol": "222222",
                    "name": "교차검증종목",
                    "change_pct": 15.0,
                    "amount_eok": 0.0,
                    "data_quality": "incomplete_turnover",
                    "turnover_source": "fluctuation_rank",
                    "live_candidate_eligible": False,
                }
            ],
        }
        krx_rows = [
            {
                "symbol": "222222",
                "amount": 12_340_000_000,
                "source": "KRX-2026-07-16",
            }
        ]
        with (
            patch.object(suite, "fetch_kr_market_rows", return_value=("2026-07-16", krx_rows)),
            patch.object(suite, "build_kis_fluctuation_radar", return_value=radar),
            patch.object(suite, "_daily_replay_drill_symbols", return_value=["005930"]),
            patch.object(suite, "run_historical_paper_replay", side_effect=_fake_replay),
            patch.object(suite, "_append_jsonl"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = suite.run_post_market_daily_replay_drill(
                target_date="2026-07-16",
                repeats=1,
                remember=False,
            )

        mover = result["today_movers"][0]
        self.assertEqual(123.4, mover["amount_eok"])
        self.assertEqual("complete_for_replay", mover["data_quality"])
        self.assertEqual("krx_daily_crosscheck", mover["turnover_source"])
        self.assertTrue(mover["replay_turnover_verified"])
        self.assertTrue(mover["replay_analysis_eligible"])
        self.assertFalse(mover["live_candidate_eligible"])
        self.assertTrue(mover["analysis_only"])
        self.assertEqual(1, result["replay_turnover_verified_mover_count"])
        self.assertEqual(1, result["krx_crosschecked_mover_count"])
        self.assertTrue(result["symbol_selection_contract"]["krx_turnover_crosscheck_does_not_enable_live_candidate"])

    def test_prior_day_krx_turnover_cannot_complete_today_replay_evidence(self):
        radar = {
            "ok": True,
            "items": [
                {
                    "symbol": "222222",
                    "name": "날짜불일치종목",
                    "change_pct": 15.0,
                    "amount_eok": 0.0,
                    "data_quality": "incomplete_turnover",
                    "turnover_source": "fluctuation_rank",
                    "live_candidate_eligible": False,
                }
            ],
        }
        stale_rows = [
            {
                "symbol": "222222",
                "amount": 12_340_000_000,
                "source": "KRX-2026-07-15",
            }
        ]
        with (
            patch.object(suite, "fetch_kr_market_rows", return_value=("2026-07-15", stale_rows)),
            patch.object(suite, "build_kis_fluctuation_radar", return_value=radar),
            patch.object(suite, "_daily_replay_drill_symbols", return_value=["005930"]),
            patch.object(suite, "run_historical_paper_replay", side_effect=_fake_replay),
            patch.object(suite, "_append_jsonl"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = suite.run_post_market_daily_replay_drill(
                target_date="2026-07-16",
                repeats=1,
                remember=False,
            )

        mover = result["today_movers"][0]
        self.assertEqual(0.0, mover["amount_eok"])
        self.assertEqual("incomplete_turnover", mover["data_quality"])
        self.assertFalse(mover["turnover_crosscheck"]["date_match"])
        self.assertFalse(mover["replay_turnover_verified"])
        self.assertEqual(0, result["krx_crosschecked_mover_count"])

    def test_explicit_symbols_override_gainer_selection(self):
        radar = {
            "ok": True,
            "items": [
                {
                    "symbol": "111111",
                    "name": "상승종목",
                    "change_pct": 12.0,
                    "amount_eok": 100.0,
                    "data_quality": "complete",
                    "turnover_source": "fluctuation_rank",
                    "live_candidate_eligible": True,
                }
            ],
        }
        with (
            patch.object(suite, "fetch_kr_market_rows", return_value=("2026-07-16", [])),
            patch.object(suite, "build_kis_fluctuation_radar", return_value=radar),
            patch.object(suite, "run_historical_paper_replay", side_effect=_fake_replay) as replay,
            patch.object(suite, "_append_jsonl"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = suite.run_post_market_daily_replay_drill(
                target_date="2026-07-16",
                repeats=1,
                symbols=["005930"],
                remember=False,
            )

        self.assertEqual(["005930"], result["symbols"])
        self.assertTrue(result["symbol_selection_contract"]["explicit_symbols_override"])
        self.assertEqual(["005930"], replay.call_args.kwargs["symbols"])

    def test_repeats_share_one_immutable_data_bundle(self):
        with (
            patch.object(suite, "fetch_kr_market_rows", return_value=("2026-07-16", [])),
            patch.object(suite, "build_kis_fluctuation_radar", return_value={"ok": True, "items": []}),
            patch.object(suite, "_daily_replay_drill_symbols", return_value=["005930", "000660"]),
            patch.object(suite, "run_historical_paper_replay", side_effect=_fake_replay) as replay,
            patch.object(suite, "_append_jsonl"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = suite.run_post_market_daily_replay_drill(
                target_date="2026-07-16",
                repeats=3,
                remember=False,
            )

        self.bundle_builder.assert_called_once()
        self.assertEqual(3, replay.call_count)
        self.assertTrue(all(call.kwargs["replay_data_bundle"] is self.shared_bundle for call in replay.call_args_list))
        shared = result["shared_replay_data_bundle"]
        self.assertTrue(shared["created"])
        self.assertTrue(shared["used_for_all_completed_runs"])
        self.assertTrue(shared["bundle_hash_consistent"])
        self.assertEqual([self.shared_bundle["content_hash"]], shared["run_bundle_hashes"])
        self.assertFalse(shared["fallback_to_per_run_fetch"])
        self.assertFalse(shared["live_order_allowed"])

    def test_bundle_build_failure_falls_back_and_is_disclosed(self):
        self.bundle_builder.side_effect = ValueError("bundle incomplete")
        with (
            patch.object(suite, "fetch_kr_market_rows", return_value=("2026-07-16", [])),
            patch.object(suite, "build_kis_fluctuation_radar", return_value={"ok": True, "items": []}),
            patch.object(suite, "_daily_replay_drill_symbols", return_value=["005930"]),
            patch.object(suite, "run_historical_paper_replay", side_effect=_fake_replay) as replay,
            patch.object(suite, "_append_jsonl"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = suite.run_post_market_daily_replay_drill(
                target_date="2026-07-16",
                repeats=2,
                remember=False,
            )

        self.assertEqual(2, replay.call_count)
        self.assertTrue(all(call.kwargs["replay_data_bundle"] is None for call in replay.call_args_list))
        shared = result["shared_replay_data_bundle"]
        self.assertFalse(shared["created"])
        self.assertTrue(shared["fallback_to_per_run_fetch"])
        self.assertIn("bundle incomplete", shared["fallback_reason"])
        self.assertFalse(shared["used_for_all_completed_runs"])


if __name__ == "__main__":
    unittest.main()
