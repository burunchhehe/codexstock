import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.replay_data_backfill_worker import PaperReplayDataBackfillWorker


class ReplayDataBackfillWorkerTests(unittest.TestCase):
    def test_restart_restores_history_but_not_stale_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "running": True,
                        "busy": True,
                        "current_request_id": "HREGAP-OLD",
                        "cycle_count": 3,
                        "next_due_at": "2099-01-01T00:00:00+09:00",
                        "last_result": {"status": "queue_empty"},
                    }
                ),
                encoding="utf-8",
            )
            worker = PaperReplayDataBackfillWorker(
                select_next=lambda: {"ok": True, "status": "queue_empty"},
                process=lambda request_id: {},
                state_path=state_path,
            )

        self.assertEqual(3, worker.cycle_count)
        self.assertEqual("queue_empty", worker.last_result["status"])
        self.assertTrue(worker.restored_from_state)
        self.assertFalse(worker.running)
        self.assertEqual("", worker.current_request_id)
        self.assertEqual("", worker.next_due_at)

    def test_one_bounded_request_is_compacted_and_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            worker = PaperReplayDataBackfillWorker(
                select_next=lambda: {"ok": True, "request_id": "HREGAP-1"},
                process=lambda request_id: {
                    "ok": True,
                    "status": "backfill_and_reconciliation_complete",
                    "request_id": request_id,
                    "source_replay_id": "HREPLAY-1",
                    "validation": {"row_count": 100, "blocker_count": 0},
                    "replay_regeneration": {
                        "status": "verified_replacement_candidate",
                        "new_replay_id": "HREPLAY-2",
                    },
                    "live_order_allowed": False,
                },
                state_path=state_path,
            )
            result = worker.run_once()
            persisted = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(1, worker.cycle_count)
        self.assertEqual(100, result["row_count"])
        self.assertNotIn("validation", result)
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual("HREPLAY-2", persisted["last_result"]["new_replay_id"])

    def test_empty_queue_does_not_call_processor(self):
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayDataBackfillWorker(
                select_next=lambda: {"ok": True, "status": "queue_empty"},
                process=lambda request_id: calls.append(request_id),
                state_path=Path(temp_dir) / "state.json",
            )
            result = worker.run_once()

        self.assertEqual("queue_empty", result["status"])
        self.assertEqual([], calls)

    def test_terminal_empty_queue_auto_stops_background_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayDataBackfillWorker(
                select_next=lambda: {"ok": True, "status": "queue_empty"},
                process=lambda request_id: {},
                state_path=Path(temp_dir) / "state.json",
                initial_delay_seconds=0,
                should_auto_stop=lambda result: result.get("status") == "queue_empty",
            )
            worker.start()
            deadline = time.time() + 2
            while worker.status()["thread_alive"] and time.time() < deadline:
                time.sleep(0.01)
            status = worker.status()

        self.assertFalse(status["running"])
        self.assertFalse(status["thread_alive"])
        self.assertTrue(status["last_result"]["auto_stopped"])
        self.assertEqual("terminal_queue_idle", status["last_result"]["auto_stop_reason"])

    def test_concurrent_cycle_is_rejected(self):
        entered = threading.Event()
        release = threading.Event()

        def process(request_id):
            entered.set()
            release.wait(2)
            return {"ok": True, "status": "complete", "request_id": request_id}

        with tempfile.TemporaryDirectory() as temp_dir:
            worker = PaperReplayDataBackfillWorker(
                select_next=lambda: {"ok": True, "request_id": "HREGAP-1"},
                process=process,
                state_path=Path(temp_dir) / "state.json",
            )
            thread = threading.Thread(target=worker.run_once)
            thread.start()
            self.assertTrue(entered.wait(1))
            duplicate = worker.run_once()
            release.set()
            thread.join(2)

        self.assertEqual("worker_busy", duplicate["status"])
        self.assertFalse(duplicate["live_order_allowed"])


if __name__ == "__main__":
    unittest.main()
