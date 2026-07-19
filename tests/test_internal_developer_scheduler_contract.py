from __future__ import annotations

import shutil
import subprocess
import os
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"


class InternalDeveloperSchedulerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = (TOOLS / "run_internal_developer.ps1").read_text(encoding="utf-8")
        self.hidden = (TOOLS / "run_internal_developer_hidden.vbs").read_text(encoding="utf-8")
        self.installer = (TOOLS / "register_internal_developer.ps1").read_text(encoding="utf-8")

    def test_task_is_hidden_one_minute_and_non_overlapping(self) -> None:
        self.assertIn("CodexStock-InternalDeveloper", self.installer)
        self.assertIn("-RepetitionInterval (New-TimeSpan -Minutes 1)", self.installer)
        self.assertIn("-MultipleInstances IgnoreNew", self.installer)
        self.assertIn("-Hidden", self.installer)
        self.assertIn("-ExecutionTimeLimit (New-TimeSpan -Minutes 5)", self.installer)
        self.assertIn("shell.Run(command, 0, True)", self.hidden)

    def test_install_does_not_start_unless_explicitly_requested(self) -> None:
        self.assertIn("[switch]$StartNow", self.installer)
        self.assertIn("if ($StartNow)", self.installer)
        self.assertNotIn("schtasks.exe /Run", self.installer)
        self.assertIn("-ValidateOnly", self.installer)

    def test_foreign_named_task_is_not_silently_overwritten(self) -> None:
        self.assertIn("[switch]$ReplaceForeignTask", self.installer)
        self.assertIn("already exists with a foreign action", self.installer)
        self.assertIn("Register-ScheduledTask -TaskName $taskName -InputObject $task -Force", self.installer)

    def test_runner_uses_approved_runtime_contract_and_active_data_log(self) -> None:
        self.assertIn("read_runtime_root_contract", self.runner)
        self.assertIn("Test-ApprovedPython", self.runner)
        self.assertIn("Get-ApprovedPythonCandidates", self.runner)
        self.assertIn("CODEXSTOCK_USER_DATA_DIR", self.runner)
        self.assertIn("Join-Path $userDataRoot 'internal_developer'", self.runner)
        self.assertIn("'scheduler.log'", self.runner)
        self.assertIn("'-m' 'app.internal_developer_service' 'once'", self.runner)
        self.assertNotIn("stock_suite_app.py", self.runner)
        self.assertIn("%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", self.hidden)

    def test_scheduler_files_do_not_contain_forbidden_mutation_commands(self) -> None:
        combined = "\n".join((self.runner, self.hidden, self.installer)).lower()
        for forbidden in (
            "submit_order",
            "place_order",
            "api_key =",
            "risk_limit =",
            "git apply",
            "set-executionpolicy unrestricted",
        ):
            self.assertNotIn(forbidden, combined)

    @unittest.skipUnless(shutil.which("powershell.exe"), "PowerShell is required")
    def test_powershell_scripts_parse_without_execution(self) -> None:
        for script_name in ("run_internal_developer.ps1", "register_internal_developer.ps1"):
            script = TOOLS / script_name
            command = (
                "$tokens=$null;$errors=$null;"
                "[System.Management.Automation.Language.Parser]::ParseFile("
                "$env:CODEXSTOCK_TEST_PS_PATH,[ref]$tokens,[ref]$errors)|Out-Null;"
                "if($errors.Count){$errors|ForEach-Object{$_.Message};exit 1}"
            )
            environment = os.environ.copy()
            environment["CODEXSTOCK_TEST_PS_PATH"] = str(script)
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                env=environment,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
