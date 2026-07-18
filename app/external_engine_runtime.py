from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

try:
    from runtime_paths import active_data_root
except ModuleNotFoundError:  # Package import path used by tests and tooling.
    from .runtime_paths import active_data_root


VECTORBT_COMMIT = "bf7aff6d081fda1e9cd7dc0464d68f98309875a1"
VECTORBT_SHORT_COMMIT = VECTORBT_COMMIT[:12]
NAUTILUS_RELEASE_COMMIT = "8160730c7c550480b0a439fb11086a4c4de15f0b"
NAUTILUS_RUNTIME_FOLDER = "ba64d945b929"
LEAN_COMMIT = "046fb456f8282c1749e42fcf7f8fa45fa4595d74"
DOTNET_SDK_VERSION = "10.0.301"
OPENBB_COMMIT = "1c74893140292944e71ff5cdd9536edf12f05483"
QLIB_COMMIT = "d5379c520f66a39953bad76234a7019a72796fd0"
BACKTRADER_COMMIT = "b853d7c90b6721476eb5a5ea3135224e33db1f14"
FREQTRADE_COMMIT = "6275efeef6118a7c143af4913d71c7ff3d9a77ef"
VNPY_COMMIT = "1b78494979deb4c4996f6b864f234d9839f2f239"
FINRL_COMMIT = "2334a5fe6d30629157f13c3b0319e1637e15e123"


def _parse_external_json(stdout: str) -> dict[str, Any]:
    candidates = [stdout]
    candidates.extend(reversed([line.strip() for line in stdout.splitlines() if line.strip().startswith("{")]))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


def _run_external_process(
    args: list[str],
    *,
    cwd: str | None = None,
    input: str | None = None,
    capture_output: bool = False,
    text: bool = False,
    encoding: str | None = None,
    errors: str | None = None,
    timeout: float | None = None,
    creationflags: int = 0,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    popen_options: dict[str, Any] = {
        "cwd": cwd,
        "stdin": subprocess.PIPE if input is not None else None,
        "stdout": subprocess.PIPE if capture_output else None,
        "stderr": subprocess.PIPE if capture_output else None,
    }
    if text:
        popen_options.update(
            {
                "text": True,
                "encoding": encoding or "utf-8",
                "errors": errors or "replace",
            }
        )
    if env is not None:
        popen_options["env"] = env
    if os.name == "nt":
        popen_options["creationflags"] = (
            int(creationflags)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        popen_options["start_new_session"] = True

    process = subprocess.Popen(args, **popen_options)
    try:
        stdout, stderr = process.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout = exc.output
            stderr = exc.stderr
        raise subprocess.TimeoutExpired(
            args,
            timeout,
            output=stdout,
            stderr=stderr,
        ) from exc

    completed = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    if check and completed.returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            args,
            output=stdout,
            stderr=stderr,
        )
    return completed


def _external_run_evidence_path(repo_root: Path, engine_id: str) -> Path:
    return active_data_root(repo_root) / "external_engine_runs" / f"{engine_id}.json"


def _load_last_run_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema") != "codexstock_external_engine_run_evidence_v1":
        return {}
    last_run = payload.get("last_run")
    return dict(last_run) if isinstance(last_run, dict) else {}


def _persist_last_run_evidence(path: Path, engine_id: str, last_run: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(last_run)
    payload = {
        "schema": "codexstock_external_engine_run_evidence_v1",
        "engine_id": engine_id,
        "saved_at_epoch": time.time(),
        "last_run": evidence,
        "live_order_allowed": False,
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, allow_nan=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return evidence


class VectorbtRuntime:
    def __init__(self, repo_root: Path, *, engine_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        local_app_data = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        engines = Path(engine_root) if engine_root is not None else local_app_data / "CodexStock" / "engines"
        self.runtime_root = engines / "vectorbt" / VECTORBT_SHORT_COMMIT
        self.python_path = self.runtime_root / ".venv" / "Scripts" / "python.exe"
        self.worker_path = self.repo_root / "tools" / "external_engines" / "vectorbt_worker.py"
        self._lock = threading.Lock()
        self._engine_id = "vectorbt"
        self.evidence_path = _external_run_evidence_path(self.repo_root, self._engine_id)
        self._last_run: dict[str, Any] = _load_last_run_evidence(self.evidence_path)

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        installed = self.python_path.is_file()
        worker_ready = self.worker_path.is_file()
        result: dict[str, Any] = {
            "ok": installed and worker_ready,
            "engine_name": "vectorbt",
            "installed": installed,
            "worker_ready": worker_ready,
            "connected": installed and worker_ready,
            "runtime_mode": "spawn_on_demand_only",
            "runtime_root": str(self.runtime_root),
            "python_path": str(self.python_path),
            "worker_path": str(self.worker_path),
            "engine_commit": VECTORBT_COMMIT,
            "busy": self._lock.locked(),
            "last_run": dict(self._last_run),
            "live_order_allowed": False,
        }
        if probe and result["ok"]:
            try:
                completed = _run_external_process(
                    [str(self.python_path), "-c", "import vectorbt; print(vectorbt.__version__)"],
                    cwd=str(self.runtime_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=45,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                result["probe_ok"] = completed.returncode == 0
                result["engine_version"] = completed.stdout.strip()[:80]
                if completed.returncode != 0:
                    result["probe_error"] = completed.stderr.strip()[:300]
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["probe_ok"] = False
                result["probe_error"] = str(exc)[:300]
        return result

    def run_backtest(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        fast_windows: list[int] | None = None,
        slow_windows: list[int] | None = None,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "vectorbt_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "vectorbt",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }

        started = time.perf_counter()
        request = {
            "action": "run_external_backtest",
            "engine_commit": VECTORBT_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "snapshot": snapshot,
            "fast_windows": fast_windows or [5, 10, 20],
            "slow_windows": slow_windows or [20, 40, 60],
            "initial_cash": 10_000_000,
            "fee_rate": 0.0015,
            "slippage_rate": 0.001,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(10, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            stdout = completed.stdout[:200_000]
            stderr = completed.stderr[:20_000]
            result = _parse_external_json(stdout)
            if not result:
                result = {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = stderr if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "candidate_count": result.get("candidate_count", 0),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "vectorbt",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "vectorbt",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()

    def run_portfolio_scenarios(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        fast_window: int = 10,
        slow_window: int = 40,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "vectorbt_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "vectorbt",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "evaluate_portfolio_scenarios",
            "engine_commit": VECTORBT_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "snapshot": snapshot,
            "fast_window": int(fast_window),
            "slow_window": int(slow_window),
            "initial_cash": 10_000_000,
            "fee_rate": 0.0015,
            "slippage_rate": 0.001,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(10, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:300_000]) or {
                "ok": False,
                "error": "invalid_external_engine_json",
            }
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:20_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "action": "evaluate_portfolio_scenarios",
                "scenario_count": result.get("scenario_count", 0),
                "symbol_count": result.get("symbol_count", 0),
                "quality_gate_passed": bool((result.get("quality_gate") or {}).get("passed")),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "vectorbt",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "vectorbt",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()


class NautilusRuntime:
    def __init__(self, repo_root: Path, *, engine_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        local_app_data = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        engines = Path(engine_root) if engine_root is not None else local_app_data / "CodexStock" / "engines"
        self.runtime_root = engines / "nautilus_trader" / NAUTILUS_RUNTIME_FOLDER
        self.python_path = self.runtime_root / ".venv" / "Scripts" / "python.exe"
        self.worker_path = self.repo_root / "tools" / "external_engines" / "nautilus_worker.py"
        self._lock = threading.Lock()
        self._engine_id = "nautilus-trader"
        self.evidence_path = _external_run_evidence_path(self.repo_root, self._engine_id)
        self._last_run: dict[str, Any] = _load_last_run_evidence(self.evidence_path)

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        installed = self.python_path.is_file()
        worker_ready = self.worker_path.is_file()
        result: dict[str, Any] = {
            "ok": installed and worker_ready,
            "engine_name": "NautilusTrader",
            "installed": installed,
            "worker_ready": worker_ready,
            "connected": installed and worker_ready,
            "runtime_mode": "spawn_on_demand_only",
            "runtime_root": str(self.runtime_root),
            "python_path": str(self.python_path),
            "worker_path": str(self.worker_path),
            "engine_version": "1.230.0",
            "release_commit": NAUTILUS_RELEASE_COMMIT,
            "busy": self._lock.locked(),
            "last_run": dict(self._last_run),
            "live_order_allowed": False,
        }
        if probe and result["ok"]:
            try:
                completed = _run_external_process(
                    [str(self.python_path), "-c", "import nautilus_trader; print(nautilus_trader.__version__)"],
                    cwd=str(self.runtime_root),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                result["probe_ok"] = completed.returncode == 0
                result["engine_version"] = completed.stdout.strip()[:80]
                if completed.returncode != 0:
                    result["probe_error"] = completed.stderr.strip()[:300]
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["probe_ok"] = False
                result["probe_error"] = str(exc)[:300]
        return result

    def run_replay(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        fast_window: int = 10,
        slow_window: int = 60,
        timeout_seconds: int = 240,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "nautilus_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "NautilusTrader",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "run_external_replay",
            "release_commit": NAUTILUS_RELEASE_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "snapshot": snapshot,
            "fast_window": int(fast_window),
            "slow_window": int(slow_window),
            "initial_cash": 10_000_000,
            "fee_rate": 0.0015,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 240), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            stdout = completed.stdout[:200_000]
            stderr = completed.stderr[:30_000]
            result = _parse_external_json(stdout)
            if not result:
                result = {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = stderr if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "symbol_count": result.get("symbol_count", 0),
                "reconciliation_ok": result.get("reconciliation_ok", False),
                "error": str(result.get("error") or "")[:300],
                "process_returncode": completed.returncode,
            })
            return result
        except subprocess.TimeoutExpired:
            timeout_result = {
                "ok": False,
                "engine_name": "NautilusTrader",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
            self._last_run = _persist_last_run_evidence(
                self.evidence_path,
                self._engine_id,
                {
                    "ok": False,
                    "finished_at_epoch": time.time(),
                    "runtime_elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
                    "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
                    "result_hash": "",
                    "symbol_count": 0,
                    "reconciliation_ok": False,
                    "error": "external_engine_timeout",
                },
            )
            return timeout_result
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "NautilusTrader",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()

    def run_execution_stress(
        self,
        microstructure_events: list[dict[str, Any]],
        snapshot_meta: dict[str, Any],
        *,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "nautilus_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "NautilusTrader",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "evaluate_execution_stress",
            "release_commit": NAUTILUS_RELEASE_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "microstructure_events": microstructure_events[:200],
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(20, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:500_000]) or {
                "ok": False,
                "error": "invalid_external_engine_json",
            }
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:30_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            quality_gate = result.get("quality_gate") if isinstance(result.get("quality_gate"), dict) else {}
            orderbook = result.get("orderbook_evidence") if isinstance(result.get("orderbook_evidence"), dict) else {}
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "action": "evaluate_execution_stress",
                "quality_gate_passed": bool(quality_gate.get("passed")),
                "partial_fill_passed": bool(quality_gate.get("partial_fill_passed")),
                "unfilled_passed": bool(quality_gate.get("unfilled_passed")),
                "latency_passed": bool(quality_gate.get("latency_passed")),
                "orderbook_event_count": int(orderbook.get("event_count") or 0),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "NautilusTrader",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "NautilusTrader",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()


class LeanRuntime:
    def __init__(self, repo_root: Path, *, engine_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        local_app_data = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        engines = Path(engine_root) if engine_root is not None else local_app_data / "CodexStock" / "engines"
        self.runtime_root = engines / "lean" / LEAN_COMMIT[:12]
        self.dotnet_path = engines / "_toolchains" / f"dotnet-{DOTNET_SDK_VERSION}" / "dotnet.exe"
        self.launcher_path = self.runtime_root / "bin" / "QuantConnect.Lean.Launcher.dll"
        self.worker_path = self.runtime_root / "worker" / "CodexStock.LeanWorker.dll"
        self.advanced_worker_path = self.runtime_root / "worker" / "CodexStock.LeanAdvancedWorker.dll"
        self._lock = threading.Lock()
        self._engine_id = "quantconnect-lean"
        self.evidence_path = _external_run_evidence_path(self.repo_root, self._engine_id)
        self._last_run: dict[str, Any] = _load_last_run_evidence(self.evidence_path)

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        sdk_ready = self.dotnet_path.is_file()
        launcher_ready = self.launcher_path.is_file()
        worker_ready = self.worker_path.is_file()
        advanced_worker_ready = self.advanced_worker_path.is_file()
        result: dict[str, Any] = {
            "ok": sdk_ready and launcher_ready and worker_ready,
            "engine_name": "QuantConnect Lean",
            "installed": sdk_ready and launcher_ready,
            "worker_ready": worker_ready,
            "advanced_worker_ready": advanced_worker_ready,
            "connected": sdk_ready and launcher_ready and worker_ready,
            "runtime_mode": "spawn_on_demand_only",
            "adapter_mode": "lean_indicator_cross_validation_v1",
            "runtime_root": str(self.runtime_root),
            "dotnet_path": str(self.dotnet_path),
            "launcher_path": str(self.launcher_path),
            "worker_path": str(self.worker_path),
            "advanced_worker_path": str(self.advanced_worker_path),
            "dotnet_sdk_version": DOTNET_SDK_VERSION,
            "engine_commit": LEAN_COMMIT,
            "busy": self._lock.locked(),
            "last_run": dict(self._last_run),
            "known_dependency_advisories": True,
            "network_access_allowed": False,
            "live_order_allowed": False,
        }
        if probe and result["ok"]:
            try:
                completed = _run_external_process(
                    [str(self.dotnet_path), str(self.worker_path), "--probe"],
                    cwd=str(self.runtime_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                result["probe_ok"] = completed.returncode == 0
                if completed.returncode != 0:
                    result["probe_error"] = completed.stderr.strip()[:300]
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["probe_ok"] = False
                result["probe_error"] = str(exc)[:300]
        return result

    def run_crosscheck(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        fast_window: int = 10,
        slow_window: int = 60,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "lean_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "QuantConnect Lean",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "run_external_backtest",
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "snapshot": snapshot,
            "fast_window": int(fast_window),
            "slow_window": int(slow_window),
            "initial_cash": 10_000_000,
            "fee_rate": 0.0015,
            "slippage_rate": 0.001,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.dotnet_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(20, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
                env={
                    **os.environ,
                    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                    "DOTNET_NOLOGO": "1",
                },
            )
            stdout = completed.stdout[:200_000]
            stderr = completed.stderr[:30_000]
            result = _parse_external_json(stdout)
            if not result:
                result = {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = stderr if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "symbol_count": result.get("symbol_count", 0),
                "reconciliation_ok": result.get("reconciliation_ok", False),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "QuantConnect Lean",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "QuantConnect Lean",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()

    def run_market_lifecycle_validation(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        market: str,
        universe_intervals: list[dict[str, Any]],
        corporate_actions: list[dict[str, Any]],
        holidays: list[str] | None = None,
        corporate_action_history_checked: bool = False,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"] or not status.get("advanced_worker_ready"):
            return {**status, "ok": False, "error": "lean_advanced_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "QuantConnect Lean",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "validate_market_lifecycle",
            "engine_commit": LEAN_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "market": str(market or "KR").upper(),
            "snapshot": snapshot,
            "universe_intervals": universe_intervals,
            "corporate_actions": corporate_actions,
            "corporate_action_history_checked": bool(corporate_action_history_checked),
            "holidays": holidays or [],
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.dotnet_path), str(self.advanced_worker_path)],
                cwd=str(self.advanced_worker_path.parent),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(20, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
                env={
                    **os.environ,
                    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                    "DOTNET_NOLOGO": "1",
                },
            )
            result = _parse_external_json(completed.stdout[:500_000]) or {
                "ok": False,
                "error": "invalid_external_engine_json",
            }
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:30_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            quality_gate = result.get("quality_gate") if isinstance(result.get("quality_gate"), dict) else {}
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "action": "validate_market_lifecycle",
                "quality_gate_passed": bool(quality_gate.get("passed")),
                "blockers": list(quality_gate.get("blockers") or [])[:12],
                "checked_row_count": result.get("checked_row_count", 0),
                "universe_interval_count": result.get("universe_interval_count", 0),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "QuantConnect Lean",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "QuantConnect Lean",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()


class OpenBBRuntime:
    def __init__(self, repo_root: Path, *, engine_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        local_app_data = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        engines = Path(engine_root) if engine_root is not None else local_app_data / "CodexStock" / "engines"
        self.runtime_root = engines / "openbb" / OPENBB_COMMIT[:12]
        self.python_path = self.runtime_root / ".venv" / "Scripts" / "python.exe"
        self.worker_path = self.repo_root / "tools" / "external_engines" / "openbb_worker.py"
        self._lock = threading.Lock()
        self._engine_id = "openbb"
        self.evidence_path = _external_run_evidence_path(self.repo_root, self._engine_id)
        self._last_run: dict[str, Any] = _load_last_run_evidence(self.evidence_path)

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        installed = self.python_path.is_file()
        worker_ready = self.worker_path.is_file()
        result: dict[str, Any] = {
            "ok": installed and worker_ready,
            "engine_name": "OpenBB",
            "installed": installed,
            "worker_ready": worker_ready,
            "connected": installed and worker_ready,
            "runtime_mode": "spawn_on_demand_only",
            "runtime_root": str(self.runtime_root),
            "python_path": str(self.python_path),
            "worker_path": str(self.worker_path),
            "source_commit": OPENBB_COMMIT,
            "components": ["openbb-core 1.6.13", "openbb-yfinance 1.6.3"],
            "busy": self._lock.locked(),
            "last_run": dict(self._last_run),
            "network_scope": "public_market_data_only",
            "credentials_allowed": False,
            "live_order_allowed": False,
        }
        if probe and result["ok"]:
            try:
                completed = _run_external_process(
                    [
                        str(self.python_path),
                        "-c",
                        "import openbb_core,openbb_yfinance,yfinance; print(yfinance.__version__)",
                    ],
                    cwd=str(self.runtime_root),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                result["probe_ok"] = completed.returncode == 0
                result["provider_version"] = completed.stdout.strip()[:80]
                if completed.returncode != 0:
                    result["probe_error"] = completed.stderr.strip()[:300]
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["probe_ok"] = False
                result["probe_error"] = str(exc)[:300]
        return result

    def run_crosscheck(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "openbb_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "crosscheck_external_market_data",
            "source_commit": OPENBB_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "descriptor": snapshot_meta.get("descriptor") if isinstance(snapshot_meta.get("descriptor"), dict) else {},
            "snapshot": snapshot,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            stdout = completed.stdout[:200_000]
            stderr = completed.stderr[:30_000]
            result = _parse_external_json(stdout)
            if not result:
                result = {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = stderr if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "symbol_count": result.get("symbol_count", 0),
                "external_row_count": result.get("external_row_count", 0),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()

    def run_fundamental_macro_calendar_crosscheck(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        economic_calendar_events: list[dict[str, Any]] | None = None,
        timeout_seconds: int = 240,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "openbb_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "crosscheck_fundamental_macro_calendar",
            "source_commit": OPENBB_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "descriptor": snapshot_meta.get("descriptor") if isinstance(snapshot_meta.get("descriptor"), dict) else {},
            "snapshot": snapshot,
            "economic_calendar_events": economic_calendar_events or [],
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(20, min(int(timeout_seconds or 240), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:500_000]) or {
                "ok": False,
                "error": "invalid_external_engine_json",
            }
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:30_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            quality_gate = result.get("quality_gate") if isinstance(result.get("quality_gate"), dict) else {}
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "action": "crosscheck_fundamental_macro_calendar",
                "quality_gate_passed": bool(quality_gate.get("passed")),
                "blockers": list(quality_gate.get("blockers") or [])[:12],
                "fundamental_symbol_count": len(result.get("fundamental_results") or []),
                "macro_series_count": len(result.get("macro_results") or []),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()

    def run_historical_backfill(
        self,
        contract: dict[str, Any],
        *,
        request_id: str,
        request_hash: str,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "openbb_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "fetch_historical_ohlcv",
            "source_commit": OPENBB_COMMIT,
            "request_id": str(request_id or ""),
            "request_hash": str(request_hash or ""),
            "contract": contract,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(30, min(int(timeout_seconds or 300), 900)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:2_000_000])
            if not result:
                result = {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:30_000] if completed.returncode != 0 else ""
            result["score_allowed"] = False
            result["promotion_allowed"] = False
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "action": "fetch_historical_ohlcv",
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "request_id": request_id,
                "dataset_hash": result.get("dataset_hash", ""),
                "row_count": result.get("row_count", 0),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "OpenBB",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()


class QlibRuntime:
    def __init__(self, repo_root: Path, *, engine_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        local_app_data = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        engines = Path(engine_root) if engine_root is not None else local_app_data / "CodexStock" / "engines"
        self.runtime_root = engines / "qlib" / QLIB_COMMIT[:12]
        self.python_path = self.runtime_root / ".venv" / "Scripts" / "python.exe"
        self.worker_path = self.repo_root / "tools" / "external_engines" / "qlib_worker.py"
        self._lock = threading.Lock()
        self._engine_id = "qlib"
        self.evidence_path = _external_run_evidence_path(self.repo_root, self._engine_id)
        self._last_run: dict[str, Any] = _load_last_run_evidence(self.evidence_path)

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        installed = self.python_path.is_file()
        worker_ready = self.worker_path.is_file()
        result: dict[str, Any] = {
            "ok": installed and worker_ready,
            "engine_name": "Qlib",
            "installed": installed,
            "worker_ready": worker_ready,
            "connected": installed and worker_ready,
            "runtime_mode": "spawn_on_demand_only",
            "runtime_root": str(self.runtime_root),
            "python_path": str(self.python_path),
            "worker_path": str(self.worker_path),
            "source_commit": QLIB_COMMIT,
            "components": ["pyqlib 0.9.7", "Qlib IC/Rank IC/long-short evaluation"],
            "busy": self._lock.locked(),
            "last_run": dict(self._last_run),
            "network_access_allowed": False,
            "credentials_allowed": False,
            "live_order_allowed": False,
        }
        if probe and result["ok"]:
            try:
                completed = _run_external_process(
                    [
                        str(self.python_path),
                        "-c",
                        "import qlib; from qlib.contrib.eva.alpha import calc_ic; print(qlib.__version__)",
                    ],
                    cwd=str(self.runtime_root),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                result["probe_ok"] = completed.returncode == 0
                result["engine_version"] = completed.stdout.strip()[:80]
                if completed.returncode != 0:
                    result["probe_error"] = completed.stderr.strip()[:300]
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["probe_ok"] = False
                result["probe_error"] = str(exc)[:300]
        return result

    def run_oos_evaluation(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "qlib_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "Qlib",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "evaluate_oos_rank_model",
            "source_commit": QLIB_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "descriptor": snapshot_meta.get("descriptor") if isinstance(snapshot_meta.get("descriptor"), dict) else {},
            "snapshot": snapshot,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            stdout = completed.stdout[:200_000]
            stderr = completed.stderr[:30_000]
            result = _parse_external_json(stdout) or {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = stderr if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "instrument_count": result.get("instrument_count", 0),
                "oos_row_count": result.get("oos_row_count", 0),
                "mean_rank_ic": result.get("mean_rank_ic"),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "Qlib",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "Qlib",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()

    def run_rolling_model_comparison(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        fold_count: int = 4,
        timeout_seconds: int = 240,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "qlib_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {
                "ok": False,
                "engine_name": "Qlib",
                "error": "external_engine_busy",
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        started = time.perf_counter()
        request = {
            "action": "evaluate_rolling_model_comparison",
            "source_commit": QLIB_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "descriptor": snapshot_meta.get("descriptor") if isinstance(snapshot_meta.get("descriptor"), dict) else {},
            "snapshot": snapshot,
            "fold_count": max(3, min(int(fold_count or 4), 8)),
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(20, min(int(timeout_seconds or 240), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:500_000]) or {
                "ok": False,
                "error": "invalid_external_engine_json",
            }
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:30_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "action": "evaluate_rolling_model_comparison",
                "fold_count": result.get("fold_count", 0),
                "model_count": result.get("model_count", 0),
                "selected_research_model": result.get("selected_research_model", ""),
                "quality_gate_passed": bool((result.get("quality_gate") or {}).get("passed")),
            })
            return result
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "engine_name": "Qlib",
                "error": "external_engine_timeout",
                "timeout_seconds": timeout_seconds,
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        except OSError as exc:
            return {
                "ok": False,
                "engine_name": "Qlib",
                "error": "external_engine_start_failed",
                "detail": str(exc)[:300],
                "runtime_mode": "spawn_on_demand_only",
                "live_order_allowed": False,
            }
        finally:
            self._lock.release()


class ResearchBundleRuntime:
    def __init__(self, repo_root: Path, *, engine_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        local_app_data = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        engines = Path(engine_root) if engine_root is not None else local_app_data / "CodexStock" / "engines"
        self.runtime_root = engines / "backtrader" / BACKTRADER_COMMIT[:12]
        self.python_path = self.runtime_root / ".venv" / "Scripts" / "python.exe"
        self.worker_path = self.repo_root / "tools" / "external_engines" / "backtrader_worker.py"
        self.freqtrade_runtime_root = engines / "freqtrade" / FREQTRADE_COMMIT[:12]
        self.freqtrade_python_path = self.freqtrade_runtime_root / ".venv" / "Scripts" / "python.exe"
        self.freqtrade_worker_path = self.repo_root / "tools" / "external_engines" / "freqtrade_policy_worker.py"
        self.vnpy_runtime_root = engines / "vnpy" / VNPY_COMMIT[:12]
        self.vnpy_python_path = self.vnpy_runtime_root / ".venv" / "Scripts" / "python.exe"
        self.vnpy_worker_path = self.repo_root / "tools" / "external_engines" / "vnpy_contract_worker.py"
        self.finrl_runtime_root = engines / "finrl" / FINRL_COMMIT[:12]
        self.finrl_python_path = self.finrl_runtime_root / ".venv" / "Scripts" / "python.exe"
        self.finrl_worker_path = self.repo_root / "tools" / "external_engines" / "finrl_environment_worker.py"
        self._lock = threading.Lock()
        self._engine_id = "research-bundle"
        self.evidence_path = _external_run_evidence_path(self.repo_root, self._engine_id)
        self._last_run: dict[str, Any] = _load_last_run_evidence(self.evidence_path)
        self._subengine_evidence_paths = {
            name: _external_run_evidence_path(self.repo_root, f"research-bundle-{name.lower()}")
            for name in ("Backtrader", "Freqtrade", "vn.py", "FinRL")
        }
        self._subengine_runs = {
            name: _load_last_run_evidence(path)
            for name, path in self._subengine_evidence_paths.items()
        }

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        backtrader_ready = self.python_path.is_file() and self.worker_path.is_file()
        freqtrade_ready = self.freqtrade_python_path.is_file() and self.freqtrade_worker_path.is_file()
        vnpy_ready = self.vnpy_python_path.is_file() and self.vnpy_worker_path.is_file()
        finrl_ready = self.finrl_python_path.is_file() and self.finrl_worker_path.is_file()
        connected_count = int(backtrader_ready) + int(freqtrade_ready) + int(vnpy_ready) + int(finrl_ready)
        result: dict[str, Any] = {
            "ok": backtrader_ready,
            "engine_name": "Freqtrade/vn.py/Backtrader/FinRL",
            "installed": backtrader_ready,
            "worker_ready": self.worker_path.is_file(),
            "connected": backtrader_ready,
            "runtime_mode": "spawn_on_demand_only",
            "runtime_root": str(self.runtime_root),
            "python_path": str(self.python_path),
            "worker_path": str(self.worker_path),
            "source_commit": BACKTRADER_COMMIT,
            "busy": self._lock.locked(),
            "last_run": dict(self._last_run),
            "subengine_last_runs": {
                name: dict(last_run) for name, last_run in self._subengine_runs.items()
            },
            "adapter_progress": {"connected": connected_count, "total": 4},
            "subengines": {
                "Backtrader": "connected",
                "Freqtrade": "connected" if freqtrade_ready else "adapter_pending",
                "vn.py": "connected" if vnpy_ready else "adapter_pending",
                "FinRL": "connected" if finrl_ready else "adapter_pending",
            },
            "freqtrade_runtime_root": str(self.freqtrade_runtime_root),
            "freqtrade_python_path": str(self.freqtrade_python_path),
            "freqtrade_worker_path": str(self.freqtrade_worker_path),
            "vnpy_runtime_root": str(self.vnpy_runtime_root),
            "vnpy_python_path": str(self.vnpy_python_path),
            "vnpy_worker_path": str(self.vnpy_worker_path),
            "finrl_runtime_root": str(self.finrl_runtime_root),
            "finrl_python_path": str(self.finrl_python_path),
            "finrl_worker_path": str(self.finrl_worker_path),
            "network_access_allowed": False,
            "credentials_allowed": False,
            "live_order_allowed": False,
        }
        if probe and result["ok"]:
            try:
                completed = _run_external_process(
                    [str(self.python_path), "-c", "import backtrader as bt; print(bt.__version__)"],
                    cwd=str(self.runtime_root),
                    capture_output=True,
                    text=True,
                    timeout=45,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                result["probe_ok"] = completed.returncode == 0
                result["engine_version"] = completed.stdout.strip()[:80]
                if completed.returncode != 0:
                    result["probe_error"] = completed.stderr.strip()[:300]
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["probe_ok"] = False
                result["probe_error"] = str(exc)[:300]
        return result

    def run_freqtrade_policy_check(
        self,
        *,
        allocation_pct: float,
        paper_wallet: float,
        max_open_trades: int,
        stoploss_pct: float,
        timeout_seconds: int = 90,
    ) -> dict[str, Any]:
        if not self.freqtrade_python_path.is_file() or not self.freqtrade_worker_path.is_file():
            return {"ok": False, "engine_name": "Freqtrade", "error": "freqtrade_policy_runtime_not_ready", "live_order_allowed": False}
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "engine_name": "Freqtrade", "error": "external_engine_busy", "live_order_allowed": False}
        started = time.perf_counter()
        request = {
            "action": "validate_paper_operation_policy",
            "source_commit": FREQTRADE_COMMIT,
            "allocation_pct": allocation_pct,
            "paper_wallet": paper_wallet,
            "max_open_trades": max_open_trades,
            "stoploss_pct": stoploss_pct,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.freqtrade_python_path), str(self.freqtrade_worker_path)],
                cwd=str(self.freqtrade_runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 90), 180)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:100_000]) or {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:20_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "engine": "Freqtrade",
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "contract_hash": result.get("contract_hash", ""),
                "risk_tier": (result.get("paper_contract") or {}).get("risk_tier", {}),
            })
            self._subengine_runs["Freqtrade"] = _persist_last_run_evidence(
                self._subengine_evidence_paths["Freqtrade"],
                "research-bundle-freqtrade",
                self._last_run,
            )
            return result
        except subprocess.TimeoutExpired:
            return {"ok": False, "engine_name": "Freqtrade", "error": "external_engine_timeout", "live_order_allowed": False}
        except OSError as exc:
            return {"ok": False, "engine_name": "Freqtrade", "error": "external_engine_start_failed", "detail": str(exc)[:300], "live_order_allowed": False}
        finally:
            self._lock.release()

    def run_vnpy_contract_check(self, orders: list[dict[str, Any]], *, timeout_seconds: int = 90) -> dict[str, Any]:
        if not self.vnpy_python_path.is_file() or not self.vnpy_worker_path.is_file():
            return {"ok": False, "engine_name": "vn.py", "error": "vnpy_contract_runtime_not_ready", "live_order_allowed": False}
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "engine_name": "vn.py", "error": "external_engine_busy", "live_order_allowed": False}
        started = time.perf_counter()
        request = {
            "action": "validate_order_contract",
            "source_commit": VNPY_COMMIT,
            "orders": orders,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.vnpy_python_path), str(self.vnpy_worker_path)],
                cwd=str(self.vnpy_runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 90), 180)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:100_000]) or {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:20_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "engine": "vn.py",
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "result_hash": result.get("result_hash", ""),
                "order_count": result.get("order_count", 0),
                "reconciled_count": result.get("reconciled_count", 0),
            })
            self._subengine_runs["vn.py"] = _persist_last_run_evidence(
                self._subengine_evidence_paths["vn.py"],
                "research-bundle-vn.py",
                self._last_run,
            )
            return result
        except subprocess.TimeoutExpired:
            return {"ok": False, "engine_name": "vn.py", "error": "external_engine_timeout", "live_order_allowed": False}
        except OSError as exc:
            return {"ok": False, "engine_name": "vn.py", "error": "external_engine_start_failed", "detail": str(exc)[:300], "live_order_allowed": False}
        finally:
            self._lock.release()

    def run_finrl_environment_check(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        allocation_cap_pct: float = 30.0,
        paper_capital: float = 100_000_000.0,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        if not self.finrl_python_path.is_file() or not self.finrl_worker_path.is_file():
            return {"ok": False, "engine_name": "FinRL", "error": "finrl_environment_runtime_not_ready", "live_order_allowed": False}
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "engine_name": "FinRL", "error": "external_engine_busy", "live_order_allowed": False}
        started = time.perf_counter()
        request = {
            "action": "validate_finrl_paper_environment",
            "source_commit": FINRL_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "snapshot": snapshot,
            "allocation_cap_pct": allocation_cap_pct,
            "paper_capital": paper_capital,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.finrl_python_path), str(self.finrl_worker_path)],
                cwd=str(self.finrl_runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 120), 300)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:150_000]) or {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:20_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "engine": "FinRL",
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "result_hash": result.get("result_hash", ""),
                "environment_validated": result.get("environment_validated", False),
                "max_exposure_pct": result.get("max_exposure_pct", 0),
            })
            self._subengine_runs["FinRL"] = _persist_last_run_evidence(
                self._subengine_evidence_paths["FinRL"],
                "research-bundle-finrl",
                self._last_run,
            )
            return result
        except subprocess.TimeoutExpired:
            return {"ok": False, "engine_name": "FinRL", "error": "external_engine_timeout", "live_order_allowed": False}
        except OSError as exc:
            return {"ok": False, "engine_name": "FinRL", "error": "external_engine_start_failed", "detail": str(exc)[:300], "live_order_allowed": False}
        finally:
            self._lock.release()

    def run_backtrader_check(
        self,
        snapshot: dict[str, Any],
        snapshot_meta: dict[str, Any],
        *,
        fast_window: int = 5,
        slow_window: int = 20,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["ok"]:
            return {**status, "ok": False, "error": "research_bundle_runtime_not_ready"}
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "engine_name": "Backtrader", "error": "external_engine_busy", "live_order_allowed": False}
        started = time.perf_counter()
        request = {
            "action": "event_backtest_bias_check",
            "source_commit": BACKTRADER_COMMIT,
            "snapshot_id": str(snapshot_meta.get("snapshot_id") or ""),
            "dataset_hash": str(snapshot_meta.get("dataset_hash") or ""),
            "descriptor": snapshot_meta.get("descriptor") if isinstance(snapshot_meta.get("descriptor"), dict) else {},
            "snapshot": snapshot,
            "fast_window": fast_window,
            "slow_window": slow_window,
            "commission_rate": 0.00015,
            "slippage_rate": 0.0005,
            "live_order_allowed": False,
        }
        try:
            completed = _run_external_process(
                [str(self.python_path), str(self.worker_path)],
                cwd=str(self.runtime_root),
                input=json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                capture_output=True,
                text=True,
                timeout=max(20, min(int(timeout_seconds or 180), 600)),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            result = _parse_external_json(completed.stdout[:200_000]) or {"ok": False, "error": "invalid_external_engine_json"}
            result["process_returncode"] = completed.returncode
            result["runtime_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            result["stderr"] = completed.stderr[:30_000] if completed.returncode != 0 else ""
            result["live_order_allowed"] = False
            self._last_run = _persist_last_run_evidence(self.evidence_path, self._engine_id, {
                "ok": bool(result.get("ok")),
                "finished_at_epoch": time.time(),
                "runtime_elapsed_ms": result["runtime_elapsed_ms"],
                "snapshot_id": result.get("snapshot_id", ""),
                "result_hash": result.get("result_hash", ""),
                "symbol_count": result.get("symbol_count", 0),
                "unreconciled_position_count": result.get("unreconciled_position_count", 0),
            })
            self._subengine_runs["Backtrader"] = _persist_last_run_evidence(
                self._subengine_evidence_paths["Backtrader"],
                "research-bundle-backtrader",
                self._last_run,
            )
            return result
        except subprocess.TimeoutExpired:
            return {"ok": False, "engine_name": "Backtrader", "error": "external_engine_timeout", "live_order_allowed": False}
        except OSError as exc:
            return {"ok": False, "engine_name": "Backtrader", "error": "external_engine_start_failed", "detail": str(exc)[:300], "live_order_allowed": False}
        finally:
            self._lock.release()
