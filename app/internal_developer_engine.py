"""Deterministic, fail-closed operational recovery for CodexStock.

This module intentionally contains no model client, shell runner, process killer,
or trading integration.  Language-model advice is treated as untrusted data: only
the structured ``proposed_actions`` array is considered, and every action must
pass the exact schema below before a trusted, registered Python callable can run.

The engine is deliberately loosely coupled to ``InternalDeveloperStore``.  The
store is duck-typed so the policy and classifier can be tested in isolation and
embedded without creating an import cycle.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote


class IssueType(str, Enum):
    NO_ISSUE = "NO_ISSUE"
    HEARTBEAT_MISSING = "HEARTBEAT_MISSING"
    BUSY_PROGRESSING = "BUSY_PROGRESSING"
    BUSY_STALLED = "BUSY_STALLED"
    CACHE_INVALID = "CACHE_INVALID"
    EXTERNAL_ENGINE_DISCONNECTED = "EXTERNAL_ENGINE_DISCONNECTED"
    RETRYABLE_RESEARCH_JOB = "RETRYABLE_RESEARCH_JOB"
    INTERNAL_STATE_LEDGER_INCONSISTENT = "INTERNAL_STATE_LEDGER_INCONSISTENT"
    DB_LOCKED = "DB_LOCKED"
    PROCESS_UNRESPONSIVE = "PROCESS_UNRESPONSIVE"
    DIAGNOSTIC_ENDPOINT_UNAVAILABLE = "DIAGNOSTIC_ENDPOINT_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    CLEAR_NAMED_CACHE = "CLEAR_NAMED_CACHE"
    RECONNECT_EXTERNAL_ENGINE = "RECONNECT_EXTERNAL_ENGINE"
    RETRY_RESEARCH_JOB = "RETRY_RESEARCH_JOB"
    RESTORE_INTERNAL_STATE_LEDGER = "RESTORE_INTERNAL_STATE_LEDGER"
    DETECT_DB_LOCK = "DETECT_DB_LOCK"
    REQUEST_CODEXSTOCK_RESTART = "REQUEST_CODEXSTOCK_RESTART"
    WRITE_INCIDENT_REPORT = "WRITE_INCIDENT_REPORT"


ALLOWED_ACTIONS = frozenset(action.value for action in ActionType)

# Exact parameter names are part of the security boundary.  In particular,
# there is no field that can carry a path, command, code, credential, order, or
# security/risk mutation.
ACTION_PARAMETER_SCHEMAS: dict[ActionType, frozenset[str]] = {
    ActionType.CLEAR_NAMED_CACHE: frozenset({"cache_id"}),
    ActionType.RECONNECT_EXTERNAL_ENGINE: frozenset({"engine_id"}),
    ActionType.RETRY_RESEARCH_JOB: frozenset({"job_id"}),
    ActionType.RESTORE_INTERNAL_STATE_LEDGER: frozenset({"ledger_id"}),
    ActionType.DETECT_DB_LOCK: frozenset({"database_id"}),
    ActionType.REQUEST_CODEXSTOCK_RESTART: frozenset({"expected_pid", "reason_code"}),
    ActionType.WRITE_INCIDENT_REPORT: frozenset({"report_type"}),
}

_TARGET_FIELD = {
    ActionType.CLEAR_NAMED_CACHE: "cache_id",
    ActionType.RECONNECT_EXTERNAL_ENGINE: "engine_id",
    ActionType.RETRY_RESEARCH_JOB: "job_id",
    ActionType.RESTORE_INTERNAL_STATE_LEDGER: "ledger_id",
    ActionType.DETECT_DB_LOCK: "database_id",
}
_REGISTERED_HANDLER_ACTIONS = frozenset(
    {
        ActionType.CLEAR_NAMED_CACHE,
        ActionType.RECONNECT_EXTERNAL_ENGINE,
        ActionType.RETRY_RESEARCH_JOB,
        ActionType.RESTORE_INTERNAL_STATE_LEDGER,
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SAFE_REASON = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_REPORT_TYPES = frozenset({"diagnostic", "recovery", "escalation"})
_DANGEROUS_TARGET_FRAGMENTS = (
    "live_order",
    "real_order",
    "api_key",
    "secret_key",
    "risk_limit",
    "risk_relax",
    "security_setting",
    "disable_security",
    "source_code",
    "code_patch",
    "shell",
)


class ActionRejected(ValueError):
    """Raised when untrusted action data fails the recovery policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class IssueClassification:
    code: IssueType
    severity: str
    actionable: bool
    summary: str
    evidence: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_code": self.code.value,
            "severity": self.severity,
            "actionable": self.actionable,
            "summary": self.summary,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class HandlerBinding:
    handler: Callable[[dict[str, object], dict[str, object]], object]
    verifier: Callable[[object, dict[str, object], dict[str, object]], object]


@dataclass
class _CircuitState:
    failures: int = 0
    opened_at: float | None = None


def _dig(payload: Mapping[str, object], *paths: str) -> object | None:
    for dotted in paths:
        current: object = payload
        found = True
        for part in dotted.split("."):
            if not isinstance(current, Mapping) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            return current
    return None


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _age_seconds(
    payload: Mapping[str, object],
    *,
    now: float,
    age_paths: Sequence[str],
    timestamp_paths: Sequence[str],
) -> float | None:
    age = _dig(payload, *age_paths)
    if _is_number(age):
        return max(0.0, float(age))
    timestamp = _dig(payload, *timestamp_paths)
    if _is_number(timestamp):
        return max(0.0, now - float(timestamp))
    return None


def _bool_is(payload: Mapping[str, object], expected: bool, *paths: str) -> bool:
    value = _dig(payload, *paths)
    return isinstance(value, bool) and value is expected


def classify_issues(
    observation: Mapping[str, object],
    *,
    now_epoch: float | None = None,
    heartbeat_timeout_seconds: float = 300.0,
    busy_stall_timeout_seconds: float = 300.0,
) -> list[IssueClassification]:
    """Return all recognized states in deterministic safety-priority order.

    ``BUSY_PROGRESSING`` is an intentional non-actionable state.  A stale main
    heartbeat alone must not cause a restart while a declared long-running job
    is still making recent progress.
    """

    if not isinstance(observation, Mapping):
        raise TypeError("observation must be a mapping")
    now = float(time.time() if now_epoch is None else now_epoch)
    heartbeat_timeout = max(1.0, float(heartbeat_timeout_seconds))
    stall_timeout = max(1.0, float(busy_stall_timeout_seconds))
    results: list[IssueClassification] = []

    declared_classification = str(
        _dig(observation, "classification", "issue_code") or ""
    ).strip().upper()
    if declared_classification == IssueType.DIAGNOSTIC_ENDPOINT_UNAVAILABLE.value:
        http_error = observation.get("http_error")
        error_type = (
            str(http_error.get("error_type") or "")[:120]
            if isinstance(http_error, Mapping)
            else ""
        )
        results.append(
            IssueClassification(
                IssueType.DIAGNOSTIC_ENDPOINT_UNAVAILABLE,
                "high",
                False,
                "A fixed local read-only diagnostic endpoint did not answer this cycle.",
                {
                    "diagnostic_scope": "bounded_local_http",
                    "error_type": error_type,
                },
            )
        )

    process_unresponsive = _bool_is(
        observation, False, "process_responsive", "process.responsive"
    ) or _bool_is(observation, True, "process_unresponsive")

    ledger_consistent = _dig(
        observation,
        "internal_ledger_consistent",
        "internal_state_ledger.consistent",
        "internal_developer_ledger.consistent",
    )
    if ledger_consistent is False or _bool_is(
        observation, True, "internal_ledger_inconsistent", "internal_state_ledger.inconsistent"
    ):
        results.append(
            IssueClassification(
                IssueType.INTERNAL_STATE_LEDGER_INCONSISTENT,
                "high",
                True,
                "The internal developer's own state ledger failed consistency checks.",
                {"internal_ledger_consistent": False},
            )
        )

    db_locked = _bool_is(observation, True, "db_locked", "database.locked") or str(
        _dig(observation, "database.status") or ""
    ).strip().lower() in {"locked", "busy"}
    if db_locked:
        results.append(
            IssueClassification(
                IssueType.DB_LOCKED,
                "high",
                True,
                "A registered database appears locked; only a read-only probe is allowed.",
                {"db_locked": True},
            )
        )

    heartbeat_age = _age_seconds(
        observation,
        now=now,
        age_paths=("heartbeat_age_seconds", "heartbeat.age_seconds"),
        timestamp_paths=("heartbeat_at_epoch", "heartbeat.at_epoch", "heartbeat_at"),
    )
    heartbeat_missing = _bool_is(
        observation, True, "heartbeat_missing", "heartbeat.missing"
    ) or _bool_is(observation, False, "heartbeat_ok", "heartbeat.ok") or (
        heartbeat_age is not None and heartbeat_age > heartbeat_timeout
    )
    busy_active = _bool_is(
        observation, True, "busy", "busy_active", "busy_operation.active"
    )
    progress_age = _age_seconds(
        observation,
        now=now,
        age_paths=("progress_age_seconds", "busy_operation.progress_age_seconds"),
        timestamp_paths=(
            "progress_at_epoch",
            "busy_operation.progress_at_epoch",
            "busy_operation.last_progress_at_epoch",
        ),
    )
    explicitly_stalled = _bool_is(
        observation, True, "stalled", "busy_stalled", "busy_operation.stalled"
    )
    explicitly_progressing = _bool_is(
        observation, True, "busy_progressing", "busy_operation.progressing"
    )
    busy_stalled = explicitly_stalled or (
        busy_active and progress_age is not None and progress_age > stall_timeout
    )
    busy_progressing = bool(
        explicitly_progressing
        or (busy_active and progress_age is not None and progress_age <= stall_timeout)
    )
    if busy_stalled:
        results.append(
            IssueClassification(
                IssueType.BUSY_STALLED,
                "high",
                True,
                "A declared long-running operation stopped reporting progress.",
                {
                    "busy": True,
                    "progress_age_seconds": progress_age,
                    "stall_timeout_seconds": stall_timeout,
                },
            )
        )
    elif (heartbeat_missing or process_unresponsive) and busy_progressing:
        results.append(
            IssueClassification(
                IssueType.BUSY_PROGRESSING,
                "info",
                False,
                "The main heartbeat is stale, but the declared operation is making progress.",
                {
                    "heartbeat_age_seconds": heartbeat_age,
                    "busy": True,
                    "progress_age_seconds": progress_age,
                },
            )
        )
    elif process_unresponsive:
        results.insert(
            0,
            IssueClassification(
                IssueType.PROCESS_UNRESPONSIVE,
                "critical",
                True,
                "CodexStock process did not answer a direct responsiveness probe.",
                {"process_responsive": False},
            ),
        )
    elif heartbeat_missing:
        results.append(
            IssueClassification(
                IssueType.HEARTBEAT_MISSING,
                "high",
                True,
                "The main heartbeat exceeded its allowed age.",
                {
                    "heartbeat_age_seconds": heartbeat_age,
                    "heartbeat_timeout_seconds": heartbeat_timeout,
                },
            )
        )

    if _bool_is(observation, False, "cache_valid", "cache.valid") or _bool_is(
        observation, True, "cache_invalid", "cache.invalid"
    ):
        results.append(
            IssueClassification(
                IssueType.CACHE_INVALID,
                "medium",
                True,
                "A named operational cache failed validation.",
                {"cache_valid": False},
            )
        )

    if _bool_is(
        observation,
        False,
        "external_engine_connected",
        "external_engine.connected",
    ) or _bool_is(
        observation, True, "external_engine_disconnected", "external_engine.disconnected"
    ):
        results.append(
            IssueClassification(
                IssueType.EXTERNAL_ENGINE_DISCONNECTED,
                "high",
                True,
                "A registered external engine is disconnected.",
                {"external_engine_connected": False},
            )
        )

    job_status = str(
        _dig(observation, "research_job_status", "research_job.status") or ""
    ).strip().lower()
    retryable = _bool_is(
        observation, True, "research_job_retryable", "research_job.retryable"
    )
    if retryable and job_status in {"failed", "retryable", "retryable_failure", "error"}:
        results.append(
            IssueClassification(
                IssueType.RETRYABLE_RESEARCH_JOB,
                "medium",
                True,
                "A research-only job failed with an explicit retryable marker.",
                {"research_job_status": job_status, "retryable": True},
            )
        )

    if results:
        return results

    abnormal = _bool_is(observation, True, "abnormal", "unhealthy")
    status = str(_dig(observation, "status", "health.status") or "").strip().lower()
    if abnormal or status in {"error", "failed", "degraded", "unhealthy", "unknown_failure"}:
        return [
            IssueClassification(
                IssueType.UNKNOWN,
                "high",
                False,
                "An abnormal condition was reported but did not match a safe recovery rule.",
                {"status": status or "unspecified", "abnormal": abnormal},
            )
        ]
    return [
        IssueClassification(
            IssueType.NO_ISSUE,
            "info",
            False,
            "No operational issue was detected.",
            {},
        )
    ]


def classify_issue(
    observation: Mapping[str, object],
    *,
    now_epoch: float | None = None,
    heartbeat_timeout_seconds: float = 300.0,
    busy_stall_timeout_seconds: float = 300.0,
) -> IssueClassification:
    """Return the highest-priority deterministic classification."""

    return classify_issues(
        observation,
        now_epoch=now_epoch,
        heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        busy_stall_timeout_seconds=busy_stall_timeout_seconds,
    )[0]


class InternalDeveloperEngine:
    """Policy-gated operational recovery coordinator.

    Handlers and verifiers are trusted application code registered at startup.
    GPT text, paths, module names, and commands can never register a handler.
    """

    def __init__(
        self,
        store: object,
        *,
        heartbeat_timeout_seconds: float = 300.0,
        busy_stall_timeout_seconds: float = 300.0,
        max_attempts: int = 2,
        cooldown_seconds: float = 60.0,
        circuit_failure_threshold: int = 3,
        circuit_open_seconds: float = 300.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if circuit_failure_threshold < 1:
            raise ValueError("circuit_failure_threshold must be positive")
        self.store = store
        self.heartbeat_timeout_seconds = max(1.0, float(heartbeat_timeout_seconds))
        self.busy_stall_timeout_seconds = max(1.0, float(busy_stall_timeout_seconds))
        self.max_attempts = int(max_attempts)
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self.circuit_failure_threshold = int(circuit_failure_threshold)
        self.circuit_open_seconds = max(1.0, float(circuit_open_seconds))
        self._clock = clock
        self._handlers: dict[tuple[ActionType, str], HandlerBinding] = {}
        self._databases: dict[str, Path] = {}
        self._idempotent_results: dict[str, dict[str, object]] = {}
        self._last_attempt_at: dict[str, float] = {}
        self._circuits: dict[str, _CircuitState] = {}
        self._lock = threading.RLock()

    def register_handler(
        self,
        action: ActionType | str,
        target_id: str,
        handler: Callable[[dict[str, object], dict[str, object]], object],
        verifier: Callable[[object, dict[str, object], dict[str, object]], object],
    ) -> None:
        action_type = self._coerce_action_type(action)
        if action_type not in _REGISTERED_HANDLER_ACTIONS:
            raise ValueError(f"{action_type.value} uses a built-in safety handler")
        safe_target = self._validate_safe_identifier(target_id, "target_id")
        if not callable(handler) or not callable(verifier):
            raise TypeError("handler and verifier must be trusted callables")
        with self._lock:
            self._handlers[(action_type, safe_target)] = HandlerBinding(handler, verifier)

    def register_named_cache(
        self,
        cache_id: str,
        clear: Callable[[dict[str, object], dict[str, object]], object],
        verify: Callable[[object, dict[str, object], dict[str, object]], object],
    ) -> None:
        self.register_handler(ActionType.CLEAR_NAMED_CACHE, cache_id, clear, verify)

    def register_external_engine(
        self,
        engine_id: str,
        reconnect: Callable[[dict[str, object], dict[str, object]], object],
        verify: Callable[[object, dict[str, object], dict[str, object]], object],
    ) -> None:
        self.register_handler(
            ActionType.RECONNECT_EXTERNAL_ENGINE, engine_id, reconnect, verify
        )

    def register_research_job(
        self,
        job_id: str,
        retry: Callable[[dict[str, object], dict[str, object]], object],
        verify: Callable[[object, dict[str, object], dict[str, object]], object],
    ) -> None:
        self.register_handler(ActionType.RETRY_RESEARCH_JOB, job_id, retry, verify)

    def register_internal_state_ledger(
        self,
        ledger_id: str,
        restore: Callable[[dict[str, object], dict[str, object]], object],
        verify: Callable[[object, dict[str, object], dict[str, object]], object],
    ) -> None:
        self.register_handler(
            ActionType.RESTORE_INTERNAL_STATE_LEDGER, ledger_id, restore, verify
        )

    def register_database(self, database_id: str, path: str | Path) -> None:
        """Register a trusted local SQLite target; advice may refer only to its ID."""

        safe_id = self._validate_safe_identifier(database_id, "database_id")
        resolved = Path(path).expanduser().resolve(strict=False)
        with self._lock:
            self._databases[safe_id] = resolved

    def diagnose(self, observation: Mapping[str, object]) -> dict[str, object]:
        issues = classify_issues(
            observation,
            now_epoch=self._clock(),
            heartbeat_timeout_seconds=self.heartbeat_timeout_seconds,
            busy_stall_timeout_seconds=self.busy_stall_timeout_seconds,
        )
        actions = self.recommend_actions(observation, issues)
        return {
            "schema_version": "codexstock.internal-developer.diagnostic.v1",
            "observed_at_epoch": self._clock(),
            "primary_issue": issues[0].code.value,
            "issues": [issue.to_dict() for issue in issues],
            "recommended_actions": actions,
            "auto_recovery_available": bool(actions)
            and issues[0].code not in {IssueType.UNKNOWN, IssueType.BUSY_PROGRESSING},
        }

    def recommend_actions(
        self,
        observation: Mapping[str, object],
        issues: Sequence[IssueClassification] | None = None,
    ) -> list[dict[str, object]]:
        """Build only exact-schema actions from observed resource IDs."""

        classified = list(issues or classify_issues(
            observation,
            now_epoch=self._clock(),
            heartbeat_timeout_seconds=self.heartbeat_timeout_seconds,
            busy_stall_timeout_seconds=self.busy_stall_timeout_seconds,
        ))
        proposals: list[dict[str, object]] = []
        seen: set[str] = set()

        def add(action: ActionType, parameters: dict[str, object]) -> None:
            candidate = {"action": action.value, "parameters": parameters}
            decision = self.evaluate_action(candidate)
            if not decision["accepted"]:
                return
            canonical = json.dumps(decision["normalized"], sort_keys=True, separators=(",", ":"))
            if canonical not in seen:
                seen.add(canonical)
                proposals.append(decision["normalized"])

        for issue in classified:
            if issue.code is IssueType.CACHE_INVALID:
                target = _dig(observation, "cache_id", "cache.id", "cache.cache_id")
                if isinstance(target, str):
                    add(ActionType.CLEAR_NAMED_CACHE, {"cache_id": target})
            elif issue.code is IssueType.EXTERNAL_ENGINE_DISCONNECTED:
                target = _dig(
                    observation, "engine_id", "external_engine.id", "external_engine.engine_id"
                )
                if isinstance(target, str):
                    add(ActionType.RECONNECT_EXTERNAL_ENGINE, {"engine_id": target})
            elif issue.code is IssueType.RETRYABLE_RESEARCH_JOB:
                target = _dig(observation, "job_id", "research_job.id", "research_job.job_id")
                if isinstance(target, str):
                    add(ActionType.RETRY_RESEARCH_JOB, {"job_id": target})
            elif issue.code is IssueType.INTERNAL_STATE_LEDGER_INCONSISTENT:
                target = _dig(
                    observation,
                    "ledger_id",
                    "internal_state_ledger.id",
                    "internal_developer_ledger.id",
                )
                if isinstance(target, str):
                    add(ActionType.RESTORE_INTERNAL_STATE_LEDGER, {"ledger_id": target})
            elif issue.code is IssueType.DB_LOCKED:
                target = _dig(observation, "database_id", "database.id", "database.database_id")
                if isinstance(target, str):
                    add(ActionType.DETECT_DB_LOCK, {"database_id": target})
            elif issue.code in {
                IssueType.HEARTBEAT_MISSING,
                IssueType.PROCESS_UNRESPONSIVE,
            }:
                pid = _dig(observation, "expected_pid", "process.pid")
                if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
                    add(
                        ActionType.REQUEST_CODEXSTOCK_RESTART,
                        {"expected_pid": pid, "reason_code": issue.code.value.lower()},
                    )
            elif issue.code is IssueType.BUSY_STALLED:
                add(ActionType.WRITE_INCIDENT_REPORT, {"report_type": "escalation"})

        if not proposals and classified[0].code not in {
            IssueType.NO_ISSUE,
            IssueType.BUSY_PROGRESSING,
        }:
            add(ActionType.WRITE_INCIDENT_REPORT, {"report_type": "escalation"})
        return proposals

    def evaluate_action(self, proposal: object) -> dict[str, object]:
        try:
            normalized = self.validate_action(proposal)
        except ActionRejected as exc:
            return {
                "accepted": False,
                "reason_code": exc.code,
                "message": str(exc),
                "normalized": None,
            }
        return {
            "accepted": True,
            "reason_code": "allowed",
            "message": "Action passed the exact allowlist policy.",
            "normalized": normalized,
        }

    def validate_action(self, proposal: object) -> dict[str, object]:
        if not isinstance(proposal, Mapping):
            raise ActionRejected("invalid_action_shape", "Action must be an object.")
        root_keys = set(proposal.keys())
        if root_keys != {"action", "parameters"}:
            raise ActionRejected(
                "unexpected_action_fields",
                "Action must contain exactly 'action' and 'parameters'.",
            )
        action_type = self._coerce_action_type(proposal.get("action"), rejected=True)
        parameters = proposal.get("parameters")
        if not isinstance(parameters, Mapping):
            raise ActionRejected("invalid_parameters", "parameters must be an object.")
        expected_fields = ACTION_PARAMETER_SCHEMAS[action_type]
        if set(parameters.keys()) != set(expected_fields):
            raise ActionRejected(
                "unexpected_parameter_fields",
                f"{action_type.value} requires exactly {sorted(expected_fields)}.",
            )
        normalized = dict(parameters)
        target_field = _TARGET_FIELD.get(action_type)
        if target_field:
            normalized[target_field] = self._validate_safe_identifier(
                normalized[target_field], target_field, rejected=True
            )
        elif action_type is ActionType.REQUEST_CODEXSTOCK_RESTART:
            pid = normalized["expected_pid"]
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                raise ActionRejected("invalid_expected_pid", "expected_pid must be a positive integer.")
            reason = normalized["reason_code"]
            if not isinstance(reason, str) or not _SAFE_REASON.fullmatch(reason):
                raise ActionRejected("invalid_reason_code", "reason_code must be a safe identifier.")
        elif action_type is ActionType.WRITE_INCIDENT_REPORT:
            report_type = normalized["report_type"]
            if report_type not in _REPORT_TYPES:
                raise ActionRejected(
                    "invalid_report_type", f"report_type must be one of {sorted(_REPORT_TYPES)}."
                )
        return {"action": action_type.value, "parameters": normalized}

    def execute_advice(
        self,
        incident_id: str,
        advice: Mapping[str, object],
        *,
        advice_id: str | None = None,
    ) -> dict[str, object]:
        """Execute policy-approved structured actions; never interpret advice text."""

        safe_incident = self._validate_safe_identifier(incident_id, "incident_id")
        if not isinstance(advice, Mapping):
            raise TypeError("advice must be a mapping")
        proposed = advice.get("proposed_actions", [])
        if not isinstance(proposed, list):
            proposed = []
            malformed = True
        else:
            malformed = False
        results: list[dict[str, object]] = []
        for index, proposal in enumerate(proposed):
            decision = self.evaluate_action(proposal)
            if not decision["accepted"]:
                results.append({"index": index, "status": "rejected", **decision})
                continue
            outcome = self.execute_action(
                safe_incident,
                decision["normalized"],
                idempotency_key=None,
                source="external_advice",
            )
            results.append({"index": index, **outcome})
        summary = {
            "incident_id": safe_incident,
            "advice_id": advice_id,
            "text_ignored": True,
            "malformed_proposed_actions": malformed,
            "proposed_action_count": len(proposed),
            "results": results,
        }
        self._record_event("internal_developer_advice_evaluated", summary)
        if advice_id and hasattr(self.store, "update_advice"):
            try:
                self.store.update_advice(advice_id, {"engine_result": summary})
            except Exception as exc:  # store telemetry must not expand authority
                self._record_event(
                    "internal_developer_store_error",
                    {"operation": "update_advice", "error_type": type(exc).__name__},
                )
        return summary

    def execute_action(
        self,
        incident_id: str,
        proposal: Mapping[str, object],
        *,
        idempotency_key: str | None = None,
        source: str = "automatic",
    ) -> dict[str, object]:
        normalized = self.validate_action(proposal)
        safe_incident = self._validate_safe_identifier(incident_id, "incident_id")
        if source not in {"automatic", "external_advice", "manual_policy_test"}:
            raise ValueError("unsupported action source")
        action_type = ActionType(normalized["action"])
        parameters = dict(normalized["parameters"])
        key = self._idempotency_key(safe_incident, normalized, idempotency_key)
        circuit_key = self._circuit_key(action_type, parameters)
        now = self._clock()

        with self._lock:
            prior = self._idempotent_results.get(key) or self._persisted_success(
                safe_incident, key
            )
            if prior is not None:
                return {
                    **dict(prior),
                    "status": "idempotent_replay",
                    "idempotency_key": key,
                    "executed": False,
                }

            circuit = self._circuits.setdefault(circuit_key, _CircuitState())
            if circuit.opened_at is not None:
                elapsed = now - circuit.opened_at
                if elapsed < self.circuit_open_seconds:
                    return self._blocked_result(
                        safe_incident,
                        normalized,
                        key,
                        "circuit_open",
                        self.circuit_open_seconds - elapsed,
                    )
                circuit.failures = 0
                circuit.opened_at = None

            last_attempt = self._last_attempt_at.get(circuit_key)
            if last_attempt is not None and now - last_attempt < self.cooldown_seconds:
                return self._blocked_result(
                    safe_incident,
                    normalized,
                    key,
                    "cooldown_active",
                    self.cooldown_seconds - (now - last_attempt),
                )

            binding = self._resolve_binding(action_type, parameters)
            if isinstance(binding, dict):
                return {
                    "incident_id": safe_incident,
                    "action": action_type.value,
                    "parameters": parameters,
                    "status": "rejected",
                    "executed": False,
                    "idempotency_key": key,
                    **binding,
                }
            self._last_attempt_at[circuit_key] = now

            context = {
                "incident_id": safe_incident,
                "action": action_type.value,
                "source": source,
                "idempotency_key": key,
            }
            attempt_records: list[dict[str, object]] = []
            succeeded = False
            final_result: dict[str, object] = {}
            for attempt_number in range(1, self.max_attempts + 1):
                started = self._clock()
                handler_result: object = None
                verification: object = None
                try:
                    handler_result = binding.handler(dict(parameters), dict(context))
                    handler_ok, handler_details, retryable = self._outcome_parts(handler_result)
                    if handler_ok:
                        verification = binding.verifier(
                            handler_result, dict(parameters), dict(context)
                        )
                        verified, verification_details, _ = self._outcome_parts(verification)
                    else:
                        verified, verification_details = False, {"ok": False, "skipped": True}
                except Exception as exc:
                    handler_ok = False
                    verified = False
                    retryable = True
                    handler_details = {
                        "success": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                    }
                    verification_details = {"ok": False, "skipped": True}
                attempt_ok = bool(handler_ok and verified)
                attempt_record = {
                    "action": action_type.value,
                    "parameters": dict(parameters),
                    "idempotency_key": key,
                    "attempt_number": attempt_number,
                    "started_at_epoch": started,
                    "finished_at_epoch": self._clock(),
                    "status": "succeeded" if attempt_ok else "failed",
                    "handler_result": handler_details,
                    "post_verification": verification_details,
                }
                attempt_records.append(attempt_record)
                self._record_attempt(safe_incident, attempt_record)
                if attempt_ok:
                    succeeded = True
                    final_result = {
                        "handler_result": handler_details,
                        "post_verification": verification_details,
                    }
                    break
                final_result = {
                    "handler_result": handler_details,
                    "post_verification": verification_details,
                }
                if not retryable:
                    break

            outcome = {
                "incident_id": safe_incident,
                "action": action_type.value,
                "parameters": parameters,
                "status": "succeeded" if succeeded else "failed",
                "executed": True,
                "idempotency_key": key,
                "attempt_count": len(attempt_records),
                **final_result,
            }
            if succeeded:
                circuit.failures = 0
                circuit.opened_at = None
                self._idempotent_results[key] = dict(outcome)
                if hasattr(self.store, "learn_playbook"):
                    try:
                        self.store.learn_playbook(safe_incident, normalized, outcome)
                    except Exception as exc:
                        self._record_event(
                            "internal_developer_store_error",
                            {"operation": "learn_playbook", "error_type": type(exc).__name__},
                        )
            else:
                circuit.failures += 1
                if circuit.failures >= self.circuit_failure_threshold:
                    circuit.opened_at = self._clock()
                    outcome["circuit_opened"] = True
            self._record_event("internal_developer_action_result", outcome)
            return outcome

    def run_cycle(
        self,
        observation: Mapping[str, object],
        *,
        auto_recover: bool = True,
    ) -> dict[str, object]:
        """Diagnose one observation, optionally recover, verify, and report."""

        diagnostic = self.diagnose(observation)
        primary = IssueType(str(diagnostic["primary_issue"]))
        if primary is IssueType.NO_ISSUE:
            return {"status": "healthy", "diagnostic": diagnostic, "incident_id": None, "results": []}
        if primary is IssueType.BUSY_PROGRESSING:
            self._record_event("internal_developer_busy_progressing", diagnostic)
            return {
                "status": "busy_progressing",
                "diagnostic": diagnostic,
                "incident_id": None,
                "results": [],
            }

        incident_id = self._open_incident(diagnostic)
        self._transition(incident_id, "DIAGNOSING", note="Deterministic diagnosis completed.")
        proposed = list(diagnostic["recommended_actions"])
        results: list[dict[str, object]] = []
        if auto_recover and proposed:
            self._transition(incident_id, "AUTO_RECOVERING", note="Allowlisted recovery started.")
            for proposal in proposed:
                results.append(self.execute_action(incident_id, proposal))

        attempted = bool(results)
        all_succeeded = attempted and all(row.get("status") in {"succeeded", "idempotent_replay"} for row in results)
        requested_restart = any(
            row.get("action") == ActionType.REQUEST_CODEXSTOCK_RESTART.value
            and row.get("status") in {"succeeded", "idempotent_replay"}
            for row in results
        )
        only_diagnosed_lock = primary is IssueType.DB_LOCKED and all_succeeded
        if not auto_recover:
            final_state = "NEW"
            status = "diagnosed"
        elif requested_restart:
            final_state = "WAITING_FOR_RESTART"
            status = "restart_requested"
        elif primary is IssueType.BUSY_STALLED:
            final_state = "NEEDS_EXTERNAL_ADVICE"
            status = "busy_stalled_reported"
        elif all_succeeded and not only_diagnosed_lock and primary is not IssueType.UNKNOWN:
            final_state = "RECOVERED_UNREVIEWED"
            status = "recovered"
        elif attempted and not all_succeeded:
            final_state = "RECOVERY_FAILED"
            status = "recovery_failed"
        else:
            final_state = "NEEDS_EXTERNAL_ADVICE"
            status = "needs_external_advice"
        self._transition(
            incident_id,
            final_state,
            note="Recovery cycle completed.",
            metadata={"result_count": len(results)},
        )
        report = {
            "schema_version": "codexstock.internal-developer.report.v1",
            "incident_id": incident_id,
            "status": status,
            "diagnostic": diagnostic,
            "recovery_results": results,
            "needs_external_advice": final_state in {"NEEDS_EXTERNAL_ADVICE", "RECOVERY_FAILED"},
        }
        self._write_report(incident_id, report)
        return {
            "status": status,
            "diagnostic": diagnostic,
            "incident_id": incident_id,
            "results": results,
            "report": report,
        }

    def _resolve_binding(
        self, action_type: ActionType, parameters: dict[str, object]
    ) -> HandlerBinding | dict[str, object]:
        target_field = _TARGET_FIELD.get(action_type)
        if action_type in _REGISTERED_HANDLER_ACTIONS:
            target = str(parameters[target_field])
            binding = self._handlers.get((action_type, target))
            if binding is None:
                return {
                    "reason_code": "unregistered_target",
                    "message": "No trusted handler is registered for this action target.",
                }
            return binding
        if action_type is ActionType.DETECT_DB_LOCK:
            database_id = str(parameters["database_id"])
            if database_id not in self._databases:
                return {
                    "reason_code": "unregistered_database",
                    "message": "database_id is not registered for a read-only probe.",
                }
            return HandlerBinding(self._probe_registered_database, self._verify_database_probe)
        if action_type is ActionType.REQUEST_CODEXSTOCK_RESTART:
            if not hasattr(self.store, "request_restart"):
                return {
                    "reason_code": "restart_store_unavailable",
                    "message": "The store cannot create a restart request.",
                }
            return HandlerBinding(self._request_restart, self._verify_store_action)
        if action_type is ActionType.WRITE_INCIDENT_REPORT:
            if not hasattr(self.store, "write_report"):
                return {
                    "reason_code": "report_store_unavailable",
                    "message": "The store cannot write an incident report.",
                }
            return HandlerBinding(self._write_action_report, self._verify_store_action)
        return {"reason_code": "action_not_allowlisted", "message": "Action is not allowed."}

    def _probe_registered_database(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        database_id = str(parameters["database_id"])
        path = self._databases[database_id]
        result: dict[str, object] = {
            "success": True,
            "probe_completed": True,
            "database_id": database_id,
            "mode": "read_only",
            "locked": False,
            "exists": path.is_file(),
            "retryable": False,
        }
        if not path.is_file():
            return {
                **result,
                "success": False,
                "probe_completed": False,
                "error_type": "FileNotFoundError",
            }
        uri_path = quote(path.as_posix(), safe="/:~")
        try:
            connection = sqlite3.connect(
                f"file:{uri_path}?mode=ro",
                uri=True,
                timeout=0.1,
                isolation_level=None,
            )
            try:
                connection.execute("PRAGMA query_only = ON")
                connection.execute("PRAGMA schema_version").fetchone()
            finally:
                connection.close()
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            locked = "locked" in message or "busy" in message
            result.update(
                {
                    "locked": locked,
                    "sqlite_error": str(exc)[:300],
                    "error_type": type(exc).__name__,
                }
            )
            if not locked:
                result["success"] = False
                result["retryable"] = True
        except (OSError, sqlite3.Error) as exc:
            result.update(
                {
                    "success": False,
                    "probe_completed": False,
                    "error_type": type(exc).__name__,
                    "sqlite_error": str(exc)[:300],
                    "retryable": True,
                }
            )
        return result

    @staticmethod
    def _verify_database_probe(
        result: object, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        ok = isinstance(result, Mapping) and result.get("probe_completed") is True
        return {"ok": ok, "verified": "read_only_probe_completed"}

    def _request_restart(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        result = self.store.request_restart(
            int(parameters["expected_pid"]),
            str(context["incident_id"]),
            str(parameters["reason_code"]),
        )
        if isinstance(result, Mapping):
            return {"success": bool(result.get("success", result.get("ok", True))), **dict(result)}
        return {"success": result is not False, "restart_request_created": result is not False}

    def _write_action_report(
        self, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        incident_id = str(context["incident_id"])
        incident: object = None
        if hasattr(self.store, "get_incident"):
            incident = self.store.get_incident(incident_id)
        payload = {
            "schema_version": "codexstock.internal-developer.report.v1",
            "incident_id": incident_id,
            "report_type": parameters["report_type"],
            "incident": incident if isinstance(incident, Mapping) else None,
        }
        result = self.store.write_report(incident_id, payload)
        if isinstance(result, Mapping):
            return {"success": bool(result.get("success", result.get("ok", True))), **dict(result)}
        return {"success": result is not False, "report_written": result is not False}

    @staticmethod
    def _verify_store_action(
        result: object, parameters: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        if isinstance(result, Mapping):
            ok = bool(result.get("success", result.get("ok", False)))
        else:
            ok = result is True
        return {"ok": ok, "store_acknowledged": ok}

    @staticmethod
    def _outcome_parts(result: object) -> tuple[bool, dict[str, object], bool]:
        if isinstance(result, Mapping):
            details = dict(result)
            ok = bool(details.get("success", details.get("ok", True)))
            retryable = bool(details.get("retryable", True))
            return ok, details, retryable
        if isinstance(result, bool):
            return result, {"success": result}, True
        if result is None:
            return False, {"success": False, "reason": "empty_result"}, True
        return True, {"success": True, "result_type": type(result).__name__}, True

    def _idempotency_key(
        self,
        incident_id: str,
        normalized: Mapping[str, object],
        explicit: str | None,
    ) -> str:
        if explicit is not None:
            if not isinstance(explicit, str) or not _SAFE_ID.fullmatch(explicit):
                raise ActionRejected(
                    "invalid_idempotency_key", "idempotency_key must be a safe identifier."
                )
            return explicit
        canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(f"{incident_id}\n{canonical}".encode("utf-8")).hexdigest()[:32]
        return f"recovery:{digest}"

    @staticmethod
    def _circuit_key(action_type: ActionType, parameters: Mapping[str, object]) -> str:
        target_field = _TARGET_FIELD.get(action_type)
        if target_field:
            target = str(parameters[target_field])
        elif action_type is ActionType.REQUEST_CODEXSTOCK_RESTART:
            target = str(parameters["expected_pid"])
        else:
            target = str(parameters.get("report_type", "default"))
        return f"{action_type.value}:{target}"

    def _blocked_result(
        self,
        incident_id: str,
        normalized: Mapping[str, object],
        key: str,
        reason_code: str,
        retry_after: float,
    ) -> dict[str, object]:
        result = {
            "incident_id": incident_id,
            "action": normalized["action"],
            "parameters": dict(normalized["parameters"]),
            "status": "blocked",
            "executed": False,
            "reason_code": reason_code,
            "retry_after_seconds": round(max(0.0, retry_after), 3),
            "idempotency_key": key,
        }
        self._record_event("internal_developer_action_blocked", result)
        return result

    def _persisted_success(self, incident_id: str, key: str) -> dict[str, object] | None:
        if not hasattr(self.store, "get_incident"):
            return None
        try:
            incident = self.store.get_incident(incident_id)
        except Exception:
            return None
        if not isinstance(incident, Mapping):
            return None
        attempts = incident.get("recovery_attempts", incident.get("attempts", []))
        if not isinstance(attempts, list):
            return None
        for attempt in reversed(attempts):
            if (
                isinstance(attempt, Mapping)
                and attempt.get("idempotency_key") == key
                and attempt.get("status") == "succeeded"
            ):
                return {
                    "incident_id": incident_id,
                    "action": attempt.get("action"),
                    "parameters": dict(attempt.get("parameters", {}))
                    if isinstance(attempt.get("parameters"), Mapping)
                    else {},
                    "attempt_count": 0,
                    "handler_result": attempt.get("handler_result", {}),
                    "post_verification": attempt.get("post_verification", {}),
                }
        return None

    def _record_attempt(self, incident_id: str, attempt: dict[str, object]) -> None:
        if hasattr(self.store, "record_recovery_attempt"):
            try:
                self.store.record_recovery_attempt(incident_id, attempt)
                return
            except Exception as exc:
                self._record_event(
                    "internal_developer_store_error",
                    {"operation": "record_recovery_attempt", "error_type": type(exc).__name__},
                )
        self._record_event("internal_developer_recovery_attempt", attempt)

    def _record_event(self, event_type: str, payload: Mapping[str, object]) -> None:
        if not hasattr(self.store, "record_event"):
            return
        try:
            self.store.record_event(event_type, dict(payload))
        except Exception:
            return

    def _open_incident(self, diagnostic: Mapping[str, object]) -> str:
        if hasattr(self.store, "open_incident"):
            try:
                opened = self.store.open_incident(dict(diagnostic))
                if isinstance(opened, str) and _SAFE_ID.fullmatch(opened):
                    return opened
                if isinstance(opened, Mapping):
                    candidate = opened.get("incident_id", opened.get("id"))
                    if isinstance(candidate, str) and _SAFE_ID.fullmatch(candidate):
                        return candidate
            except Exception as exc:
                self._record_event(
                    "internal_developer_store_error",
                    {"operation": "open_incident", "error_type": type(exc).__name__},
                )
        canonical = json.dumps(diagnostic, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        return f"INC-{int(self._clock())}-{digest}"

    def _transition(
        self,
        incident_id: str,
        new_state: str,
        *,
        note: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if hasattr(self.store, "transition_incident"):
            try:
                self.store.transition_incident(
                    incident_id, new_state, note=note, metadata=dict(metadata or {})
                )
            except Exception as exc:
                self._record_event(
                    "internal_developer_store_error",
                    {"operation": "transition_incident", "error_type": type(exc).__name__},
                )

    def _write_report(self, incident_id: str, payload: Mapping[str, object]) -> None:
        if hasattr(self.store, "write_report"):
            try:
                self.store.write_report(incident_id, dict(payload))
                return
            except Exception as exc:
                self._record_event(
                    "internal_developer_store_error",
                    {"operation": "write_report", "error_type": type(exc).__name__},
                )
        self._record_event("internal_developer_report_fallback", dict(payload))

    @staticmethod
    def _coerce_action_type(
        action: ActionType | str | object, *, rejected: bool = False
    ) -> ActionType:
        try:
            return action if isinstance(action, ActionType) else ActionType(str(action))
        except ValueError as exc:
            if rejected:
                raise ActionRejected(
                    "action_not_allowlisted",
                    "Action is outside the operational recovery allowlist.",
                ) from exc
            raise ValueError("action is outside the operational recovery allowlist") from exc

    @staticmethod
    def _validate_safe_identifier(
        value: object, field: str, *, rejected: bool = False
    ) -> str:
        def fail(code: str, message: str) -> None:
            if rejected:
                raise ActionRejected(code, message)
            raise ValueError(message)

        if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
            fail("invalid_target_identifier", f"{field} must be a safe identifier, not a path.")
        lowered = value.lower()
        if any(fragment in lowered for fragment in _DANGEROUS_TARGET_FRAGMENTS):
            fail("forbidden_target", f"{field} refers to a forbidden capability.")
        return value


__all__ = [
    "ACTION_PARAMETER_SCHEMAS",
    "ALLOWED_ACTIONS",
    "ActionRejected",
    "ActionType",
    "InternalDeveloperEngine",
    "IssueClassification",
    "IssueType",
    "classify_issue",
    "classify_issues",
]
