import unittest

from app.stock_suite_app import _external_signal_snapshot_validation_result


class ExternalSignalSnapshotValidationTests(unittest.TestCase):
    def test_matching_common_snapshot_remains_pending_stage2_and_never_promotes(self):
        report_signature = "a" * 64
        dataset_hash = "b" * 64
        request = {
            "dedupe_key": "report:signal",
            "signal_id": "SIG-1",
            "symbol": "005930",
            "report_signature": report_signature,
            "stage2_snapshot_id": "snapshot-1",
            "stage2_dataset_hash": dataset_hash,
            "live_order_allowed": False,
        }
        snapshot = {
            "ready": True,
            "report_signature": report_signature,
            "snapshot_id": "snapshot-1",
            "dataset_hash": dataset_hash,
            "symbols": ["005930"],
            "dataset_integrity": {
                "ok": True,
                "fatal_issue_count": 0,
                "row_count": 120,
                "currencies": {"KRW": 120},
                "markets": {"KR": 120},
            },
        }

        result = _external_signal_snapshot_validation_result(
            request,
            report_signature=report_signature,
            stage2_snapshot=snapshot,
            verified_at="2026-07-13T18:00:00+09:00",
        )

        self.assertEqual("SNAPSHOT_VERIFIED_PENDING_STAGE2_RESULT", result["status"])
        self.assertTrue(result["snapshot_validation"]["passed"])
        self.assertEqual("SNAPSHOT_ONLY", result["validation_grade"])
        self.assertFalse(result["stage2_result_gate_passed"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["promotion_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_symbol_or_hash_mismatch_is_blocked(self):
        request = {
            "dedupe_key": "report:signal",
            "signal_id": "SIG-1",
            "symbol": "005930",
            "report_signature": "a" * 64,
            "stage2_snapshot_id": "snapshot-1",
            "stage2_dataset_hash": "c" * 64,
            "live_order_allowed": False,
        }
        snapshot = {
            "ready": True,
            "report_signature": "a" * 64,
            "snapshot_id": "snapshot-1",
            "dataset_hash": "b" * 64,
            "symbols": ["000660"],
            "dataset_integrity": {"ok": True, "fatal_issue_count": 0},
        }

        result = _external_signal_snapshot_validation_result(
            request,
            report_signature="a" * 64,
            stage2_snapshot=snapshot,
        )

        self.assertEqual("SNAPSHOT_BLOCKED", result["status"])
        self.assertIn("dataset_hash_matched", result["snapshot_validation"]["blockers"])
        self.assertIn("symbol_in_snapshot", result["snapshot_validation"]["blockers"])
        self.assertFalse(result["promotion_allowed"])
        self.assertFalse(result["live_order_allowed"])


if __name__ == "__main__":
    unittest.main()
