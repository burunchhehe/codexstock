from __future__ import annotations

import json
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


JobHandler = Callable[[dict[str, Any], Callable[[float, str], None], Callable[[], bool]], dict[str, Any]]
JobHandlerResolver = Callable[[str], JobHandler]


class AsyncJobManager:
    """Small persistent in-process queue for bounded Research Forge workloads."""

    _executors: dict[str, ThreadPoolExecutor] = {}
    _futures: dict[str, Future[Any]] = {}
    _initialized: set[str] = set()
    _lock = threading.RLock()

    def __init__(self, root: Path, max_workers: int = 2) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_workers = max(1, min(4, int(max_workers)))
        key = str(root.resolve())
        with self._lock:
            if key not in self._executors:
                self._executors[key] = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="research-forge")
            first_in_process = key not in self._initialized
            self._initialized.add(key)
        self._executor = self._executors[key]
        if first_in_process:
            self.recover_orphaned_running()

    def submit(self, job_type: str, payload: dict[str, Any], handler: JobHandler) -> dict[str, Any]:
        if not job_type.replace("_", "").isalnum():
            raise ValueError("invalid async job type")
        job_id = f"job_{uuid4().hex}"
        now = _now()
        job = {
            "schema_version": 1, "job_id": job_id, "type": job_type,
            "status": "QUEUED", "progress_percent": 0.0, "phase": "queued",
            "payload": dict(payload), "result": None, "error": None,
            "cancel_requested": False, "attempt": 1,
            "created_at": now, "updated_at": now, "started_at": None, "finished_at": None,
        }
        self._save(job)
        lease = self._claim(job_id)
        if lease is None:
            raise RuntimeError("failed to claim newly created async job")
        future = self._executor.submit(self._execute, job_id, handler, lease)
        with self._lock:
            self._futures[job_id] = future
        return self.get(job_id)

    def retry(self, job_id: str, handler: JobHandler) -> dict[str, Any]:
        job = self.get(job_id)
        if job["status"] not in {"FAILED", "CANCELLED", "INTERRUPTED"}:
            raise ValueError("only failed, cancelled, or interrupted jobs can be retried")
        job.update({
            "status": "QUEUED", "progress_percent": 0.0, "phase": "queued",
            "result": None, "error": None, "cancel_requested": False,
            "attempt": int(job.get("attempt") or 1) + 1, "updated_at": _now(),
            "started_at": None, "finished_at": None,
        })
        self._save(job)
        lease = self._claim(job_id)
        if lease is None:
            raise RuntimeError("async job is still owned by another worker")
        future = self._executor.submit(self._execute, job_id, handler, lease)
        with self._lock:
            self._futures[job_id] = future
        return self.get(job_id)

    def resume_interrupted(self, resolver: JobHandlerResolver, limit: int = 20) -> dict[str, Any]:
        """Claim and resume persisted interrupted jobs exactly once across worker processes."""
        resumed: list[str] = []
        skipped: list[str] = []
        for path in sorted(self.root.glob("job_*.json")):
            if len(resumed) >= max(1, min(200, int(limit))):
                break
            job = self.get(path.stem)
            if job.get("status") != "INTERRUPTED" or job.get("cancel_requested"):
                continue
            job_id = str(job["job_id"])
            lease = self._claim(job_id)
            if lease is None:
                skipped.append(job_id)
                continue
            try:
                current = self.get(job_id)
                if current.get("status") != "INTERRUPTED":
                    skipped.append(job_id)
                    self._release_claim(lease)
                    continue
                current.update({
                    "status": "QUEUED", "phase": "restart_resume_queued",
                    "error": None, "result": None, "cancel_requested": False,
                    "attempt": int(current.get("attempt") or 1) + 1,
                    "updated_at": _now(), "started_at": None, "finished_at": None,
                    "resume_count": int(current.get("resume_count") or 0) + 1,
                })
                self._save(current)
                handler = resolver(str(current["type"]))
                future = self._executor.submit(self._execute, job_id, handler, lease)
                with self._lock:
                    self._futures[job_id] = future
                resumed.append(job_id)
            except Exception:
                self._release_claim(lease)
                raise
        return {"ok": True, "resumed_count": len(resumed), "resumed_job_ids": resumed, "claim_conflicts": skipped}

    def recover_orphaned_running(self, grace_seconds: float = 30.0) -> dict[str, Any]:
        """Mark RUNNING jobs interrupted only when their owner process is gone and the grace period elapsed."""
        recovered: list[str] = []
        active: list[str] = []
        now = datetime.now(timezone.utc)
        for path in sorted(self.root.glob("job_*.json")):
            job = self.get(path.stem)
            if job.get("status") != "RUNNING":
                continue
            updated = _parse_time(str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or ""))
            if updated is not None and (now - updated).total_seconds() < max(0.0, float(grace_seconds)):
                active.append(str(job["job_id"])); continue
            lease = self.root / f"{job['job_id']}.lease"
            owner_alive = self._lease_owner_alive(lease)
            if owner_alive:
                active.append(str(job["job_id"])); continue
            self._discard_stale_lease(lease, str(job["job_id"]))
            current = self.get(str(job["job_id"]))
            if current.get("status") != "RUNNING":
                continue
            current.update({"status": "INTERRUPTED", "phase": "worker_owner_lost", "error": {"type": "WorkerOwnerLost", "message": "owning worker process is no longer alive"}, "updated_at": _now(), "finished_at": _now()})
            self._save(current); recovered.append(str(job["job_id"]))
        return {"ok": True, "recovered_count": len(recovered), "recovered_job_ids": recovered, "active_job_ids": active}

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.get(job_id)
            if job["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return job
            job["cancel_requested"] = True
            job["phase"] = "cancellation_requested"
            job["updated_at"] = _now()
            future = self._futures.get(job_id)
            cancelled_before_start = bool(future and future.cancel())
            if cancelled_before_start:
                job.update({"status": "CANCELLED", "phase": "cancelled", "finished_at": _now()})
            self._save(job)
        return job

    def get(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        # On Windows an open reader can make os.replace fail with WinError 5.
        # Serialize local reads with the atomic temp-file replacement performed
        # by _save so polling/cancellation cannot turn a valid job into FAILED.
        with self._lock:
            if not path.is_file():
                raise ValueError("async job not found")
            return json.loads(path.read_text(encoding="utf-8"))

    def status(self, job_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        if job_id:
            return {"ok": True, "job": self.get(job_id)}
        jobs = [self.get(path.stem) for path in sorted(self.root.glob("job_*.json"))]
        counts: dict[str, int] = {}
        for job in jobs:
            counts[job["status"]] = counts.get(job["status"], 0) + 1
        return {"ok": True, "job_count": len(jobs), "status_counts": counts, "jobs": jobs[-max(1, min(200, limit)):]}

    def _execute(self, job_id: str, handler: JobHandler, lease: Path | None = None) -> None:
        # Claiming RUNNING and requesting cancellation must be one serialized
        # state transition. Otherwise a stale pre-cancel snapshot can overwrite
        # cancel_requested=True and silently lose the user's cancellation.
        with self._lock:
            job = self.get(job_id)
            if job.get("cancel_requested"):
                self._finish_cancelled(job)
                if lease is not None:
                    self._release_claim(lease)
                return
            job.update({"status": "RUNNING", "phase": "starting", "started_at": _now(), "updated_at": _now()})
            self._save(job)

        def cancelled() -> bool:
            return bool(self.get(job_id).get("cancel_requested"))

        def progress(percent: float, phase: str) -> None:
            with self._lock:
                current = self.get(job_id)
                current["progress_percent"] = max(float(current.get("progress_percent") or 0), min(99.0, float(percent)))
                if not current.get("cancel_requested"):
                    current["phase"] = str(phase)[:200]
                current["updated_at"] = _now()
                self._save(current)

        try:
            result = handler(dict(job["payload"]), progress, cancelled)
            current = self.get(job_id)
            if current.get("cancel_requested"):
                self._finish_cancelled(current)
            else:
                current.update({"status": "SUCCEEDED", "progress_percent": 100.0, "phase": "completed", "result": result, "finished_at": _now(), "updated_at": _now()})
                self._save(current)
        except Exception as exc:
            with self._lock:
                current = self.get(job_id)
                if current.get("cancel_requested"):
                    self._finish_cancelled(current)
                else:
                    current.update({"status": "FAILED", "phase": "failed", "error": {"type": type(exc).__name__, "message": str(exc)}, "finished_at": _now(), "updated_at": _now()})
                    self._save(current)
        finally:
            with self._lock:
                self._futures.pop(job_id, None)
            if lease is not None:
                self._release_claim(lease)

    def _finish_cancelled(self, job: dict[str, Any]) -> None:
        job.update({"status": "CANCELLED", "phase": "cancelled", "finished_at": _now(), "updated_at": _now()})
        self._save(job)

    def _path(self, job_id: str) -> Path:
        if not job_id.startswith("job_") or not job_id.replace("_", "").isalnum():
            raise ValueError("invalid async job id")
        return self.root / f"{job_id}.json"

    def _claim(self, job_id: str) -> Path | None:
        lease = self.root / f"{job_id}.lease"
        try:
            lease.mkdir()
            (lease / "owner.json").write_text(json.dumps({"claimed_at": _now(), "process": "research-forge-worker", "pid": os.getpid()}), encoding="utf-8")
            return lease
        except FileExistsError:
            if self._lease_owner_alive(lease):
                return None
            if not self._discard_stale_lease(lease, job_id):
                return None
            return self._claim(job_id)

    @staticmethod
    def _lease_owner_alive(lease: Path) -> bool:
        try:
            owner = json.loads((lease / "owner.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False
        return _process_alive(int(owner.get("pid") or 0))

    def _discard_stale_lease(self, lease: Path, job_id: str) -> bool:
        if not lease.exists():
            return True
        tombstone = self.root / f"{job_id}.stale-{uuid4().hex}"
        try:
            lease.replace(tombstone)
            stale_owner = tombstone / "owner.json"
            if stale_owner.exists(): stale_owner.unlink()
            tombstone.rmdir()
            return True
        except (FileNotFoundError, FileExistsError, OSError):
            return False

    @staticmethod
    def _release_claim(lease: Path) -> None:
        try:
            owner = lease / "owner.json"
            if owner.exists(): owner.unlink()
            lease.rmdir()
        except FileNotFoundError:
            pass

    def _save(self, job: dict[str, Any]) -> None:
        path = self._path(str(job["job_id"]))
        temporary = path.with_suffix(".json.tmp")
        with self._lock:
            temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            temporary.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False
