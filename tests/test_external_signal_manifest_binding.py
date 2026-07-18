import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.stock_suite_app import (
    EXTERNAL_SIGNAL_SCHEMA,
    ExternalSignalFilePoller,
    _external_signal_manifest_binding,
)


class ExternalSignalManifestBindingTests(unittest.TestCase):
    def _report(self):
        return {
            "schema": EXTERNAL_SIGNAL_SCHEMA,
            "generated_at": "2026-07-13T16:34:27+09:00",
            "report_type": "regular",
            "report_slot": "post_close",
            "signals": [{"signal_id": "SIG-1"}],
            "urgent_triggers": [],
        }

    def _manifest(self, path):
        return {
            "report_schema": EXTERNAL_SIGNAL_SCHEMA,
            "latest_report_generated_at": "2026-07-13T16:34:27+09:00",
            "latest_report_type": "regular",
            "latest_report_slot": "post_close",
            "signal_count": 1,
            "urgent_count": 0,
            "latest_json": str(path),
            "codexstock_receiver_contract": {"read_file": str(path)},
        }

    def test_legacy_manifest_is_cross_bound_without_claiming_declared_hash(self):
        path = Path("C:/external-search-mcp/codexstock_outbox/latest_external_signal_report.json")
        result = _external_signal_manifest_binding(
            self._manifest(path),
            self._report(),
            report_path=path,
            source_fingerprint="a" * 64,
        )

        self.assertTrue(result["passed"])
        self.assertFalse(result["hash_declared"])
        self.assertEqual("receiver_computed_legacy_manifest", result["hash_binding_mode"])

    def test_declared_hash_or_count_mismatch_blocks_report(self):
        path = Path("C:/external-search-mcp/codexstock_outbox/latest_external_signal_report.json")
        manifest = self._manifest(path)
        manifest["signal_count"] = 2
        manifest["report_sha256"] = "b" * 64
        result = _external_signal_manifest_binding(
            manifest,
            self._report(),
            report_path=path,
            source_fingerprint="a" * 64,
        )

        self.assertFalse(result["passed"])
        self.assertIn("signal_count_matched", result["blockers"])
        self.assertIn("declared_sha256_matched", result["blockers"])

    def test_poller_restores_fingerprint_without_reviving_running_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "poller.json"
            fingerprint = hashlib.sha256(b"report").hexdigest()
            state_path.write_text(
                json.dumps(
                    {
                        "running": True,
                        "status": "WATCHING",
                        "source_fingerprint": fingerprint,
                        "last_result": "UNCHANGED_SKIPPED",
                    }
                ),
                encoding="utf-8",
            )
            with patch("app.stock_suite_app.EXTERNAL_SIGNAL_POLLER_STATE_FILE", state_path):
                poller = ExternalSignalFilePoller()

        self.assertEqual(fingerprint, poller.last_fingerprint)
        self.assertTrue(poller.restored_from_state)
        self.assertFalse(poller.state["running"])
        self.assertEqual("IDLE", poller.state["status"])


if __name__ == "__main__":
    unittest.main()
