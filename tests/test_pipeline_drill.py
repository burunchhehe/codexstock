import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_suite.pipeline_drill import run_isolated_pipeline_drill


class PipelineDrillTests(unittest.TestCase):
    def test_isolated_drill_proves_handoff_without_real_order(self):
        with tempfile.TemporaryDirectory() as directory:
            proof = run_isolated_pipeline_drill(
                Path(directory),
                now=datetime(2026, 7, 21, 8, 10, tzinfo=timezone(timedelta(hours=9))),
            )
            self.assertTrue(proof["ok"])
            self.assertEqual(proof["result_state"], "SHADOW_ACCEPTED")
            self.assertFalse(proof["real_order_allowed"])
            self.assertTrue(proof["checks"]["real_order_blocked"])
            self.assertTrue((Path(directory) / "pipeline_drill" / "latest.json").exists())


if __name__ == "__main__":
    unittest.main()
