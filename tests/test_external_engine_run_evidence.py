import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.external_engine_runtime import (
    LeanRuntime,
    NautilusRuntime,
    OpenBBRuntime,
    QlibRuntime,
    ResearchBundleRuntime,
    VectorbtRuntime,
    _external_run_evidence_path,
    _external_process_error,
    _load_last_run_evidence,
    _persist_last_run_evidence,
    _run_external_process,
    _terminate_process_tree,
)


class ExternalEngineRunEvidenceTests(unittest.TestCase):
    def test_windows_code_integrity_failure_is_classified(self):
        error, detail = _external_process_error(
            "ImportError: DLL load failed: 애플리케이션 제어 정책에서 이 파일을 차단했습니다.",
            1,
        )

        self.assertEqual("windows_code_integrity_blocked", error)
        self.assertIn("애플리케이션 제어 정책", detail)

    def test_explicit_engine_root_is_independent_of_process_local_app_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            engine_root = root / "owner-runtime" / "engines"
            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(root / "systemprofile" / "AppData" / "Local"),
                    "CODEXSTOCK_USER_DATA_DIR": str(root / "owner-runtime" / "data"),
                },
            ):
                vectorbt = VectorbtRuntime(repo_root, engine_root=engine_root)
                nautilus = NautilusRuntime(repo_root, engine_root=engine_root)
                lean = LeanRuntime(repo_root, engine_root=engine_root)
                openbb = OpenBBRuntime(repo_root, engine_root=engine_root)
                qlib = QlibRuntime(repo_root, engine_root=engine_root)
                bundle = ResearchBundleRuntime(repo_root, engine_root=engine_root)

        runtime_roots = [
            vectorbt.runtime_root,
            nautilus.runtime_root,
            lean.runtime_root,
            openbb.runtime_root,
            qlib.runtime_root,
            bundle.runtime_root,
            bundle.freqtrade_runtime_root,
            bundle.vnpy_runtime_root,
            bundle.finrl_runtime_root,
        ]
        self.assertTrue(all(engine_root.resolve() in path.resolve().parents for path in runtime_roots))
        self.assertTrue(all("systemprofile" not in str(path).lower() for path in runtime_roots))

    def test_successful_round_trip_evidence_survives_runtime_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vectorbt.json"
            expected = {
                "ok": True,
                "finished_at_epoch": 1_720_000_000.0,
                "snapshot_id": "snapshot-1",
                "result_hash": "result-1",
            }

            saved = _persist_last_run_evidence(path, "vectorbt", expected)
            loaded = _load_last_run_evidence(path)
            envelope = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(expected, saved)
        self.assertEqual(expected, loaded)
        self.assertEqual("codexstock_external_engine_run_evidence_v1", envelope["schema"])
        self.assertEqual("vectorbt", envelope["engine_id"])
        self.assertFalse(envelope["live_order_allowed"])

    def test_evidence_is_stored_under_private_user_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"CODEXSTOCK_USER_DATA_DIR": directory}):
                path = _external_run_evidence_path(Path(directory) / "repo", "qlib")

        self.assertEqual(Path(directory) / "external_engine_runs" / "qlib.json", path)

    def test_invalid_or_partial_evidence_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema":"wrong","last_run":{"ok":true}}', encoding="utf-8")
            loaded = _load_last_run_evidence(path)

        self.assertEqual({}, loaded)

    def test_external_process_timeout_terminates_the_whole_tree(self):
        process = MagicMock()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["engine"], 1),
            ("partial stdout", "partial stderr"),
        ]
        process.returncode = -9
        with (
            patch("app.external_engine_runtime.subprocess.Popen", return_value=process),
            patch("app.external_engine_runtime._terminate_process_tree") as terminate,
        ):
            with self.assertRaises(subprocess.TimeoutExpired) as raised:
                _run_external_process(["engine"], capture_output=True, text=True, timeout=1)

        terminate.assert_called_once_with(process)
        self.assertEqual("partial stdout", raised.exception.output)
        self.assertEqual("partial stderr", raised.exception.stderr)

    def test_windows_tree_termination_uses_taskkill(self):
        process = MagicMock()
        process.pid = 12345
        process.poll.side_effect = [None, None]
        with (
            patch("app.external_engine_runtime.os.name", "nt"),
            patch("app.external_engine_runtime.subprocess.run") as taskkill,
        ):
            _terminate_process_tree(process)

        self.assertEqual(["taskkill", "/PID", "12345", "/T", "/F"], taskkill.call_args.args[0])
        process.kill.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
