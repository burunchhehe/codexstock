from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable


class StaleWhileRefreshStatusCache:
    """Return the last healthy status immediately while one refresh runs."""

    def __init__(
        self,
        *,
        builder: Callable[[], dict[str, object]],
        cache_path: Path,
        schema_version: str,
        ttl_seconds: int = 15,
        durable_validator: Callable[[dict[str, object]], bool] | None = None,
        bootstrap_payload: dict[str, object] | None = None,
    ) -> None:
        self._builder = builder
        self._cache_path = Path(cache_path)
        self._schema_version = schema_version
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._durable_validator = durable_validator
        self._bootstrap_payload = (
            dict(bootstrap_payload)
            if isinstance(bootstrap_payload, dict) and bootstrap_payload
            else {}
        )
        self._lock = threading.Lock()
        self._payload: dict[str, object] = {}
        self._saved_at = 0.0
        self._refreshing = False
        self._last_refresh_error = ""

    def get(self) -> dict[str, object]:
        now = time.time()
        with self._lock:
            self._load_durable_locked()
            if not self._payload and self._bootstrap_payload:
                self._payload = {
                    **self._bootstrap_payload,
                    "status_cache_bootstrap": True,
                }
                self._saved_at = now - self._ttl_seconds - 1.0
            payload = dict(self._payload)
            saved_at = self._saved_at
            refreshing = self._refreshing
            if payload and now - saved_at > self._ttl_seconds and not refreshing:
                self._refreshing = True
                refreshing = True
                threading.Thread(target=self._refresh, daemon=True).start()

        if payload:
            return self._decorate(payload, saved_at, refreshing)

        # Only a first-ever request may block. Future requests have durable fallback.
        try:
            built = self._build()
        except Exception as exc:
            return {
                "ok": False,
                "cached": False,
                "stale": False,
                "refreshing": False,
                "cache_age_seconds": 0,
                "status_cache_error": f"{type(exc).__name__}: {exc}",
            }
        self._store(built)
        return self._decorate(built, time.time(), False)

    def refresh_now(self) -> dict[str, object]:
        built = self._build()
        self._store(built)
        return self._decorate(built, time.time(), False)

    def _build(self) -> dict[str, object]:
        payload = self._builder()
        if not isinstance(payload, dict) or not payload:
            raise ValueError("status builder returned an empty payload")
        return dict(payload)

    def _refresh(self) -> None:
        try:
            self._store(self._build())
        except Exception as exc:
            with self._lock:
                self._last_refresh_error = f"{type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                self._refreshing = False

    def _store(self, payload: dict[str, object]) -> None:
        saved_at = time.time()
        durable_payload = dict(payload)
        for key in (
            "cached",
            "stale",
            "refreshing",
            "cache_age_seconds",
            "cache_source",
            "status_cache_error",
        ):
            durable_payload.pop(key, None)
        with self._lock:
            self._payload = durable_payload
            self._saved_at = saved_at
            self._last_refresh_error = ""
        record = {
            "schema_version": self._schema_version,
            "saved_at_epoch": saved_at,
            "payload": durable_payload,
        }
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._cache_path.with_name(f"{self._cache_path.name}.{os.getpid()}.tmp")
            temp_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            os.replace(temp_path, self._cache_path)
        except OSError:
            return

    def _load_durable_locked(self) -> None:
        if self._payload:
            return
        try:
            record = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
            return
        payload = record.get("payload") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != self._schema_version
            or not isinstance(payload, dict)
            or not payload
        ):
            return
        if self._durable_validator is not None:
            try:
                if not self._durable_validator(payload):
                    return
            except Exception:
                return
        self._payload = dict(payload)
        self._saved_at = float(record.get("saved_at_epoch") or 0.0)

    def _decorate(
        self,
        payload: dict[str, object],
        saved_at: float,
        refreshing: bool,
    ) -> dict[str, object]:
        age = max(0.0, time.time() - saved_at)
        with self._lock:
            error = self._last_refresh_error
        return {
            **payload,
            "cached": True,
            "stale": age > self._ttl_seconds,
            "refreshing": bool(refreshing),
            "cache_age_seconds": round(age, 2),
            "cache_source": "stale_while_refresh",
            "status_cache_error": error,
        }
