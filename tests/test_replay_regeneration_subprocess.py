import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.replay_regeneration_subprocess import replay_child_creationflags, run_replay_subprocess


class ReplayRegenerationSubprocessTests(unittest.TestCase):
    def test_safe_paper_result_is_returned_and_temp_file_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_run(command, **kwargs):
                del kwargs
                output = Path(command[command.index("--output") + 1])
                output.write_text(
                    json.dumps(
                        {
                            "ok": True,
                            "status": "verified_replacement_candidate",
                            "paper_only": True,
                            "live_order_allowed": False,
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("app.replay_regeneration_subprocess.subprocess.run", side_effect=fake_run):
                result = run_replay_subprocess(
                    "HREPLAY-1",
                    python_executable="python",
                    repo_root=root,
                    result_dir=root / "results",
                )

            leftovers = list((root / "results").glob("*.json"))

        self.assertTrue(result["ok"])
        self.assertEqual("subprocess", result["execution_isolation"])
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual([], leftovers)

    def test_child_process_uses_hidden_below_normal_priority_on_windows(self):
        flags = replay_child_creationflags()

        self.assertEqual(
            int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            flags & int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        )
        self.assertEqual(
            int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)),
            flags & int(getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)),
        )

    def test_force_is_forwarded_only_when_requested(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_run(command, **kwargs):
                del kwargs
                commands.append(command)
                output = Path(command[command.index("--output") + 1])
                output.write_text(
                    json.dumps({"ok": True, "paper_only": True, "live_order_allowed": False}),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("app.replay_regeneration_subprocess.subprocess.run", side_effect=fake_run):
                run_replay_subprocess(
                    "HREPLAY-3",
                    python_executable="python",
                    repo_root=root,
                    result_dir=root / "results",
                    force=True,
                )
                run_replay_subprocess(
                    "HREPLAY-4",
                    python_executable="python",
                    repo_root=root,
                    result_dir=root / "results",
                )

        self.assertIn("--force", commands[0])
        self.assertNotIn("--force", commands[1])

    def test_unsafe_child_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_run(command, **kwargs):
                del kwargs
                output = Path(command[command.index("--output") + 1])
                output.write_text(
                    json.dumps({"ok": True, "paper_only": False, "live_order_allowed": True}),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("app.replay_regeneration_subprocess.subprocess.run", side_effect=fake_run):
                result = run_replay_subprocess(
                    "HREPLAY-2",
                    python_executable="python",
                    repo_root=root,
                    result_dir=root / "results",
                )

        self.assertEqual("unsafe_regeneration_subprocess_result", result["status"])
        self.assertFalse(result["live_order_allowed"])

    def test_zero_exit_without_result_file_is_reported_explicitly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch(
                "app.replay_regeneration_subprocess.subprocess.run",
                return_value=subprocess.CompletedProcess(["python"], 0, "", ""),
            ):
                result = run_replay_subprocess(
                    "HREPLAY-5",
                    python_executable="python",
                    repo_root=root,
                    result_dir=root / "results",
                )

        self.assertEqual("regeneration_subprocess_result_missing", result["status"])
        self.assertIn("without writing", result["error"])
        self.assertFalse(result["live_order_allowed"])

    def test_invalid_id_never_starts_a_process(self):
        with patch("app.replay_regeneration_subprocess.subprocess.run") as runner:
            result = run_replay_subprocess(
                "bad-id",
                python_executable="python",
                repo_root=Path("."),
                result_dir=Path("results"),
            )

        self.assertEqual("invalid_replay_id", result["status"])
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
