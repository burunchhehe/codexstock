from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


class PaperReplayDataBackfillWorker:
    """Process at most one verified-data request per bounded cycle."""

    def __init__(
        self,
        *,
        select_next: Callable[[], dict[str, object]],
        process: Callable[[str], dict[str, object]],
        state_path: Path,
        interval_seconds: int = 600,
        initial_delay_seconds: int = 120,
        should_auto_stop: Callable[[dict[str, object]], bool] | None = None,
    ) -> None:
        self.select_next = select_next
        self.process = process
        self.state_path = Path(state_path)
        self.interval_seconds = max(120, int(interval_seconds))
        self.initial_delay_seconds = max(0, int(initial_delay_seconds))
        self.should_auto_stop = should_auto_stop
        self.lock = threading.Lock()
        self.persist_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.running = False
        self.current_request_id = ""
        self.last_result: dict[str, object] = {}
        self.last_error = ""
        self.last_job_error = ""
        self.cycle_count = 0
        self.next_due_at = ""
        self.restored_from_state = False
        self._restore_state()

    @staticmethod
    def _now() -> str:
        return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")

    def _restore_state(self) -> None:
        """Restore durable history without reviving stale running/busy state."""
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        try:
            self.cycle_count = max(0, int(payload.get("cycle_count") or 0))
        except (TypeError, ValueError):
            self.cycle_count = 0
        previous_result = payload.get("last_result")
        self.last_result = dict(previous_result) if isinstance(previous_result, dict) else {}
        self.last_error = str(payload.get("last_error") or "")
        self.last_job_error = str(payload.get("last_job_error") or "")
        self.restored_from_state = True

    @staticmethod
    def _compact_result(result: dict[str, object]) -> dict[str, object]:
        validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
        replay = result.get("replay_regeneration") if isinstance(result.get("replay_regeneration"), dict) else {}
        return {
            "ok": bool(result.get("ok")),
            "status": result.get("status", "unknown"),
            "request_id": result.get("request_id", ""),
            "source_replay_id": result.get("source_replay_id", ""),
            "artifact_path": result.get("artifact_path", ""),
            "row_count": validation.get("row_count", 0),
            "blocker_count": validation.get("blocker_count", 0),
            "replay_status": replay.get("status", ""),
            "new_replay_id": replay.get("new_replay_id", ""),
            "engine_error": str(result.get("engine_error") or "")[:300],
            "completed_at": PaperReplayDataBackfillWorker._now(),
            "paper_only": True,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    def status(self) -> dict[str, object]:
        thread_alive = bool(self.thread and self.thread.is_alive())
        return {
            "ok": not bool(self.last_error),
            "status": "running" if self.running and thread_alive else "stopped",
            "running": self.running,
            "thread_alive": thread_alive,
            "busy": bool(self.current_request_id),
            "current_request_id": self.current_request_id,
            "interval_seconds": self.interval_seconds,
            "initial_delay_seconds": self.initial_delay_seconds,
            "cycle_count": self.cycle_count,
            "next_due_at": self.next_due_at,
            "last_result": dict(self.last_result),
            "last_error": self.last_error,
            "last_job_error": self.last_job_error,
            "restored_from_state": self.restored_from_state,
            "state_path": str(self.state_path),
            "paper_only": True,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
            "safety": "One Stage 2 data request per cycle; no score, promotion, memory, or live order effect.",
        }

    def _persist(self) -> None:
        with self.persist_lock:
            payload = self.status()
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self.state_path)

    def run_once(self) -> dict[str, object]:
        if not self.lock.acquire(blocking=False):
            return {
                "ok": False,
                "status": "worker_busy",
                "paper_only": True,
                "live_order_allowed": False,
            }
        try:
            selected = self.select_next()
            request_id = str(selected.get("request_id") or "").strip()
            if not request_id:
                result = {
                    "ok": bool(selected.get("ok")),
                    "status": selected.get("status", "queue_empty"),
                    "completed_at": self._now(),
                    "paper_only": True,
                    "score_allowed": False,
                    "promotion_allowed": False,
                    "live_order_allowed": False,
                }
                self.last_result = result
                self.last_error = str(selected.get("error") or "")
                self._persist()
                return result
            self.current_request_id = request_id
            self.last_error = ""
            self.last_job_error = ""
            self._persist()
            started = time.perf_counter()
            raw_result = self.process(request_id)
            self.cycle_count += 1
            result = self._compact_result(raw_result)
            result["elapsed_seconds"] = round(time.perf_counter() - started, 2)
            self.last_result = result
            self.last_job_error = str(result.get("engine_error") or "")
            return result
        except Exception as exc:
            self.last_error = str(exc)
            self.last_result = {
                "ok": False,
                "status": "worker_error",
                "error": str(exc)[:500],
                "completed_at": self._now(),
                "paper_only": True,
                "live_order_allowed": False,
            }
            return dict(self.last_result)
        finally:
            self.current_request_id = ""
            try:
                self._persist()
            finally:
                self.lock.release()

    def _loop(self) -> None:
        try:
            if self.stop_event.wait(self.initial_delay_seconds):
                return
            while not self.stop_event.is_set():
                result = self.run_once()
                auto_stop = False
                if self.should_auto_stop is not None:
                    try:
                        auto_stop = bool(self.should_auto_stop(result))
                    except Exception:
                        auto_stop = False
                if auto_stop:
                    self.last_result = {
                        **self.last_result,
                        "auto_stopped": True,
                        "auto_stop_reason": "terminal_queue_idle",
                    }
                    self.next_due_at = ""
                    self._persist()
                    break
                due_ts = time.time() + self.interval_seconds
                self.next_due_at = datetime.fromtimestamp(
                    due_ts, ZoneInfo("Asia/Seoul")
                ).isoformat(timespec="seconds")
                self._persist()
                if self.stop_event.wait(self.interval_seconds):
                    break
        finally:
            self.running = False
            self.next_due_at = ""
            self._persist()

    def start(
        self,
        *,
        interval_seconds: int | None = None,
        initial_delay_seconds: int | None = None,
    ) -> dict[str, object]:
        if interval_seconds is not None:
            self.interval_seconds = max(120, int(interval_seconds))
        if initial_delay_seconds is not None:
            self.initial_delay_seconds = max(0, int(initial_delay_seconds))
        if self.thread and self.thread.is_alive():
            self.running = True
            return self.status()
        self.stop_event.clear()
        self.running = True
        due_ts = time.time() + self.initial_delay_seconds
        self.next_due_at = datetime.fromtimestamp(due_ts, ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        self.thread = threading.Thread(
            target=self._loop,
            name="paper-replay-data-backfill-worker",
            daemon=True,
        )
        self.thread.start()
        self._persist()
        return self.status()

    def stop(self) -> dict[str, object]:
        self.running = False
        self.stop_event.set()
        self.next_due_at = ""
        self._persist()
        return self.status()
