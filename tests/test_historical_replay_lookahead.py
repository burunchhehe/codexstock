import unittest
from datetime import date, timedelta
from unittest.mock import patch

from app.stock_suite_app import run_historical_paper_replay
from app.replay_calendar_evidence import verify_calendar_adjacency_proof


class HistoricalReplayLookaheadTests(unittest.TestCase):
    @staticmethod
    def _source(start, prices):
        rows = [
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "close": price,
                "adjclose": price,
            }
            for index, price in enumerate(prices)
        ]
        return {
            "source": "test_adjusted",
            "provider": "test",
            "rows": rows,
            "listing_evidence": {
                "status": "verified",
                "listed_at": "2000-01-01",
                "delisted_at": "",
            },
        }

    def test_daily_signal_executes_only_on_next_available_bar(self):
        start = date(2026, 1, 1)
        prices = [100 + index * 1.5 for index in range(25)] + [136 - index * 2.0 for index in range(12)]
        rows = [
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "close": price,
                "adjclose": price,
            }
            for index, price in enumerate(prices)
        ]
        source = {
            "source": "test_adjusted",
            "provider": "test",
            "rows": rows,
            "listing_evidence": {"status": "verified", "listed_at": "2000-01-01", "delisted_at": ""},
        }
        with patch("app.stock_suite_app._historical_close_rows", return_value=source):
            result = run_historical_paper_replay(
                ["005930"],
                rows[0]["date"],
                rows[-1]["date"],
                fast=2,
                slow=3,
                min_bars=5,
                persist_detail=False,
                strategy_mode="ma_cross",
            )

        actions = result["trades"]
        self.assertGreaterEqual(len(actions), 2)
        bundle_evidence = result["replay_data_bundle_evidence"]
        self.assertTrue(bundle_evidence["used"])
        self.assertTrue(bundle_evidence["future_rows_excluded_before_strategy"])
        self.assertTrue(
            all(
                row["market_data_snapshot_hash"]
                == bundle_evidence["slice_content_hash"]
                for row in actions
            )
        )
        self.assertTrue(all(row["decision_data_as_of"] < row["execution_at"] for row in actions))
        self.assertTrue(all(row["execution_at"] == row["date"] for row in actions))
        self.assertTrue(all(row["signal_lag_bars"] >= 1 for row in actions))
        self.assertTrue(all(row["execution_price_basis"] == "next_available_close" for row in actions))
        self.assertTrue(all(verify_calendar_adjacency_proof(row, expected_symbol=row["symbol"]) for row in actions))
        self.assertTrue(
            all(
                row["execution_symbol_bar_index"] == row["decision_symbol_bar_index"] + 1
                and row["decision_symbol_bar_date"] == row["decision_data_as_of"]
                and row["execution_symbol_bar_date"] == row["execution_at"]
                for row in actions
            )
        )
        self.assertNotEqual(actions[0]["decision_market_price"], actions[0]["market_price"])
        timing_model = result["execution_timing_model"]
        self.assertEqual("prior-bar-signal-next-close.v3", timing_model["version"])
        self.assertFalse(timing_model["same_bar_signal_execution_allowed"])
        self.assertTrue(timing_model["execution_bar_excluded_from_decision"])
        self.assertTrue(timing_model["symbol_calendar_alignment_required"])
        self.assertEqual(
            "skip_until_next_available_symbol_bar",
            timing_model["missing_execution_bar_policy"],
        )
        self.assertEqual(rows[0]["date"], result["actual_start_date"])
        self.assertEqual(rows[-1]["date"], result["actual_end_date"])
        self.assertTrue(result["data_coverage"]["portfolio_boundary_coverage_passed"])
        self.assertTrue(result["transaction_cost_audit"]["passed"])
        self.assertEqual(result["trade_count"], result["transaction_cost_audit"]["applied_action_count"])
        self.assertEqual(
            result["total_transaction_cost"],
            result["transaction_cost_audit"]["recorded_total_transaction_cost"],
        )
        reconciliation = result["trade_journal_reconciliation_summary"]
        self.assertEqual("trade-price-return-audit.v7", reconciliation["reconciliation_engine_version"])
        self.assertEqual(0, reconciliation["blocker_count"])
        self.assertEqual(0, reconciliation["official_return_blocker_count"])

    def test_breakout_ranking_ignores_execution_day_close(self):
        start = date(2026, 1, 1)
        first = self._source(start, [100.0] * 7 + [103.0, 90.0])
        second = self._source(start, [100.0] * 7 + [103.0, 200.0])

        def source_for(symbol, *_args, **_kwargs):
            return first if symbol == "005930" else second

        with patch("app.stock_suite_app._historical_close_rows", side_effect=source_for):
            result = run_historical_paper_replay(
                ["005930", "000660"],
                first["rows"][0]["date"],
                first["rows"][-1]["date"],
                fast=2,
                slow=3,
                min_bars=5,
                max_positions=1,
                persist_detail=False,
                strategy_mode="breakout",
                stop_loss_pct=40,
                take_profit_pct=1000,
                holding_limit_days=0,
            )

        buys = [row for row in result["trades"] if row["side"] == "BUY"]
        self.assertEqual(1, len(buys))
        self.assertEqual("005930", buys[0]["symbol"])
        self.assertEqual(103.0, buys[0]["decision_market_price"])
        self.assertEqual(90.0, buys[0]["market_price"])

    def test_breakout_exit_ignores_execution_day_close(self):
        start = date(2026, 1, 1)
        source = self._source(start, [100.0] * 7 + [103.0, 103.0, 50.0])
        with patch("app.stock_suite_app._historical_close_rows", return_value=source):
            result = run_historical_paper_replay(
                ["005930"],
                source["rows"][0]["date"],
                source["rows"][-1]["date"],
                fast=2,
                slow=3,
                min_bars=5,
                persist_detail=False,
                strategy_mode="breakout",
                stop_loss_pct=40,
                take_profit_pct=1000,
                holding_limit_days=0,
            )

        buys = [row for row in result["trades"] if row["side"] == "BUY"]
        sells = [row for row in result["trades"] if row["side"] == "SELL"]
        self.assertEqual(1, len(buys))
        self.assertEqual(103.0, buys[0]["market_price"])
        self.assertEqual([], sells)

    def test_turtle_master_proxy_trades_as_a_mid_term_strategy(self):
        start = date(2025, 1, 1)
        prices = [100.0 + index * 0.8 for index in range(100)]
        prices += [prices[-1] - (index + 1) * 2.5 for index in range(30)]
        source = self._source(start, prices)
        with patch("app.stock_suite_app._historical_close_rows", return_value=source):
            result = run_historical_paper_replay(
                ["005930"],
                source["rows"][0]["date"],
                source["rows"][-1]["date"],
                fast=20,
                slow=55,
                min_bars=40,
                persist_detail=False,
                strategy_mode="turtle_55",
            )

        self.assertEqual(result["strategy_horizon"], "mid_term")
        self.assertTrue(result["master_strategy_proxy"])
        self.assertTrue(result["stage2_requirements"])
        self.assertTrue(any(row["side"] == "BUY" for row in result["trades"]))
        self.assertTrue(all(row["decision_data_as_of"] < row["execution_at"] for row in result["trades"]))

    def test_us_replay_reconciles_regulatory_and_fx_costs_per_action(self):
        start = date(2026, 4, 1)
        prices = [100.0 + index * 1.5 for index in range(30)]
        prices += [prices[-1] - (index + 1) * 3.0 for index in range(15)]
        rows = [
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "close": price,
                "adjusted_close": price,
                "volume": 1_000_000,
            }
            for index, price in enumerate(prices)
        ]
        source = {
            "source": "Yahoo chart:TESTUS",
            "provider": "yahoo",
            "rows": rows,
            "listing_evidence": {
                "source": "test listing",
                "listing_date": "2000-01-01",
                "requested_start_date": rows[0]["date"],
                "effective_start_date": rows[0]["date"],
                "prelisting_gap_exempted": False,
                "effective_range_coverage_pct": 100.0,
            },
        }
        fx_rows = [
            {
                "date": row["date"],
                "close": 1400.0,
                "adjusted_close": 1400.0,
                "fx_source": "test USD/KRW",
            }
            for row in rows
        ]
        with (
            patch("app.stock_suite_app._historical_close_rows", return_value=source),
            patch(
                "app.stock_suite_app._replay_usdkrw_rows",
                return_value={"rows": fx_rows, "evidence": {"future_value_used": False}},
            ),
        ):
            result = run_historical_paper_replay(
                ["TESTUS"],
                rows[0]["date"],
                rows[-1]["date"],
                fast=2,
                slow=3,
                min_bars=5,
                persist_detail=False,
                strategy_mode="ma_cross",
            )

        buys = [row for row in result["trades"] if row["side"] == "BUY"]
        sells = [row for row in result["trades"] if row["side"] == "SELL"]
        self.assertTrue(buys)
        self.assertTrue(sells)
        self.assertTrue(result["transaction_cost_audit"]["passed"])
        self.assertGreater(result["total_fx_conversion_cost"], 0.0)
        self.assertGreater(result["total_us_sec_fee"], 0.0)
        self.assertGreater(result["total_us_finra_taf"], 0.0)
        self.assertTrue(all(row["market"] == "US" for row in result["trades"]))
        self.assertTrue(all(row["usdkrw_rate"] == 1400.0 for row in result["trades"]))
        self.assertTrue(all(row["fx_conversion_cost"] > 0.0 for row in result["trades"]))
        self.assertTrue(all(row["us_sec_fee_bps"] == 0.206 for row in sells))
        self.assertEqual(
            result["total_transaction_cost"],
            round(
                result["total_commission"]
                + result["total_slippage_cost"]
                + result["total_sell_tax"]
                + result["total_us_sec_fee"]
                + result["total_us_finra_taf"]
                + result["total_fx_conversion_cost"],
                2,
            ),
        )

    def test_signal_date_uses_symbol_prior_bar_across_market_calendar_gap(self):
        start = date(2026, 1, 1)
        gapped = self._source(start, [100.0] * 7 + [103.0, 103.0])
        gapped["rows"][-1]["date"] = (start + timedelta(days=9)).isoformat()
        calendar = self._source(start, [100.0] * 10)

        def source_for(symbol, *_args, **_kwargs):
            return gapped if symbol == "005930" else calendar

        with patch("app.stock_suite_app._historical_close_rows", side_effect=source_for):
            result = run_historical_paper_replay(
                ["005930", "000660"],
                calendar["rows"][0]["date"],
                calendar["rows"][-1]["date"],
                fast=2,
                slow=3,
                min_bars=5,
                max_positions=1,
                persist_detail=False,
                strategy_mode="breakout",
                stop_loss_pct=40,
                take_profit_pct=1000,
                holding_limit_days=0,
            )

        buys = [row for row in result["trades"] if row["side"] == "BUY"]
        self.assertEqual(1, len(buys))
        self.assertEqual("005930", buys[0]["symbol"])
        self.assertEqual((start + timedelta(days=7)).isoformat(), buys[0]["decision_data_as_of"])
        self.assertEqual((start + timedelta(days=9)).isoformat(), buys[0]["execution_at"])

    def test_missing_symbol_bar_cannot_create_stale_price_exit(self):
        start = date(2026, 1, 1)
        missing_last_day = self._source(start, [100.0] * 7 + [103.0, 103.0])
        calendar = self._source(start, [100.0] * 10)

        def source_for(symbol, *_args, **_kwargs):
            return missing_last_day if symbol == "005930" else calendar

        with patch("app.stock_suite_app._historical_close_rows", side_effect=source_for):
            result = run_historical_paper_replay(
                ["005930", "000660"],
                calendar["rows"][0]["date"],
                calendar["rows"][-1]["date"],
                fast=2,
                slow=3,
                min_bars=5,
                max_positions=1,
                persist_detail=False,
                strategy_mode="breakout",
                stop_loss_pct=40,
                take_profit_pct=1000,
                holding_limit_days=1,
            )

        buys = [row for row in result["trades"] if row["side"] == "BUY"]
        sells = [row for row in result["trades"] if row["side"] == "SELL"]
        self.assertEqual(1, len(buys))
        self.assertEqual((start + timedelta(days=8)).isoformat(), buys[0]["execution_at"])
        self.assertEqual([], sells)


if __name__ == "__main__":
    unittest.main()
