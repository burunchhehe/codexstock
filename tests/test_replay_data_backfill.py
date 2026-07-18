import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.replay_data_backfill import (
    ReplayDataBackfillService,
    audit_replay_data_backfill_storage,
    load_verified_replay_data_backfill,
    persist_replay_data_backfill,
    upsert_replay_data_backfill_index,
    validate_replay_data_backfill,
)


class ReplayDataBackfillTests(unittest.TestCase):
    def _request(self):
        return {
            "request_id": "HREGAP-test",
            "request_hash": "request-hash",
            "contract": {
                "replay_id": "HREPLAY-1",
                "symbols": ["005930"],
                "start_date": "2024-05-13",
                "end_date": "2024-05-20",
                "timeframe": "1d",
                "required_fields": ["date", "open", "high", "low", "close", "volume"],
            },
        }

    def _result(self):
        rows = [
            {
                "symbol": "005930",
                "date": "2024-05-13",
                "open": 78000.0,
                "high": 79000.0,
                "low": 77500.0,
                "close": 78500.0,
                "volume": 1000.0,
                "currency": "KRW",
                "price_unit": "won_integer",
            }
        ]
        dataset_hash = hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "ok": True,
            "schema": "codexstock_openbb_historical_backfill_result_v1",
            "action": "fetch_historical_ohlcv",
            "request_id": "HREGAP-test",
            "request_hash": "request-hash",
            "decision": "VERIFY_ONLY",
            "adjustment_applied": "splits_and_dividends",
            "dataset_hash": dataset_hash,
            "dataset_rows": rows,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    def test_valid_backfill_is_accepted_for_paper_only(self):
        validation = validate_replay_data_backfill(self._request(), self._result())

        self.assertTrue(validation["ok"])
        self.assertEqual("accepted_for_paper_replay", validation["status"])
        self.assertEqual(0, validation["blocker_count"])
        self.assertFalse(validation["live_order_allowed"])

    def test_float_rounding_noise_does_not_break_ohlc_relationship(self):
        result = self._result()
        row = result["dataset_rows"][0]
        row["close"] = row["low"]
        row["low"] = row["close"] + 1e-12
        result["dataset_hash"] = hashlib.sha256(
            json.dumps(
                result["dataset_rows"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        validation = validate_replay_data_backfill(self._request(), result)

        self.assertTrue(validation["ok"])
        self.assertNotIn("invalid_ohlc_relationship", validation["blockers"])

    def test_material_ohlc_relationship_error_is_blocked(self):
        result = self._result()
        row = result["dataset_rows"][0]
        row["high"] = row["close"] - 100.0
        result["dataset_hash"] = hashlib.sha256(
            json.dumps(
                result["dataset_rows"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        validation = validate_replay_data_backfill(self._request(), result)

        self.assertFalse(validation["ok"])
        self.assertIn("invalid_ohlc_relationship", validation["blockers"])

    def test_long_range_backfill_requires_each_symbol_to_cover_the_range(self):
        request = self._request()
        request["contract"]["start_date"] = "2000-01-01"
        request["contract"]["end_date"] = "2002-12-31"
        result = self._result()
        result["dataset_hash"] = hashlib.sha256(
            json.dumps(
                result["dataset_rows"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        validation = validate_replay_data_backfill(request, result)

        self.assertFalse(validation["ok"])
        self.assertIn("symbol_date_range_coverage_insufficient", validation["blockers"])
        self.assertEqual(["005930"], validation["insufficient_coverage_symbols"])
        self.assertGreater(validation["minimum_long_range_rows_per_symbol"], 500)

    def test_tampered_hash_and_open_live_gate_are_blocked(self):
        result = self._result()
        result["dataset_hash"] = "tampered"
        result["live_order_allowed"] = True

        validation = validate_replay_data_backfill(self._request(), result)

        self.assertFalse(validation["ok"])
        self.assertIn("dataset_hash_mismatch", validation["blockers"])
        self.assertIn("live_order_gate_open", validation["blockers"])

    def test_persisted_artifact_keeps_safety_gates_closed(self):
        request = self._request()
        result = self._result()
        validation = validate_replay_data_backfill(request, result)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = persist_replay_data_backfill(
                request,
                result,
                validation,
                output_dir=Path(temp_dir),
            )
            persisted = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(persisted["score_allowed"])
        self.assertFalse(persisted["promotion_allowed"])
        self.assertFalse(persisted["live_order_allowed"])
        self.assertTrue(persisted["validation"]["ok"])

    def test_verified_artifact_can_be_loaded_for_exact_paper_range(self):
        request = self._request()
        result = self._result()
        validation = validate_replay_data_backfill(request, result)
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            persist_replay_data_backfill(request, result, validation, output_dir=directory)
            loaded = load_verified_replay_data_backfill(
                "005930",
                "2024-05-13",
                "2024-05-20",
                result_dir=directory,
            )

        self.assertIsNotNone(loaded)
        self.assertEqual("verified_stage2_data_backfill", loaded["source"])
        self.assertEqual(result["dataset_hash"], loaded["dataset_hash"])
        self.assertEqual(result["dataset_rows"][0]["close"], loaded["rows"][0]["adjusted_close"])
        self.assertFalse(loaded["live_order_allowed"])

    def test_unverified_artifact_is_never_loaded(self):
        request = self._request()
        result = self._result()
        validation = validate_replay_data_backfill(request, result)
        validation["ok"] = False
        validation["status"] = "blocked"
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            persist_replay_data_backfill(request, result, validation, output_dir=directory)
            loaded = load_verified_replay_data_backfill(
                "005930",
                "2024-05-13",
                "2024-05-20",
                result_dir=directory,
            )

        self.assertIsNone(loaded)

    def test_sqlite_index_resolves_verified_artifact_without_directory_scan(self):
        request = self._request()
        result = self._result()
        validation = validate_replay_data_backfill(request, result)
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "artifacts"
            index_path = Path(temp_dir) / "index.sqlite3"
            artifact_path = persist_replay_data_backfill(
                request,
                result,
                validation,
                output_dir=directory,
            )
            indexed = upsert_replay_data_backfill_index(
                request,
                result,
                validation,
                artifact_path=artifact_path,
                index_path=index_path,
            )
            loaded = load_verified_replay_data_backfill(
                "005930",
                "2024-05-13",
                "2024-05-20",
                result_dir=directory,
                index_path=index_path,
            )

        self.assertTrue(indexed["ok"])
        self.assertEqual(1, indexed["artifact_count"])
        self.assertEqual(1, indexed["symbol_count"])
        self.assertIsNotNone(loaded)
        self.assertEqual(result["dataset_hash"], loaded["dataset_hash"])

    def test_service_reuses_verified_artifact_without_second_engine_call(self):
        request = self._request()
        result = self._result()
        engine_calls = []
        replay_calls = []
        ledger_rows = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ReplayDataBackfillService(
                queue_loader=lambda: {"requests": [request]},
                engine_run=lambda contract, **kwargs: engine_calls.append(kwargs) or dict(result),
                replay_regenerate=lambda replay_id, **kwargs: replay_calls.append(replay_id) or {
                    "ok": True,
                    "status": "verified_replacement_candidate",
                    "new_replay_id": "HREPLAY-2",
                },
                queue_refresh=lambda: {"status": "empty"},
                append_ledger=lambda path, row: ledger_rows.append(row),
                result_dir=root / "artifacts",
                index_path=root / "index.sqlite3",
                ledger_path=root / "ledger.jsonl",
            )
            first = service.run("HREGAP-test")
            second = service.run("HREGAP-test")

        self.assertTrue(first["ok"])
        self.assertFalse(first["artifact_reused"])
        self.assertTrue(second["artifact_reused"])
        self.assertEqual(1, len(engine_calls))
        self.assertEqual(["HREPLAY-1", "HREPLAY-1"], replay_calls)
        self.assertEqual(2, len(ledger_rows))
        self.assertTrue(all(row["live_order_allowed"] is False for row in ledger_rows))

    def test_service_waits_while_replay_worker_is_busy(self):
        service = ReplayDataBackfillService(
            queue_loader=lambda: {"requests": [self._request()]},
            engine_run=lambda contract, **kwargs: self._result(),
            replay_regenerate=lambda replay_id, **kwargs: {"ok": True},
            queue_refresh=lambda: {},
            append_ledger=lambda path, row: None,
            result_dir=Path("artifacts"),
            index_path=Path("index.sqlite3"),
            ledger_path=Path("ledger.jsonl"),
        )

        selected = service.next_candidate(replay_busy=True)

        self.assertEqual("waiting_for_replay_worker", selected["status"])
        self.assertFalse(selected["live_order_allowed"])

    def test_next_candidate_skips_recently_attempted_request(self):
        first = self._request()
        second = {
            **self._request(),
            "request_id": "HREGAP-second",
            "request_hash": "second-hash",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger_path = root / "results.jsonl"
            ledger_path.write_text(
                json.dumps(
                    {
                        "request_id": first["request_id"],
                        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
                        "status": "blocked",
                    }
                ) + "\n",
                encoding="utf-8",
            )
            service = ReplayDataBackfillService(
                queue_loader=lambda: {"requests": [first, second]},
                engine_run=lambda *args, **kwargs: {},
                replay_regenerate=lambda *args, **kwargs: {},
                queue_refresh=lambda: {},
                append_ledger=lambda *args, **kwargs: None,
                result_dir=root / "artifacts",
                index_path=root / "index.sqlite3",
                ledger_path=ledger_path,
            )

            selected = service.next_candidate(replay_busy=False)

        self.assertEqual("ready", selected["status"])
        self.assertEqual("HREGAP-second", selected["request_id"])
        self.assertEqual(1, selected["deferred_request_count"])

    def test_storage_audit_proves_index_integrity_without_deleting(self):
        request = self._request()
        result = self._result()
        validation = validate_replay_data_backfill(request, result)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            directory = root / "artifacts"
            index_path = root / "index.sqlite3"
            artifact_path = persist_replay_data_backfill(request, result, validation, output_dir=directory)
            upsert_replay_data_backfill_index(
                request,
                result,
                validation,
                artifact_path=artifact_path,
                index_path=index_path,
            )
            audit = audit_replay_data_backfill_storage(result_dir=directory, index_path=index_path)

        self.assertTrue(audit["ok"])
        self.assertEqual("ok", audit["sqlite_integrity"])
        self.assertEqual(1, audit["artifact_count"])
        self.assertEqual(0, audit["unindexed_artifact_count"])
        self.assertFalse(audit["cleanup_applied"])
        self.assertTrue(audit["dry_run_only"])


if __name__ == "__main__":
    unittest.main()
