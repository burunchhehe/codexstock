"""Independent, fail-closed operational sidecar for CodexStock.

The sidecar never imports :mod:`stock_suite_app`.  It observes the running app
through bounded local HTTP calls and delegates every recovery decision to the
deterministic internal-developer engine.  The only HTTP recovery routes in this
module are fixed constants; neither GPT advice nor an incident payload can
select a URL, a process, a file, or a command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

try:
    from app.runtime_paths import active_data_root, read_runtime_root_contract
except ModuleNotFoundError:  # direct: ``python app/internal_developer_service.py``
    from runtime_paths import active_data_root, read_runtime_root_contract


SERVICE_SCHEMA = "codexstock.internal-developer-service.v1"
SERVICE_STATE_SCHEMA = "codexstock.internal-developer-service-state.v1"
SERVICE_HEARTBEAT_SCHEMA = "codexstock.internal-developer-heartbeat.v1"

OVERVIEW_PATH = "/api/mcp/overview"
FEATURE_HEALTH_PATH = "/api/system/feature-health?compact=1&record=0"
FEATURE_HEALTH_FORCE_PATH = (
    "/api/system/feature-health?compact=1&record=0&force=1"
)
EXTERNAL_ENGINE_STATUS_PATH = "/api/external-engines/status"
KIS_RECONNECT_PATH = "/api/external-engines/kis-trading-mcp/status?force=1"
IMPROVEMENT_STATUS_PATH = "/api/external-engines/improvement-loop/status"
IMPROVEMENT_RETRY_PATH = "/api/external-engines/improvement-loop/run"
SYSTEM_RESOURCES_PATH = "/api/system/resources"
TELEGRAM_QUEUE_PATH = "/api/ops/telegram/queue"

# A recovery callback must pass through one of these exact routes.  Query or
# payload data can never add another route.
_RECOVERY_GET_PATHS = frozenset({FEATURE_HEALTH_FORCE_PATH, KIS_RECONNECT_PATH})
_RECOVERY_POST_PATHS = frozenset({IMPROVEMENT_RETRY_PATH})

FORBIDDEN_AUTOMATION = frozenset(
    {
        "cancelled_job_retry",
        "live_order",
        "api_key_change",
        "risk_limit_relaxation",
        "code_edit",
        "security_disable",
        "process_kill",
        "lock_delete",
    }
)

_ACTIVE_IMPROVEMENT_STATES = frozenset(
    {
        "ACTIVE",
        "AUTO_RECOVERING",
        "IN_PROGRESS",
        "PREPARING",
        "QUEUED",
        "RETRYING",
        "RUNNING",
        "STARTING",
    }
)
_RETRYABLE_RESEARCH_STATES = frozenset({"FAILED", "INTERRUPTED"})
_CANCELLED_STATES = frozenset({"CANCELED", "CANCELLED"})
_ADVICE_NEVER_AUTOMATES = frozenset({"REQUEST_CODEXSTOCK_RESTART"})
_TRANSIENT_REVERIFIABLE_CLASSIFICATIONS = frozenset(
    {"HEARTBEAT_MISSING", "PROCESS_UNRESPONSIVE", "DIAGNOSTIC_ENDPOINT_UNAVAILABLE"}
)
_TRANSIENT_REVERIFIABLE_STATES = frozenset(
    {"NEW", "DIAGNOSING", "RETRYING", "WAITING_FOR_RESTART"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dig(value: object, *paths: str) -> object | None:
    for dotted in paths:
        current = value
        found = True
        for part in dotted.split("."):
            if not isinstance(current, Mapping) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            return current
    return None


def _as_mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_error(exc: BaseException) -> dict[str, str]:
    return {
        "error_type": type(exc).__name__[:120],
        "error": str(exc).replace("\r", " ").replace("\n", " ")[:500],
    }


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    payload: dict[str, object]

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class HttpRequestError(RuntimeError):
    def __init__(self, method: str, path: str, detail: str) -> None:
        super().__init__(f"{method} {path}: {detail}"[:700])
        self.method = method
        self.path = path


class UrllibJsonClient:
    """Small local JSON client with no cookie jar, redirects, or retries."""

    def __init__(self, base_url: str) -> None:
        self.base_url = str(base_url).rstrip("/")

    def get(self, path: str, *, timeout: float) -> HttpResponse:
        return self._request("GET", path, None, timeout)

    def post(
        self, path: str, payload: Mapping[str, object], *, timeout: float
    ) -> HttpResponse:
        return self._request("POST", path, payload, timeout)

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None,
        timeout: float,
    ) -> HttpResponse:
        body = None
        headers = {"Accept": "application/json", "Connection": "close"}
        if payload is not None:
            body = json.dumps(dict(payload), ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=max(0.1, float(timeout))) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                status_code = int(getattr(response, "status", 200))
        except urllib.error.HTTPError as exc:
            raw = exc.read(2 * 1024 * 1024 + 1)
            status_code = int(exc.code)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise HttpRequestError(method, path, str(exc)) from exc
        if len(raw) > 2 * 1024 * 1024:
            raise HttpRequestError(method, path, "response_too_large")
        try:
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpRequestError(method, path, "invalid_json_response") from exc
        if not isinstance(decoded, dict):
            raise HttpRequestError(method, path, "response_must_be_object")
        return HttpResponse(status_code, decoded)


@dataclass
class ServiceConfig:
    base_url: str = "http://127.0.0.1:8765"
    interval_seconds: float = 60.0
    overview_timeout_seconds: float = 2.0
    diagnostic_timeout_seconds: float = 8.0
    recovery_timeout_seconds: float = 20.0
    busy_stall_seconds: float = 300.0
    restart_failure_threshold: int = 5
    expected_pid: int | None = None

    def __post_init__(self) -> None:
        self.base_url = str(self.base_url).rstrip("/")
        self.interval_seconds = max(1.0, float(self.interval_seconds))
        self.overview_timeout_seconds = max(0.1, float(self.overview_timeout_seconds))
        self.diagnostic_timeout_seconds = max(0.1, float(self.diagnostic_timeout_seconds))
        self.recovery_timeout_seconds = max(0.1, float(self.recovery_timeout_seconds))
        self.busy_stall_seconds = max(1.0, float(self.busy_stall_seconds))
        self.restart_failure_threshold = max(5, int(self.restart_failure_threshold))
        if self.expected_pid is not None and (
            isinstance(self.expected_pid, bool) or int(self.expected_pid) <= 0
        ):
            raise ValueError("expected_pid must be a positive integer")


class SingleInstanceLock:
    """One-byte inter-process lock.  The lock file is never deleted."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle: Any | None = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError("internal_developer_service_already_running")
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


class InternalDeveloperService:
    """Collect, classify, safely recover, re-verify, and persist one cycle."""

    def __init__(
        self,
        *,
        repo_root: Path,
        store: object,
        engine: object,
        http_client: object,
        config: ServiceConfig | None = None,
        data_root: Path | None = None,
        registered_databases: Mapping[str, Path] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repo_root = Path(repo_root)
        # Both calls are intentional: the sidecar reports whether the shared,
        # account-independent path contract is valid, while active_data_root is
        # the sole authority for its durable state.
        self.runtime_root_contract = read_runtime_root_contract(self.repo_root)
        self.data_root = Path(data_root) if data_root is not None else active_data_root(self.repo_root)
        self.store = store
        self.engine = engine
        self.http = http_client
        self.config = config or ServiceConfig()
        self._clock = clock
        self.root = self.data_root / "internal_developer"
        self.state_path = self.root / "service_state.json"
        self.heartbeat_path = self.root / "service_heartbeat.json"
        # This is the launcher's single, exact restart-request contract.  Do not
        # create a second look-alike request under internal_developer/.
        self.restart_request_path = self.repo_root / "runtime" / "codexstock_restart_request.json"
        self.lock_path = (
            self.repo_root / "runtime" / "internal_developer" / "service.lock"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self._state, self._state_consistent = self._load_state()
        self._kis_reconnect_authorized = False
        self._research_retry_context: dict[str, dict[str, object]] = {}
        self._registered_databases = {
            str(key): Path(value)
            for key, value in (registered_databases or {}).items()
        }
        self._register_trusted_handlers()

    @staticmethod
    def _default_state() -> dict[str, object]:
        return {
            "schema": SERVICE_STATE_SCHEMA,
            "cycle_count": 0,
            "consecutive_nonbusy_http_failures": 0,
            "last_progress_signature": "",
            "last_progress_at_epoch": None,
            "improvement_busy": False,
            "research_retry_signatures": [],
            "transient_reverification": {},
            "telegram_alerted_incidents": {},
            "last_known_pid": None,
            "last_result": {},
            "updated_at": _utc_now(),
        }

    def _load_state(self) -> tuple[dict[str, object], bool]:
        if not self.state_path.exists():
            return self._default_state(), True
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default_state(), False
        if not isinstance(payload, dict) or payload.get("schema") != SERVICE_STATE_SCHEMA:
            return self._default_state(), False
        state = self._default_state()
        state.update(payload)
        retries = state.get("research_retry_signatures")
        if not isinstance(retries, list):
            state["research_retry_signatures"] = []
            return state, False
        state["research_retry_signatures"] = [str(item) for item in retries[-256:]]
        reverification = state.get("transient_reverification")
        legacy_reverification = state.get("liveness_reverification")
        if not reverification and isinstance(legacy_reverification, dict):
            reverification = legacy_reverification
        if not isinstance(reverification, dict):
            state["transient_reverification"] = {}
            return state, False
        state["transient_reverification"] = {
            str(key): dict(value)
            for key, value in list(reverification.items())[-256:]
            if isinstance(value, Mapping)
        }
        telegram_alerted = state.get("telegram_alerted_incidents")
        if not isinstance(telegram_alerted, dict):
            state["telegram_alerted_incidents"] = {}
            return state, False
        state["telegram_alerted_incidents"] = {
            str(key): dict(value)
            for key, value in list(telegram_alerted.items())[-256:]
            if isinstance(value, Mapping)
        }
        state.pop("liveness_reverification", None)
        return state, True

    def _persist_state(self) -> None:
        self._state["schema"] = SERVICE_STATE_SCHEMA
        self._state["updated_at"] = _utc_now()
        _atomic_write_json(self.state_path, self._state)

    def _register_trusted_handlers(self) -> None:
        if hasattr(self.engine, "register_named_cache"):
            self.engine.register_named_cache(
                "feature-health", self._force_feature_health, self._verify_feature_health
            )
        if hasattr(self.engine, "register_external_engine"):
            self.engine.register_external_engine(
                "kis-trading-mcp", self._reconnect_kis, self._verify_kis_reconnect
            )
        if hasattr(self.engine, "register_internal_state_ledger"):
            self.engine.register_internal_state_ledger(
                "internal-developer-ledger",
                self._rebuild_internal_ledger,
                self._verify_internal_ledger,
            )
        if hasattr(self.engine, "register_database"):
            for database_id, path in self._registered_databases.items():
                self.engine.register_database(database_id, path)

    def _coerce_response(self, value: object) -> HttpResponse:
        if isinstance(value, HttpResponse):
            return value
        if isinstance(value, tuple) and len(value) == 2:
            first, second = value
            if isinstance(first, int):
                return HttpResponse(first, _as_mapping(second))
            if isinstance(second, int):
                return HttpResponse(second, _as_mapping(first))
        if isinstance(value, Mapping):
            status_code = value.get("__status_code__", 200)
            return HttpResponse(int(status_code), dict(value))
        raise TypeError("HTTP client must return a mapping or HttpResponse")

    def _get(self, path: str, *, timeout: float) -> HttpResponse:
        method = getattr(self.http, "get")
        return self._coerce_response(method(path, timeout=timeout))

    def _post(
        self, path: str, payload: Mapping[str, object], *, timeout: float
    ) -> HttpResponse:
        method = getattr(self.http, "post")
        return self._coerce_response(method(path, dict(payload), timeout=timeout))

    @staticmethod
    def _require_ok(response: HttpResponse, method: str, path: str) -> dict[str, object]:
        if not response.ok:
            raise HttpRequestError(method, path, f"http_status_{response.status_code}")
        return dict(response.payload)

    def _recovery_get(self, path: str) -> HttpResponse:
        if path not in _RECOVERY_GET_PATHS:
            raise PermissionError("recovery_get_path_not_allowlisted")
        return self._get(path, timeout=self.config.recovery_timeout_seconds)

    def _recovery_post(
        self, path: str, payload: Mapping[str, object]
    ) -> HttpResponse:
        if path not in _RECOVERY_POST_PATHS:
            raise PermissionError("recovery_post_path_not_allowlisted")
        return self._post(path, payload, timeout=self.config.recovery_timeout_seconds)

    @staticmethod
    def _operational_broken_count(payload: Mapping[str, object]) -> int:
        direct = payload.get("operational_broken_count")
        if isinstance(direct, (int, float)) and not isinstance(direct, bool):
            return max(0, int(direct))
        counts = payload.get("operational_counts")
        if isinstance(counts, Mapping):
            broken = counts.get("broken")
            if isinstance(broken, (int, float)) and not isinstance(broken, bool):
                return max(0, int(broken))
        checks = payload.get("checks")
        if isinstance(checks, list):
            return sum(
                1
                for row in checks
                if isinstance(row, Mapping)
                and str(row.get("operational_state") or "").lower() == "broken"
            )
        return 0

    def _registered_database_lock_candidate(
        self, payload: Mapping[str, object]
    ) -> str | None:
        """Accept only an explicit lock signal bound to a registered DB ID."""

        candidates: list[Mapping[str, object]] = []
        top_level = payload.get("database_lock")
        if isinstance(top_level, Mapping):
            candidates.append(top_level)
        checks = payload.get("checks")
        if isinstance(checks, list):
            candidates.extend(row for row in checks if isinstance(row, Mapping))
        for row in candidates:
            operational_state = str(row.get("operational_state") or "").lower()
            metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
            database_id = str(
                row.get("database_id")
                or metadata.get("database_id")
                or ""
            )
            if database_id not in self._registered_databases:
                continue
            text = " ".join(
                str(row.get(key) or "")
                for key in ("id", "status", "detail", "status_reason", "error")
            ).lower()
            explicit_locked = row.get("locked") is True or metadata.get("locked") is True
            lock_word = any(token in text for token in ("database locked", "db locked", "sqlite locked", "sqlite_busy"))
            if explicit_locked or (operational_state == "broken" and lock_word):
                return database_id
        return None

    def _probe_registered_database_locks(self) -> str | None:
        """Return the first locked trusted SQLite ID using read-only access.

        The path never comes from HTTP, MCP, or advice.  Missing databases are
        skipped, and no WAL/SHM/lock file is removed.  ``PRAGMA schema_version``
        deliberately touches the database schema while remaining read-only;
        unlike ``SELECT 1`` it can actually surface an exclusive SQLite lock.
        """

        for database_id, raw_path in sorted(self._registered_databases.items()):
            path = Path(raw_path).resolve(strict=False)
            if not path.is_file():
                continue
            uri_path = quote(path.as_posix(), safe="/:~")
            try:
                connection = sqlite3.connect(
                    f"file:{uri_path}?mode=ro",
                    uri=True,
                    timeout=0.05,
                    isolation_level=None,
                )
                try:
                    connection.execute("PRAGMA query_only = ON")
                    connection.execute("PRAGMA schema_version").fetchone()
                finally:
                    connection.close()
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if "locked" in message or "busy" in message:
                    return database_id
                self._safe_store_event(
                    "database.readonly-probe-error",
                    {"database_id": database_id, **_safe_error(exc)},
                )
            except (OSError, sqlite3.Error) as exc:
                self._safe_store_event(
                    "database.readonly-probe-error",
                    {"database_id": database_id, **_safe_error(exc)},
                )
        return None

    def _force_feature_health(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        response = self._recovery_get(FEATURE_HEALTH_FORCE_PATH)
        return {
            "success": response.ok,
            "retryable": False,
            "status_code": response.status_code,
            "operational_broken_count": self._operational_broken_count(response.payload),
            "payload": response.payload,
        }

    def _verify_feature_health(
        self,
        result: object,
        parameters: dict[str, object],
        context: dict[str, object],
    ) -> dict[str, object]:
        row = _as_mapping(result)
        return {
            "ok": row.get("success") is True
            and int(row.get("operational_broken_count") or 0) == 0,
            "operational_broken_count": int(row.get("operational_broken_count") or 0),
        }

    @staticmethod
    def _is_safe_kis_engine(row: Mapping[str, object]) -> bool:
        policy = str(row.get("execution_policy") or "").lower()
        return bool(
            str(row.get("engine_id") or "").lower() == "kis-trading-mcp"
            and "resident" in policy
            and "read_only" in policy
            and row.get("live_order_allowed") is False
        )

    @staticmethod
    def _kis_connected(payload: Mapping[str, object]) -> bool:
        if isinstance(payload.get("connected"), bool):
            return payload.get("connected") is True
        engines = payload.get("engines")
        if isinstance(engines, list):
            for row in engines:
                if isinstance(row, Mapping) and str(row.get("engine_id") or "").lower() == "kis-trading-mcp":
                    return row.get("connected") is True
        return False

    def _reconnect_kis(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        if not self._kis_reconnect_authorized:
            return {
                "success": False,
                "retryable": False,
                "reason": "resident_read_only_kis_evidence_missing",
            }
        response = self._recovery_get(KIS_RECONNECT_PATH)
        return {
            "success": response.ok,
            "retryable": False,
            "status_code": response.status_code,
            "connected": self._kis_connected(response.payload),
            "live_order_allowed": False,
        }

    def _verify_kis_reconnect(
        self,
        result: object,
        parameters: dict[str, object],
        context: dict[str, object],
    ) -> dict[str, object]:
        row = _as_mapping(result)
        return {
            "ok": row.get("success") is True and row.get("connected") is True,
            "verified": "resident_read_only_kis_connected",
            "live_order_allowed": False,
        }

    def _rebuild_internal_ledger(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        method = getattr(self.store, "rebuild_state_ledger", None)
        if not callable(method):
            method = getattr(self.store, "rebuild_ledgers", None)
        if not callable(method):
            return {"success": False, "retryable": False, "reason": "ledger_rebuilder_missing"}
        rebuilt = method()
        self._state = self._default_state()
        self._state_consistent = True
        self._persist_state()
        return {"success": rebuilt is not False, "retryable": False, "rebuilt": True}

    def _verify_internal_ledger(
        self,
        result: object,
        parameters: dict[str, object],
        context: dict[str, object],
    ) -> dict[str, object]:
        row = _as_mapping(result)
        try:
            status = self.store.status() if hasattr(self.store, "status") else {}
            readable = isinstance(status, Mapping)
        except Exception:
            readable = False
        return {"ok": row.get("success") is True and readable and self._state_consistent}

    @staticmethod
    def _research_signature(payload: Mapping[str, object], status: str) -> str:
        state = payload.get("state") if isinstance(payload.get("state"), Mapping) else payload
        material = {
            "cycle_id": state.get("cycle_id"),
            "status": status,
            "finished_at": state.get("finished_at"),
            "phase": state.get("phase"),
            "error": str(state.get("error") or state.get("last_error") or "")[:300],
        }
        canonical = json.dumps(material, ensure_ascii=True, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _register_research_retry(
        self, job_id: str, signature: str, original_status: str
    ) -> None:
        self._research_retry_context[job_id] = {
            "signature": signature,
            "original_status": original_status,
        }
        if hasattr(self.engine, "register_research_job"):
            self.engine.register_research_job(
                job_id, self._retry_research_job, self._verify_research_retry
            )

    def _retry_research_job(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        job_id = str(parameters.get("job_id") or "")
        retry = self._research_retry_context.get(job_id)
        if not retry or retry.get("original_status") not in _RETRYABLE_RESEARCH_STATES:
            return {"success": False, "retryable": False, "reason": "research_retry_not_authorized"}
        signature = str(retry["signature"])
        attempted = {str(item) for item in self._state.get("research_retry_signatures", [])}
        if signature in attempted:
            return {"success": False, "retryable": False, "reason": "research_retry_already_attempted"}
        # Persist before the call: a timeout has an unknown outcome and must not
        # be submitted a second time.
        attempted.add(signature)
        self._state["research_retry_signatures"] = sorted(attempted)[-256:]
        self._persist_state()
        response = self._recovery_post(
            IMPROVEMENT_RETRY_PATH,
            {
                "requested_by": "internal-developer-operational-recovery",
                "research_only": True,
                "live_order_allowed": False,
            },
        )
        response_status = str(response.payload.get("status") or "").upper()
        accepted = response.ok or (
            response.status_code == 409 and response_status == "ALREADY_RUNNING"
        )
        return {
            "success": accepted,
            "retryable": False,
            "status_code": response.status_code,
            "status": response_status,
            "research_only": True,
            "live_order_allowed": False,
        }

    @staticmethod
    def _verify_research_retry(
        result: object,
        parameters: dict[str, object],
        context: dict[str, object],
    ) -> dict[str, object]:
        row = _as_mapping(result)
        return {
            "ok": row.get("success") is True
            and row.get("research_only") is True
            and row.get("live_order_allowed") is False,
            "verified": "one_research_only_retry_submitted",
        }

    def _safe_store_event(self, event_type: str, payload: Mapping[str, object]) -> None:
        if not hasattr(self.store, "record_event"):
            return
        try:
            self.store.record_event(event_type, dict(payload))
        except Exception:
            pass

    def _store_ledger_consistent(self) -> bool:
        if not self._state_consistent:
            return False
        if not hasattr(self.store, "status"):
            return True
        try:
            status = self.store.status()
        except Exception:
            return False
        explicit = _dig(
            status,
            "ledger_consistent",
            "consistent",
            "ledger.consistent",
            "integrity.ok",
        )
        if explicit is False:
            return False
        ledger_status = str(_dig(status, "ledger.status", "integrity.status") or "").lower()
        return ledger_status not in {"corrupt", "corrupted", "inconsistent", "invalid"}

    def _fallback_report(
        self,
        classification: str,
        summary: str,
        evidence: Mapping[str, object],
    ) -> dict[str, object]:
        diagnostic = {
            "schema_version": "codexstock.internal-developer.diagnostic.v1",
            "classification": str(classification),
            "component": "internal-developer-service",
            "severity": "high",
            "summary": str(summary)[:500],
            "evidence": dict(evidence),
            "execution_authorized": False,
        }
        try:
            opened = self.store.open_incident(diagnostic)
            incident_id = (
                str(opened)
                if isinstance(opened, str)
                else str(_dig(opened, "incident_id", "id") or "")
            )
            if hasattr(self.store, "transition_incident"):
                self.store.transition_incident(
                    incident_id,
                    "NEEDS_EXTERNAL_ADVICE",
                    note="Sidecar report-only fallback; no mutation executed.",
                )
            report = self.store.write_report(
                incident_id,
                {
                    "classification": classification,
                    "summary": summary,
                    "evidence": dict(evidence),
                    "needs_external_advice": True,
                    "execution_authorized": False,
                },
            )
            return {
                "status": "needs_external_advice",
                "incident_id": incident_id,
                "report": report,
                "engine_error": True,
            }
        except Exception as exc:
            return {
                "status": "report_persistence_failed",
                "incident_id": None,
                "engine_error": True,
                **_safe_error(exc),
            }

    def _engine_cycle(
        self, observation: Mapping[str, object], *, auto_recover: bool
    ) -> dict[str, object]:
        try:
            result = self.engine.run_cycle(dict(observation), auto_recover=auto_recover)
            if not isinstance(result, Mapping):
                raise TypeError("engine result must be a mapping")
            return dict(result)
        except Exception as exc:
            return self._fallback_report(
                str(observation.get("classification") or observation.get("status") or "UNKNOWN_FAILURE"),
                "The deterministic engine cycle failed; the sidecar remained alive.",
                {"observation": dict(observation), **_safe_error(exc)},
            )

    def _process_one_pending_advice(self) -> dict[str, object] | None:
        """Apply at most one structured advice record through local policy.

        GPT text is never interpreted.  A stored record merely proposes exact
        action objects; the deterministic engine validates them again and can
        reach only handlers registered by this process.  Restart remains an
        automatic liveness decision and is never accepted from external
        advice, even though the automatic engine can request one after five
        confirmed non-busy failures.
        """

        list_advice = getattr(self.store, "list_advice", None)
        get_incident = getattr(self.store, "get_incident", None)
        update_advice = getattr(self.store, "update_advice", None)
        transition = getattr(self.store, "transition_incident", None)
        execute_advice = getattr(self.engine, "execute_advice", None)
        if not all(callable(item) for item in (list_advice, get_incident, update_advice, transition, execute_advice)):
            return None

        try:
            records = list_advice(limit=25)
        except Exception as exc:
            self._safe_store_event("advice.scan-failed", _safe_error(exc))
            return None
        if not isinstance(records, list):
            return None

        for record in records:
            if not isinstance(record, Mapping) or str(record.get("status") or "").upper() != "RECEIVED":
                continue
            evaluation = record.get("policy_evaluation")
            if isinstance(evaluation, Mapping) and evaluation.get("quarantined") is True:
                continue
            advice_id = str(record.get("advice_id") or "")
            incident_id = str(record.get("incident_id") or "")
            try:
                incident = get_incident(incident_id)
            except Exception as exc:
                update_advice(
                    advice_id,
                    {
                        "status": "REJECTED",
                        "review_note": "Incident lookup failed; no action was executed.",
                        "application_result": {"executed": False, **_safe_error(exc)},
                    },
                )
                return {
                    "status": "external_advice_rejected",
                    "classification": "EXTERNAL_ADVICE_REJECTED",
                    "incident_id": incident_id or None,
                    "advice_id": advice_id,
                    "execution_authorized": False,
                    "auto_recovery_executed": False,
                    "restart_requested": False,
                }
            if not isinstance(incident, Mapping) or str(incident.get("state") or "") != "ADVICE_RECEIVED":
                continue

            advice_payload = record.get("advice")
            proposed = (
                advice_payload.get("proposed_actions", [])
                if isinstance(advice_payload, Mapping)
                else []
            )
            if not isinstance(proposed, list):
                proposed = []
            locally_allowed: list[object] = []
            locally_rejected: list[dict[str, object]] = []
            for index, proposal in enumerate(proposed[:8]):
                action_name = (
                    str(proposal.get("action") or "").upper()
                    if isinstance(proposal, Mapping)
                    else ""
                )
                if action_name in _ADVICE_NEVER_AUTOMATES:
                    locally_rejected.append(
                        {
                            "index": index,
                            "status": "rejected",
                            "accepted": False,
                            "reason_code": "external_advice_restart_forbidden",
                            "executed": False,
                        }
                    )
                else:
                    locally_allowed.append(proposal)

            if not locally_allowed:
                transition(
                    incident_id,
                    "NEEDS_CODE_FIX",
                    note="External advice contained no locally executable structured recovery action.",
                    metadata={"advice_id": advice_id, "execution_authorized": False},
                )
                application = {
                    "executed": False,
                    "text_ignored": True,
                    "results": locally_rejected,
                    "reason_code": "no_locally_allowed_structured_action",
                }
                update_advice(
                    advice_id,
                    {
                        "status": "REJECTED",
                        "review_note": "No locally allowed structured action; free text was ignored.",
                        "application_result": application,
                    },
                )
                return {
                    "status": "external_advice_rejected",
                    "classification": "EXTERNAL_ADVICE_REJECTED",
                    "incident_id": incident_id,
                    "advice_id": advice_id,
                    "results": locally_rejected,
                    "execution_authorized": False,
                    "auto_recovery_executed": False,
                    "restart_requested": False,
                }

            transition(
                incident_id,
                "AUTO_RECOVERING",
                note="Structured external guidance entered deterministic local policy review.",
                metadata={"advice_id": advice_id, "execution_authorized": False},
            )
            try:
                engine_result = execute_advice(
                    incident_id,
                    {"proposed_actions": locally_allowed},
                    advice_id=advice_id,
                )
                engine_results = (
                    list(engine_result.get("results", []))
                    if isinstance(engine_result, Mapping)
                    and isinstance(engine_result.get("results"), list)
                    else []
                )
                results = locally_rejected + engine_results
                evaluated = [row for row in engine_results if isinstance(row, Mapping)]
                executed = [row for row in evaluated if row.get("executed") is True]
                policy_success = bool(evaluated) and all(
                    str(row.get("status") or "") in {"succeeded", "idempotent_replay"}
                    for row in evaluated
                )
                repair_actions = {
                    "CLEAR_NAMED_CACHE",
                    "RECONNECT_EXTERNAL_ENGINE",
                    "RETRY_RESEARCH_JOB",
                    "RESTORE_INTERNAL_STATE_LEDGER",
                }
                repair_results = [
                    row for row in evaluated if str(row.get("action") or "") in repair_actions
                ]
                unresolved_database_lock = any(
                    str(row.get("action") or "") == "DETECT_DB_LOCK"
                    and isinstance(row.get("handler_result"), Mapping)
                    and row.get("handler_result", {}).get("locked") is True
                    for row in evaluated
                )
                recovered = bool(repair_results) and policy_success and not unresolved_database_lock
                final_state = (
                    "RECOVERED_UNREVIEWED"
                    if recovered
                    else "NEEDS_CODE_FIX"
                    if policy_success
                    else "RECOVERY_FAILED"
                )
                transition(
                    incident_id,
                    final_state,
                    note="External guidance was evaluated and re-verified by local policy.",
                    metadata={"advice_id": advice_id, "execution_authorized": False},
                )
                application = {
                    "executed": bool(executed),
                    "success": policy_success,
                    "recovered": recovered,
                    "text_ignored": True,
                    "results": results,
                }
                update_advice(
                    advice_id,
                    {
                        "status": "ACCEPTED_AS_GUIDANCE" if policy_success else "REJECTED",
                        "review_note": "Evaluated by deterministic local policy; advice itself had no authority.",
                        "application_result": application,
                    },
                )
                if hasattr(self.store, "write_report"):
                    self.store.write_report(
                        incident_id,
                        {
                            "status": (
                                "recovered_from_external_guidance"
                                if recovered
                                else "external_guidance_recorded"
                                if policy_success
                                else "external_guidance_failed"
                            ),
                            "source": "gpt_via_mcp",
                            "advice_id": advice_id,
                            "execution_authorized": False,
                            "text_ignored": True,
                            "recovery_results": results,
                            "needs_external_advice": not recovered,
                        },
                    )
                return {
                    "status": (
                        "recovered_from_external_guidance"
                        if recovered
                        else "external_advice_recorded"
                        if policy_success
                        else "external_advice_recovery_failed"
                    ),
                    "classification": "EXTERNAL_ADVICE_POLICY_REVIEW",
                    "incident_id": incident_id,
                    "advice_id": advice_id,
                    "results": results,
                    "execution_authorized": False,
                    "auto_recovery_executed": bool(executed),
                    "restart_requested": False,
                }
            except Exception as exc:
                try:
                    transition(
                        incident_id,
                        "RECOVERY_FAILED",
                        note="External guidance policy review failed closed.",
                        metadata={"advice_id": advice_id, **_safe_error(exc)},
                    )
                except Exception:
                    pass
                update_advice(
                    advice_id,
                    {
                        "status": "REJECTED",
                        "review_note": "Policy review failed closed; no further action was attempted.",
                        "application_result": {"executed": False, **_safe_error(exc)},
                    },
                )
                return {
                    "status": "external_advice_recovery_failed",
                    "classification": "EXTERNAL_ADVICE_POLICY_REVIEW",
                    "incident_id": incident_id,
                    "advice_id": advice_id,
                    "execution_authorized": False,
                    "auto_recovery_executed": False,
                    "restart_requested": False,
                    **_safe_error(exc),
                }
        return None

    def _finish(self, result: Mapping[str, object], *, phase: str = "idle") -> dict[str, object]:
        final = dict(result)
        cycle_count = int(self._state.get("cycle_count") or 0) + 1
        previous_result = (
            dict(self._state.get("last_result", {}))
            if isinstance(self._state.get("last_result"), Mapping)
            else {}
        )
        self._state["cycle_count"] = cycle_count
        self._state["last_result"] = {
            "status": final.get("status"),
            "classification": final.get("classification"),
            "incident_id": final.get("incident_id"),
            "at": _utc_now(),
        }
        telegram_alert = self._queue_one_urgent_telegram_report()
        if telegram_alert is not None:
            final["telegram_alert"] = telegram_alert
        self._persist_state()
        heartbeat = {
            "schema": SERVICE_HEARTBEAT_SCHEMA,
            "service": "internal-developer",
            "pid": os.getpid(),
            "cycle_count": cycle_count,
            "phase": phase,
            "status": final.get("status", "unknown"),
            "classification": final.get("classification"),
            "consecutive_nonbusy_http_failures": int(
                self._state.get("consecutive_nonbusy_http_failures") or 0
            ),
            "runtime_root_contract_valid": self.runtime_root_contract.get("valid") is True,
            "updated_at": _utc_now(),
            "live_order_allowed": False,
        }
        _atomic_write_json(self.heartbeat_path, heartbeat)
        # The current heartbeat already has a stable single-file location.
        # Keep the immutable audit trail bounded: record startup, state changes,
        # and one hourly checkpoint instead of creating 525,600 files per year.
        state_changed = (
            previous_result.get("status") != heartbeat["status"]
            or previous_result.get("classification") != heartbeat["classification"]
        )
        if cycle_count == 1 or state_changed or cycle_count % 60 == 0:
            self._safe_store_event("service.heartbeat", heartbeat)
        final.setdefault("service_schema", SERVICE_SCHEMA)
        final.setdefault("heartbeat", heartbeat)
        return final

    @staticmethod
    def _telegram_report_text(
        incident: Mapping[str, object], report: Mapping[str, object]
    ) -> str:
        payload = report.get("payload") if isinstance(report.get("payload"), Mapping) else {}

        def clean(value: object, limit: int = 600) -> str:
            if isinstance(value, (list, tuple)):
                value = "; ".join(str(item) for item in value[:8])
            elif isinstance(value, Mapping):
                value = json.dumps(dict(value), ensure_ascii=False, default=str)
            return str(value or "-").replace("\r", " ").replace("\n", " ")[:limit]

        return "\n".join(
            [
                "[긴급] 코덱스스톡 내부 개발자 보고",
                "자동 복구가 끝나지 않아 대표 확인이 필요합니다.",
                f"장애: {clean(incident.get('classification'), 120)}",
                f"구성요소: {clean(incident.get('component'), 160)}",
                f"상태: {clean(incident.get('state'), 80)} / 심각도 {clean(incident.get('severity'), 40)}",
                f"내용: {clean(incident.get('summary'))}",
                f"원인: {clean(payload.get('cause'))}",
                f"다음 조치: {clean(payload.get('next_step'))}",
                f"사건 ID: {clean(incident.get('incident_id'), 120)}",
                f"보고서 ID: {clean(report.get('report_id'), 120)}",
                "실전 주문·보안 설정·코드 자동 수정 권한은 없습니다.",
            ]
        )[:3500]

    def _queue_one_urgent_telegram_report(self) -> dict[str, object] | None:
        list_reports = getattr(self.store, "list_reports", None)
        get_incident = getattr(self.store, "get_incident", None)
        if not callable(list_reports) or not callable(get_incident):
            return None
        alerted_raw = self._state.get("telegram_alerted_incidents")
        alerted = dict(alerted_raw) if isinstance(alerted_raw, Mapping) else {}
        try:
            reports = list_reports(limit=50)
        except Exception as exc:
            self._safe_store_event("telegram.report-scan-failed", _safe_error(exc))
            return None
        if not isinstance(reports, list):
            return None
        urgent_states = {"RECOVERY_FAILED", "NEEDS_EXTERNAL_ADVICE", "NEEDS_CODE_FIX"}
        terminal_states = {"RECOVERED_UNREVIEWED", "REVIEWED", "CLOSED"}
        for report in reports:
            if not isinstance(report, Mapping):
                continue
            incident_id = str(report.get("incident_id") or "")
            report_id = str(report.get("report_id") or "")
            if not incident_id or not report_id or incident_id in alerted:
                continue
            try:
                incident = get_incident(incident_id)
            except Exception as exc:
                self._safe_store_event(
                    "telegram.incident-read-failed",
                    {"incident_id": incident_id, **_safe_error(exc)},
                )
                continue
            if not isinstance(incident, Mapping):
                continue
            payload = report.get("payload") if isinstance(report.get("payload"), Mapping) else {}
            state = str(incident.get("state") or "").upper()
            severity = str(incident.get("severity") or "").lower()
            if state in terminal_states:
                continue
            urgent = bool(
                state in urgent_states
                or payload.get("needs_external_advice") is True
                or severity in {"critical", "emergency"}
            )
            if not urgent:
                continue
            text = self._telegram_report_text(incident, report)
            try:
                response = self._post(
                    TELEGRAM_QUEUE_PATH,
                    {
                        "text": text,
                        "message_type": "internal_developer_urgent",
                        "source": "internal-developer-service",
                        "metadata": {
                            "incident_id": incident_id,
                            "report_id": report_id,
                            "single_delivery": True,
                            "single_delivery_id": incident_id,
                        },
                    },
                    timeout=self.config.overview_timeout_seconds,
                )
            except Exception as exc:
                self._safe_store_event(
                    "telegram.alert-queue-failed",
                    {"incident_id": incident_id, "report_id": report_id, **_safe_error(exc)},
                )
                return {"queued": False, "retry_next_cycle": True, "report_id": report_id}
            record = response.payload.get("record") if isinstance(response.payload.get("record"), Mapping) else {}
            queue_status = str(record.get("status") or "").lower()
            accepted = response.ok and queue_status in {"queued", "deduped", "sent"}
            if not accepted:
                self._safe_store_event(
                    "telegram.alert-not-accepted",
                    {
                        "incident_id": incident_id,
                        "report_id": report_id,
                        "status_code": response.status_code,
                        "queue_status": queue_status,
                    },
                )
                return {
                    "queued": False,
                    "retry_next_cycle": True,
                    "report_id": report_id,
                    "queue_status": queue_status,
                }
            alerted[incident_id] = {
                "report_id": report_id,
                "queued_at": _utc_now(),
                "queue_status": queue_status,
                "outbox_id": record.get("id"),
            }
            self._state["telegram_alerted_incidents"] = dict(list(alerted.items())[-256:])
            self._safe_store_event(
                "telegram.alert-queued",
                {
                    "incident_id": incident_id,
                    "report_id": report_id,
                    "outbox_id": record.get("id"),
                    "single_delivery": True,
                },
            )
            return {
                "queued": True,
                "single_delivery": True,
                "incident_id": incident_id,
                "report_id": report_id,
                "outbox_id": record.get("id"),
            }
        return None

    def _progress_state(
        self, payload: Mapping[str, object], now: float
    ) -> dict[str, object]:
        state = payload.get("state") if isinstance(payload.get("state"), Mapping) else payload
        status = str(state.get("status") or payload.get("status") or "").upper()
        busy = bool(
            status in _ACTIVE_IMPROVEMENT_STATES
            or payload.get("thread_alive") is True
            or payload.get("heavy_research_lock_active") is True
        )
        material = {
            "cycle_id": state.get("cycle_id"),
            "status": status,
            "phase": state.get("phase"),
            "phase_index": state.get("phase_index"),
            "progress_pct": state.get("progress_pct"),
            "updated_at": state.get("updated_at"),
        }
        signature = hashlib.sha256(
            json.dumps(material, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        prior_signature = str(self._state.get("last_progress_signature") or "")
        if busy and signature != prior_signature:
            self._state["last_progress_signature"] = signature
            self._state["last_progress_at_epoch"] = now
        last_progress = self._state.get("last_progress_at_epoch")
        if not isinstance(last_progress, (int, float)) or isinstance(last_progress, bool):
            last_progress = now
            if busy:
                self._state["last_progress_at_epoch"] = now
        progress_age = max(0.0, now - float(last_progress))
        self._state["improvement_busy"] = busy
        self._state["improvement_status"] = status
        return {
            "busy": busy,
            "status": status,
            "signature": signature,
            "progress_age_seconds": round(progress_age, 3),
            "stalled": busy and progress_age > self.config.busy_stall_seconds,
            "state": dict(state),
        }

    def _cached_busy_state(self, now: float) -> dict[str, object]:
        busy = self._state.get("improvement_busy") is True
        last_progress = self._state.get("last_progress_at_epoch")
        age = (
            max(0.0, now - float(last_progress))
            if isinstance(last_progress, (int, float)) and not isinstance(last_progress, bool)
            else float("inf")
        )
        return {
            "busy": busy,
            "progress_age_seconds": age,
            "stalled": busy and age > self.config.busy_stall_seconds,
        }

    @staticmethod
    def _extract_pid(payload: Mapping[str, object]) -> int | None:
        value = _dig(
            payload,
            "app.pid",
            "runtime.pid",
            "runtime_pid",
            "process_id",
            "pid",
        )
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return None

    def _expected_pid(self) -> int | None:
        if self.config.expected_pid is not None:
            return int(self.config.expected_pid)
        value = self._state.get("last_known_pid")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return None

    def _reset_transient_reverification(self) -> None:
        raw = self._state.get("transient_reverification")
        if not isinstance(raw, Mapping):
            self._state["transient_reverification"] = {}
            return
        reset: dict[str, dict[str, object]] = {}
        for incident_id, value in raw.items():
            if not isinstance(value, Mapping):
                continue
            row = dict(value)
            row["consecutive_healthy_cycles"] = 0
            row["last_reset_at"] = _utc_now()
            reset[str(incident_id)] = row
        self._state["transient_reverification"] = reset

    @staticmethod
    def _restart_expected_pid(incident: Mapping[str, object]) -> int | None:
        attempts = incident.get("recovery_attempts")
        if not isinstance(attempts, list):
            return None
        for attempt in reversed(attempts):
            if not isinstance(attempt, Mapping):
                continue
            if str(attempt.get("action") or "") != "REQUEST_CODEXSTOCK_RESTART":
                continue
            if str(attempt.get("status") or "") != "succeeded":
                continue
            parameters = attempt.get("parameters")
            expected_pid = (
                parameters.get("expected_pid") if isinstance(parameters, Mapping) else None
            )
            if (
                isinstance(expected_pid, int)
                and not isinstance(expected_pid, bool)
                and expected_pid > 0
            ):
                return expected_pid
        return None

    def _reconcile_recovered_transient_incidents(
        self, *, current_pid: int | None
    ) -> list[str]:
        """Close stale liveness incidents only after a complete healthy cycle.

        A one-off observation needs one full read-only health cycle.  If the
        incident ever requested a restart, three consecutive healthy cycles are
        required because the launcher may either restart the process or observe
        that the original process recovered.  No process action is performed
        here; this updates only the internal developer's own incident ledger.
        """

        list_incidents = getattr(self.store, "list_incidents", None)
        transition = getattr(self.store, "transition_incident", None)
        if not callable(list_incidents) or not callable(transition):
            return []
        try:
            incidents = list_incidents(limit=500)
        except Exception as exc:
            self._safe_store_event("transient.reverification-scan-failed", _safe_error(exc))
            return []
        if not isinstance(incidents, list):
            return []

        raw_trackers = self._state.get("transient_reverification")
        trackers = dict(raw_trackers) if isinstance(raw_trackers, Mapping) else {}
        active_ids: set[str] = set()
        recovered: list[str] = []
        for incident in incidents:
            if not isinstance(incident, Mapping):
                continue
            incident_id = str(incident.get("incident_id") or "")
            classification = str(incident.get("classification") or "").upper()
            state = str(incident.get("state") or "").upper()
            if (
                not incident_id
                or classification not in _TRANSIENT_REVERIFIABLE_CLASSIFICATIONS
                or state not in _TRANSIENT_REVERIFIABLE_STATES
            ):
                continue
            active_ids.add(incident_id)
            expected_pid = self._restart_expected_pid(incident)
            # The independent launcher owns this request.  Its mere existence,
            # including a malformed file, is a fail-closed reason not to claim
            # that restart recovery has completed and not to touch the file.
            if expected_pid is not None and self.restart_request_path.exists():
                trackers[incident_id] = {
                    "classification": classification,
                    "consecutive_healthy_cycles": 0,
                    "required_healthy_cycles": 3,
                    "expected_pre_recovery_pid": expected_pid,
                    "pending_restart_request": True,
                    "last_verified_at": _utc_now(),
                }
                continue
            if expected_pid is not None and current_pid is None:
                trackers[incident_id] = {
                    "classification": classification,
                    "consecutive_healthy_cycles": 0,
                    "required_healthy_cycles": 3,
                    "expected_pre_recovery_pid": expected_pid,
                    "pending_restart_request": False,
                    "current_pid_known": False,
                    "last_verified_at": _utc_now(),
                }
                continue
            required_cycles = 3 if expected_pid is not None else 1
            prior = trackers.get(incident_id)
            prior_count = (
                int(prior.get("consecutive_healthy_cycles") or 0)
                if isinstance(prior, Mapping)
                else 0
            )
            healthy_cycles = prior_count + 1
            pid_changed = bool(
                expected_pid is not None
                and current_pid is not None
                and current_pid != expected_pid
            )
            recovery_basis = (
                "restart_verified_by_pid_change"
                if pid_changed
                else "service_restored_without_verified_restart"
                if expected_pid is not None
                else "transient_liveness_restored"
            )
            verification = {
                "classification": classification,
                "consecutive_healthy_cycles": healthy_cycles,
                "required_healthy_cycles": required_cycles,
                "current_pid": current_pid,
                "expected_pre_recovery_pid": expected_pid,
                "pid_changed": pid_changed,
                "restart_verified": pid_changed,
                "recovery_basis": recovery_basis,
                "last_verified_at": _utc_now(),
            }
            trackers[incident_id] = verification
            if healthy_cycles < required_cycles:
                continue
            try:
                transition(
                    incident_id,
                    "RECOVERED_UNREVIEWED",
                    note="The liveness fault cleared and bounded read-only health checks passed.",
                    metadata={
                        "verification": "consecutive_full_readonly_health_cycles",
                        "healthy_cycles": healthy_cycles,
                        "required_cycles": required_cycles,
                        "pid_changed": pid_changed,
                        "restart_verified": pid_changed,
                        "recovery_basis": recovery_basis,
                        "execution_authorized": False,
                    },
                )
            except Exception as exc:
                self._safe_store_event(
                    "transient.reverification-transition-failed",
                    {"incident_id": incident_id, **_safe_error(exc)},
                )
                continue
            write_report = getattr(self.store, "write_report", None)
            if callable(write_report):
                try:
                    write_report(
                        incident_id,
                        {
                            "status": "recovered_after_transient_reverification",
                            "cause": classification,
                            "actions": ["No process mutation; observed responsiveness recovery."],
                            "verification": verification,
                            "next_step": "Human or GPT review of the retained incident report.",
                            "needs_external_advice": False,
                            "execution_authorized": False,
                            "execution_performed": False,
                            "live_order_allowed": False,
                        },
                    )
                except Exception as exc:
                    self._safe_store_event(
                        "transient.reverification-report-failed",
                        {"incident_id": incident_id, **_safe_error(exc)},
                    )
            self._safe_store_event(
                "transient.reverified",
                {"incident_id": incident_id, **verification},
            )
            recovered.append(incident_id)
            trackers.pop(incident_id, None)

        self._state["transient_reverification"] = {
            key: value
            for key, value in trackers.items()
            if key in active_ids and isinstance(value, Mapping)
        }
        return recovered

    def _atomic_restart_fallback(
        self, expected_pid: int, incident_id: str | None, reason: str
    ) -> dict[str, object]:
        payload = {
            "schema": "codexstock.restart-request.v1",
            "request_id": "RST-" + uuid.uuid4().hex.upper(),
            "incident_id": incident_id,
            "expected_pid": expected_pid,
            "reason": reason,
            "requested_at": _utc_now(),
            "requested": True,
            "execution_performed": False,
            "scheduler_authority_required": True,
            "source": "internal-developer-service-fallback",
        }
        _atomic_write_json(self.restart_request_path, payload)
        self._safe_store_event("restart.requested", payload)
        return payload

    def _handle_unreachable(self, exc: BaseException, now: float) -> dict[str, object]:
        # A failed overview probe breaks any pending "consecutive healthy"
        # liveness verification streak.
        self._reset_transient_reverification()
        cached_busy = self._cached_busy_state(now)
        if cached_busy["busy"] and not cached_busy["stalled"]:
            self._state["consecutive_nonbusy_http_failures"] = 0
            self._safe_store_event(
                "service.busy-progressing",
                {"progress_age_seconds": cached_busy["progress_age_seconds"], **_safe_error(exc)},
            )
            return {
                "status": "busy_progressing",
                "classification": "BUSY_PROGRESSING",
                "auto_recovery_executed": False,
                "restart_requested": False,
                "progress_age_seconds": cached_busy["progress_age_seconds"],
            }
        if cached_busy["stalled"]:
            self._state["consecutive_nonbusy_http_failures"] = 0
            result = self._engine_cycle(
                {
                    "classification": "BUSY_STALLED",
                    "busy": True,
                    "busy_stalled": True,
                    "progress_age_seconds": cached_busy["progress_age_seconds"],
                    "heartbeat_missing": True,
                    "status": "degraded",
                    "http_error": _safe_error(exc),
                },
                auto_recover=False,
            )
            return {
                **result,
                "status": "busy_stalled_reported",
                "classification": "BUSY_STALLED",
                "auto_recovery_executed": False,
                "restart_requested": False,
            }

        failures = int(self._state.get("consecutive_nonbusy_http_failures") or 0) + 1
        self._state["consecutive_nonbusy_http_failures"] = failures
        threshold_reached = failures >= self.config.restart_failure_threshold
        expected_pid = self._expected_pid()
        observation: dict[str, object] = {
            "classification": "HEARTBEAT_MISSING",
            "heartbeat_missing": True,
            "heartbeat_age_seconds": failures * self.config.interval_seconds,
            "status": "degraded",
            "http_error": _safe_error(exc),
            "nonbusy_http_failure_count": failures,
        }
        if threshold_reached and expected_pid is not None:
            observation["expected_pid"] = expected_pid
        result = self._engine_cycle(
            observation,
            auto_recover=bool(threshold_reached and expected_pid is not None),
        )
        restart_requested = result.get("status") == "restart_requested"
        if (
            threshold_reached
            and expected_pid is not None
            and result.get("engine_error") is True
            and not restart_requested
        ):
            restart = self._atomic_restart_fallback(
                expected_pid,
                str(result.get("incident_id") or "") or None,
                "five_consecutive_nonbusy_http_failures",
            )
            result["restart_request"] = restart
            restart_requested = True
        return {
            **result,
            "status": "restart_requested" if restart_requested else "app_unreachable_reported",
            "classification": "HEARTBEAT_MISSING",
            "consecutive_nonbusy_http_failures": failures,
            "restart_threshold": self.config.restart_failure_threshold,
            "restart_requested": restart_requested,
            "restart_deferred_missing_pid": bool(threshold_reached and expected_pid is None),
        }

    def _diagnostic_failure(self, exc: BaseException) -> dict[str, object]:
        self._reset_transient_reverification()
        result = self._engine_cycle(
            {
                "classification": "DIAGNOSTIC_ENDPOINT_UNAVAILABLE",
                "status": "degraded",
                "abnormal": True,
                "summary": "A read-only diagnostic endpoint was unavailable.",
                "http_error": _safe_error(exc),
            },
            auto_recover=False,
        )
        return {
            **result,
            "status": "diagnostic_endpoint_reported",
            "classification": "DIAGNOSTIC_ENDPOINT_UNAVAILABLE",
            "auto_recovery_executed": False,
            "restart_requested": False,
        }

    def run_once(self) -> dict[str, object]:
        """Run exactly one bounded observation/recovery cycle."""

        now = float(self._clock())
        try:
            if not self._store_ledger_consistent():
                result = self._engine_cycle(
                    {
                        "classification": "INTERNAL_STATE_LEDGER_INCONSISTENT",
                        "internal_ledger_consistent": False,
                        "ledger_id": "internal-developer-ledger",
                    },
                    auto_recover=True,
                )
                return self._finish(
                    {**result, "classification": "INTERNAL_STATE_LEDGER_INCONSISTENT"},
                    phase="ledger-recovery",
                )

            try:
                overview_response = self._get(
                    OVERVIEW_PATH, timeout=self.config.overview_timeout_seconds
                )
                overview = self._require_ok(overview_response, "GET", OVERVIEW_PATH)
            except Exception as exc:
                return self._finish(self._handle_unreachable(exc, now), phase="unreachable")

            self._state["consecutive_nonbusy_http_failures"] = 0
            pid = self._extract_pid(overview)
            try:
                resources = self._require_ok(
                    self._get(
                        SYSTEM_RESOURCES_PATH,
                        timeout=self.config.overview_timeout_seconds,
                    ),
                    "GET",
                    SYSTEM_RESOURCES_PATH,
                )
                pid = self._extract_pid(resources) or pid
            except Exception:
                pass
            if pid is not None:
                self._state["last_known_pid"] = pid

            try:
                improvement = self._require_ok(
                    self._get(
                        IMPROVEMENT_STATUS_PATH,
                        timeout=self.config.diagnostic_timeout_seconds,
                    ),
                    "GET",
                    IMPROVEMENT_STATUS_PATH,
                )
                progress = self._progress_state(improvement, now)
            except Exception as exc:
                return self._finish(self._diagnostic_failure(exc), phase="diagnosing")

            if progress["busy"] and not progress["stalled"]:
                self._safe_store_event(
                    "service.busy-progressing",
                    {
                        "progress_age_seconds": progress["progress_age_seconds"],
                        "improvement_status": progress["status"],
                    },
                )
                return self._finish(
                    {
                        "status": "busy_progressing",
                        "classification": "BUSY_PROGRESSING",
                        "auto_recovery_executed": False,
                        "restart_requested": False,
                        "progress": progress,
                    },
                    phase="busy",
                )
            if progress["stalled"]:
                result = self._engine_cycle(
                    {
                        "classification": "BUSY_STALLED",
                        "busy": True,
                        "busy_stalled": True,
                        "progress_age_seconds": progress["progress_age_seconds"],
                        "status": "degraded",
                        "improvement_loop": progress["state"],
                    },
                    auto_recover=False,
                )
                return self._finish(
                    {
                        **result,
                        "status": "busy_stalled_reported",
                        "classification": "BUSY_STALLED",
                        "auto_recovery_executed": False,
                        "restart_requested": False,
                    },
                    phase="stalled",
                )

            try:
                feature_health = self._require_ok(
                    self._get(
                        FEATURE_HEALTH_PATH,
                        timeout=self.config.diagnostic_timeout_seconds,
                    ),
                    "GET",
                    FEATURE_HEALTH_PATH,
                )
                external_status = self._require_ok(
                    self._get(
                        EXTERNAL_ENGINE_STATUS_PATH,
                        timeout=self.config.diagnostic_timeout_seconds,
                    ),
                    "GET",
                    EXTERNAL_ENGINE_STATUS_PATH,
                )
            except Exception as exc:
                return self._finish(self._diagnostic_failure(exc), phase="diagnosing")

            broken_count = self._operational_broken_count(feature_health)
            observation: dict[str, object] = {
                "status": "healthy",
                "heartbeat_ok": True,
                "cache_valid": broken_count == 0,
                "cache_id": "feature-health",
                "operational_broken_count": broken_count,
                # Delayed and verification-pending are evidence, not faults.
                "delayed_count": int(feature_health.get("delayed_count") or 0),
                "verification_pending_count": int(
                    feature_health.get("verification_pending_count") or 0
                ),
            }
            database_id = self._registered_database_lock_candidate(feature_health)
            if database_id is None:
                database_id = self._probe_registered_database_locks()
            if database_id is not None:
                observation.update(
                    {
                        "db_locked": True,
                        "database_id": database_id,
                        "database_probe_scope": "registered_sqlite_read_only",
                    }
                )

            self._kis_reconnect_authorized = False
            engines = external_status.get("engines")
            if isinstance(engines, list):
                for item in engines:
                    if not isinstance(item, Mapping) or not self._is_safe_kis_engine(item):
                        continue
                    disconnected = item.get("connected") is not True
                    if disconnected:
                        self._kis_reconnect_authorized = True
                        observation.update(
                            {
                                "external_engine_connected": False,
                                "engine_id": "kis-trading-mcp",
                                "kis_reconnect_scope": "resident_read_only_only",
                            }
                        )
                    break

            improvement_status = str(progress["status"] or "").upper()
            if improvement_status in _CANCELLED_STATES:
                self._safe_store_event(
                    "service.cancelled-observed",
                    {
                        "status": improvement_status,
                        "retry_allowed": False,
                        "reason": "cancelled_is_intentional_terminal_state",
                    },
                )
            elif improvement_status in _RETRYABLE_RESEARCH_STATES:
                signature = self._research_signature(improvement, improvement_status)
                attempted = {
                    str(item) for item in self._state.get("research_retry_signatures", [])
                }
                if signature not in attempted:
                    job_id = f"improvement-{signature[:20]}"
                    self._register_research_retry(job_id, signature, improvement_status)
                    observation.update(
                        {
                            "research_job_status": "failed",
                            "research_job_retryable": True,
                            "job_id": job_id,
                            "original_research_job_status": improvement_status,
                        }
                    )
                else:
                    observation.update(
                        {
                            "status": "degraded",
                            "abnormal": True,
                            "research_retry_exhausted": True,
                        }
                    )

            advice_result = self._process_one_pending_advice()
            if advice_result is not None:
                return self._finish(advice_result, phase="external-advice-review")

            result = self._engine_cycle(observation, auto_recover=True)
            primary_issue = str(_dig(result, "diagnostic.primary_issue") or "NO_ISSUE")
            if primary_issue == "NO_ISSUE" and result.get("status") == "healthy":
                reverified_transient_incidents = self._reconcile_recovered_transient_incidents(
                    current_pid=pid
                )
            else:
                self._reset_transient_reverification()
                reverified_transient_incidents = []
            return self._finish(
                {
                    **result,
                    "classification": primary_issue,
                    "operational_broken_count": broken_count,
                    "delayed_ignored": True,
                    "verification_pending_ignored": True,
                    "reverified_transient_incidents": reverified_transient_incidents,
                    "restart_requested": result.get("status") == "restart_requested",
                },
                phase="idle",
            )
        except Exception as exc:
            fallback = self._fallback_report(
                "SIDECAR_INTERNAL_ERROR",
                "The sidecar caught an internal error and stayed alive.",
                _safe_error(exc),
            )
            return self._finish(
                {**fallback, "classification": "SIDECAR_INTERNAL_ERROR"},
                phase="error",
            )

    def run_loop(self, stop_event: threading.Event | None = None) -> int:
        stopper = stop_event or threading.Event()
        while not stopper.is_set():
            started = time.monotonic()
            self.run_once()
            remaining = max(0.0, self.config.interval_seconds - (time.monotonic() - started))
            stopper.wait(remaining)
        return 0


def build_default_service(
    *,
    repo_root: Path | None = None,
    config: ServiceConfig | None = None,
) -> InternalDeveloperService:
    # Importing these modules has no app-server side effect and avoids a hard
    # dependency for unit tests that inject fakes.
    try:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore
    except ModuleNotFoundError:  # direct script execution from the app directory
        from internal_developer_engine import InternalDeveloperEngine
        from internal_developer_store import InternalDeveloperStore

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    data_root = active_data_root(root)
    store = InternalDeveloperStore(root, data_root=data_root)
    engine = InternalDeveloperEngine(
        store,
        max_attempts=1,
        cooldown_seconds=60.0,
        circuit_failure_threshold=3,
    )
    resolved_config = config or ServiceConfig(
        base_url=os.getenv("CODEXSTOCK_BASE_URL", "http://127.0.0.1:8765")
    )
    registered_databases = {
        "runtime-event-index": data_root / "runtime_event_index.sqlite3",
        "historical-market-cache": data_root / "historical_market_data_cache.sqlite3",
        "historical-replay-backfill-index": data_root
        / "historical_replay_data_backfill_index.sqlite3",
    }
    return InternalDeveloperService(
        repo_root=root,
        data_root=data_root,
        store=store,
        engine=engine,
        http_client=UrllibJsonClient(resolved_config.base_url),
        config=resolved_config,
        registered_databases=registered_databases,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CodexStock internal-developer sidecar")
    parser.add_argument("mode", choices=("once", "loop"), nargs="?", default="once")
    parser.add_argument(
        "--base-url",
        default=os.getenv("CODEXSTOCK_BASE_URL", "http://127.0.0.1:8765"),
    )
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--expected-pid", type=int, default=None)
    parser.add_argument("--repo-root", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    config = ServiceConfig(
        base_url=args.base_url,
        interval_seconds=args.interval,
        expected_pid=args.expected_pid,
    )
    service = build_default_service(
        repo_root=Path(args.repo_root).resolve() if args.repo_root else None,
        config=config,
    )
    lock = SingleInstanceLock(service.lock_path)
    if not lock.acquire():
        print(json.dumps({"ok": False, "error": "already_running"}))
        return 2
    try:
        if args.mode == "once":
            print(json.dumps(service.run_once(), ensure_ascii=False, default=str))
            return 0
        try:
            return service.run_loop()
        except KeyboardInterrupt:
            return 0
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXTERNAL_ENGINE_STATUS_PATH",
    "FEATURE_HEALTH_FORCE_PATH",
    "FEATURE_HEALTH_PATH",
    "FORBIDDEN_AUTOMATION",
    "HttpRequestError",
    "HttpResponse",
    "IMPROVEMENT_RETRY_PATH",
    "IMPROVEMENT_STATUS_PATH",
    "InternalDeveloperService",
    "KIS_RECONNECT_PATH",
    "OVERVIEW_PATH",
    "ServiceConfig",
    "SingleInstanceLock",
    "UrllibJsonClient",
    "build_default_service",
    "main",
]
