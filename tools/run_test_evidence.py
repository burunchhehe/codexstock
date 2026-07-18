from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.runtime_paths import active_data_root


REPORT_SCHEMA = "codexstock.test-evidence-report.v1"
SOURCE_SUFFIXES = {".py", ".js", ".css", ".html", ".ps1", ".json", ".toml"}
SOURCE_ROOTS = ("app", "tools", "tests")


def _sha256_json(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _source_snapshot() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for root_name in SOURCE_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            try:
                content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
            rows.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": content_sha256,
                }
            )
    return {
        "file_count": len(rows),
        "sha256": _sha256_json(rows),
        "roots": list(SOURCE_ROOTS),
    }


def _git_evidence() -> dict[str, object]:
    def run(*arguments: str) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["git", *arguments],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)
        value = (result.stdout or result.stderr or "").strip()
        return result.returncode == 0, value

    commit_ok, commit_value = run("rev-parse", "HEAD")
    branch_ok, branch_value = run("rev-parse", "--abbrev-ref", "HEAD")
    status_ok, status_value = run("status", "--porcelain")
    return {
        "available": commit_ok,
        "commit_sha": commit_value if commit_ok else None,
        "branch": branch_value if branch_ok else None,
        "dirty": bool(status_value) if status_ok else None,
        "status_entry_count": len(status_value.splitlines()) if status_ok and status_value else 0,
        "error": None if commit_ok else commit_value,
    }


def _test_classification(test_id: str) -> str:
    lowered = test_id.lower()
    if "integration" in lowered:
        return "integration"
    if any(token in lowered for token in ("endpoint", "local_api", "http")):
        return "local_api"
    if any(token in lowered for token in ("external_engine", "research_forge", "kis_mcp")):
        return "engine_contract"
    return "unit"


def _skip_classification(reason: str) -> str:
    lowered = reason.lower()
    if any(token in lowered for token in ("not installed", "dependency", "unavailable")):
        return "dependency_unavailable"
    if any(token in lowered for token in ("network", "credential", "token", "account")):
        return "external_access_unavailable"
    if any(token in lowered for token in ("windows", "linux", "platform")):
        return "platform_not_applicable"
    return "explicit_test_skip"


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.passed_ids: list[str] = []
        self.failed_rows: list[dict[str, str]] = []
        self.error_rows: list[dict[str, str]] = []
        self.skipped_rows: list[dict[str, str]] = []

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self.passed_ids.append(test.id())

    def addFailure(self, test: unittest.case.TestCase, err: tuple[type[BaseException], BaseException, Any]) -> None:
        super().addFailure(test, err)
        self.failed_rows.append({"test_id": test.id(), "traceback": self._exc_info_to_string(err, test)})

    def addError(self, test: unittest.case.TestCase, err: tuple[type[BaseException], BaseException, Any]) -> None:
        super().addError(test, err)
        self.error_rows.append({"test_id": test.id(), "traceback": self._exc_info_to_string(err, test)})

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.skipped_rows.append(
            {
                "test_id": test.id(),
                "reason": reason,
                "skip_classification": _skip_classification(reason),
            }
        )


def _load_suite(names: list[str], discover: bool) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    if discover:
        return loader.discover(str(REPO_ROOT / "tests"), pattern="test_*.py", top_level_dir=str(REPO_ROOT))
    return loader.loadTestsFromNames(names or ["tests"])


def run_test_evidence(
    names: list[str],
    *,
    discover: bool = False,
    run_classification: str = "regression",
    output_path: Path | None = None,
    verbosity: int = 1,
) -> tuple[dict[str, object], int]:
    # Test imports must not compete with the running local app for its singleton lock.
    os.environ.setdefault("CODEXSTOCK_ALLOW_TEST_IMPORT", "1")
    started_at = datetime.now().astimezone()
    started_monotonic = time.monotonic()
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=verbosity, resultclass=EvidenceResult)
    result = runner.run(_load_suite(names, discover))
    finished_at = datetime.now().astimezone()
    elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
    assert isinstance(result, EvidenceResult)

    classified_ids = (
        result.passed_ids
        + [row["test_id"] for row in result.failed_rows]
        + [row["test_id"] for row in result.error_rows]
        + [row["test_id"] for row in result.skipped_rows]
    )
    classification_counts: dict[str, int] = {}
    for test_id in classified_ids:
        key = _test_classification(test_id)
        classification_counts[key] = classification_counts.get(key, 0) + 1

    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "status": "PASSED" if result.wasSuccessful() else "FAILED",
        "run_classification": run_classification,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "requested_tests": names,
        "discover": discover,
        "summary": {
            "run": result.testsRun,
            "passed": len(result.passed_ids),
            "failed": len(result.failed_rows),
            "errors": len(result.error_rows),
            "skipped": len(result.skipped_rows),
            "classification_counts": classification_counts,
        },
        "skipped": result.skipped_rows,
        "failures": result.failed_rows,
        "errors": result.error_rows,
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "timezone": str(started_at.tzinfo),
            "cwd": str(REPO_ROOT),
            "codexstock_user_data_dir_configured": bool(
                str(os.environ.get("CODEXSTOCK_USER_DATA_DIR") or "").strip()
            ),
            "test_import_lock_bypass": True,
        },
        "source": {
            "git": _git_evidence(),
            "snapshot": _source_snapshot(),
        },
        "runner_output": stream.getvalue()[-12000:],
        "safety": {
            "live_order_allowed": False,
            "secrets_recorded": False,
        },
    }
    destination = output_path
    if destination is None:
        output_dir = active_data_root(REPO_ROOT) / "test_evidence"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = finished_at.strftime("%Y%m%dT%H%M%S%z")
        destination = output_dir / f"test-evidence-{timestamp}.json"
    report["report_path"] = str(destination)
    report["report_sha256"] = _sha256_json(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return report, 0 if result.wasSuccessful() else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unittest suites and write reproducible CodexStock evidence.")
    parser.add_argument("tests", nargs="*", help="Fully-qualified unittest names.")
    parser.add_argument("--discover", action="store_true", help="Discover all tests under tests/.")
    parser.add_argument("--classification", default="regression", help="Purpose of this test run.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report JSON path.")
    parser.add_argument("--verbosity", type=int, choices=(0, 1, 2), default=1)
    arguments = parser.parse_args()
    report, exit_code = run_test_evidence(
        arguments.tests,
        discover=arguments.discover,
        run_classification=arguments.classification,
        output_path=arguments.output,
        verbosity=arguments.verbosity,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": report["summary"],
                "report_sha256": report["report_sha256"],
                "report_path": report["report_path"],
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
