import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import stock_suite_app as suite


class IntradayMarketPulseTests(unittest.TestCase):
    @staticmethod
    def _row(rank: int = 1) -> dict[str, object]:
        return {
            "rank": rank,
            "symbol": "005930",
            "name": "삼성전자",
            "price": 75_000,
            "change_pct": 3.2,
            "amount": 40_000_000_000,
            "volume": 1_500_000,
            "foreign_net_amount": 8_000_000_000,
            "institution_net_amount": 6_000_000_000,
        }

    def _probes(self, row: dict[str, object] | None = None):
        item = row or self._row()
        return {
            name: (lambda current=item: {"ok": True, "items": [dict(current)]})
            for name in ("amount", "volume", "gainers", "losers", "foreign", "institution")
        }

    @patch.object(suite, "_read_jsonl", return_value=[])
    def test_first_pulse_is_baseline_not_false_rapid_alert(self, _read_jsonl):
        result = suite.build_intraday_market_pulse(
            persist=False,
            force=True,
            probe_overrides=self._probes(),
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["comparable_previous_snapshot"])
        self.assertEqual(result["rapid_move_count"], 0)
        self.assertTrue(result["items"][0]["baseline_only"])
        self.assertFalse(result["items"][0]["rapid_move"])
        self.assertFalse(result["items"][0].get("live_order_allowed", False))

    def test_previous_pulse_produces_amount_price_rank_and_flow_alerts(self):
        previous_at = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(seconds=60)
        previous = {
            "generated_at": previous_at.isoformat(timespec="seconds"),
            "items": [
                {
                    "symbol": "005930",
                    "amount": 10_000_000_000,
                    "change_pct": 1.8,
                    "foreign_net_amount": 2_000_000_000,
                    "institution_net_amount": 1_000_000_000,
                    "source_ranks": {
                        "amount": 10,
                        "volume": 8,
                        "gainers": 9,
                        "foreign": 7,
                        "institution": 8,
                    },
                }
            ],
        }
        with patch.object(suite, "_read_jsonl", return_value=[previous]):
            result = suite.build_intraday_market_pulse(
                persist=False,
                force=True,
                probe_overrides=self._probes(),
            )
        item = result["items"][0]
        self.assertTrue(result["comparable_previous_snapshot"])
        self.assertTrue(item["rapid_move"])
        self.assertIn("amount_acceleration", item["rapid_signals"])
        self.assertIn("price_acceleration", item["rapid_signals"])
        self.assertIn("rank_jump", item["rapid_signals"])
        self.assertIn("foreign_flow_acceleration", item["rapid_signals"])
        self.assertIn("institution_flow_acceleration", item["rapid_signals"])
        self.assertGreater(item["amount_velocity_eok_per_min"], 30.0)
        self.assertEqual("strong", item["source_coverage_status"])
        self.assertEqual(6, item["source_coverage_count"])
        self.assertTrue(item["verified_for_live_radar"])
        self.assertIn("source_convergence", item["rapid_signals"])
        self.assertIn("liquidity_price_supply_cluster", item["rapid_signals"])
        self.assertEqual("urgent", item["alert_tier"])
        self.assertEqual(60, item["action_deadline_seconds"])

    def test_new_multi_source_rank_entrant_is_promoted_fast(self):
        previous_at = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(seconds=60)
        previous = {
            "generated_at": previous_at.isoformat(timespec="seconds"),
            "items": [
                {
                    "symbol": "000660",
                    "amount": 1_000_000_000,
                    "change_pct": 0.1,
                    "source_ranks": {"amount": 26},
                    "sources": ["amount"],
                }
            ],
        }
        row = {
            "rank": 7,
            "symbol": "005930",
            "name": "Samsung Electronics",
            "price": 75_000,
            "change_pct": 2.6,
            "amount": 22_000_000_000,
            "volume": 1_200_000,
            "foreign_net_amount": 2_000_000_000,
            "institution_net_amount": 1_500_000_000,
        }

        with patch.object(suite, "_read_jsonl", return_value=[previous]):
            result = suite.build_intraday_market_pulse(
                persist=False,
                force=True,
                probe_overrides=self._probes(row),
            )

        item = result["items"][0]
        self.assertTrue(result["comparable_previous_snapshot"])
        self.assertTrue(item["rapid_move"])
        self.assertIn("new_opportunity_pool_entrant", item["rapid_signals"])
        self.assertIn("liquidity_price_supply_cluster", item["rapid_signals"])
        self.assertEqual("watch_now", item["alert_tier"])
        self.assertEqual(180, item["action_deadline_seconds"])
        self.assertEqual(
            ["amount", "foreign", "gainers", "institution", "losers", "volume"],
            item["newly_confirmed_sources"],
        )

    @patch.object(suite, "_read_jsonl", return_value=[])
    def test_thin_source_coverage_is_not_promoted_to_live_radar(self, _read_jsonl):
        thin_pulse = suite.build_intraday_market_pulse(
            persist=False,
            force=True,
            probe_overrides={
                "amount": lambda: {"ok": True, "items": [self._row()]},
                "volume": lambda: {"ok": False, "items": [], "message": "timeout"},
                "gainers": lambda: {"ok": False, "items": [], "message": "timeout"},
                "losers": lambda: {"ok": False, "items": [], "message": "timeout"},
                "foreign": lambda: {"ok": False, "items": [], "message": "timeout"},
                "institution": lambda: {"ok": False, "items": [], "message": "timeout"},
            },
        )
        item = thin_pulse["items"][0]
        self.assertEqual("thin", item["source_coverage_status"])
        self.assertFalse(item["verified_for_live_radar"])
        self.assertEqual([], suite._marketwide_intraday_candidate_pool(limit=3, pulse=thin_pulse))

    @patch.object(suite, "_read_jsonl", return_value=[])
    def test_two_source_fresh_mover_enters_provisional_detail_lane(self, _read_jsonl):
        row = self._row(rank=5)
        probes = {
            "amount": lambda: {"ok": True, "items": [dict(row)]},
            "volume": lambda: {"ok": True, "items": []},
            "gainers": lambda: {"ok": True, "items": []},
            "losers": lambda: {"ok": True, "items": []},
            "foreign": lambda: {"ok": True, "items": [dict(row)]},
            "institution": lambda: {"ok": True, "items": []},
        }
        pulse = suite.build_intraday_market_pulse(
            persist=False,
            force=True,
            probe_overrides=probes,
        )

        item = pulse["items"][0]
        self.assertEqual(6, pulse["source_success_count"])
        self.assertEqual(2, item["source_coverage_count"])
        self.assertFalse(item["verified_for_live_radar"])
        self.assertTrue(item["provisional_for_detail_radar"])
        self.assertEqual("provisional_detail_validation", item["radar_admission"])
        self.assertFalse(item["score_allowed"])
        self.assertFalse(item["live_order_allowed"])

        candidates = suite._marketwide_intraday_candidate_pool(limit=3, pulse=pulse)
        self.assertEqual(1, len(candidates))
        self.assertEqual("005930", candidates[0]["symbol"])
        self.assertEqual("provisional_detail_validation", candidates[0]["candidate_validation_status"])
        self.assertFalse(candidates[0]["score_allowed"])
        self.assertFalse(candidates[0]["live_order_allowed"])

    @patch.object(suite, "_read_jsonl", return_value=[])
    def test_normal_empty_kis_flow_ranks_count_as_available_but_not_as_signal(self, _read_jsonl):
        price_row = dict(self._row())
        price_row.pop("foreign_net_amount", None)
        price_row.pop("institution_net_amount", None)
        result = suite.build_intraday_market_pulse(
            persist=False,
            force=True,
            probe_overrides={
                "amount": lambda: {"ok": True, "items": [dict(price_row)]},
                "volume": lambda: {"ok": True, "items": [dict(price_row)]},
                "gainers": lambda: {"ok": True, "items": [dict(price_row)]},
                "losers": lambda: {"ok": True, "items": [dict(price_row)]},
                "foreign": lambda: {"ok": False, "items": [], "message": "정상처리 되었습니다."},
                "institution": lambda: {"ok": False, "items": [], "message": "정상처리 되었습니다."},
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(6, result["source_success_count"])
        self.assertEqual(0, result["source_failure_count"])
        empty_sources = {
            row["source"]: row for row in result["source_status"] if row.get("empty_but_confirmed")
        }
        self.assertEqual({"foreign", "institution"}, set(empty_sources))
        item = result["items"][0]
        self.assertNotIn("foreign", item["sources"])
        self.assertNotIn("institution", item["sources"])
        self.assertEqual("usable", item["source_coverage_status"])
        self.assertEqual(0.0, item["foreign_net_amount"])
        self.assertEqual(0.0, item["institution_net_amount"])
        self.assertNotIn("foreign_flow_acceleration", item["rapid_signals"])
        self.assertNotIn("institution_flow_acceleration", item["rapid_signals"])
        self.assertNotIn("liquidity_price_supply_cluster", item["rapid_signals"])

    @patch.object(suite, "_read_jsonl", return_value=[])
    def test_six_broad_probes_use_at_most_three_workers(self, _read_jsonl):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def probe():
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.04)
            with lock:
                active -= 1
            return {"ok": True, "items": [self._row()]}

        result = suite.build_intraday_market_pulse(
            persist=False,
            force=True,
            probe_overrides={name: probe for name in self._probes()},
        )
        self.assertEqual(result["parallel_worker_count"], 3)
        self.assertGreaterEqual(max_active, 2)
        self.assertLessEqual(max_active, 3)

    def test_recent_pulse_is_reused_without_new_broker_calls(self):
        recent = {
            "ok": True,
            "schema": "codexstock_intraday_market_pulse_v1",
            "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "items": [self._row()],
        }

        def should_not_run():
            self.fail("recent pulse should have been served from cache")

        with patch.object(suite, "_read_jsonl", return_value=[recent]):
            result = suite.build_intraday_market_pulse(
                persist=False,
                force=False,
                probe_overrides={"amount": should_not_run},
            )
        self.assertTrue(result["cached"])
        self.assertLessEqual(result["cache_age_seconds"], 45)
        self.assertEqual("fresh", result["freshness_status"])
        self.assertFalse(result["force_refresh_recommended"])
        self.assertGreater(result["next_refresh_in_seconds"], 0)
        self.assertEqual("codexstock_intraday_market_pulse_cache_policy_v1", result["cache_policy"]["schema"])
        self.assertTrue(result["cache_policy"]["cached"])

    def test_singleflight_coalesces_concurrent_force_refresh(self):
        calls = 0
        calls_lock = threading.Lock()
        start = threading.Barrier(3)
        results: list[dict[str, object]] = []

        def fake_build(*_args, **_kwargs):
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.08)
            return {
                "ok": True,
                "schema": "codexstock_intraday_market_pulse_v1",
                "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
                "items": [self._row()],
            }

        def run() -> None:
            start.wait()
            results.append(suite.build_intraday_market_pulse(force=True, persist=False))

        with suite.INTRADAY_MARKET_PULSE_MEMORY_LOCK:
            suite.INTRADAY_MARKET_PULSE_MEMORY.clear()
        workers = [threading.Thread(target=run) for _ in range(2)]
        with patch.object(suite, "_build_intraday_market_pulse_uncached", side_effect=fake_build):
            for worker in workers:
                worker.start()
            start.wait()
            for worker in workers:
                worker.join(timeout=2)
        with suite.INTRADAY_MARKET_PULSE_MEMORY_LOCK:
            suite.INTRADAY_MARKET_PULSE_MEMORY.clear()

        self.assertEqual(1, calls)
        self.assertEqual(2, len(results))
        self.assertEqual(1, sum(1 for row in results if row.get("singleflight_coalesced")))
        self.assertTrue(all(not row.get("live_order_allowed", False) for row in results))

    def test_cache_policy_marks_stale_pulse_for_force_refresh(self):
        stale_at = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(seconds=120)
        policy = suite._intraday_market_pulse_cache_policy(
            stale_at.isoformat(timespec="seconds"),
            cache_ttl_seconds=15,
            now=datetime.now(ZoneInfo("Asia/Seoul")),
            cached=True,
        )
        self.assertEqual("refresh_due", policy["freshness_status"])
        self.assertTrue(policy["force_refresh_recommended"])
        self.assertEqual(0.0, policy["next_refresh_in_seconds"])

    def test_per_symbol_detail_reads_are_bounded_and_parallel(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def payload(kind: str):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.025)
            with lock:
                active -= 1
            if kind == "quote":
                return {"ok": True, "name": "테스트", "price": 10_000, "change_pct": 1.0}
            return {
                "ok": True,
                "name": "테스트",
                "momentum_pct": 0.5,
                "avg_strength": 110,
                "latest_strength": 112,
                "buy_pressure": 10,
                "latest": {"time": "100000"},
                "source": kind,
            }

        with (
            patch.object(suite, "live_quote", side_effect=lambda *_args, **_kwargs: payload("quote")),
            patch.object(suite, "live_minute_history", side_effect=lambda *_args, **_kwargs: payload("minute")),
            patch.object(suite, "live_time_conclusion", side_effect=lambda *_args, **_kwargs: payload("conclusion")),
            patch.object(suite, "_verified_external_signal_candidates", return_value=[]),
        ):
            result = suite.build_intraday_minute_radar(
                symbols=["005930", "000660", "035420", "035720"],
                limit=4,
                persist=False,
            )
        self.assertEqual(result["detail_worker_count"], 3)
        self.assertGreaterEqual(max_active, 2)
        self.assertLessEqual(max_active, 3)
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["detail_failure_count"], 0)

    def test_market_focus_cycle_runs_real_read_only_pulse(self):
        daemon = suite.AiResearchDaemon()
        pulse = {
            "ok": True,
            "schema": "codexstock_intraday_market_pulse_v1",
            "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "scan_duration_ms": 120.0,
            "source_success_count": 6,
            "source_failure_count": 0,
            "rapid_move_count": 1,
            "top": self._row(),
            "alerts": [{**self._row(), "rapid_signals": ["amount_acceleration"]}],
        }
        focus = {"market_open": True, "priorities": [], "deferred_tasks": []}
        with (
            patch.object(suite, "build_intraday_market_pulse", return_value=pulse) as market_pulse,
            patch.object(daemon, "set_activity"),
            patch.object(daemon, "update_staff_activity"),
            patch.object(suite.MEMORY, "append_cycle"),
            patch.object(suite.JOURNAL, "add"),
        ):
            result = daemon._run_market_execution_focus_cycle("daemon", focus)
        market_pulse.assert_called_once_with(limit=30, persist=True, force=True)
        self.assertEqual(result["status"], "MARKET_PULSE_ACTIVE")
        self.assertEqual(result["market_pulse"]["rapid_move_count"], 1)
        self.assertTrue(result["market_pulse"]["read_only"])
        self.assertFalse(result["order_allowed"])


if __name__ == "__main__":
    unittest.main()
