import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from stock_suite.sidecar_supervisor import ExecutionSidecarSupervisor


class ExecutionSidecarSupervisorTests(unittest.TestCase):
    def test_alive_process_is_only_monitored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "status.json"
            status.write_text(
                json.dumps({"process_id": 123, "mode": "shadow"}),
                encoding="utf-8",
            )
            starts = []
            supervisor = ExecutionSidecarSupervisor(
                repo_root=root, status_file=status, state_file=root / "supervisor.json",
                process_alive=lambda pid: pid == 123,
                process_factory=lambda *args, **kwargs: starts.append(args),
            )
            result = supervisor.tick()
        self.assertEqual(result["state"], "MONITORING")
        self.assertEqual(result["retry_after_seconds"], 0.0)
        self.assertTrue(result["mode_verified"])
        self.assertTrue(result["mode_matches"])
        self.assertEqual(starts, [])

    def test_alive_process_with_wrong_mode_is_not_reported_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "status.json"
            status.write_text(
                json.dumps({"process_id": 123, "mode": "live"}),
                encoding="utf-8",
            )
            starts = []
            supervisor = ExecutionSidecarSupervisor(
                repo_root=root,
                status_file=status,
                state_file=root / "supervisor.json",
                mode="shadow",
                process_alive=lambda pid: pid == 123,
                process_factory=lambda *args, **kwargs: starts.append(args),
            )
            result = supervisor.tick()
        self.assertEqual("MODE_MISMATCH", result["state"])
        self.assertFalse(result["ok"])
        self.assertTrue(result["restart_required"])
        self.assertEqual("shadow", result["expected_mode"])
        self.assertEqual("live", result["actual_mode"])
        self.assertEqual([], starts)

    def test_missing_process_is_restarted_once_then_cooled_down(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "status.json"
            status.write_text(json.dumps({"process_id": 999}), encoding="utf-8")
            starts = []
            clock = [100.0]

            def factory(*args, **kwargs):
                starts.append((args, kwargs))
                return SimpleNamespace(pid=321, poll=lambda: None)

            supervisor = ExecutionSidecarSupervisor(
                repo_root=root, status_file=status, state_file=root / "supervisor.json",
                process_alive=lambda pid: False, process_factory=factory,
                monotonic=lambda: clock[0], restart_cooldown_seconds=15,
            )
            first = supervisor.tick()
            clock[0] = 101.0
            second = supervisor.tick()
        self.assertEqual(first["state"], "RESTART_LAUNCHED")
        self.assertEqual(first["restart_count"], 1)
        self.assertEqual(second["state"], "RESTART_COOLDOWN")
        self.assertEqual(len(starts), 1)

    def test_child_exit_code_is_persisted_before_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "status.json"
            status.write_text(json.dumps({"process_id": 0}), encoding="utf-8")
            child = SimpleNamespace(pid=321, poll=lambda: 17)
            supervisor = ExecutionSidecarSupervisor(
                repo_root=root, status_file=status, state_file=root / "supervisor.json",
                process_alive=lambda pid: False, process_factory=lambda *args, **kwargs: child,
                monotonic=lambda: 100.0,
            )
            supervisor._child = child
            result = supervisor.tick()
        self.assertEqual(result["last_child_exit_code"], 17)
        self.assertIn("last_child_exit_at", result)

    def test_selected_live_mode_is_preserved_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = root / "status.json"
            status.write_text(json.dumps({"process_id": 0}), encoding="utf-8")
            commands = []
            environments = []

            def factory(command, **kwargs):
                commands.append(command)
                environments.append(kwargs.get("env", {}))
                return SimpleNamespace(pid=77, poll=lambda: None)

            supervisor = ExecutionSidecarSupervisor(
                repo_root=root,
                status_file=status,
                state_file=root / "supervisor.json",
                process_alive=lambda _: False,
                process_factory=factory,
                monotonic=lambda: 100.0,
                mode="live",
            )
            result = supervisor.tick()
        self.assertEqual("live", result["mode"])
        self.assertEqual("live", commands[0][commands[0].index("--mode") + 1])
        self.assertEqual("1", environments[0]["CODEXSTOCK_ENABLE_EXTERNAL_LIVE_EXECUTOR"])


if __name__ == "__main__":
    unittest.main()
