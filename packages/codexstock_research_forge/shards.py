from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class ResearchShardCoordinator:
    """Durable filesystem queue that lets independent research workers claim shards exactly once."""

    def __init__(self, root: Path) -> None:
        self.root = root; self.root.mkdir(parents=True, exist_ok=True)

    def create_batch(self, job_type: str, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        if not job_type.replace("_", "").isalnum() or not 1 <= len(payloads) <= 10_000:
            raise ValueError("research shard batch requires a valid type and 1..10000 payloads")
        if not all(isinstance(value, dict) for value in payloads):
            raise ValueError("research shard payloads must be objects")
        batch_id = "batch_" + uuid4().hex; batch_root = self.root / batch_id; batch_root.mkdir()
        created = _now(); shard_ids = []
        for index, payload in enumerate(payloads):
            shard_id = f"shard_{index:06d}_{uuid4().hex}"
            shard = {"schema_version": 1, "batch_id": batch_id, "shard_id": shard_id, "job_type": job_type, "status": "PENDING", "payload": payload, "payload_hash": _hash(payload), "result": None, "result_hash": None, "error": None, "attempt": 0, "worker_id": None, "worker_token": None, "created_at": created, "updated_at": created, "heartbeat_at": None, "finished_at": None}
            self._write(batch_root / f"{shard_id}.json", shard); shard_ids.append(shard_id)
        manifest = {"schema_version": 1, "batch_id": batch_id, "job_type": job_type, "shard_count": len(shard_ids), "shard_ids": shard_ids, "created_at": created, "research_only": True, "live_order_allowed": False}
        manifest["manifest_hash"] = _hash(manifest); self._write(batch_root / "manifest.json", manifest)
        return self.status(batch_id)

    def claim(self, batch_id: str, worker_id: str, lease_seconds: int = 300) -> dict[str, Any]:
        batch_root = self._batch_root(batch_id); worker = _safe_worker(worker_id)
        lease_seconds = max(30, min(3600, int(lease_seconds))); self.requeue_stale(batch_id, lease_seconds)
        for path in sorted(batch_root.glob("shard_*.json")):
            lease = path.with_suffix(".lease")
            try: lease.mkdir()
            except FileExistsError: continue
            try:
                shard = self._read_shard(path)
                if shard["status"] != "PENDING": continue
                token = uuid4().hex; now = _now()
                shard.update({"status": "RUNNING", "worker_id": worker, "worker_token": token, "attempt": int(shard.get("attempt") or 0) + 1, "heartbeat_at": now, "updated_at": now, "error": None})
                self._write(path, shard)
                (lease / "owner.json").write_text(json.dumps({"worker_id": worker, "worker_token": token, "claimed_at": now}), encoding="utf-8")
                return {"ok": True, "claimed": True, "shard": shard, "lease_seconds": lease_seconds}
            finally:
                if not (lease / "owner.json").is_file(): self._remove_lease(lease)
        return {"ok": True, "claimed": False, "shard": None, "lease_seconds": lease_seconds}

    def heartbeat(self, batch_id: str, shard_id: str, worker_token: str) -> dict[str, Any]:
        path, shard = self._owned(batch_id, shard_id, worker_token); now = _now()
        shard.update({"heartbeat_at": now, "updated_at": now}); self._write(path, shard)
        return {"ok": True, "shard_id": shard_id, "heartbeat_at": now}

    def finish(self, batch_id: str, shard_id: str, worker_token: str, *, result: dict[str, Any] | None = None, error: str = "", retryable: bool = False) -> dict[str, Any]:
        path, shard = self._owned(batch_id, shard_id, worker_token); now = _now()
        if error:
            status = "PENDING" if retryable else "FAILED"
            shard.update({"status": status, "error": str(error)[:2000], "result": None, "result_hash": None, "worker_id": None, "worker_token": None, "heartbeat_at": None, "finished_at": None if retryable else now, "updated_at": now})
        else:
            if not isinstance(result, dict): raise ValueError("successful shard completion requires an object result")
            shard.update({"status": "SUCCEEDED", "result": result, "result_hash": _hash(result), "error": None, "finished_at": now, "updated_at": now})
        self._write(path, shard); self._remove_lease(path.with_suffix(".lease"))
        return {"ok": True, "shard": shard}

    def requeue_stale(self, batch_id: str, lease_seconds: int = 300) -> dict[str, Any]:
        batch_root = self._batch_root(batch_id); threshold = datetime.now(timezone.utc) - timedelta(seconds=max(30, int(lease_seconds))); requeued = []
        for path in sorted(batch_root.glob("shard_*.json")):
            shard = self._read_shard(path)
            if shard["status"] != "RUNNING": continue
            heartbeat = _parse(str(shard.get("heartbeat_at") or shard.get("updated_at") or ""))
            if heartbeat and heartbeat > threshold: continue
            lease = path.with_suffix(".lease")
            tombstone = lease.with_name(lease.name + ".stale-" + uuid4().hex)
            try:
                if lease.exists(): lease.replace(tombstone)
                shard.update({"status": "PENDING", "worker_id": None, "worker_token": None, "heartbeat_at": None, "updated_at": _now(), "error": "stale worker lease requeued"})
                self._write(path, shard); requeued.append(shard["shard_id"])
            finally: self._remove_lease(tombstone)
        return {"ok": True, "requeued_count": len(requeued), "requeued_shard_ids": requeued}

    def status(self, batch_id: str) -> dict[str, Any]:
        batch_root = self._batch_root(batch_id); manifest = json.loads((batch_root / "manifest.json").read_text(encoding="utf-8"))
        stored = manifest.pop("manifest_hash", ""); manifest_ok = stored == _hash(manifest); manifest["manifest_hash"] = stored
        shards = [self._read_shard(path) for path in sorted(batch_root.glob("shard_*.json"))]
        counts: dict[str, int] = {}
        for shard in shards: counts[shard["status"]] = counts.get(shard["status"], 0) + 1
        done = counts.get("SUCCEEDED", 0) + counts.get("FAILED", 0)
        return {"ok": manifest_ok, "manifest": manifest, "status_counts": counts, "completed_count": done, "progress_percent": round(done / len(shards) * 100, 3) if shards else 0.0, "shards": shards, "research_only": True, "live_order_allowed": False}

    def _owned(self, batch_id: str, shard_id: str, token: str) -> tuple[Path, dict[str, Any]]:
        path = self._batch_root(batch_id) / f"{_safe_shard(shard_id)}.json"; shard = self._read_shard(path)
        if shard["status"] != "RUNNING" or not token or shard.get("worker_token") != token: raise PermissionError("research shard is not owned by this worker token")
        return path, shard

    def _batch_root(self, batch_id: str) -> Path:
        if not batch_id.startswith("batch_") or not batch_id.replace("_", "").isalnum(): raise ValueError("invalid research batch id")
        path = self.root / batch_id
        if not path.is_dir() or not (path / "manifest.json").is_file(): raise ValueError("research batch not found")
        return path

    @staticmethod
    def _read_shard(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or payload.get("status") not in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED"} or payload.get("payload_hash") != _hash(payload.get("payload")):
            raise ValueError("research shard integrity verification failed")
        if payload.get("result") is not None and payload.get("result_hash") != _hash(payload["result"]): raise ValueError("research shard result integrity verification failed")
        return payload

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)

    @staticmethod
    def _remove_lease(path: Path) -> None:
        try:
            owner = path / "owner.json"
            if owner.exists(): owner.unlink()
            path.rmdir()
        except FileNotFoundError: pass


def _safe_worker(value: str) -> str:
    value = str(value)
    if not value or len(value) > 100 or not all(char.isalnum() or char in {"-", "_", "."} for char in value): raise ValueError("invalid research worker id")
    return value


def _safe_shard(value: str) -> str:
    value = str(value)
    if not value.startswith("shard_") or not value.replace("_", "").isalnum(): raise ValueError("invalid research shard id")
    return value


def _hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")); return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _now() -> str: return datetime.now(timezone.utc).isoformat()


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")); return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError: return None
