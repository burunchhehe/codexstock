from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


TextFormatter = Callable[[object, int], str]
ManifestBinder = Callable[..., dict[str, object]]
ReportReceiver = Callable[..., tuple[dict[str, object], int]]
ReportNormalizer = Callable[[object], tuple[dict[str, object] | None, list[str]]]


class ExternalSignalFilePollerCore:
    """Poll an information-only external-engine outbox without blocking the app."""

    def __init__(
        self,
        *,
        state_path: Path,
        outbox_path_provider: Callable[[], Path],
        manifest_binder: ManifestBinder,
        report_receiver: ReportReceiver,
        text_formatter: TextFormatter,
        max_bytes: int,
        stale_minutes: int,
    ) -> None:
        self.state_path = state_path
        self.outbox_path_provider = outbox_path_provider
        self.manifest_binder = manifest_binder
        self.report_receiver = report_receiver
        self.text_formatter = text_formatter
        self.max_bytes = int(max_bytes)
        self.stale_minutes = int(stale_minutes)
        self.timezone = ZoneInfo("Asia/Seoul")
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.interval_seconds = 15
        self.last_fingerprint = ""
        self.state: dict[str, object] = {
            "schema": "codexstock_external_signal_poller_state_v1",
            "running": False,
            "status": "IDLE",
            "polling_seconds": self.interval_seconds,
            "outbox": str(self.outbox_path()),
            "last_checked_at": "",
            "last_imported_at": "",
            "last_report_generated_at": "",
            "last_result": "",
            "last_error": "",
            "live_order_allowed": False,
        }
        self.restored_from_state = False
        self._restore_state()

    def _restore_state(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        fingerprint = str(payload.get("source_fingerprint") or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            self.last_fingerprint = fingerprint
        for key in (
            "last_checked_at",
            "last_imported_at",
            "last_report_generated_at",
            "last_result",
            "source_age_minutes",
            "source_fingerprint",
            "source_json_valid",
            "manifest_generated_at",
            "manifest_binding",
        ):
            if key in payload:
                self.state[key] = payload[key]
        self.restored_from_state = True
        self.state["restored_from_state"] = True

    def outbox_path(self) -> Path:
        return Path(self.outbox_path_provider())

    def _save_state(self) -> None:
        snapshot = dict(self.state)
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.state_path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp_path.replace(self.state_path)
        except OSError:
            pass

    def _update(self, **changes: object) -> None:
        with self.lock:
            self.state.update(changes)
            self._save_state()

    def status(self) -> dict[str, object]:
        with self.lock:
            return dict(self.state)

    @staticmethod
    def validate_manifest(manifest: object) -> dict[str, object]:
        if not isinstance(manifest, dict):
            raise ValueError("receiver_manifest_must_be_object")
        if manifest.get("schema") != "external_search_codexstock_receiver_manifest_v1":
            raise ValueError("unsupported_receiver_manifest_schema")
        safety = manifest.get("safety") if isinstance(manifest.get("safety"), dict) else {}
        if (
            safety.get("decision_scope") != "information_only"
            or safety.get("external_engine_decision") != "VERIFY_ONLY"
            or safety.get("live_order_allowed") is not False
            or safety.get("requires_codexstock_validation") is not True
        ):
            raise ValueError("unsafe_receiver_manifest")
        return manifest

    # Compatibility alias retained for callers that used the former app-local class.
    _validate_manifest = validate_manifest

    def poll_once(self) -> dict[str, object]:
        outbox = self.outbox_path()
        report_path = outbox / "latest_external_signal_report.json"
        manifest_path = outbox / "receiver_manifest.json"
        checked_at = datetime.now(self.timezone).isoformat(timespec="seconds")
        try:
            if not manifest_path.is_file() or not report_path.is_file():
                self._update(
                    status="WAITING_FOR_OUTBOX",
                    outbox=str(outbox),
                    last_checked_at=checked_at,
                    last_error="receiver_manifest_or_report_missing",
                )
                return self.status()
            manifest = self.validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
            before = report_path.stat()
            if before.st_size <= 0 or before.st_size > self.max_bytes:
                raise ValueError("external_report_size_not_allowed")
            raw = report_path.read_bytes()
            after = report_path.stat()
            if before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
                raise OSError("external_report_changed_during_read")
            fingerprint = hashlib.sha256(raw).hexdigest()
            report = json.loads(raw.decode("utf-8"))
            if not isinstance(report, dict):
                raise ValueError("external_report_must_be_object")
            manifest_binding = self.manifest_binder(
                manifest,
                report,
                report_path=report_path,
                source_fingerprint=fingerprint,
            )
            if not manifest_binding.get("passed"):
                raise ValueError(
                    "manifest_report_binding_failed:"
                    + ",".join(str(item) for item in manifest_binding.get("blockers", []))
                )
            generated_at_text = self.text_formatter(report.get("generated_at"), 80)
            try:
                generated_at = datetime.fromisoformat(generated_at_text.replace("Z", "+00:00"))
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=self.timezone)
            except ValueError as exc:
                raise ValueError("external_report_generated_at_invalid") from exc
            source_age_minutes = max(
                0,
                int((datetime.now(self.timezone) - generated_at.astimezone(self.timezone)).total_seconds() / 60),
            )
            if source_age_minutes > self.stale_minutes:
                with self.lock:
                    self.last_fingerprint = fingerprint
                self._update(
                    status="SOURCE_STALE",
                    outbox=str(outbox),
                    last_checked_at=checked_at,
                    last_report_generated_at=generated_at_text,
                    source_age_minutes=source_age_minutes,
                    source_fingerprint=fingerprint,
                    source_json_valid=True,
                    manifest_binding=manifest_binding,
                    last_result="STALE_REPORT_QUARANTINED",
                    last_enqueued_verification_count=0,
                    last_error="external_report_stale",
                )
                return self.status()
            with self.lock:
                unchanged = fingerprint == self.last_fingerprint
            if unchanged:
                self._update(
                    status="WATCHING",
                    last_checked_at=checked_at,
                    last_report_generated_at=generated_at_text,
                    source_age_minutes=source_age_minutes,
                    source_fingerprint=fingerprint,
                    source_json_valid=True,
                    manifest_binding=manifest_binding,
                    last_result="UNCHANGED_SKIPPED",
                    last_enqueued_verification_count=0,
                    last_error="",
                )
                return self.status()
            receipt, http_status = self.report_receiver(
                report,
                source="external-search-mcp-file-poller",
            )
            with self.lock:
                self.last_fingerprint = fingerprint
            accepted = http_status == 200
            self._update(
                status="WATCHING" if accepted else "REPORT_REJECTED",
                outbox=str(outbox),
                last_checked_at=checked_at,
                last_imported_at=checked_at if accepted else self.state.get("last_imported_at", ""),
                last_report_generated_at=self.text_formatter(report.get("generated_at"), 80),
                source_age_minutes=source_age_minutes,
                manifest_generated_at=self.text_formatter(manifest.get("generated_at"), 80),
                source_fingerprint=fingerprint,
                source_json_valid=True,
                manifest_binding=manifest_binding,
                last_result=receipt.get("status", ""),
                last_enqueued_verification_count=receipt.get("enqueued_verification_count", 0),
                last_error="" if accepted else ";".join(receipt.get("errors", [])),
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            self._update(
                status="TRANSIENT_ERROR",
                outbox=str(outbox),
                last_checked_at=checked_at,
                source_json_valid=False,
                last_error=self.text_formatter(exc, 500),
            )
        return self.status()

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            self.poll_once()
            self.stop_event.wait(self.interval_seconds)

    def start(self, interval_seconds: int = 15) -> dict[str, object]:
        with self.lock:
            if self.thread and self.thread.is_alive():
                return dict(self.state)
            self.interval_seconds = max(5, min(int(interval_seconds or 15), 3600))
            self.stop_event.clear()
            self.state.update(
                running=True,
                status="STARTING",
                polling_seconds=self.interval_seconds,
                outbox=str(self.outbox_path()),
                last_error="",
            )
            self.thread = threading.Thread(
                target=self._loop,
                name="external-signal-file-poller",
                daemon=True,
            )
            self.thread.start()
            return dict(self.state)


def audit_external_signal_source_integrity(
    poller: ExternalSignalFilePollerCore,
    *,
    manifest_binder: ManifestBinder,
    report_normalizer: ReportNormalizer,
    text_formatter: TextFormatter,
    max_bytes: int,
    stale_minutes: int,
) -> dict[str, object]:
    """Read-only audit of the current outbox, independent of cached poller state."""
    timezone = ZoneInfo("Asia/Seoul")
    outbox = poller.outbox_path()
    report_path = outbox / "latest_external_signal_report.json"
    manifest_path = outbox / "receiver_manifest.json"
    checked_at = datetime.now(timezone)
    result: dict[str, object] = {
        "schema": "codexstock_external_signal_source_integrity_v1",
        "checked_at": checked_at.isoformat(timespec="seconds"),
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
        "report_exists": report_path.is_file(),
        "manifest_exists": manifest_path.is_file(),
        "json_valid": False,
        "schema_valid": False,
        "manifest_valid": False,
        "stale_after_minutes": int(stale_minutes),
        "age_minutes": None,
        "stale": True,
        "usable": False,
        "status": "MISSING",
        "errors": [],
    }
    errors: list[str] = []
    if not report_path.is_file() or not manifest_path.is_file():
        errors.append("receiver_manifest_or_report_missing")
        result["errors"] = errors
        return result
    manifest: dict[str, object] = {}
    try:
        manifest = poller.validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
        result["manifest_valid"] = True
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"manifest:{text_formatter(exc, 240)}")
    try:
        before = report_path.stat()
        if before.st_size <= 0 or before.st_size > int(max_bytes):
            raise ValueError("external_report_size_not_allowed")
        raw = report_path.read_bytes()
        after = report_path.stat()
        if before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
            raise OSError("external_report_changed_during_read")
        report = json.loads(raw.decode("utf-8"))
        result["json_valid"] = True
        result["size_bytes"] = after.st_size
        result["modified_at"] = datetime.fromtimestamp(after.st_mtime, tz=timezone).isoformat(timespec="seconds")
        result["fingerprint"] = hashlib.sha256(raw).hexdigest()
        if result["manifest_valid"]:
            binding = manifest_binder(
                manifest,
                report,
                report_path=report_path,
                source_fingerprint=str(result["fingerprint"]),
            )
            result["manifest_binding"] = binding
            if not binding.get("passed"):
                errors.extend(f"binding:{item}" for item in binding.get("blockers", []))
        normalized, validation_errors = report_normalizer(report)
        if normalized is None:
            errors.extend(f"report:{item}" for item in validation_errors[:12])
        else:
            result["schema_valid"] = True
            generated_at_text = text_formatter(normalized.get("generated_at"), 80)
            result["generated_at"] = generated_at_text
            try:
                generated_at = datetime.fromisoformat(generated_at_text.replace("Z", "+00:00"))
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=timezone)
                age_minutes = max(0, int((checked_at - generated_at.astimezone(timezone)).total_seconds() / 60))
                result["age_minutes"] = age_minutes
                result["stale"] = age_minutes > int(stale_minutes)
            except ValueError:
                errors.append("report:generated_at_invalid")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"report:{text_formatter(exc, 240)}")
    result["usable"] = bool(
        result["manifest_valid"]
        and result["json_valid"]
        and result["schema_valid"]
        and bool((result.get("manifest_binding") or {}).get("passed"))
        and not result["stale"]
        and not errors
    )
    result["status"] = (
        "USABLE"
        if result["usable"]
        else "STALE"
        if result["json_valid"] and result["schema_valid"] and result["stale"]
        else "INVALID"
    )
    result["errors"] = errors
    return result
