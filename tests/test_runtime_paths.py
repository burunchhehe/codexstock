from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.runtime_paths import (
    RUNTIME_ROOT_CONTRACT_FILENAME,
    RUNTIME_ROOT_CONTRACT_SCHEMA,
    USER_DATA_ENV_KEY,
    USE_REPO_DATA_ENV_KEY,
    active_data_root,
    ensure_runtime_root_contract,
    read_runtime_root_contract,
    runtime_root_resolution,
)


class RuntimeRootContractTests(unittest.TestCase):
    def _paths(self, directory: str) -> tuple[Path, Path]:
        base = Path(directory)
        repo = base / "repo"
        repo.mkdir()
        user_data = base / "owner" / "AppData" / "Local" / "CodexStock" / "data"
        return repo, user_data

    def test_verified_contract_survives_a_different_execution_account(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, user_data = self._paths(directory)
            written = ensure_runtime_root_contract(
                repo,
                user_data,
                python_executable=Path(sys.executable),
            )
            system_local = Path(directory) / "systemprofile" / "AppData" / "Local"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(system_local)}, clear=True):
                resolved = active_data_root(repo)
                resolution = runtime_root_resolution(repo)

        self.assertTrue(written["valid"])
        self.assertEqual(user_data, resolved)
        self.assertEqual("verified_runtime_root_contract", resolution["source"])
        self.assertTrue(resolution["execution_account_independent"])

    def test_explicit_environment_overrides_a_valid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, user_data = self._paths(directory)
            ensure_runtime_root_contract(repo, user_data)
            explicit = Path(directory) / "explicit" / "CodexStock" / "data"
            with patch.dict(
                os.environ,
                {USER_DATA_ENV_KEY: str(explicit)},
                clear=True,
            ):
                resolved = active_data_root(repo)
                resolution = runtime_root_resolution(repo)

        self.assertEqual(explicit, resolved)
        self.assertEqual("explicit_environment", resolution["source"])

    def test_tampered_contract_is_rejected_instead_of_redirecting_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, user_data = self._paths(directory)
            ensure_runtime_root_contract(repo, user_data)
            path = repo / "runtime" / RUNTIME_ROOT_CONTRACT_FILENAME
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["user_data_root"] = str(Path(directory) / "attacker" / "CodexStock" / "data")
            path.write_text(json.dumps(payload), encoding="utf-8")
            system_local = Path(directory) / "systemprofile" / "AppData" / "Local"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(system_local)}, clear=True):
                contract = read_runtime_root_contract(repo)
                resolved = active_data_root(repo)

        self.assertFalse(contract["valid"])
        self.assertEqual("contract_hash_mismatch", contract["error"])
        self.assertEqual(system_local / "CodexStock" / "data", resolved)

    def test_explicit_repo_opt_in_remains_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, user_data = self._paths(directory)
            ensure_runtime_root_contract(repo, user_data)
            with patch.dict(
                os.environ,
                {USE_REPO_DATA_ENV_KEY: "1"},
                clear=True,
            ):
                resolved = active_data_root(repo)

        self.assertEqual(repo / "data", resolved)

    def test_contract_contains_no_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo, user_data = self._paths(directory)
            ensure_runtime_root_contract(repo, user_data)
            contract = read_runtime_root_contract(repo)

        self.assertTrue(contract["valid"])
        self.assertEqual(RUNTIME_ROOT_CONTRACT_SCHEMA, contract["schema"])
        self.assertFalse(contract["contains_secrets"])
        serialized = json.dumps(contract).lower()
        self.assertNotIn("app_secret", serialized)
        self.assertNotIn("access_token", serialized)


if __name__ == "__main__":
    unittest.main()
