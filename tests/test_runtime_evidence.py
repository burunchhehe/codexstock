import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_suite.runtime_evidence import RuntimeEvidenceLedger, audit_runtime_evidence


class RuntimeEvidenceTests(unittest.TestCase):
    def test_continuous_heartbeats_prove_only_observed_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            ledger = RuntimeEvidenceLedger(path, session_id="A")
            start = datetime.now(timezone.utc) - timedelta(minutes=2)
            ledger.heartbeat("shadow", 1, True, start)
            ledger.heartbeat("shadow", 2, True, start + timedelta(seconds=60))
            ledger.heartbeat("shadow", 3, True, start + timedelta(seconds=120))
            audit = audit_runtime_evidence(path, max_gap_seconds=90)
        self.assertTrue(audit["ok"])
        self.assertAlmostEqual(audit["continuous_hours"], 2 / 60, places=5)
        self.assertEqual(audit["heartbeat_count"], 3)
        self.assertEqual(audit["total_heartbeat_count"], 3)
        self.assertAlmostEqual(
            (datetime.fromisoformat(audit["continuous_started_at"]) - start).total_seconds(),
            0.0,
            places=2,
        )

    def test_gap_breaks_continuous_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            ledger = RuntimeEvidenceLedger(path, session_id="A")
            start = datetime.now(timezone.utc) - timedelta(minutes=5)
            ledger.heartbeat("shadow", 1, True, start)
            ledger.heartbeat("shadow", 2, True, start + timedelta(minutes=5))
            audit = audit_runtime_evidence(path, max_gap_seconds=90)
        self.assertEqual(audit["continuous_hours"], 0.0)
        self.assertGreater(audit["max_observed_gap_seconds"], 90)

    def test_failed_heartbeat_invalidates_current_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            ledger = RuntimeEvidenceLedger(path, session_id="A")
            now = datetime.now(timezone.utc)
            ledger.heartbeat("shadow", 1, False, now)
            audit = audit_runtime_evidence(path)
        self.assertFalse(audit["ok"])
        self.assertEqual(audit["reason"], "failed_heartbeat")

    def test_success_after_failure_starts_new_continuous_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            ledger = RuntimeEvidenceLedger(path, session_id="A")
            start = datetime.now(timezone.utc) - timedelta(minutes=2)
            ledger.heartbeat("shadow", 1, False, start)
            ledger.heartbeat("shadow", 2, True, start + timedelta(seconds=60))
            ledger.heartbeat("shadow", 3, True, start + timedelta(seconds=120))
            audit = audit_runtime_evidence(path)
        self.assertTrue(audit["ok"])
        self.assertAlmostEqual(audit["continuous_hours"], 1 / 60, places=5)

    def test_new_process_session_resets_continuous_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            start = datetime.now(timezone.utc) - timedelta(minutes=2)
            first = RuntimeEvidenceLedger(path, session_id="A")
            first.heartbeat("shadow", 1, True, start)
            first.heartbeat("shadow", 2, True, start + timedelta(seconds=60))
            second = RuntimeEvidenceLedger(path, session_id="B")
            second.heartbeat("shadow", 1, True, start + timedelta(seconds=61))
            audit = audit_runtime_evidence(path)
        self.assertEqual(audit["current_session_id"], "B")
        self.assertEqual(audit["continuous_hours"], 0.0)
        self.assertEqual(audit["heartbeat_count"], 1)
        self.assertEqual(audit["total_heartbeat_count"], 3)

    def test_heartbeat_count_excludes_prior_session_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            start = datetime.now(timezone.utc) - timedelta(minutes=3)
            first = RuntimeEvidenceLedger(path, session_id="OLD")
            first.heartbeat("shadow", 1, True, start)
            first.heartbeat("shadow", 2, True, start + timedelta(seconds=60))
            current = RuntimeEvidenceLedger(path, session_id="CURRENT")
            current.heartbeat("shadow", 1, True, start + timedelta(seconds=120))
            current.heartbeat("shadow", 2, True, start + timedelta(seconds=180))
            audit = audit_runtime_evidence(path)
        self.assertEqual(audit["heartbeat_count"], 2)
        self.assertEqual(audit["total_heartbeat_count"], 4)

    def test_future_heartbeat_cannot_create_runtime_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            future = datetime.now(timezone.utc) + timedelta(hours=24)
            RuntimeEvidenceLedger(path, session_id="FUTURE").heartbeat("shadow", 1, True, future)
            audit = audit_runtime_evidence(path)
        self.assertFalse(audit["ok"])
        self.assertEqual(audit["reason"], "heartbeat_from_future")
        self.assertEqual(audit["continuous_hours"], 0.0)

    def test_audit_reports_current_runtime_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.sqlite3"
            RuntimeEvidenceLedger(path, session_id="PAPER").heartbeat(
                "paper", 1, True, datetime.now(timezone.utc)
            )
            audit = audit_runtime_evidence(path)
        self.assertEqual(audit["current_mode"], "paper")


if __name__ == "__main__":
    unittest.main()
