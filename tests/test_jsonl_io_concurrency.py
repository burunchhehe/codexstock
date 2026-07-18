import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import stock_suite_app as suite


class JsonlIoConcurrencyTests(unittest.TestCase):
    def test_append_mirrors_before_releasing_file_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            lock = suite._jsonl_io_lock(path)
            mirror_lock_states: list[bool] = []

            def capture_lock_state(*_args, **_kwargs):
                mirror_lock_states.append(bool(lock._is_owned()))
                return True

            with patch.object(
                suite,
                "_mirror_runtime_event_to_sqlite",
                side_effect=capture_lock_state,
            ):
                suite._append_jsonl(path, {"id": 1})

        self.assertEqual([True], mirror_lock_states)

    def test_reader_waits_for_same_file_compaction_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            path.write_text('{"id": 1}\n', encoding="utf-8")
            lock = suite._jsonl_io_lock(path)
            entered = threading.Event()
            finished = threading.Event()
            rows: list[dict[str, object]] = []

            def read_rows() -> None:
                entered.set()
                rows.extend(suite._read_jsonl(path))
                finished.set()

            lock.acquire()
            try:
                worker = threading.Thread(target=read_rows, daemon=True)
                worker.start()
                self.assertTrue(entered.wait(1.0))
                self.assertFalse(finished.wait(0.1))
            finally:
                lock.release()
            worker.join(1.0)

        self.assertTrue(finished.is_set())
        self.assertEqual([{"id": 1}], rows)

    def test_staff_compaction_retries_windows_replace_and_preserves_tail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ai_staff_meetings.jsonl"
            path.write_text(
                "".join(json.dumps({"id": index}) + "\n" for index in range(30)),
                encoding="utf-8",
            )
            real_replace = os.replace
            attempts = 0

            def replace_once_locked(source: object, target: object) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError("simulated Windows reader lock")
                real_replace(source, target)

            with (
                patch.object(suite, "AI_STAFF_MEETING_FILE", path),
                patch.object(suite.os, "replace", side_effect=replace_once_locked),
                patch.object(
                    suite,
                    "_synchronize_runtime_event_index_after_rewrite",
                    return_value=True,
                ) as synchronize_index,
            ):
                suite._compact_staff_meeting_file(max_rows=20)

            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            leftovers = list(path.parent.glob(f".{path.name}.*.tmp"))

        self.assertEqual(2, attempts)
        self.assertEqual(list(range(10, 30)), [row["id"] for row in rows])
        self.assertEqual([], leftovers)
        synchronize_index.assert_called_once()
        self.assertEqual(list(range(10, 30)), [row["id"] for row in synchronize_index.call_args.args[1]])

    def test_tail_helpers_use_reverse_valid_row_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large-events.jsonl"
            path.write_bytes(b'{"id":1}\n{"id":2}\n{"id":')

            with patch.object(
                suite,
                "_iter_jsonl_snapshot_lines",
                side_effect=AssertionError("full scan must not be used for tail reads"),
            ):
                rows = suite._jsonl_tail_rows(path, limit=2)
                latest_line = suite._jsonl_tail_line(path)

        self.assertEqual([1, 2], [row["id"] for row in rows])
        self.assertEqual(2, json.loads(latest_line)["id"])

    def test_missed_buy_compaction_resynchronizes_derived_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missed_buy_reviews.jsonl"
            path.write_text(
                "".join(json.dumps({"id": index}) + "\n" for index in range(60)),
                encoding="utf-8",
            )
            with patch.object(
                suite,
                "_synchronize_runtime_event_index_after_rewrite",
                return_value=True,
            ) as synchronize_index:
                result = suite._compact_missed_buy_review_history(max_rows=50, path=path)

        self.assertTrue(result["compacted"])
        self.assertTrue(result["runtime_event_index_synchronized"])
        synchronize_index.assert_called_once()
        indexed_rows = synchronize_index.call_args.args[1]
        self.assertEqual("jsonl_compaction_summary", indexed_rows[0]["type"])
        self.assertEqual(list(range(10, 60)), [row["id"] for row in indexed_rows[1:]])

    def test_external_or_temporary_jsonl_cannot_pollute_shared_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            external_path = Path(temp_dir) / "events.jsonl"
            external_path.write_text('{"id":1}\n', encoding="utf-8")
            with patch.object(
                suite,
                "_runtime_event_index_connection",
                side_effect=AssertionError("shared index must not be opened"),
            ) as connection, patch.object(suite, "USER_DATA_ROOT", external_path.parent):
                mirrored = suite._mirror_runtime_event_to_sqlite(external_path, {"id": 1})
                synchronized = suite._synchronize_runtime_event_index_after_rewrite(
                    external_path,
                    [{"id": 1}],
                )

        self.assertFalse(mirrored)
        self.assertFalse(synchronized)
        connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
