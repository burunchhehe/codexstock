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


if __name__ == "__main__":
    unittest.main()
