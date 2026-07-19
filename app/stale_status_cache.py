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
        max_refresh_seconds: float = 300.0,
        retry_delay_seconds: float = 15.0,
        durable_validator: Callable[[dict[str, object]], bool] | None = None,
        bootstrap_payload: dict[str, object] | None = None,
    ) -> None:
        self._builder = builder
        self._cache_path = Path(cache_path)
        self._schema_version = schema_version
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._max_refresh_seconds = max(0.05, float(max_refresh_seconds))
        self._retry_delay_seconds = max(0.0, float(retry_delay_seconds))
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
        self._refresh_started_at_monotonic = 0.0
        self._refresh_generation = 0
        self._next_retry_at_monotonic = 0.0
        self._last_refresh_error = ""

    def get(self) -> dict[str, object]:
        now = time.time()
        now_monotonic = time.monotonic()
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
            refresh_elapsed = (
                now_monotonic - self._refresh_started_at_monotonic
                if refreshing and self._refresh_started_at_monotonic > 0.0
                else 0.0
            )
            if refreshing and refresh_elapsed > self._max_refresh_seconds:
                self._refresh_generation += 1
                self._refreshing = False
                self._refresh_started_at_monotonic = 0.0
                self._next_retry_at_monotonic = (
                    now_monotonic + self._retry_delay_seconds
                )
                self._last_refresh_error = (
                    "TimeoutError: status refresh exceeded "
                    f"{self._max_refresh_seconds:.2f}s"
                )
                refreshing = False
            if (
                payload
                and now - saved_at > self._ttl_seconds
                and not refreshing
                and now_monotonic >= self._next_retry_at_monotonic
            ):
                self._refreshing = True
                self._refresh_started_at_monotonic = now_monotonic
                self._refresh_generation += 1
                refresh_generation = self._refresh_generation
                refreshing = True
                threading.Thread(
                    target=self._refresh,
                    args=(refresh_generation,),
                    daemon=True,
                ).start()

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
        with self._lock:
            self._refresh_generation += 1
            refresh_generation = self._refresh_generation
            self._refreshing = True
            self._refresh_started_at_monotonic = time.monotonic()
        try:
            built = self._build()
            self._store(built, refresh_generation=refresh_generation)
            return self._decorate(built, time.time(), False)
        finally:
            with self._lock:
                if refresh_generation == self._refresh_generation:
                    self._refreshing = False
                    self._refresh_started_at_monotonic = 0.0

    def request_refresh(self) -> dict[str, object]:
        """Start one background refresh and return the current status immediately."""
        now = time.time()
        now_monotonic = time.monotonic()
        payload: dict[str, object] = {}
        saved_at = 0.0
        already_refreshing = False
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
            if self._refreshing:
                already_refreshing = True
            else:
                self._refreshing = True
                self._refresh_started_at_monotonic = now_monotonic
                self._refresh_generation += 1
                refresh_generation = self._refresh_generation
                threading.Thread(
                    target=self._refresh,
                    args=(refresh_generation,),
                    daemon=True,
                ).start()
        if already_refreshing:
            return self._decorate(payload, saved_at, True) if payload else {
                "ok": False,
                "cached": False,
                "stale": False,
                "refreshing": True,
                "cache_age_seconds": 0,
            }
        if payload:
            return self._decorate(payload, saved_at, True)
        return {
            "ok": False,
            "cached": False,
            "stale": False,
            "refreshing": True,
            "cache_age_seconds": 0,
            "status": "refresh_requested",
        }

    def _build(self) -> dict[str, object]:
        payload = self._builder()
        if not isinstance(payload, dict) or not payload:
            raise ValueError("status builder returned an empty payload")
        return dict(payload)

    def _refresh(self, refresh_generation: int) -> None:
        try:
            self._store(
                self._build(),
                refresh_generation=refresh_generation,
            )
        except Exception as exc:
            with self._lock:
                if refresh_generation == self._refresh_generation:
                    self._last_refresh_error = f"{type(exc).__name__}: {exc}"
                    self._next_retry_at_monotonic = (
                        time.monotonic() + self._retry_delay_seconds
                    )
        finally:
            with self._lock:
                if refresh_generation == self._refresh_generation:
                    self._refreshing = False
                    self._refresh_started_at_monotonic = 0.0

    def _store(
        self,
        payload: dict[str, object],
        *,
        refresh_generation: int | None = None,
    ) -> bool:
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
            if (
                refresh_generation is not None
                and refresh_generation != self._refresh_generation
            ):
                return False
            self._payload = durable_payload
            self._saved_at = saved_at
            self._last_refresh_error = ""
            self._next_retry_at_monotonic = 0.0
        record = {
            "schema_version": self._schema_version,
            "saved_at_epoch": saved_at,
            "payload": durable_payload,
        }
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._cache_path.with_name(
                f"{self._cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            temp_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            os.replace(temp_path, self._cache_path)
        except OSError:
            return True
        return True

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
            refresh_elapsed = (
                max(0.0, time.monotonic() - self._refresh_started_at_monotonic)
                if refreshing and self._refresh_started_at_monotonic > 0.0
                else 0.0
            )
        return {
            **payload,
            "cached": True,
            "stale": age > self._ttl_seconds,
            "refreshing": bool(refreshing),
            "cache_age_seconds": round(age, 2),
            "cache_source": "stale_while_refresh",
            "status_cache_error": error,
            "refresh_timed_out": error.startswith("TimeoutError:"),
            "refresh_elapsed_seconds": round(refresh_elapsed, 2),
            "refresh_timeout_seconds": round(self._max_refresh_seconds, 2),
        }
