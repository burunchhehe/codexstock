from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest


_TEST_RUNTIME_ROOT: Path | None = None


def _is_true(name: str) -> bool:
    return str(os.environ.get(name, "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


if not _is_true("CODEXSTOCK_TEST_USE_REAL_RUNTIME"):
    _TEST_RUNTIME_ROOT = Path(tempfile.mkdtemp(prefix="codexstock-pytest-"))
    test_data_root = _TEST_RUNTIME_ROOT / "CodexStock" / "data"
    test_data_root.mkdir(parents=True, exist_ok=True)
    os.environ["CODEXSTOCK_USER_DATA_DIR"] = str(test_data_root)
    os.environ["CODEXSTOCK_RUNTIME_ROOT_CONTRACT"] = str(
        _TEST_RUNTIME_ROOT / "runtime-root-contract.json"
    )
    os.environ["CODEXSTOCK_TEST_MODE"] = "1"

    @atexit.register
    def _remove_test_runtime() -> None:
        if _TEST_RUNTIME_ROOT is not None:
            shutil.rmtree(_TEST_RUNTIME_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_runtime_path_contract_tests(request, monkeypatch):
    if request.path.name == "test_runtime_paths.py":
        monkeypatch.delenv("CODEXSTOCK_USER_DATA_DIR", raising=False)
        monkeypatch.delenv("CODEXSTOCK_RUNTIME_ROOT_CONTRACT", raising=False)
