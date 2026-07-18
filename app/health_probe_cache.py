from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


_CACHE_LOCK = threading.Lock()


def load_probe_cache(
    memory_cache: dict[str, object],
    cache_path: Path,
    *,
    schema_version: str,
    scope: str,
    ttl_seconds: int,
) -> dict[str, object] | None:
    """Load a scope-bound probe result from memory or durable restart cache."""
    now = time.time()
    ttl = max(1, int(ttl_seconds))
    with _CACHE_LOCK:
        payload = memory_cache.get("payload")
        saved_at = float(memory_cache.get("saved_at") or 0.0)
        if (
            isinstance(payload, dict)
            and payload
            and memory_cache.get("scope") == scope
            and now - saved_at <= ttl
        ):
            return {
                **payload,
                "cached": True,
                "cache_source": "memory",
                "cache_age_seconds": round(max(0.0, now - saved_at), 2),
            }
        try:
            record = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        durable_payload = record.get("payload") if isinstance(record, dict) else None
        durable_saved_at = float(record.get("saved_at_epoch") or 0.0) if isinstance(record, dict) else 0.0
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != schema_version
            or record.get("scope") != scope
            or not isinstance(durable_payload, dict)
            or not durable_payload
            or now - durable_saved_at > ttl
        ):
            return None
        memory_cache.update(
            {"saved_at": durable_saved_at, "scope": scope, "payload": dict(durable_payload)}
        )
        return {
            **durable_payload,
            "cached": True,
            "cache_source": "disk",
            "cache_age_seconds": round(max(0.0, now - durable_saved_at), 2),
        }


def save_probe_cache(
    memory_cache: dict[str, object],
    cache_path: Path,
    payload: dict[str, object],
    *,
    schema_version: str,
    scope: str,
) -> None:
    """Atomically persist a bounded health result without mutating audited data."""
    now = time.time()
    durable_payload = dict(payload)
    durable_payload.pop("cache_source", None)
    durable_payload.pop("cache_age_seconds", None)
    with _CACHE_LOCK:
        memory_cache.update({"saved_at": now, "scope": scope, "payload": durable_payload})
        record = {
            "schema_version": schema_version,
            "scope": scope,
            "saved_at_epoch": now,
            "payload": durable_payload,
        }
        try:
            target = Path(cache_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp_path = target.with_name(f"{target.name}.{os.getpid()}.tmp")
            temp_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            os.replace(temp_path, target)
        except OSError:
            return
