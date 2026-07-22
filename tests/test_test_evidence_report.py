import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.run_test_evidence import REPORT_SCHEMA, _load_suite, run_test_evidence


class TestEvidenceReportTests(unittest.TestCase):
    def test_discovery_accepts_non_package_tests_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n"
                "class SampleTest(unittest.TestCase):\n"
                "    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            with patch("tools.run_test_evidence.REPO_ROOT", root):
                suite = _load_suite([], discover=True)

        self.assertEqual(suite.countTestCases(), 1)

    def test_report_records_environment_source_and_skip_reason(self) -> None:
        class PassingTest(unittest.TestCase):
            def test_pass(self) -> None:
                self.assertTrue(True)

        class SkippedTest(unittest.TestCase):
            @unittest.skip("dependency not installed")
            def test_skip(self) -> None:
                self.fail("skip contract failed")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch(
                "tools.run_test_evidence._load_suite",
                return_value=unittest.TestSuite(
                    [PassingTest("test_pass"), SkippedTest("test_skip")]
                ),
            ):
                report, exit_code = run_test_evidence(
                    ["synthetic"],
                    run_classification="unit-contract",
                    output_path=path,
                    verbosity=0,
                )
            stored = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual(REPORT_SCHEMA, report["schema"])
        self.assertEqual("PASSED", report["status"])
        self.assertEqual(2, report["summary"]["run"])
        self.assertEqual(1, report["summary"]["skipped"])
        self.assertEqual("dependency_unavailable", report["skipped"][0]["skip_classification"])
        self.assertIn("python_version", report["environment"])
        self.assertIn("git", report["source"])
        self.assertEqual(64, len(report["source"]["snapshot"]["sha256"]))
        self.assertEqual(report["report_sha256"], stored["report_sha256"])
        self.assertFalse(report["safety"]["live_order_allowed"])


if __name__ == "__main__":
    unittest.main()
