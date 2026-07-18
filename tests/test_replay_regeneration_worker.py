import json
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.replay_recovery import build_replay_data_gap_manifest
from app.replay_regeneration_worker import PaperReplayRegenerationWorker


class PaperReplayRegenerationWorkerTests(unittest.TestCase):
    def test_default_interval_keeps_bounded_continuous_paper_throughput(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: {},
                state_path=Path(temp_dir) / "worker.json",
            )

        self.assertEqual(15, worker.interval_seconds)
        self.assertFalse(worker.status()["live_order_allowed"])
        self.assertFalse(worker.status()["automatic_promotion"])

    def test_adaptive_cooldown_accelerates_success_and_backs_off_failures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: {},
                state_path=Path(temp_dir) / "worker.json",
                interval_seconds=15,
            )

        self.assertEqual(
            (15, "success_cooldown"),
            worker._cooldown_for_result({"ok": True, "status": "verified_replacement_candidate"}),
        )
        self.assertEqual(
            (15, "success_cooldown"),
            worker._cooldown_for_result({"ok": False, "status": "quarantined_new_result"}),
        )
        self.assertEqual(
            (2, "market_closed_day_full_batch"),
            worker._cooldown_for_result(
                {
                    "ok": True,
                    "status": "verified_replacement_candidate",
                    "selection": {
                        "schedule_mode": "market_closed_day_full_batch",
                        "paper_only": True,
                        "live_order_allowed": False,
                    },
                }
            ),
        )
        self.assertEqual(
            (0, "manual_paper_focus_batch"),
            worker._cooldown_for_result(
                {
                    "ok": True,
                    "status": "verified_replacement_candidate",
                    "selection": {
                        "schedule_mode": "manual_paper_focus_batch",
                        "paper_only": True,
                        "live_order_allowed": False,
                    },
                }
            ),
        )
        self.assertEqual(
            (15, "success_cooldown"),
            worker._cooldown_for_result(
                {
                    "ok": True,
                    "status": "verified_replacement_candidate",
                    "selection": {
                        "schedule_mode": "market_closed_day_full_batch",
                        "paper_only": True,
                        "live_order_allowed": True,
                    },
                }
            ),
        )
        self.assertEqual(
            (60, "failure_backoff"),
            worker._cooldown_for_result({"ok": False, "status": "regeneration_failed"}),
        )
        self.assertEqual(
            (300, "queue_idle"),
            worker._cooldown_for_result({"ok": True, "status": "queue_complete"}),
        )
        self.assertEqual(
            (300, "schedule_wait"),
            worker._cooldown_for_result({"ok": True, "status": "scheduled_for_market_closed_day"}),
        )
        self.assertEqual(
            (900, "selection_schedule"),
            worker._cooldown_for_result(
                {
                    "ok": True,
                    "status": "weekday_after_hours_cooldown",
                    "selection": {"retry_after_seconds": 900},
                }
            ),
        )
        self.assertEqual(2, worker.status()["closed_day_success_cooldown_seconds"])

    def test_restart_restores_history_but_not_stale_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "worker.json"
            state_path.write_text(
                json.dumps(
                    {
                        "running": True,
                        "busy": True,
                        "current_replay_id": "HREPLAY-OLD",
                        "cycle_count": 7,
                        "next_due_at": "2099-01-01T00:00:00+09:00",
                        "last_wait_seconds": 900,
                        "last_wait_reason": "selection_schedule",
                        "last_result": {
                            "status": "weekday_after_hours_cooldown",
                            "selection": {
                                "schedule_mode": "weekday_after_hours_bounded",
                                "retry_after_seconds": 900,
                                "cadence_seconds": 900,
                                "next_eligible_at": "2026-07-14T21:45:00+09:00",
                                "max_source_trade_count": 25,
                            },
                        },
                        "last_job_error": "",
                    }
                ),
                encoding="utf-8",
            )
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: {},
                state_path=state_path,
            )

        self.assertEqual(7, worker.cycle_count)
        self.assertEqual("weekday_after_hours_cooldown", worker.last_result["status"])
        self.assertEqual(900, worker.last_wait_seconds)
        self.assertEqual("selection_schedule", worker.last_wait_reason)
        self.assertEqual(
            "weekday_after_hours_bounded",
            worker.last_result["selection"]["schedule_mode"],
        )
        self.assertTrue(worker.restored_from_state)
        self.assertFalse(worker.running)
        self.assertEqual("", worker.current_replay_id)
        self.assertEqual("", worker.next_due_at)

    def test_run_once_persists_paper_only_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "worker.json"
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "ready", "replay_id": "HREPLAY-1"},
                regenerate=lambda replay_id: {
                    "ok": True,
                    "status": "verified_replacement_candidate",
                    "source_replay_id": replay_id,
                    "live_order_allowed": False,
                },
                state_path=state_path,
            )
            with (
                patch("app.replay_regeneration_worker.time.perf_counter", side_effect=[100.0, 101.0]),
                patch.object(worker, "_now", return_value="2026-07-14T21:40:00+09:00"),
            ):
                result = worker.run_once()
            persisted = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual("HREPLAY-1", result["replay_id"])
        self.assertEqual(1, worker.cycle_count)
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["automatic_promotion"])
        self.assertEqual("verified_replacement_candidate", persisted["last_result"]["status"])
        self.assertEqual("2026-07-14T21:40:00+09:00", persisted["last_check_at"])
        self.assertEqual("2026-07-14T21:40:00+09:00", persisted["last_success_at"])
        self.assertEqual(1, len(persisted["recent_success_elapsed_seconds"]))
        self.assertNotIn("selection", persisted["last_result"])
        self.assertNotIn("regeneration", persisted["last_result"])
        self.assertIn("regeneration", result)

    def test_public_status_uses_bounded_result_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: {},
                state_path=Path(temp_dir) / "worker.json",
            )
            worker.last_result = {
                "ok": True,
                "status": "verified_replacement_candidate",
                "replay_id": "HREPLAY-1",
                "regeneration": {"closed_trade_sample": [{"symbol": "005930"}] * 500},
                "paper_only": True,
                "live_order_allowed": False,
            }

            full = worker.status()
            public = worker.public_status()

        self.assertIn("regeneration", full["last_result"])
        self.assertNotIn("regeneration", public["last_result"])
        self.assertEqual("summary", public["response_detail"])
        self.assertFalse(public["live_order_allowed"])

    def test_public_status_preserves_only_safe_schedule_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: {},
                state_path=Path(temp_dir) / "worker.json",
            )
            worker.last_result = {
                "ok": True,
                "status": "weekday_after_hours_cooldown",
                "selection": {
                    "schedule_mode": "weekday_after_hours_bounded",
                    "retry_after_seconds": 900,
                    "cadence_seconds": 900,
                    "next_eligible_at": "2026-07-14T21:45:00+09:00",
                    "max_source_trade_count": 25,
                    "load_policy": {
                        "cadence_seconds": 900,
                        "serial_worker": True,
                        "paper_only": True,
                        "live_order_allowed": False,
                        "private_runtime_detail": "must-not-leak",
                    },
                    "replay_id": "HREPLAY-SECRET-DETAIL",
                },
            }

            public = worker.public_status()

        selection = public["last_result"]["selection"]
        self.assertEqual("weekday_after_hours_bounded", selection["schedule_mode"])
        self.assertEqual(900, selection["retry_after_seconds"])
        self.assertEqual(900, selection["cadence_seconds"])
        self.assertEqual("2026-07-14T21:45:00+09:00", selection["next_eligible_at"])
        self.assertTrue(selection["load_policy"]["serial_worker"])
        self.assertFalse(selection["load_policy"]["live_order_allowed"])
        self.assertNotIn("private_runtime_detail", selection["load_policy"])
        self.assertNotIn("replay_id", selection)

    def test_restart_restores_only_bounded_valid_success_durations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "worker.json"
            state_path.write_text(
                json.dumps(
                    {
                        "recent_success_elapsed_seconds": [0, "bad", *range(1, 25), 90_000],
                        "last_result": {"status": "verified_replacement_candidate", "elapsed_seconds": 99},
                    }
                ),
                encoding="utf-8",
            )
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: {},
                state_path=state_path,
            )

        self.assertEqual(20, len(worker.recent_success_elapsed_seconds))
        self.assertEqual(5.0, worker.recent_success_elapsed_seconds[0])
        self.assertEqual(24.0, worker.recent_success_elapsed_seconds[-1])


class ReplayDataGapManifestTests(unittest.TestCase):
    def test_only_latest_nonretryable_failure_becomes_blocked_stage2_request(self):
        ledger = [
            {
                "id": "HREGEN-OLD",
                "source_replay_id": "HREPLAY-1",
                "status": "regeneration_failed",
                "retryable": True,
            },
            {
                "id": "HREGEN-NEW",
                "source_replay_id": "HREPLAY-1",
                "status": "regeneration_failed",
                "retryable": False,
                "failure_kind": "input_or_market_data_unavailable",
                "error": "missing bars",
            },
            {
                "id": "HREGEN-OK",
                "source_replay_id": "HREPLAY-2",
                "status": "verified_replacement_candidate",
            },
        ]
        contract = {
            "ok": True,
            "run_arguments": {
                "symbols": ["005930", "NVDA", "005930"],
                "start_date": "2024-01-01",
                "end_date": "2024-06-30",
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gaps.json"
            result = build_replay_data_gap_manifest(
                ledger,
                contract_loader=lambda replay_id: contract,
                output_path=path,
                now=lambda: datetime(2026, 7, 13, 17, 0, 0),
            )
            persisted = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(1, result["request_count"])
        request = result["requests"][0]
        self.assertEqual(["005930", "NVDA"], request["contract"]["symbols"])
        self.assertEqual("HREGEN-NEW", request["source_failure_ledger_id"])
        self.assertFalse(request["score_allowed"])
        self.assertFalse(request["promotion_allowed"])
        self.assertFalse(request["live_order_allowed"])
        self.assertEqual(request["request_hash"], persisted["requests"][0]["request_hash"])

    def test_price_contract_quarantine_becomes_stage2_request(self):
        ledger = [
            {
                "id": "HREGEN-PRICE",
                "source_replay_id": "HREPLAY-1",
                "status": "quarantined_new_result",
                "official_return_block_reasons": [
                    "price_currency_unit_audit_not_passed",
                    "price_contract_blocker_present",
                ],
            }
        ]
        contract = {
            "ok": True,
            "run_arguments": {
                "symbols": ["000660"],
                "start_date": "2000-01-01",
                "end_date": "2002-12-31",
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_replay_data_gap_manifest(
                ledger,
                contract_loader=lambda replay_id: contract,
                output_path=Path(temp_dir) / "gaps.json",
                now=lambda: datetime(2026, 7, 14, 1, 0, 0),
            )

        self.assertEqual(1, result["request_count"])
        request = result["requests"][0]
        self.assertEqual("price_currency_unit_contract_unavailable", request["failure_kind"])
        self.assertEqual(["000660"], request["contract"]["symbols"])
        self.assertFalse(request["live_order_allowed"])

    def test_concurrent_run_is_rejected_without_duplicate_regeneration(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def regenerate(replay_id):
            calls.append(replay_id)
            entered.set()
            release.wait(2)
            return {"ok": True, "status": "verified_replacement_candidate"}

        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "ready", "replay_id": "HREPLAY-2"},
                regenerate=regenerate,
                state_path=Path(temp_dir) / "worker.json",
            )
            thread = threading.Thread(target=worker.run_once)
            thread.start()
            self.assertTrue(entered.wait(1))
            duplicate = worker.run_once()
            release.set()
            thread.join(2)

        self.assertEqual("worker_busy", duplicate["status"])
        self.assertEqual(["HREPLAY-2"], calls)
        self.assertFalse(duplicate["live_order_allowed"])

    def test_empty_queue_never_calls_regeneration(self):
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: calls.append(replay_id),
                state_path=Path(temp_dir) / "worker.json",
            )
            result = worker.run_once()

        self.assertEqual("queue_complete", result["status"])
        self.assertEqual([], calls)
        self.assertFalse(result["live_order_allowed"])

    def test_background_worker_auto_stops_after_completed_queue(self):
        selections = []
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayRegenerationWorker(
                select_next=lambda: selections.append("checked")
                or {"ok": True, "status": "queue_complete"},
                regenerate=lambda replay_id: self.fail(
                    f"completed queue must not regenerate {replay_id}"
                ),
                state_path=Path(temp_dir) / "worker.json",
                initial_delay_seconds=0,
            )
            worker.start(initial_delay_seconds=0)
            worker.thread.join(2)
            status = worker.status()

        self.assertEqual(["checked"], selections)
        self.assertFalse(status["running"])
        self.assertFalse(status["thread_alive"])
        self.assertEqual("queue_complete_auto_stopped", status["last_wait_reason"])
        self.assertEqual(0, status["last_wait_seconds"])
        self.assertEqual("queue_complete", status["last_result"]["status"])


if __name__ == "__main__":
    unittest.main()
