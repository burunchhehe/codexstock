import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ops_core import HepiOpsCore


class OpsReportScheduleTests(unittest.TestCase):
    def test_pre_market_report_starts_at_0740(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.ops_core.configured_user_data_root", return_value=None):
                ops = HepiOpsCore(Path(temp_dir))
            window = ops.telegram_policy()["scheduled_report_windows"]["pre_market"]

        self.assertTrue(window["enabled"])
        self.assertEqual("07:40", window["time"])
        self.assertEqual(45, window["grace_minutes"])

    def test_single_delivery_incident_is_deduped_even_when_text_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.ops_core.configured_user_data_root", return_value=None):
                ops = HepiOpsCore(Path(temp_dir))
            metadata = {
                "incident_id": "INC-DRILL-1",
                "single_delivery": True,
                "single_delivery_id": "INC-DRILL-1",
            }

            first = ops.queue_telegram(
                "incident needs external advice",
                message_type="internal_developer_urgent",
                source="internal-developer-service",
                metadata=metadata,
            )
            second = ops.queue_telegram(
                "incident state changed but must not be sent twice",
                message_type="internal_developer_urgent",
                source="internal-developer-service",
                metadata=metadata,
            )

            self.assertEqual("queued", first["status"])
            self.assertEqual("deduped", second["status"])
            self.assertEqual(first["id"], second["policy"]["matched_id"])
            self.assertEqual(1, len(ops.telegram_outbox()))


if __name__ == "__main__":
    unittest.main()
