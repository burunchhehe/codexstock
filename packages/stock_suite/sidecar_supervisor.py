"""Lightweight supervisor for the independent Shadow execution sidecar."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .execution_sidecar import process_is_alive


def _read_mapping(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_mapping(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        for attempt in range(40):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


class ExecutionSidecarSupervisor:
    def __init__(
        self,
        *,
        repo_root: Path,
        status_file: Path,
        state_file: Path,
        interval_seconds: float = 5.0,
        restart_cooldown_seconds: float = 15.0,
        mode: str = "shadow",
        process_alive: Callable[[int], bool] = process_is_alive,
        process_factory: Callable[..., object] = subprocess.Popen,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.status_file = Path(status_file)
        self.state_file = Path(state_file)
        self.interval_seconds = max(1.0, float(interval_seconds))
        self.restart_cooldown_seconds = max(5.0, float(restart_cooldown_seconds))
        if mode not in {"shadow", "paper", "live"}:
            raise ValueError("invalid_execution_sidecar_mode")
        self.mode = mode
        self.process_alive = process_alive
        self.process_factory = process_factory
        self.monotonic = monotonic
        self._last_restart_attempt = -1e12
        self._child: object | None = None
        self.child_log_file = self.state_file.with_name("supervisor-child.log")
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def tick(self) -> dict[str, object]:
        status = _read_mapping(self.status_file)
        process_id = int(status.get("process_id") or 0)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        previous = _read_mapping(self.state_file)
        if self._child is not None:
            exit_code = self._child.poll()
            if exit_code is not None:
                previous["last_child_exit_code"] = int(exit_code)
                previous["last_child_exit_at"] = now
                self._child = None
        if self.process_alive(process_id):
            actual_mode = str(status.get("mode") or "").strip().lower()
            mode_verified = actual_mode in {"shadow", "paper", "live"}
            mode_matches = bool(mode_verified and actual_mode == self.mode)
            state = {
                **previous,
                "ok": mode_matches,
                "state": (
                    "MONITORING"
                    if mode_matches
                    else "MODE_MISMATCH"
                    if mode_verified
                    else "MODE_UNVERIFIED"
                ),
                "checked_at": now,
                "sidecar_process_id": process_id,
                "mode": self.mode,
                "expected_mode": self.mode,
                "actual_mode": actual_mode or "unknown",
                "mode_verified": mode_verified,
                "mode_matches": mode_matches,
                "restart_required": not mode_matches,
                "retry_after_seconds": 0.0,
                "last_error": (
                    ""
                    if mode_matches
                    else f"execution_sidecar_mode_mismatch: expected={self.mode}, actual={actual_mode or 'unknown'}"
                ),
            }
            _write_mapping(self.state_file, state)
            return state

        elapsed = self.monotonic() - self._last_restart_attempt
        if elapsed < self.restart_cooldown_seconds:
            state = {
                **previous,
                "ok": False,
                "state": "RESTART_COOLDOWN",
                "checked_at": now,
                "sidecar_process_id": process_id,
                "restart_required": True,
                "retry_after_seconds": round(self.restart_cooldown_seconds - elapsed, 2),
            }
            _write_mapping(self.state_file, state)
            return state

        self._last_restart_attempt = self.monotonic()
        command = [
            sys.executable,
            str(self.repo_root / "app" / "execution_sidecar_service.py"),
            "--mode", self.mode, "--interval", "1",
        ]
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        child_environment = dict(os.environ)
        child_environment["CODEXSTOCK_ENABLE_EXTERNAL_LIVE_EXECUTOR"] = (
            "1" if self.mode == "live" else "0"
        )
        try:
            self.child_log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.child_log_file.open("ab", buffering=0) as child_log:
                child = self.process_factory(
                    command,
                    cwd=str(self.repo_root),
                    stdin=subprocess.DEVNULL,
                    stdout=child_log,
                    stderr=child_log,
                    creationflags=creationflags,
                    env=child_environment,
                )
            self._child = child
            child_pid = int(getattr(child, "pid", 0) or 0)
            state = {
                **previous,
                "ok": True,
                "state": "RESTART_LAUNCHED",
                "checked_at": now,
                "sidecar_process_id": child_pid,
                "restart_required": False,
                "retry_after_seconds": 0.0,
                "restart_count": int(previous.get("restart_count") or 0) + 1,
                "last_restart_at": now,
                "last_restart_reason": "sidecar_process_not_alive",
                "mode": self.mode,
                "last_error": "",
            }
        except Exception as exc:
            state = {
                **previous,
                "ok": False,
                "state": "RESTART_FAILED",
                "checked_at": now,
                "sidecar_process_id": 0,
                "restart_required": True,
                "last_error": f"{type(exc).__name__}: {exc}"[:500],
            }
        _write_mapping(self.state_file, state)
        return state

    def start(self) -> dict[str, object]:
        if self._thread and self._thread.is_alive():
            return _read_mapping(self.state_file)

        def run() -> None:
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(self.interval_seconds)

        self._stop.clear()
        self._thread = threading.Thread(target=run, name="execution-sidecar-supervisor", daemon=True)
        self._thread.start()
        return {"ok": True, "state": "STARTED", "interval_seconds": self.interval_seconds}
