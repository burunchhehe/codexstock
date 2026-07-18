from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


class PaperReplayRegenerationWorker:
    """Run one idempotent Paper replay recovery at a bounded interval."""

    def __init__(
        self,
        *,
        select_next: Callable[[], dict[str, object]],
        regenerate: Callable[[str], dict[str, object]],
        state_path: Path,
        interval_seconds: int = 15,
        initial_delay_seconds: int = 30,
        closed_day_success_cooldown_seconds: int = 2,
    ) -> None:
        self.select_next = select_next
        self.regenerate = regenerate
        self.state_path = Path(state_path)
        self.interval_seconds = max(15, int(interval_seconds))
        self.initial_delay_seconds = max(0, int(initial_delay_seconds))
        self.closed_day_success_cooldown_seconds = max(
            1,
            min(self.interval_seconds, int(closed_day_success_cooldown_seconds)),
        )
        self.lock = threading.Lock()
        self.persist_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.running = False
        self.current_replay_id = ""
        self.last_result: dict[str, object] = {}
        self.last_error = ""
        self.last_job_error = ""
        self.last_check_at = ""
        self.last_success_at = ""
        self.cycle_count = 0
        self.next_due_at = ""
        self.last_wait_seconds = self.interval_seconds
        self.last_wait_reason = "initial"
        self.recent_success_elapsed_seconds: list[float] = []
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
        recent_durations = payload.get("recent_success_elapsed_seconds")
        if isinstance(recent_durations, list):
            valid_durations: list[float] = []
            for value in recent_durations:
                try:
                    duration = float(value)
                except (TypeError, ValueError):
                    continue
                if 0.0 < duration < 86_400.0:
                    valid_durations.append(round(duration, 2))
            self.recent_success_elapsed_seconds = valid_durations[-20:]
        if not self.recent_success_elapsed_seconds:
            previous_status = str(self.last_result.get("status") or "").strip().lower()
            try:
                previous_elapsed = float(self.last_result.get("elapsed_seconds") or 0.0)
            except (TypeError, ValueError):
                previous_elapsed = 0.0
            if previous_status in {"verified_replacement_candidate", "quarantined_new_result"} and previous_elapsed > 0.0:
                self.recent_success_elapsed_seconds.append(round(previous_elapsed, 2))
        self.last_error = str(payload.get("last_error") or "")
        self.last_job_error = str(payload.get("last_job_error") or "")
        self.last_check_at = str(payload.get("last_check_at") or "")
        self.last_success_at = str(payload.get("last_success_at") or "")
        previous_status = str(self.last_result.get("status") or "").strip().lower()
        previous_completed_at = str(self.last_result.get("completed_at") or "")
        if not self.last_check_at:
            self.last_check_at = previous_completed_at
        if not self.last_success_at and previous_status == "verified_replacement_candidate":
            self.last_success_at = previous_completed_at
        try:
            self.last_wait_seconds = max(
                self.interval_seconds,
                int(payload.get("last_wait_seconds") or self.interval_seconds),
            )
        except (TypeError, ValueError):
            self.last_wait_seconds = self.interval_seconds
        self.last_wait_reason = str(payload.get("last_wait_reason") or "restored_schedule")
        self.restored_from_state = True

    def _persist(self) -> None:
        with self.persist_lock:
            payload = self.status()
            payload["last_result"] = self._durable_result_summary(self.last_result)
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self.state_path)

    @staticmethod
    def _durable_result_summary(result: dict[str, object]) -> dict[str, object]:
        """Keep restart state small; detailed replay evidence already has its own ledger."""
        allowed_keys = (
            "ok",
            "status",
            "replay_id",
            "elapsed_seconds",
            "completed_at",
            "error",
            "paper_only",
            "automatic_promotion",
            "live_order_allowed",
        )
        summary = {key: result[key] for key in allowed_keys if key in result}
        selection = result.get("selection") if isinstance(result.get("selection"), dict) else {}
        safe_selection_keys = (
            "status",
            "schedule_mode",
            "retry_after_seconds",
            "cadence_seconds",
            "next_eligible_at",
            "next_schedule_check_at",
            "max_source_trade_count",
            "load_policy",
            "active_review_required_milestones",
            "manual_recheck_endpoint",
            "score_allowed",
            "promotion_allowed",
            "paper_only",
            "live_order_allowed",
        )
        if selection and any(
            key in selection
            for key in (
                "schedule_mode",
                "retry_after_seconds",
                "cadence_seconds",
                "next_eligible_at",
                "next_schedule_check_at",
                "max_source_trade_count",
            )
        ):
            safe_selection = {
                key: selection[key]
                for key in safe_selection_keys
                if key in selection and key != "load_policy"
            }
            load_policy = selection.get("load_policy")
            if isinstance(load_policy, dict):
                safe_load_policy_keys = (
                    "cadence_seconds",
                    "observed_job_count",
                    "observed_p75_seconds",
                    "target_compute_share_pct",
                    "minimum_cooldown_seconds",
                    "maximum_cooldown_seconds",
                    "serial_worker",
                    "paper_only",
                    "live_order_allowed",
                )
                safe_selection["load_policy"] = {
                    key: load_policy[key]
                    for key in safe_load_policy_keys
                    if key in load_policy
                }
            summary["selection"] = safe_selection
        return summary

    def status(self) -> dict[str, object]:
        thread_alive = bool(self.thread and self.thread.is_alive())
        return {
            "ok": not bool(self.last_error),
            "status": "running" if self.running and thread_alive else "stopped",
            "running": self.running,
            "thread_alive": thread_alive,
            "busy": bool(self.current_replay_id),
            "current_replay_id": self.current_replay_id,
            "interval_seconds": self.interval_seconds,
            "closed_day_success_cooldown_seconds": self.closed_day_success_cooldown_seconds,
            "initial_delay_seconds": self.initial_delay_seconds,
            "cycle_count": self.cycle_count,
            "next_due_at": self.next_due_at,
            "last_wait_seconds": self.last_wait_seconds,
            "last_wait_reason": self.last_wait_reason,
            "recent_success_elapsed_seconds": list(self.recent_success_elapsed_seconds),
            "last_result": self.last_result,
            "last_error": self.last_error,
            "last_job_error": self.last_job_error,
            "last_check_at": self.last_check_at,
            "last_success_at": self.last_success_at,
            "restored_from_state": self.restored_from_state,
            "state_path": str(self.state_path),
            "paper_only": True,
            "automatic_promotion": False,
            "live_order_allowed": False,
            "safety": "One bounded Paper replay per cycle; no live order or automatic promotion.",
        }

    def public_status(self) -> dict[str, object]:
        """Return a bounded API payload while detailed evidence stays in its ledgers."""
        payload = self.status()
        payload["last_result"] = self._durable_result_summary(self.last_result)
        payload["response_detail"] = "summary"
        return payload

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
            replay_id = str(selected.get("replay_id") or "").strip().upper()
            if not replay_id:
                result = {
                    "ok": bool(selected.get("ok")),
                    "status": selected.get("status", "queue_empty"),
                    "selection": selected,
                    "completed_at": self._now(),
                    "paper_only": True,
                    "live_order_allowed": False,
                }
                self.last_check_at = str(result["completed_at"])
                self.last_result = result
                self.last_error = str(selected.get("error") or "")
                self._persist()
                return result
            self.current_replay_id = replay_id
            self.last_error = ""
            self.last_job_error = ""
            self._persist()
            started = time.perf_counter()
            regeneration = self.regenerate(replay_id)
            self.cycle_count += 1
            result = {
                "ok": bool(regeneration.get("ok")),
                "status": regeneration.get("status", "unknown"),
                "replay_id": replay_id,
                "elapsed_seconds": round(time.perf_counter() - started, 2),
                "completed_at": self._now(),
                "selection": selected,
                "regeneration": regeneration,
                "paper_only": True,
                "automatic_promotion": False,
                "live_order_allowed": False,
            }
            self.last_check_at = str(result["completed_at"])
            self.last_result = result
            if str(result.get("status") or "").strip().lower() in {
                "verified_replacement_candidate",
                "quarantined_new_result",
            }:
                elapsed = float(result.get("elapsed_seconds") or 0.0)
                if elapsed > 0.0:
                    self.recent_success_elapsed_seconds = (
                        self.recent_success_elapsed_seconds + [round(elapsed, 2)]
                    )[-20:]
            if str(result.get("status") or "").strip().lower() == "verified_replacement_candidate":
                self.last_success_at = str(result["completed_at"])
            ledger = regeneration.get("ledger") if isinstance(regeneration.get("ledger"), dict) else {}
            self.last_job_error = str(regeneration.get("error") or ledger.get("error") or "")
            return result
        except Exception as exc:
            self.last_error = str(exc)
            self.last_job_error = ""
            self.last_result = {
                "ok": False,
                "status": "worker_error",
                "error": str(exc),
                "completed_at": self._now(),
                "paper_only": True,
                "live_order_allowed": False,
            }
            self.last_check_at = str(self.last_result["completed_at"])
            return dict(self.last_result)
        finally:
            self.current_replay_id = ""
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
                if (
                    bool(result.get("ok"))
                    and str(result.get("status") or "").strip().lower()
                    == "queue_complete"
                ):
                    self.last_wait_seconds = 0
                    self.last_wait_reason = "queue_complete_auto_stopped"
                    self.next_due_at = ""
                    break
                wait_seconds, wait_reason = self._cooldown_for_result(result)
                self.last_wait_seconds = wait_seconds
                self.last_wait_reason = wait_reason
                due_ts = time.time() + wait_seconds
                self.next_due_at = datetime.fromtimestamp(
                    due_ts, ZoneInfo("Asia/Seoul")
                ).isoformat(timespec="seconds")
                self._persist()
                if self.stop_event.wait(wait_seconds):
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
            self.interval_seconds = max(15, int(interval_seconds))
        if initial_delay_seconds is not None:
            self.initial_delay_seconds = max(0, int(initial_delay_seconds))
        if self.thread and self.thread.is_alive():
            self.running = True
            return self.status()
        self.stop_event.clear()
        self.running = True
        first_due_ts = time.time() + self.initial_delay_seconds
        self.next_due_at = datetime.fromtimestamp(
            first_due_ts, ZoneInfo("Asia/Seoul")
        ).isoformat(timespec="seconds")
        self.thread = threading.Thread(
            target=self._loop,
            name="paper-replay-regeneration-worker",
            daemon=True,
        )
        self.thread.start()
        self._persist()
        return self.status()

    def _cooldown_for_result(self, result: dict[str, object]) -> tuple[int, str]:
        status = str(result.get("status") or "").strip().lower()
        selection = result.get("selection") if isinstance(result.get("selection"), dict) else {}
        try:
            retry_after_seconds = int(selection.get("retry_after_seconds") or 0)
        except (TypeError, ValueError):
            retry_after_seconds = 0
        if retry_after_seconds > 0:
            return max(15, retry_after_seconds), "selection_schedule"
        if status in {"queue_complete", "no_recoverable_contract_in_queue"}:
            return max(300, self.interval_seconds), "queue_idle"
        if status in {"scheduled_for_market_closed_day", "weekday_after_hours_cooldown"}:
            return max(300, self.interval_seconds), "schedule_wait"
        if status in {"verified_replacement_candidate", "quarantined_new_result"}:
            schedule_mode = str(selection.get("schedule_mode") or "")
            safe_paper_lane = (
                selection.get("paper_only") is True
                and selection.get("live_order_allowed") is False
            )
            if schedule_mode == "manual_paper_focus_batch" and safe_paper_lane:
                return 0, schedule_mode
            if schedule_mode == "market_closed_day_full_batch" and safe_paper_lane:
                return self.closed_day_success_cooldown_seconds, schedule_mode
            return self.interval_seconds, "success_cooldown"
        if status in {"worker_error", "regeneration_failed", "worker_busy"} or not bool(result.get("ok")):
            return max(60, self.interval_seconds * 4), "failure_backoff"
        return self.interval_seconds, "success_cooldown"

    def stop(self) -> dict[str, object]:
        self.running = False
        self.stop_event.set()
        self.next_due_at = ""
        self._persist()
        return self.status()
