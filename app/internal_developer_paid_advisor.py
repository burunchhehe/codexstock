"""Approval and budget gate for paid remote developer advice."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping


SCHEMA = "codexstock.internal-developer-paid-advisor.v1"
ALLOWED_INCIDENT_STATES = frozenset(
    {"RECOVERY_FAILED", "NEEDS_EXTERNAL_ADVICE", "NEEDS_CODE_FIX"}
)
SECRET_KEY = re.compile(
    r"(?i)(api[_-]?key|app[_-]?secret|authorization|password|token|account[_-]?no|credential)"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _safe_id(prefix: str, material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def redact(value: object, *, depth: int = 0) -> object:
    """Recursively remove credentials and bound content sent to an advisor."""
    if depth > 8:
        return "[DEPTH_LIMIT]"
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for raw_key, raw_value in list(value.items())[:100]:
            key = str(raw_key)[:120]
            result[key] = "[REDACTED]" if SECRET_KEY.search(key) else redact(raw_value, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [redact(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        text = value[:8000]
        text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)
        text = re.sub(
            r"(?i)\b(api[_-]?key|app[_-]?secret|password|token)\s*[:=]\s*\S+",
            r"\1=[REDACTED]",
            text,
        )
        return text
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1000]


class PaidAdvisorGate:
    """Persist explicit approval, bounded usage, and quarantined advisor output."""

    def __init__(
        self,
        root: Path,
        *,
        max_incident_budget_krw: int = 5000,
        max_daily_budget_krw: int = 10000,
        max_calls_per_incident: int = 3,
    ) -> None:
        self.root = Path(root)
        self.requests_dir = self.root / "paid_advisor_requests"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.max_incident_budget_krw = max(100, int(max_incident_budget_krw))
        self.max_daily_budget_krw = max(self.max_incident_budget_krw, int(max_daily_budget_krw))
        self.max_calls_per_incident = max(1, int(max_calls_per_incident))
        self._lock = threading.RLock()

    def _path(self, request_id: str) -> Path:
        if not re.fullmatch(r"GPTREQ-[A-F0-9]{20}", str(request_id or "")):
            raise ValueError("invalid_paid_advisor_request_id")
        return self.requests_dir / f"{request_id}.json"

    def _write(self, record: dict[str, object]) -> None:
        path = self._path(str(record["request_id"]))
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def get(self, request_id: str) -> dict[str, object]:
        try:
            payload = json.loads(self._path(request_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(request_id) from exc
        if not isinstance(payload, dict):
            raise ValueError("invalid_paid_advisor_record")
        return payload

    def status(self, limit: int = 10) -> dict[str, object]:
        rows: list[dict[str, object]] = []
        for path in self.requests_dir.glob("GPTREQ-*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(row, dict):
                rows.append(row)
        rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
        today = _now().date().isoformat()
        return {
            "ok": True,
            "schema": SCHEMA,
            "request_count": len(rows),
            "awaiting_approval_count": sum(
                row.get("status") == "AWAITING_USER_APPROVAL" for row in rows
            ),
            "approved_count": sum(row.get("status") == "APPROVED" for row in rows),
            "quarantined_advice_count": sum(
                row.get("status") == "ADVICE_QUARANTINED" for row in rows
            ),
            "daily_used_budget_krw": self._daily_used(today),
            "max_daily_budget_krw": self.max_daily_budget_krw,
            "max_incident_budget_krw": self.max_incident_budget_krw,
            "max_calls_per_incident": self.max_calls_per_incident,
            "latest": rows[: max(1, min(int(limit or 10), 50))],
            "execution_authorized": False,
            "code_edit_authorized": False,
            "live_order_allowed": False,
        }

    def request(
        self,
        *,
        incident_id: str,
        incident_state: str,
        self_recovery_attempts: int,
        diagnostic_bundle: dict[str, object],
        requested_budget_krw: int = 5000,
    ) -> dict[str, object]:
        state = str(incident_state or "").upper()
        attempts = int(self_recovery_attempts or 0)
        if state not in ALLOWED_INCIDENT_STATES:
            raise ValueError("incident_not_eligible_for_paid_advisor")
        if attempts < 2:
            raise ValueError("self_recovery_attempts_insufficient")
        budget = max(100, min(int(requested_budget_krw or 0), self.max_incident_budget_krw))
        safe_bundle = redact(diagnostic_bundle)
        material = json.dumps(
            {"incident_id": incident_id, "bundle": safe_bundle},
            ensure_ascii=True,
            sort_keys=True,
        )
        request_id = _safe_id("GPTREQ", material)
        with self._lock:
            path = self._path(request_id)
            if path.exists():
                return self.get(request_id)
            now = _now()
            record = {
                "schema": SCHEMA,
                "request_id": request_id,
                "incident_id": str(incident_id),
                "status": "AWAITING_USER_APPROVAL",
                "created_at": _stamp(now),
                "updated_at": _stamp(now),
                "approval_expires_at": "",
                "self_recovery_attempts": attempts,
                "approved_by": "",
                "approved_budget_krw": 0,
                "requested_budget_krw": budget,
                "used_budget_krw": 0,
                "call_count": 0,
                "diagnostic_bundle": safe_bundle,
                "execution_authorized": False,
                "code_edit_authorized": False,
                "live_order_allowed": False,
            }
            self._write(record)
            return record

    def approve(
        self,
        request_id: str,
        *,
        approved_by: str,
        budget_krw: int,
        ttl_minutes: int = 30,
    ) -> dict[str, object]:
        actor = str(approved_by or "").strip()
        if not actor:
            raise ValueError("explicit_approver_required")
        with self._lock:
            record = self.get(request_id)
            if record.get("status") not in {"AWAITING_USER_APPROVAL", "APPROVED"}:
                raise ValueError("paid_advisor_request_not_approvable")
            approved = min(
                max(100, int(budget_krw or 0)),
                int(record["requested_budget_krw"]),
                self.max_incident_budget_krw,
            )
            now = _now()
            record.update(
                {
                    "status": "APPROVED",
                    "approved_by": actor[:120],
                    "approved_budget_krw": approved,
                    "approval_expires_at": _stamp(now + timedelta(minutes=max(1, min(ttl_minutes, 120)))),
                    "updated_at": _stamp(now),
                }
            )
            self._write(record)
            return record

    def _daily_used(self, day: str) -> int:
        total = 0
        for path in self.requests_dir.glob("GPTREQ-*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(row.get("updated_at") or "")[:10] == day:
                total += int(row.get("used_budget_krw") or 0)
        return total

    def invoke(
        self,
        request_id: str,
        *,
        estimated_cost_krw: int,
        advisor: Callable[[dict[str, object]], dict[str, object]],
    ) -> dict[str, object]:
        """Invoke one approved advisor callback and quarantine its response."""
        estimate = max(1, int(estimated_cost_krw or 0))
        with self._lock:
            record = self.get(request_id)
            if record.get("status") != "APPROVED":
                raise ValueError("paid_advisor_not_approved")
            expiry = datetime.fromisoformat(str(record.get("approval_expires_at") or ""))
            now = _now()
            if expiry.astimezone(timezone.utc) <= now:
                record["status"] = "APPROVAL_EXPIRED"
                record["updated_at"] = _stamp(now)
                self._write(record)
                raise ValueError("paid_advisor_approval_expired")
            if int(record.get("call_count") or 0) >= self.max_calls_per_incident:
                raise ValueError("paid_advisor_call_limit_reached")
            if int(record.get("used_budget_krw") or 0) + estimate > int(record["approved_budget_krw"]):
                raise ValueError("paid_advisor_incident_budget_exceeded")
            if self._daily_used(now.date().isoformat()) + estimate > self.max_daily_budget_krw:
                raise ValueError("paid_advisor_daily_budget_exceeded")
            record["status"] = "INVOKING"
            record["updated_at"] = _stamp(now)
            self._write(record)
        try:
            raw_result = advisor(
                {
                    "incident_id": record["incident_id"],
                    "diagnostic_bundle": record["diagnostic_bundle"],
                    "constraints": {
                        "return_structured_advice_only": True,
                        "no_live_orders": True,
                        "no_credentials": True,
                        "no_security_or_risk_relaxation": True,
                    },
                }
            )
            safe_result = redact(raw_result)
            if not isinstance(safe_result, dict):
                raise ValueError("advisor_response_must_be_mapping")
        except Exception as exc:
            with self._lock:
                record = self.get(request_id)
                record.update(
                    {
                        "status": "FAILED",
                        "last_error": f"{type(exc).__name__}: {exc}"[:500],
                        "updated_at": _stamp(),
                    }
                )
                self._write(record)
            raise
        with self._lock:
            record = self.get(request_id)
            record.update(
                {
                    "status": "ADVICE_QUARANTINED",
                    "call_count": int(record.get("call_count") or 0) + 1,
                    "used_budget_krw": int(record.get("used_budget_krw") or 0) + estimate,
                    "advisor_result": safe_result,
                    "updated_at": _stamp(),
                    "execution_authorized": False,
                    "code_edit_authorized": False,
                    "live_order_allowed": False,
                }
            )
            self._write(record)
            return record
