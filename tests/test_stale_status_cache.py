import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.stale_status_cache import StaleWhileRefreshStatusCache


class StaleWhileRefreshStatusCacheTests(unittest.TestCase):
    def test_rejects_durable_payload_when_source_validator_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "test.v1",
                        "saved_at_epoch": time.time(),
                        "payload": {"ok": True, "source_signature": "old"},
                    }
                ),
                encoding="utf-8",
            )
            build_count = 0

            def builder():
                nonlocal build_count
                build_count += 1
                return {"ok": True, "source_signature": "new"}

            cache = StaleWhileRefreshStatusCache(
                builder=builder,
                cache_path=path,
                schema_version="test.v1",
                durable_validator=lambda payload: payload.get("source_signature") == "new",
            )

            result = cache.get()

            self.assertEqual("new", result["source_signature"])
            self.assertEqual(1, build_count)
    def test_stale_payload_returns_immediately_and_refreshes_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "status.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": "test.v1",
                        "saved_at_epoch": time.time() - 60,
                        "payload": {"ok": True, "value": "old"},
                    }
                ),
                encoding="utf-8",
            )
            started = threading.Event()
            release = threading.Event()
            calls = 0

            def builder():
                nonlocal calls
                calls += 1
                started.set()
                release.wait(2)
                return {"ok": True, "value": "new"}

            cache = StaleWhileRefreshStatusCache(
                builder=builder,
                cache_path=cache_path,
                schema_version="test.v1",
                ttl_seconds=1,
            )
            before = time.perf_counter()
            first = cache.get()
            elapsed = time.perf_counter() - before
            second = cache.get()

            self.assertLess(elapsed, 0.25)
            self.assertEqual("old", first["value"])
            self.assertTrue(first["stale"])
            self.assertTrue(first["refreshing"])
            self.assertEqual("old", second["value"])
            self.assertEqual(1, calls)
            self.assertTrue(started.wait(1))

            release.set()
            deadline = time.time() + 2
            current = second
            while time.time() < deadline:
                current = cache.get()
                if current.get("value") == "new":
                    break
                time.sleep(0.02)
            self.assertEqual("new", current["value"])

    def test_bootstrap_payload_makes_the_first_request_non_blocking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "status.json"
            started = threading.Event()
            release = threading.Event()
            calls = 0

            def builder():
                nonlocal calls
                calls += 1
                started.set()
                release.wait(2)
                return {"ok": True, "status": "ready", "value": "fresh"}

            cache = StaleWhileRefreshStatusCache(
                builder=builder,
                cache_path=cache_path,
                schema_version="test.v1",
                ttl_seconds=30,
                bootstrap_payload={
                    "ok": False,
                    "status": "refreshing",
                    "value": "bootstrap",
                },
            )
            try:
                before = time.perf_counter()
                first = cache.get()
                elapsed = time.perf_counter() - before
                second = cache.get()

                self.assertLess(elapsed, 0.25)
                self.assertEqual("refreshing", first["status"])
                self.assertEqual("bootstrap", first["value"])
                self.assertTrue(first["status_cache_bootstrap"])
                self.assertTrue(first["stale"])
                self.assertTrue(first["refreshing"])
                self.assertEqual("bootstrap", second["value"])
                self.assertEqual(1, calls)
                self.assertTrue(started.wait(1))

                release.set()
                deadline = time.time() + 2
                current = second
                while time.time() < deadline:
                    current = cache.get()
                    if current.get("value") == "fresh":
                        break
                    time.sleep(0.02)
                self.assertEqual("fresh", current["value"])
                self.assertNotIn("status_cache_bootstrap", current)
            finally:
                release.set()

    def test_first_request_persists_for_restart_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "status.json"
            first = StaleWhileRefreshStatusCache(
                builder=lambda: {"ok": True, "value": 7},
                cache_path=cache_path,
                schema_version="test.v1",
            )
            self.assertEqual(7, first.get()["value"])
            second = StaleWhileRefreshStatusCache(
                builder=lambda: (_ for _ in ()).throw(RuntimeError("must not block")),
                cache_path=cache_path,
                schema_version="test.v1",
            )
            self.assertEqual(7, second.get()["value"])


if __name__ == "__main__":
    unittest.main()
