from __future__ import annotations

"""Durable, local storage for the CodexStock internal-developer sidecar.

The store is deliberately an execution-free boundary.  It persists diagnostics,
reports and external advice, but never turns advice into an executable command.
Every mutable artifact is a separate JSON file written with ``os.replace`` so a
crash cannot leave a half-written JSON document.
"""

import hashlib
import json
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:  # Package import in the application and direct import from ``app/`` both work.
    from app.runtime_paths import active_data_root
except ModuleNotFoundError:  # pragma: no cover - exercised by direct script/import smoke tests
    from runtime_paths import active_data_root


STORE_SCHEMA = "codexstock.internal-developer-store.v1"
INCIDENT_SCHEMA = "codexstock.internal-developer-incident.v1"
REPORT_SCHEMA = "codexstock.internal-developer-report.v1"
ADVICE_SCHEMA = "codexstock.internal-developer-advice.v1"
EVENT_SCHEMA = "codexstock.internal-developer-event.v1"
PLAYBOOK_SCHEMA = "codexstock.internal-developer-playbook.v1"
RESTART_REQUEST_SCHEMA = "codexstock.restart-request.v1"
INDEX_SCHEMA = "codexstock.internal-developer-index.v1"
STATE_SCHEMA = "codexstock.internal-developer-state.v1"

MAX_INPUT_BYTES = 256 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024
MAX_TEXT_CHARS = 16_000
MAX_COLLECTION_ITEMS = 100
MAX_DEPTH = 8
MAX_RECOVERY_ATTEMPTS = 50

INCIDENT_STATES = frozenset(
    {
        "NEW",
        "DIAGNOSING",
        "AUTO_RECOVERING",
        "RECOVERED_UNREVIEWED",
        "REVIEWED",
        "CLOSED",
        "RECOVERY_FAILED",
        "NEEDS_EXTERNAL_ADVICE",
        "ADVICE_RECEIVED",
        "RETRYING",
        "NEEDS_CODE_FIX",
        "WAITING_FOR_RESTART",
    }
)
OPEN_STATES = frozenset(
    {
        "NEW",
        "DIAGNOSING",
        "AUTO_RECOVERING",
        "RECOVERY_FAILED",
        "NEEDS_EXTERNAL_ADVICE",
        "ADVICE_RECEIVED",
        "RETRYING",
        "NEEDS_CODE_FIX",
        "WAITING_FOR_RESTART",
    }
)
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "NEW": frozenset(
        {
            "AUTO_RECOVERING",
            "DIAGNOSING",
            "RECOVERED_UNREVIEWED",
            "RECOVERY_FAILED",
            "NEEDS_EXTERNAL_ADVICE",
            "NEEDS_CODE_FIX",
            "CLOSED",
        }
    ),
    "DIAGNOSING": frozenset(
        {
            "NEW",
            "AUTO_RECOVERING",
            "RECOVERED_UNREVIEWED",
            "RECOVERY_FAILED",
            "NEEDS_EXTERNAL_ADVICE",
            "NEEDS_CODE_FIX",
            "WAITING_FOR_RESTART",
            "CLOSED",
        }
    ),
    "AUTO_RECOVERING": frozenset(
        {
            "RECOVERED_UNREVIEWED",
            "RECOVERY_FAILED",
            "NEEDS_EXTERNAL_ADVICE",
            "NEEDS_CODE_FIX",
            "WAITING_FOR_RESTART",
            "CLOSED",
        }
    ),
    "RECOVERY_FAILED": frozenset(
        {
            "DIAGNOSING",
            "AUTO_RECOVERING",
            "NEEDS_EXTERNAL_ADVICE",
            "ADVICE_RECEIVED",
            "NEEDS_CODE_FIX",
            "WAITING_FOR_RESTART",
            "CLOSED",
        }
    ),
    "NEEDS_EXTERNAL_ADVICE": frozenset(
        {"ADVICE_RECEIVED", "DIAGNOSING", "AUTO_RECOVERING", "NEEDS_CODE_FIX", "WAITING_FOR_RESTART", "CLOSED"}
    ),
    "ADVICE_RECEIVED": frozenset({"DIAGNOSING", "RETRYING", "AUTO_RECOVERING", "NEEDS_CODE_FIX", "WAITING_FOR_RESTART", "CLOSED"}),
    "RETRYING": frozenset(
        {"DIAGNOSING", "RECOVERED_UNREVIEWED", "RECOVERY_FAILED", "NEEDS_EXTERNAL_ADVICE", "NEEDS_CODE_FIX", "WAITING_FOR_RESTART"}
    ),
    "RECOVERED_UNREVIEWED": frozenset({"REVIEWED", "RETRYING", "CLOSED"}),
    "REVIEWED": frozenset({"CLOSED", "RETRYING"}),
    "NEEDS_CODE_FIX": frozenset({"DIAGNOSING", "AUTO_RECOVERING", "WAITING_FOR_RESTART", "CLOSED"}),
    "WAITING_FOR_RESTART": frozenset({"DIAGNOSING", "RECOVERED_UNREVIEWED", "RECOVERY_FAILED", "CLOSED"}),
    "CLOSED": frozenset(),
}

_ID_RE = re.compile(r"^[A-Z]{2,16}-[A-Z0-9][A-Z0-9_-]{0,95}$")
_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SECRET_KEY_RE = re.compile(
    r"(?:api[ _-]?key|access[ _-]?token|refresh[ _-]?token|authorization|password|passwd|"
    r"client[ _-]?secret|private[ _-]?key|credential|cookie|session[ _-]?token|secret)$",
    re.IGNORECASE,
)
_ACCOUNT_KEY_RE = re.compile(
    r"(?:account|account[ _-]?(?:no|number)|cano|acnt|계좌(?:번호)?)$", re.IGNORECASE
)
_FORBIDDEN_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "live_order": (
        re.compile(r"\b(?:live|real)[ _-]?(?:order|trade)\b", re.IGNORECASE),
        re.compile(r"실전\s*(?:주문|매수|매도)|실계좌\s*(?:주문|매매)"),
    ),
    "api_credentials": (
        re.compile(r"\b(?:api[ _-]?key|access[ _-]?token|secret|credential)s?\b", re.IGNORECASE),
        re.compile(r"(?:API|인증)\s*(?:키|토큰).{0,20}(?:변경|교체|삭제|노출)"),
    ),
    "risk_limit_relaxation": (
        re.compile(r"\b(?:relax|raise|disable|bypass).{0,30}\brisk[ _-]?limit", re.IGNORECASE),
        re.compile(r"(?:리스크|위험)\s*(?:한도|제한).{0,20}(?:완화|상향|해제|우회)"),
    ),
    "code_modification": (
        re.compile(r"\b(?:edit|modify|patch|rewrite).{0,30}\b(?:code|source|python|file)s?\b", re.IGNORECASE),
        re.compile(r"(?:코드|소스|파이썬|파일).{0,20}(?:수정|패치|재작성|덮어쓰기)"),
    ),
    "security_disable": (
        re.compile(r"\b(?:disable|remove|bypass).{0,30}\b(?:security|authentication|firewall|guard)s?\b", re.IGNORECASE),
        re.compile(r"(?:보안|인증|방화벽|안전장치).{0,20}(?:해제|비활성|우회|삭제)"),
    ),
}
_ALLOWED_ACTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "CACHE_CLEAR": re.compile(r"cache.{0,20}(?:clear|reset)|캐시.{0,20}(?:초기화|삭제)", re.IGNORECASE),
    "EXTERNAL_ENGINE_RECONNECT": re.compile(
        r"(?:(?:external[ _-]?engine|engine).{0,30}reconnect|reconnect.{0,30}(?:external[ _-]?engine|engine)|"
        r"외부\s*엔진.{0,30}재연결|재연결.{0,30}외부\s*엔진)",
        re.IGNORECASE,
    ),
    "FAILED_TASK_RETRY": re.compile(r"(?:failed[ _-]?task|job).{0,30}retry|실패\s*작업.{0,30}재시도", re.IGNORECASE),
    "STATE_LEDGER_RESTORE": re.compile(r"(?:state[ _-]?ledger).{0,30}restore|상태\s*원장.{0,30}복구", re.IGNORECASE),
    "DB_LOCK_DIAGNOSIS": re.compile(r"(?:db|database).{0,20}lock|DB\s*잠금", re.IGNORECASE),
    "RESTART_REQUEST": re.compile(r"restart[ _-]?request|재시작\s*요청", re.IGNORECASE),
    "INCIDENT_REPORT": re.compile(r"incident[ _-]?report|장애\s*리포트", re.IGNORECASE),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def _validate_id(value: object, prefix: str | None = None) -> str:
    candidate = str(value or "").strip().upper()
    if not _ID_RE.fullmatch(candidate):
        raise ValueError("invalid object id")
    if prefix and not candidate.startswith(prefix + "-"):
        raise ValueError(f"object id must start with {prefix}-")
    return candidate


def _mask_account(value: object) -> str:
    raw = str(value or "")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return "[MASKED_ACCOUNT]"
    return "*" * max(4, len(digits) - 4) + digits[-4:]


def _redact_text(value: str) -> str:
    text = value[:MAX_TEXT_CHARS]
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)\bsk-[A-Za-z0-9_-]{8,}", "[REDACTED_API_KEY]", text)
    text = re.sub(
        r"(?i)\b(api[ _-]?key|access[ _-]?token|refresh[ _-]?token|password|client[ _-]?secret)"
        r"\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?<!\d)(\d{2,6})-(\d{2,6})-(\d{2,6})(?!\d)",
        lambda match: "****-****-" + re.sub(r"\D", "", match.group(0))[-4:],
        text,
    )
    text = re.sub(
        r"(?i)\b(account(?:[ _-]?(?:no|number))?|계좌(?:번호)?)\s*[:=]?\s*([0-9][0-9 -]{7,28}[0-9])",
        lambda match: f"{match.group(1)}={_mask_account(match.group(2))}",
        text,
    )
    return text


def _json_safe(value: object, *, depth: int = 0, key: str = "") -> object:
    if _SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if _ACCOUNT_KEY_RE.search(key):
        return _mask_account(value)
    if depth >= MAX_DEPTH:
        return "[MAX_DEPTH]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Path):
        return _redact_text(str(value))
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for item_key, item_value in list(value.items())[:MAX_COLLECTION_ITEMS]:
            clean_key = _redact_text(str(item_key))[:160]
            result[clean_key] = _json_safe(item_value, depth=depth + 1, key=clean_key)
        if len(value) > MAX_COLLECTION_ITEMS:
            result["_truncated_items"] = len(value) - MAX_COLLECTION_ITEMS
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        rows = list(value)
        result = [_json_safe(item, depth=depth + 1) for item in rows[:MAX_COLLECTION_ITEMS]]
        if len(rows) > MAX_COLLECTION_ITEMS:
            result.append({"_truncated_items": len(rows) - MAX_COLLECTION_ITEMS})
        return result
    return _redact_text(str(value))


def _bounded_payload(value: object, *, limit: int = MAX_PAYLOAD_BYTES) -> object:
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"payload is not serializable: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raw = raw[:MAX_INPUT_BYTES]
    safe = _json_safe(value)
    encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(encoded) <= limit:
        return safe
    preview = _redact_text(encoded[: max(1, limit // 2)].decode("utf-8", errors="ignore"))
    return {
        "truncated": True,
        "original_sanitized_bytes": len(encoded),
        "sanitized_sha256": hashlib.sha256(encoded).hexdigest(),
        "preview": preview,
    }


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_flatten_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return "\n".join(_flatten_text(item) for item in value)
    return str(value or "")


def _policy_evaluation(value: object) -> dict[str, object]:
    text = _flatten_text(value)[:MAX_INPUT_BYTES]
    normalized_text = re.sub(r"[_-]+", " ", text)
    forbidden = sorted(
        category
        for category, patterns in _FORBIDDEN_PATTERNS.items()
        if any(pattern.search(candidate) for pattern in patterns for candidate in (text, normalized_text))
    )
    allowed = sorted(
        name
        for name, pattern in _ALLOWED_ACTION_PATTERNS.items()
        if pattern.search(text) or pattern.search(normalized_text)
    )
    return {
        "execution_authorized": False,
        "trust": "untrusted_external_guidance",
        "allowed_action_mentions": allowed,
        "forbidden_categories": forbidden,
        "quarantined": bool(forbidden),
        "requires_policy_validation": True,
        "requires_human_review": True,
    }


def _diagnostic_fingerprint(diagnostic: dict[str, object]) -> str:
    supplied = diagnostic.get("fingerprint")
    if supplied not in (None, ""):
        material: object = str(supplied).strip().lower()[:512]
    else:
        issues = diagnostic.get("issues") if isinstance(diagnostic.get("issues"), list) else []
        primary = issues[0] if issues and isinstance(issues[0], dict) else {}
        material = {
            "classification": str(
                diagnostic.get("primary_issue")
                or diagnostic.get("classification")
                or diagnostic.get("code")
                or primary.get("issue_code")
                or "UNKNOWN_FAILURE"
            ).upper(),
            "component": str(diagnostic.get("component") or primary.get("component") or "unknown").lower(),
            "summary": " ".join(
                str(diagnostic.get("summary") or primary.get("summary") or "").lower().split()
            ),
        }
    canonical = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class InternalDeveloperStore:
    """Atomic filesystem store below the active CodexStock data root."""

    def __init__(self, repo_root: Path, *, data_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root)
        self.data_root = Path(data_root) if data_root is not None else active_data_root(self.repo_root)
        self.root = self.data_root / "internal_developer"
        self.incidents_dir = self.root / "incidents"
        self.reports_dir = self.root / "reports"
        self.advice_dir = self.root / "advice"
        self.events_dir = self.root / "events"
        self.playbooks_dir = self.root / "playbooks"
        self.telegram_dir = self.root / "telegram"
        self.launcher_dir = self.root / "launcher"
        self.index_path = self.root / "index.json"
        self.state_path = self.root / "state.json"
        self.latest_report_path = self.root / "latest_report.json"
        self.telegram_report_path = self.telegram_dir / "latest_report.txt"
        self.launcher_report_path = self.launcher_dir / "latest_report.txt"
        self.restart_request_path = self.repo_root / "runtime" / "codexstock_restart_request.json"
        self._lock = threading.RLock()
        for directory in (
            self.incidents_dir,
            self.reports_dir,
            self.advice_dir,
            self.events_dir,
            self.playbooks_dir,
            self.telegram_dir,
            self.launcher_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self._ensure_ledgers()

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(40):
                try:
                    os.replace(temporary, path)
                    break
                except PermissionError:
                    if attempt >= 39:
                        raise
                    time.sleep(0.05)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(_redact_text(text))
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(40):
                try:
                    os.replace(temporary, path)
                    break
                except PermissionError:
                    if attempt >= 39:
                        raise
                    time.sleep(0.05)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _records(self, directory: Path, *, id_key: str, prefix: str) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for path in directory.glob(f"{prefix}-*.json"):
            payload = self._read_json(path)
            if payload is None:
                continue
            try:
                record_id = _validate_id(payload.get(id_key), prefix)
            except ValueError:
                continue
            if path.stem.upper() != record_id:
                continue
            records.append(payload)
        return records

    def _entity_specs(self) -> tuple[tuple[str, Path, str, str], ...]:
        return (
            ("incidents", self.incidents_dir, "incident_id", "INC"),
            ("reports", self.reports_dir, "report_id", "REP"),
            ("advice", self.advice_dir, "advice_id", "ADV"),
            ("events", self.events_dir, "event_id", "EVT"),
            ("playbooks", self.playbooks_dir, "playbook_id", "PB"),
        )

    def _ensure_ledgers(self) -> None:
        index = self._read_json(self.index_path)
        state = self._read_json(self.state_path)
        if not index or index.get("schema") != INDEX_SCHEMA or not state or state.get("schema") != STATE_SCHEMA:
            self.rebuild_ledgers()

    def rebuild_ledgers(self) -> dict[str, object]:
        """Reconstruct the disposable index and state ledger from source records."""
        with self._lock:
            entity_records: dict[str, list[dict[str, object]]] = {}
            index_entities: dict[str, dict[str, object]] = {}
            for name, directory, id_key, prefix in self._entity_specs():
                rows = self._records(directory, id_key=id_key, prefix=prefix)
                entity_records[name] = rows
                index_entities[name] = {
                    str(row[id_key]): {
                        "updated_at": row.get("updated_at") or row.get("created_at") or row.get("received_at"),
                        "state": row.get("state") or row.get("status") or row.get("review_status"),
                        "path": str((directory / f"{row[id_key]}.json").relative_to(self.root)),
                    }
                    for row in rows
                }
            now = _utc_now()
            index_payload: dict[str, object] = {
                "schema": INDEX_SCHEMA,
                "store_schema": STORE_SCHEMA,
                "rebuilt_at": now,
                "entities": index_entities,
            }
            summary = self._status_from_records(entity_records, generated_at=now)
            state_payload: dict[str, object] = {
                "schema": STATE_SCHEMA,
                "store_schema": STORE_SCHEMA,
                "rebuilt_at": now,
                "status": summary,
            }
            self._atomic_write_json(self.index_path, index_payload)
            self._atomic_write_json(self.state_path, state_payload)
            return {"index": index_payload, "state": state_payload}

    def _refresh(self) -> None:
        self.rebuild_ledgers()

    def open_incident(self, diagnostic: dict[str, object]) -> dict[str, object]:
        if not isinstance(diagnostic, dict):
            raise TypeError("diagnostic must be a dict")
        with self._lock:
            incident_id = _validate_id(diagnostic.get("incident_id"), "INC") if diagnostic.get("incident_id") else _make_id("INC")
            path = self.incidents_dir / f"{incident_id}.json"
            if path.exists():
                raise FileExistsError(f"incident already exists: {incident_id}")
            now = _utc_now()
            safe = _bounded_payload(diagnostic)
            assert isinstance(safe, dict)
            issues = safe.get("issues") if isinstance(safe.get("issues"), list) else []
            primary = issues[0] if issues and isinstance(issues[0], dict) else {}
            fingerprint = _diagnostic_fingerprint(safe)
            incoming_classification = str(
                safe.get("primary_issue")
                or safe.get("classification")
                or safe.get("code")
                or primary.get("issue_code")
                or "UNKNOWN_FAILURE"
            )[:96]
            for existing in self._records(self.incidents_dir, id_key="incident_id", prefix="INC"):
                same_fingerprint = existing.get("fingerprint") == fingerprint
                refines_unknown_component = bool(
                    str(existing.get("classification") or "") == incoming_classification
                    and str(existing.get("component") or "unknown").lower() == "unknown"
                )
                if existing.get("state") not in OPEN_STATES or not (
                    same_fingerprint or refines_unknown_component
                ):
                    continue
                duplicate_id = _validate_id(existing.get("incident_id"), "INC")
                history = existing.get("history") if isinstance(existing.get("history"), list) else []
                history.append(
                    {
                        "from": existing.get("state"),
                        "to": existing.get("state"),
                        "at": now,
                        "note": "duplicate diagnostic observation deduplicated",
                    }
                )
                existing.update(
                    {
                        "updated_at": now,
                        "last_seen_at": now,
                        "recurrence_count": int(existing.get("recurrence_count") or 1) + 1,
                        "deduplicated": True,
                        "history": history[-100:],
                    }
                )
                # A repeated observation may carry a newer, more precise
                # diagnostic contract.  Refresh descriptive evidence without
                # changing incident state or discarding recovery history.
                component = str(safe.get("component") or primary.get("component") or "").strip()
                summary = str(safe.get("summary") or primary.get("summary") or "").strip()
                if component and component.lower() != "unknown":
                    existing["component"] = component[:160]
                if summary and summary != "-":
                    existing["summary"] = _redact_text(summary)
                existing["diagnostic"] = safe
                self._atomic_write_json(self.incidents_dir / f"{duplicate_id}.json", existing)
                self._record_event_unlocked(
                    "incident.deduplicated", {"incident_id": duplicate_id, "fingerprint": fingerprint}
                )
                self._refresh()
                return existing
            record: dict[str, object] = {
                "schema": INCIDENT_SCHEMA,
                "incident_id": incident_id,
                "state": "NEW",
                "severity": str(safe.get("severity") or primary.get("severity") or "warning")[:32].lower(),
                "classification": str(
                    safe.get("primary_issue")
                    or safe.get("classification")
                    or safe.get("code")
                    or primary.get("issue_code")
                    or "UNKNOWN_FAILURE"
                )[:96],
                "component": str(safe.get("component") or primary.get("component") or "unknown")[:160],
                "summary": _redact_text(
                    str(safe.get("summary") or primary.get("summary") or "Operational anomaly detected")
                ),
                "created_at": now,
                "updated_at": now,
                "reviewed": False,
                "fingerprint": fingerprint,
                "recurrence_count": 1,
                "last_seen_at": now,
                "deduplicated": False,
                "diagnostic": safe,
                "recovery_attempts": [],
                "history": [{"from": None, "to": "NEW", "at": now, "note": "incident opened"}],
            }
            self._atomic_write_json(path, record)
            self._record_event_unlocked("incident.opened", {"incident_id": incident_id, "state": "NEW"})
            self._refresh()
            return record

    def get_incident(self, incident_id: str) -> dict[str, object] | None:
        value = _validate_id(incident_id, "INC")
        return self._read_json(self.incidents_dir / f"{value}.json")

    def transition_incident(
        self,
        incident_id: str,
        new_state: str,
        note: str = "",
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with self._lock:
            value = _validate_id(incident_id, "INC")
            target = str(new_state or "").strip().upper()
            if target not in INCIDENT_STATES:
                raise ValueError(f"unknown incident state: {target}")
            path = self.incidents_dir / f"{value}.json"
            record = self._read_json(path)
            if record is None:
                raise KeyError(value)
            current = str(record.get("state") or "")
            if target == current or target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise ValueError(f"invalid incident transition: {current} -> {target}")
            pipeline_classes = {
                "MARKET_SCAN_STALLED",
                "CANDIDATE_VALIDATION_STALLED",
                "CANDIDATE_PROMOTION_STALLED",
                "SIGNED_SIGNAL_MISSING",
                "EXECUTOR_HANDOFF_FAILED",
                "LEGACY_APPROVAL_GATE_ACTIVE",
            }
            if target == "CLOSED" and str(record.get("classification") or "").upper() in pipeline_classes:
                closure = metadata if isinstance(metadata, dict) else {}
                required = (
                    "root_cause_confirmed",
                    "reproduction_checked",
                    "end_to_end_verified",
                    "regression_test_passed",
                )
                missing = [name for name in required if closure.get(name) is not True]
                if missing:
                    raise ValueError(
                        "pipeline incident closure requires verified evidence: " + ", ".join(missing)
                    )
            now = _utc_now()
            history = record.get("history") if isinstance(record.get("history"), list) else []
            history.append(
                {
                    "from": current,
                    "to": target,
                    "at": now,
                    "note": _redact_text(str(note or "")),
                    "metadata": _bounded_payload(metadata or {}, limit=8 * 1024),
                }
            )
            record.update(
                {
                    "state": target,
                    "updated_at": now,
                    "reviewed": target in {"REVIEWED", "CLOSED"},
                    "history": history[-100:],
                }
            )
            self._atomic_write_json(path, record)
            self._record_event_unlocked(
                "incident.transitioned", {"incident_id": value, "from": current, "to": target, "note": note}
            )
            self._refresh()
            return record

    def record_recovery_attempt(self, incident_id: str, attempt: dict[str, object]) -> dict[str, object]:
        if not isinstance(attempt, dict):
            raise TypeError("attempt must be a dict")
        with self._lock:
            value = _validate_id(incident_id, "INC")
            path = self.incidents_dir / f"{value}.json"
            record = self._read_json(path)
            if record is None:
                raise KeyError(value)
            safe = _bounded_payload(attempt, limit=16 * 1024)
            assert isinstance(safe, dict)
            attempts = record.get("recovery_attempts") if isinstance(record.get("recovery_attempts"), list) else []
            row = {"attempt_id": _make_id("ATT"), "recorded_at": _utc_now(), **safe}
            row["execution_scope"] = "allowlisted_operational_recovery_only"
            attempts.append(row)
            record["recovery_attempts"] = attempts[-MAX_RECOVERY_ATTEMPTS:]
            record["updated_at"] = row["recorded_at"]
            self._atomic_write_json(path, record)
            self._record_event_unlocked("recovery.attempt_recorded", {"incident_id": value, "attempt": row})
            self._refresh()
            return row

    def _report_text(self, incident: dict[str, object], report: dict[str, object], *, compact: bool) -> str:
        details = report.get("payload") if isinstance(report.get("payload"), dict) else {}
        lines = [
            f"[CodexStock 내부 개발자] {incident.get('state')} / {incident.get('severity')}",
            f"사건: {incident.get('incident_id')}",
            f"분류: {incident.get('classification')} / 구성요소: {incident.get('component')}",
            f"요약: {incident.get('summary')}",
        ]
        for label, key in (
            ("원인", "cause"),
            ("조치", "actions"),
            ("검증", "verification"),
            ("다음 단계", "next_step"),
            ("GPT 자문 질문", "external_advice_question"),
        ):
            if details.get(key) not in (None, "", [], {}):
                value = _flatten_text(details[key]).replace("\n", "; " if compact else "\n  - ")
                lines.append(f"{label}: {value}")
        lines.append("안전: 이 문서는 진단 자료이며 주문·키·리스크·코드·보안 설정의 실행 권한이 없습니다.")
        return _redact_text("\n".join(lines) + "\n")

    def write_report(self, incident_id: str, payload: dict[str, object]) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        with self._lock:
            value = _validate_id(incident_id, "INC")
            incident = self.get_incident(value)
            if incident is None:
                raise KeyError(value)
            report_id = _validate_id(payload.get("report_id"), "REP") if payload.get("report_id") else _make_id("REP")
            now = _utc_now()
            safe = _bounded_payload(payload)
            assert isinstance(safe, dict)
            telegram_relative = Path("reports") / f"{report_id}.telegram.txt"
            launcher_relative = Path("reports") / f"{report_id}.launcher.txt"
            report: dict[str, object] = {
                "schema": REPORT_SCHEMA,
                "report_id": report_id,
                "incident_id": value,
                "created_at": now,
                "updated_at": now,
                "review_status": "UNREVIEWED",
                "execution_authorized": False,
                "payload": safe,
                "artifacts": {
                    "telegram_text": str(telegram_relative).replace("\\", "/"),
                    "launcher_text": str(launcher_relative).replace("\\", "/"),
                },
            }
            telegram_text = self._report_text(incident, report, compact=True)
            launcher_text = self._report_text(incident, report, compact=False)
            self._atomic_write_text(self.root / telegram_relative, telegram_text)
            self._atomic_write_text(self.root / launcher_relative, launcher_text)
            self._atomic_write_json(self.reports_dir / f"{report_id}.json", report)
            self._atomic_write_json(self.latest_report_path, report)
            self._atomic_write_text(self.telegram_report_path, telegram_text)
            self._atomic_write_text(self.launcher_report_path, launcher_text)
            self._record_event_unlocked("report.written", {"incident_id": value, "report_id": report_id})
            self._refresh()
            return report

    def get_report(self, report_id: str) -> dict[str, object] | None:
        value = _validate_id(report_id, "REP")
        return self._read_json(self.reports_dir / f"{value}.json")

    def acknowledge_report(self, report_id: str, note: str = "") -> dict[str, object]:
        with self._lock:
            value = _validate_id(report_id, "REP")
            path = self.reports_dir / f"{value}.json"
            report = self._read_json(path)
            if report is None:
                raise KeyError(value)
            report.update(
                {
                    "review_status": "REVIEWED",
                    "reviewed_at": _utc_now(),
                    "review_note": _redact_text(str(note or "")),
                    "updated_at": _utc_now(),
                    "execution_authorized": False,
                }
            )
            self._atomic_write_json(path, report)
            latest = self._read_json(self.latest_report_path)
            if latest and latest.get("report_id") == value:
                self._atomic_write_json(self.latest_report_path, report)
            self._record_event_unlocked("report.reviewed", {"report_id": value})
            self._refresh()
            return report

    def submit_advice(self, payload: dict[str, object]) -> dict[str, object]:
        """Store GPT/MCP advice as bounded, redacted and never executable guidance."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        with self._lock:
            incident_id = _validate_id(payload.get("incident_id"), "INC")
            if self.get_incident(incident_id) is None:
                raise KeyError(incident_id)
            advice_id = _validate_id(payload.get("advice_id"), "ADV") if payload.get("advice_id") else _make_id("ADV")
            safe = _bounded_payload(payload)
            assert isinstance(safe, dict)
            safe.pop("execution_authorized", None)
            evaluation = _policy_evaluation(safe)
            now = _utc_now()
            record: dict[str, object] = {
                "schema": ADVICE_SCHEMA,
                "advice_id": advice_id,
                "incident_id": incident_id,
                "source": "gpt_via_mcp",
                "status": "QUARANTINED" if evaluation["quarantined"] else "RECEIVED",
                "received_at": now,
                "updated_at": now,
                "execution_authorized": False,
                "advice": safe,
                "policy_evaluation": evaluation,
            }
            self._atomic_write_json(self.advice_dir / f"{advice_id}.json", record)
            self._record_event_unlocked(
                "advice.received",
                {
                    "incident_id": incident_id,
                    "advice_id": advice_id,
                    "quarantined": evaluation["quarantined"],
                },
            )
            incident = self.get_incident(incident_id)
            if (
                not evaluation["quarantined"]
                and incident is not None
                and incident.get("state") in {"NEEDS_EXTERNAL_ADVICE", "RECOVERY_FAILED"}
            ):
                self.transition_incident(
                    incident_id,
                    "ADVICE_RECEIVED",
                    note="Bounded external guidance received; no execution authority granted.",
                    metadata={"advice_id": advice_id, "execution_authorized": False},
                )
            self._refresh()
            return record

    def get_advice(self, advice_id: str) -> dict[str, object] | None:
        value = _validate_id(advice_id, "ADV")
        return self._read_json(self.advice_dir / f"{value}.json")

    def update_advice(self, advice_id: str, changes: dict[str, object]) -> dict[str, object]:
        if not isinstance(changes, dict):
            raise TypeError("changes must be a dict")
        protected = {"execution_authorized", "advice", "policy_evaluation", "incident_id", "source", "advice_id"}
        if protected.intersection(changes):
            raise ValueError("protected advice fields cannot be changed")
        allowed = {
            "status",
            "review_note",
            "review_metadata",
            "application_result",
            "engine_result",
            "linked_playbook_id",
        }
        unknown = set(changes).difference(allowed)
        if unknown:
            raise ValueError(f"unsupported advice fields: {sorted(unknown)}")
        with self._lock:
            value = _validate_id(advice_id, "ADV")
            path = self.advice_dir / f"{value}.json"
            record = self._read_json(path)
            if record is None:
                raise KeyError(value)
            safe = _bounded_payload(changes, limit=16 * 1024)
            assert isinstance(safe, dict)
            if "status" in safe:
                target = str(safe["status"]).upper()
                if target not in {"RECEIVED", "QUARANTINED", "UNDER_REVIEW", "ACCEPTED_AS_GUIDANCE", "REJECTED", "ARCHIVED"}:
                    raise ValueError("invalid advice status")
                safe["status"] = target
            record.update(safe)
            record["execution_authorized"] = False
            record["updated_at"] = _utc_now()
            self._atomic_write_json(path, record)
            self._record_event_unlocked("advice.updated", {"advice_id": value, "changes": safe})
            self._refresh()
            return record

    def _record_event_unlocked(self, event_type: str, payload: dict[str, object]) -> dict[str, object]:
        kind = str(event_type or "").strip().lower()
        if not _EVENT_TYPE_RE.fullmatch(kind):
            raise ValueError("invalid event type")
        event_id = _make_id("EVT")
        record: dict[str, object] = {
            "schema": EVENT_SCHEMA,
            "event_id": event_id,
            "event_type": kind,
            "created_at": _utc_now(),
            "payload": _bounded_payload(payload, limit=24 * 1024),
        }
        self._atomic_write_json(self.events_dir / f"{event_id}.json", record)
        return record

    def record_event(self, event_type: str, payload: dict[str, object]) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        with self._lock:
            record = self._record_event_unlocked(event_type, payload)
            self._refresh()
            return record

    def request_restart(self, expected_pid: int, incident_id: str, reason: str) -> dict[str, object]:
        with self._lock:
            value = _validate_id(incident_id, "INC")
            if self.get_incident(value) is None:
                raise KeyError(value)
            if isinstance(expected_pid, bool) or not isinstance(expected_pid, int) or expected_pid <= 0:
                raise ValueError("expected_pid must be a positive integer")
            if self.restart_request_path.exists():
                existing = self._read_json(self.restart_request_path)
                if existing is None:
                    raise FileExistsError("an unreadable restart request already exists")
                return {**existing, "already_pending": True}
            record: dict[str, object] = {
                "schema": RESTART_REQUEST_SCHEMA,
                "request_id": _make_id("RST"),
                "incident_id": value,
                "expected_pid": expected_pid,
                "reason": _redact_text(str(reason or "unspecified operational recovery")),
                "requested_at": _utc_now(),
                "requested": True,
                "success": True,
                "request_created": True,
                "execution_performed": False,
                "scheduler_authority_required": True,
                "safety": "The sidecar requests a restart; only the independent launcher may perform it.",
            }
            self._atomic_write_json(self.restart_request_path, record)
            self._record_event_unlocked("restart.requested", record)
            self._refresh()
            return record

    def learn_playbook(self, incident_id: str, action: object, result: object) -> dict[str, object]:
        with self._lock:
            value = _validate_id(incident_id, "INC")
            if self.get_incident(value) is None:
                raise KeyError(value)
            safe_action = _bounded_payload(action, limit=16 * 1024)
            safe_result = _bounded_payload(result, limit=16 * 1024)
            evaluation = _policy_evaluation(safe_action)
            result_dict = safe_result if isinstance(safe_result, dict) else {}
            action_dict = safe_action if isinstance(safe_action, dict) else {}
            structured_name = str(
                action_dict.get("action_type")
                or action_dict.get("action")
                or action_dict.get("name")
                or action_dict.get("operation")
                or ""
            ).strip().upper().replace("-", "_").replace(" ", "_")
            action_aliases = {
                "CLEAR_CACHE": "CACHE_CLEAR",
                "CLEAR_NAMED_CACHE": "CACHE_CLEAR",
                "RESET_CACHE": "CACHE_CLEAR",
                "RECONNECT_EXTERNAL_ENGINE": "EXTERNAL_ENGINE_RECONNECT",
                "EXTERNAL_ENGINE_RECONNECT": "EXTERNAL_ENGINE_RECONNECT",
                "RETRY_FAILED_TASK": "FAILED_TASK_RETRY",
                "RETRY_RESEARCH_JOB": "FAILED_TASK_RETRY",
                "FAILED_TASK_RETRY": "FAILED_TASK_RETRY",
                "RESTORE_STATE_LEDGER": "STATE_LEDGER_RESTORE",
                "RESTORE_INTERNAL_STATE_LEDGER": "STATE_LEDGER_RESTORE",
                "STATE_LEDGER_RESTORE": "STATE_LEDGER_RESTORE",
                "DETECT_DB_LOCK": "DB_LOCK_DIAGNOSIS",
                "WAIT_DB_LOCK": "DB_LOCK_DIAGNOSIS",
                "DB_LOCK_DIAGNOSIS": "DB_LOCK_DIAGNOSIS",
                "CREATE_RESTART_REQUEST": "RESTART_REQUEST",
                "REQUEST_RESTART": "RESTART_REQUEST",
                "REQUEST_CODEXSTOCK_RESTART": "RESTART_REQUEST",
                "RESTART_REQUEST": "RESTART_REQUEST",
                "WRITE_INCIDENT_REPORT": "INCIDENT_REPORT",
                "INCIDENT_REPORT": "INCIDENT_REPORT",
                "CACHE_CLEAR": "CACHE_CLEAR",
            }
            structured_allowed = action_aliases.get(structured_name)
            mentioned = list(evaluation["allowed_action_mentions"])
            if structured_allowed and structured_allowed not in mentioned:
                mentioned.append(structured_allowed)
                mentioned.sort()
                evaluation["allowed_action_mentions"] = mentioned
            post_verification = result_dict.get("post_verification")
            post_ok = bool(post_verification.get("success")) if isinstance(post_verification, dict) else False
            outcome_ok = str(result_dict.get("status") or "").lower() in {"succeeded", "idempotent_replay"}
            verified = (bool(result_dict.get("verified")) and bool(result_dict.get("success"))) or (
                outcome_ok and post_ok
            )
            reusable = bool(mentioned) and not evaluation["quarantined"] and verified
            playbook_id = _make_id("PB")
            now = _utc_now()
            record: dict[str, object] = {
                "schema": PLAYBOOK_SCHEMA,
                "playbook_id": playbook_id,
                "incident_id": value,
                "created_at": now,
                "updated_at": now,
                "status": "VERIFIED_SAFE" if reusable else "QUARANTINED_OR_UNVERIFIED",
                "action": safe_action,
                "result": safe_result,
                "policy_evaluation": evaluation,
                "automatic_reuse_eligible": reusable,
                "execution_authorized": False,
                "note": "Eligibility is evidence for the deterministic policy engine, not an executable command.",
            }
            self._atomic_write_json(self.playbooks_dir / f"{playbook_id}.json", record)
            self._record_event_unlocked(
                "playbook.learned", {"incident_id": value, "playbook_id": playbook_id, "reusable": reusable}
            )
            self._refresh()
            return record

    def _list_records(
        self, directory: Path, *, id_key: str, prefix: str, limit: int = 100
    ) -> list[dict[str, object]]:
        bounded_limit = max(0, min(int(limit), 500))
        rows = self._records(directory, id_key=id_key, prefix=prefix)
        rows.sort(
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or row.get("received_at") or ""),
            reverse=True,
        )
        return rows[:bounded_limit]

    def list_incidents(self, limit: int = 100) -> list[dict[str, object]]:
        return self._list_records(self.incidents_dir, id_key="incident_id", prefix="INC", limit=limit)

    def list_reports(self, limit: int = 100) -> list[dict[str, object]]:
        return self._list_records(self.reports_dir, id_key="report_id", prefix="REP", limit=limit)

    def list_advice(self, limit: int = 100) -> list[dict[str, object]]:
        return self._list_records(self.advice_dir, id_key="advice_id", prefix="ADV", limit=limit)

    def list_events(self, limit: int = 100, *, event_type: str | None = None) -> list[dict[str, object]]:
        rows = self._list_records(self.events_dir, id_key="event_id", prefix="EVT", limit=500)
        if event_type:
            kind = str(event_type).strip().lower()
            rows = [row for row in rows if row.get("event_type") == kind]
        return rows[: max(0, min(int(limit), 500))]

    def activity(self, limit: int = 50) -> list[dict[str, object]]:
        return self.list_events(limit=limit)

    def get_event(self, event_id: str) -> dict[str, object] | None:
        value = _validate_id(event_id, "EVT")
        return self._read_json(self.events_dir / f"{value}.json")

    def get_playbook(self, playbook_id: str) -> dict[str, object] | None:
        value = _validate_id(playbook_id, "PB")
        return self._read_json(self.playbooks_dir / f"{value}.json")

    def list_playbooks(self, limit: int = 100) -> list[dict[str, object]]:
        return self._list_records(self.playbooks_dir, id_key="playbook_id", prefix="PB", limit=limit)

    @staticmethod
    def _status_from_records(
        records: dict[str, list[dict[str, object]]], *, generated_at: str
    ) -> dict[str, object]:
        incidents = records.get("incidents", [])
        reports = records.get("reports", [])
        advice = records.get("advice", [])
        incident_by_id = {str(row.get("incident_id") or ""): row for row in incidents}

        def is_drill(row: dict[str, object]) -> bool:
            diagnostic = row.get("diagnostic") if isinstance(row.get("diagnostic"), dict) else {}
            return diagnostic.get("drill") is True or diagnostic.get("actual_failure") is False

        transient_classes = {
            "HEARTBEAT_MISSING",
            "PROCESS_UNRESPONSIVE",
            "DIAGNOSTIC_ENDPOINT_UNAVAILABLE",
        }
        all_open_incidents = [row for row in incidents if row.get("state") in OPEN_STATES]
        drill_open_incidents = [row for row in all_open_incidents if is_drill(row)]
        open_incidents = [row for row in all_open_incidents if not is_drill(row)]
        all_recovered_unreviewed = [
            row for row in incidents if row.get("state") == "RECOVERED_UNREVIEWED"
        ]
        informational_recovered = [
            row
            for row in all_recovered_unreviewed
            if is_drill(row) or str(row.get("classification") or "").upper() in transient_classes
        ]
        recovered_unreviewed = [
            row for row in all_recovered_unreviewed if row not in informational_recovered
        ]
        all_unreviewed_reports = [
            row for row in reports if row.get("review_status") != "REVIEWED"
        ]
        actionable_incident_ids = {
            str(row.get("incident_id") or "") for row in open_incidents + recovered_unreviewed
        }
        unreviewed_reports = [
            row
            for row in all_unreviewed_reports
            if str(row.get("incident_id") or "") in actionable_incident_ids
        ]
        informational_reports = [
            row for row in all_unreviewed_reports if row not in unreviewed_reports
        ]
        unreviewed_advice = [
            row
            for row in advice
            if row.get("status") in {"RECEIVED", "UNDER_REVIEW"}
            and not is_drill(incident_by_id.get(str(row.get("incident_id") or ""), {}))
        ]
        quarantined_advice = [row for row in advice if row.get("status") == "QUARANTINED"]
        latest_report = max(reports, key=lambda row: str(row.get("created_at") or ""), default=None)
        attention = bool(open_incidents or recovered_unreviewed or unreviewed_reports or unreviewed_advice)
        needs_external = any(
            row.get("state") in {"RECOVERY_FAILED", "NEEDS_EXTERNAL_ADVICE", "NEEDS_CODE_FIX"}
            for row in open_incidents
        )
        return {
            "schema": "codexstock.internal-developer-status.v1",
            "generated_at": generated_at,
            "operational_status": "healthy" if not open_incidents else "degraded",
            "healthy": not open_incidents,
            "attention_required": attention,
            "open_incidents": len(open_incidents),
            "drill_open_incidents": len(drill_open_incidents),
            "recovered_unreviewed_incidents": len(recovered_unreviewed),
            "recovered_unreviewed_total": len(all_recovered_unreviewed),
            "informational_recovered_incidents": len(informational_recovered),
            "unreviewed_reports": len(unreviewed_reports),
            "unreviewed_reports_total": len(all_unreviewed_reports),
            "informational_unreviewed_reports": len(informational_reports),
            "unreviewed_advice": len(unreviewed_advice),
            "quarantined_advice": len(quarantined_advice),
            "needs_external_advice": needs_external,
            "latest_report_id": latest_report.get("report_id") if latest_report else None,
            "counts": {name: len(rows) for name, rows in records.items()},
            "safety": {
                "external_advice_execution_authorized": False,
                "forbidden": ["live_order", "api_key_change", "risk_limit_relaxation", "code_edit", "security_disable"],
            },
        }

    def status(self) -> dict[str, object]:
        with self._lock:
            rebuilt = self.rebuild_ledgers()
            state = rebuilt["state"]
            assert isinstance(state, dict)
            summary = state.get("status")
            assert isinstance(summary, dict)
            return summary

    def attention_summary(self) -> dict[str, object]:
        summary = self.status()
        return {
            "operational_status": summary["operational_status"],
            "healthy": summary["healthy"],
            "attention_required": summary["attention_required"],
            "open_incidents": summary["open_incidents"],
            "unreviewed_reports": summary["unreviewed_reports"],
            "unreviewed_advice": summary["unreviewed_advice"],
            "latest_report_id": summary["latest_report_id"],
            "needs_external_advice": summary["needs_external_advice"],
        }


__all__ = [
    "ADVICE_SCHEMA",
    "EVENT_SCHEMA",
    "INCIDENT_SCHEMA",
    "INCIDENT_STATES",
    "InternalDeveloperStore",
    "PLAYBOOK_SCHEMA",
    "REPORT_SCHEMA",
    "RESTART_REQUEST_SCHEMA",
    "STORE_SCHEMA",
]
