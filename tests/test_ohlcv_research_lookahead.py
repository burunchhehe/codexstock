import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import hundred_billion_strategy_lab as strategy_lab
from app import stock_suite_app as stock_app
from app import walk_forward_ohlcv_research as walk_forward
from app.backtest_trade_evidence import (
    TradeEvidenceStore,
    build_run_fingerprint,
    load_reusable_verified_summary,
    reconcile_trade_actions,
)


def _market_data(final_day_volume: int) -> dict[str, dict[str, object]]:
    rows = []
    for index in range(10):
        price = 100.0 + index
        rows.append(
            {
                "date": f"2026-01-{index + 1:02d}",
                "open": price,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": final_day_volume if index == 9 else 10_000,
            }
        )
    return {
        "AAA": {
            "name": "AAA",
            "rows": rows,
            "by_date": {str(row["date"]): row for row in rows},
        }
    }


def _walk_config(name: str) -> dict[str, object]:
    return {
        "name": name,
        "min_history": 5,
        "rebalance_days": 9,
        "max_positions": 1,
        "position_pct": 100.0,
        "stop_pct": 50.0,
        "take_pct": 0.0,
        "trail_pct": 50.0,
        "hold_days": 10,
        "entry_mode": "next_open",
        "fast": 2,
        "slow": 3,
        "min_p20": -999.0,
        "min_p60": -999.0,
        "min_high_dist": -999.0,
        "min_vol_ratio": 0.0,
        "liquidity_pct": 1.0,
        "trade_cost_pct": 0.18,
        "max_gap_up_pct": 99.0,
    }


def _lab_config(name: str) -> dict[str, object]:
    return {
        **_walk_config(name),
        "family": "momentum_blend",
        "min_score": -999.0,
    }


class OhlcvResearchLookaheadTests(unittest.TestCase):
    def test_walk_forward_liquidity_never_uses_execution_day_volume(self) -> None:
        low_volume = walk_forward._run_ohlcv_strategy(_market_data(1), _walk_config("walk-low"))
        huge_volume = walk_forward._run_ohlcv_strategy(_market_data(1_000_000_000), _walk_config("walk-high"))

        self.assertEqual(100, low_volume["open_positions"][0]["quantity"])
        self.assertEqual(
            low_volume["open_positions"][0]["quantity"],
            huge_volume["open_positions"][0]["quantity"],
        )
        self.assertFalse(low_volume["execution_timing_model"]["current_day_volume_allowed"])
        self.assertTrue(low_volume["trade_evidence_audit"]["calculation_passed"])
        self.assertFalse(low_volume["trade_evidence_audit"]["official_return_claim_allowed"])

    def test_strategy_lab_liquidity_never_uses_execution_day_volume(self) -> None:
        low_volume = strategy_lab._run_strategy(_market_data(1), _lab_config("lab-low"))
        huge_volume = strategy_lab._run_strategy(_market_data(1_000_000_000), _lab_config("lab-high"))

        self.assertEqual(100, low_volume["open_positions"][0]["quantity"])
        self.assertEqual(
            low_volume["open_positions"][0]["quantity"],
            huge_volume["open_positions"][0]["quantity"],
        )
        self.assertFalse(low_volume["execution_timing_model"]["current_day_volume_allowed"])
        self.assertTrue(low_volume["trade_evidence_audit"]["calculation_passed"])

    def test_sqlite_trade_ledger_is_persisted_and_read_back_before_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "evidence.sqlite3"
            with TradeEvidenceStore(database, engine="walk-test", run_id="run-1") as store:
                result = walk_forward._run_ohlcv_strategy(
                    _market_data(1_000_000_000),
                    _walk_config("walk-persisted"),
                    store,
                )

            audit = result["trade_evidence_audit"]
            self.assertTrue(audit["calculation_passed"])
            self.assertTrue(audit["durable_ledger_verified"])
            self.assertTrue(audit["official_return_claim_allowed"])
            self.assertEqual("verified", result["performance_evidence_status"])
            with closing(sqlite3.connect(database)) as connection:
                row = connection.execute(
                    "SELECT action_count, ledger_sha256, length(compressed_actions) "
                    "FROM strategy_trade_ledgers WHERE strategy_name = ?",
                    ("walk-persisted",),
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(result["trade_count"], row[0])
            self.assertEqual(audit["ledger_sha256"], row[1])
            self.assertGreater(row[2], 0)

    def test_reconciliation_rejects_future_decision_bad_return_and_unsafe_volume(self) -> None:
        actions = [
            {
                "side": "BUY",
                "symbol": "AAA",
                "decision_data_as_of": "2026-01-02",
                "execution_at": "2026-01-02",
                "quantity": 10,
                "gross_price": 100.0,
                "price": 100.0,
                "cost_pct": 0.0,
                "liquidity_volume_basis": "execution_day_volume",
            },
            {
                "side": "SELL",
                "symbol": "AAA",
                "decision_data_as_of": "2026-01-02",
                "execution_at": "2026-01-03",
                "entry_date": "2026-01-02",
                "entry_price": 100.0,
                "quantity": 10,
                "gross_price": 110.0,
                "price": 110.0,
                "cost_pct": 0.0,
                "return_pct": 99.0,
                "exit_reason": "test",
            },
        ]
        audit = reconcile_trade_actions(
            actions,
            initial_cash=10_000.0,
            final_equity=10_100.0,
            open_positions=[],
            required_timing_model_version="past-only-ohlcv-execution.v2",
        )

        codes = {str(row["code"]) for row in audit["issues"]}
        self.assertFalse(audit["calculation_passed"])
        self.assertIn("non_past_decision", codes)
        self.assertIn("unsafe_liquidity_basis", codes)
        self.assertIn("return_mismatch", codes)

    def test_app_blocks_legacy_walk_forward_result_without_full_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_file = root / "walk.json"
            result_file.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "name": "legacy",
                                "multiple": 9.0,
                                "final_equity": 90_000_000,
                                "max_drawdown_pct": -10.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stock_app, "OHLCV_WALK_FORWARD_RESULT_FILE", result_file),
                patch.object(stock_app, "OBSIDIAN_VAULT", root),
            ):
                result = stock_app.latest_ohlcv_walk_forward_challenge()

        self.assertFalse(result["ok"])
        self.assertEqual("VERIFICATION_BLOCKED", result["status"])
        self.assertFalse(result["official_return_claim_allowed"])

    def test_app_accepts_only_readback_verified_strategy_lab_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result_file = root / "lab.json"
            evidence_audit = {
                "calculation_passed": True,
                "durable_ledger_verified": True,
                "official_return_claim_allowed": True,
            }
            result_file.write_text(
                json.dumps(
                    {
                        "status": "DONE",
                        "trade_evidence": {"all_results_verified": True},
                        "results": [
                            {
                                "name": "verified",
                                "family": "momentum_blend",
                                "multiple": 2.0,
                                "final_equity": 20_000_000,
                                "max_drawdown_pct": -8.0,
                                "trade_evidence_audit": evidence_audit,
                                "trade_ledger": {"persisted_and_readback_verified": True},
                                "performance_evidence_status": "verified",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stock_app, "HUNDRED_BILLION_LAB_RESULT_FILE", result_file),
                patch.object(stock_app, "OBSIDIAN_VAULT", root),
            ):
                result = stock_app._compact_hundred_billion_lab_result()

        self.assertTrue(result["ok"])
        self.assertEqual("READY", result["status"])
        self.assertTrue(result["official_return_claim_allowed"])

    def test_identical_verified_run_is_reused_but_changed_input_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.py"
            data_file = root / "data.json"
            result_file = root / "result.json"
            database = root / "evidence.sqlite3"
            source.write_text("print('v1')\n", encoding="utf-8")
            data_file.write_text("{}", encoding="utf-8")
            fingerprint = build_run_fingerprint(
                engine="cache-test",
                source_paths=[source],
                data_paths=[data_file],
                configs=[{"name": "strategy"}],
                options={"end": "2026-07-14"},
            )
            actions = [
                {
                    "side": "BUY",
                    "symbol": "AAA",
                    "decision_data_as_of": "2026-01-01",
                    "execution_at": "2026-01-02",
                    "quantity": 10,
                    "gross_price": 100.0,
                    "price": 100.0,
                    "cost_pct": 0.0,
                    "liquidity_volume_basis": "prior_completed_20d_average_volume",
                }
            ]
            audit = reconcile_trade_actions(
                actions,
                initial_cash=10_000.0,
                final_equity=10_000.0,
                open_positions=[{"symbol": "AAA", "quantity": 10, "avg_price": 100.0, "last_price": 100.0}],
                required_timing_model_version="past-only-ohlcv-execution.v2",
            )
            with TradeEvidenceStore(database, engine="cache-test", run_id="run-1") as store:
                audit, _ = store.persist(
                    strategy_name="strategy",
                    config={"name": "strategy"},
                    actions=actions,
                    timing_model={"version": "past-only-ohlcv-execution.v2"},
                    audit=audit,
                )
            self.assertTrue(audit["official_return_claim_allowed"])
            result_file.write_text(
                json.dumps(
                    {
                        "status": "DONE",
                        "run_fingerprint": fingerprint,
                        "trade_evidence": {
                            "run_id": "run-1",
                            "result_count": 1,
                            "all_results_verified": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            cached = load_reusable_verified_summary(
                result_file,
                expected_fingerprint=fingerprint,
                ledger_path=database,
                engine="cache-test",
            )
            changed = load_reusable_verified_summary(
                result_file,
                expected_fingerprint="changed",
                ledger_path=database,
                engine="cache-test",
            )

        self.assertIsNotNone(cached)
        self.assertIsNone(changed)

    def test_staff_meeting_cannot_reuse_legacy_ok_flag_without_official_evidence(self) -> None:
        blocked = stock_app._gate_official_ohlcv_challenge(
            {"ok": True, "status": "READY", "best": {"multiple": 99.0}}
        )
        verified = stock_app._gate_official_ohlcv_challenge(
            {"ok": True, "status": "READY", "official_return_claim_allowed": True}
        )

        self.assertFalse(blocked["ok"])
        self.assertEqual("VERIFICATION_BLOCKED", blocked["status"])
        self.assertIn("official_return_evidence_not_verified", blocked["verification_blockers"])
        self.assertTrue(verified["ok"])
        self.assertEqual("READY", verified["status"])


if __name__ == "__main__":
    unittest.main()
