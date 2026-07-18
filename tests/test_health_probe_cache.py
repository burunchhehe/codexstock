import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.health_probe_cache import load_probe_cache, save_probe_cache
from app.runtime_storage_audit import recheck_slow_jsonl_tail_benchmarks


class HealthProbeCacheTests(unittest.TestCase):
    def test_durable_cache_restores_only_matching_fresh_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "probe.json"
            memory = {"saved_at": 0.0, "scope": "", "payload": {}}
            save_probe_cache(
                memory,
                path,
                {"ok": True, "status": "ready"},
                schema_version="probe.v1",
                scope="root-a",
            )
            restored = load_probe_cache(
                {"saved_at": 0.0, "scope": "", "payload": {}},
                path,
                schema_version="probe.v1",
                scope="root-a",
                ttl_seconds=60,
            )
            wrong_scope = load_probe_cache(
                {"saved_at": 0.0, "scope": "", "payload": {}},
                path,
                schema_version="probe.v1",
                scope="root-b",
                ttl_seconds=60,
            )

        self.assertTrue(restored["cached"])
        self.assertEqual("disk", restored["cache_source"])
        self.assertIsNone(wrong_scope)

    def test_expired_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "probe.json"
            memory = {"saved_at": 0.0, "scope": "", "payload": {}}
            save_probe_cache(
                memory,
                path,
                {"ok": True},
                schema_version="probe.v1",
                scope="root-a",
            )
            memory["saved_at"] = time.time() - 120
            record = json.loads(path.read_text(encoding="utf-8"))
            record["saved_at_epoch"] = time.time() - 120
            path.write_text(json.dumps(record), encoding="utf-8")
            cached = load_probe_cache(
                memory,
                path,
                schema_version="probe.v1",
                scope="root-a",
                ttl_seconds=60,
            )

        self.assertIsNone(cached)

    def test_slow_jsonl_tail_is_retried_before_becoming_a_health_blocker(self):
        payload = {
            "jsonl_tail_benchmarks": [
                {"path": "events.jsonl", "elapsed_ms": 900.0, "status": "ok"}
            ],
            "max_jsonl_tail_ms": 900.0,
            "jsonl_tail_slow": True,
        }
        with patch(
            "app.runtime_storage_audit._tail_jsonl_benchmark",
            return_value={"path": "events.jsonl", "elapsed_ms": 2.5, "status": "ok"},
        ):
            result = recheck_slow_jsonl_tail_benchmarks(payload)

        self.assertFalse(result["jsonl_tail_slow"])
        self.assertEqual(2.5, result["max_jsonl_tail_ms"])
        self.assertEqual(900.0, result["jsonl_tail_benchmarks"][0]["initial_elapsed_ms"])
        self.assertTrue(result["jsonl_tail_benchmarks"][0]["retry_performed"])


if __name__ == "__main__":
    unittest.main()
