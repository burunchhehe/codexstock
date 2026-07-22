from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


EXCLUDED_NAMES = {
    ".env",
    ".git",
    "__pycache__",
    "data",
    "logs",
    "runtime",
    "secrets",
    "tokens",
}
SECRET_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        lowered = {part.lower() for part in relative.parts}
        if lowered & EXCLUDED_NAMES:
            continue
        if path.suffix.lower() in SECRET_SUFFIXES:
            continue
        yield relative


class SafeUpdateManager:
    """Prepare and activate code releases without touching private runtime data."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.staging_root = self.root / "staging"
        self.backup_root = self.root / "backups"
        self.records_root = self.root / "records"
        for path in (self.staging_root, self.backup_root, self.records_root):
            path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def prepare(self, source: Path, *, release_id: str) -> dict[str, object]:
        source = Path(source).resolve()
        if not source.is_dir():
            raise ValueError("update_source_missing")
        safe_id = "".join(ch for ch in str(release_id) if ch.isalnum() or ch in "-_")
        if not safe_id or safe_id != str(release_id):
            raise ValueError("invalid_release_id")
        target = self.staging_root / safe_id
        if target.exists():
            raise FileExistsError("release_already_staged")
        target.mkdir(parents=True)
        files: list[dict[str, object]] = []
        for relative in _safe_relative_files(source):
            source_file = source / relative
            target_file = target / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            files.append(
                {
                    "path": relative.as_posix(),
                    "size": target_file.stat().st_size,
                    "sha256": _hash_file(target_file),
                }
            )
        manifest = {
            "schema": "codexstock.safe-update.v1",
            "release_id": safe_id,
            "status": "STAGED",
            "created_at": _stamp(),
            "file_count": len(files),
            "files": files,
            "private_runtime_data_included": False,
            "secrets_included": False,
        }
        self._write_record(safe_id, manifest)
        return manifest

    def validate(
        self,
        release_id: str,
        validators: Iterable[Callable[[Path], tuple[bool, str]]],
    ) -> dict[str, object]:
        with self._lock:
            record = self.get(release_id)
            stage = self.staging_root / str(release_id)
            self._verify_manifest(stage, record)
            checks = []
            for validator in validators:
                ok, detail = validator(stage)
                checks.append({"ok": bool(ok), "detail": str(detail)[:1000]})
            record["validation"] = checks
            record["validated_at"] = _stamp()
            record["status"] = "VALIDATED" if checks and all(row["ok"] for row in checks) else "REJECTED"
            self._write_record(str(release_id), record)
            return record

    def activate(
        self,
        release_id: str,
        live_root: Path,
        *,
        market_priority_active: bool,
        confirm: str,
    ) -> dict[str, object]:
        if market_priority_active:
            raise PermissionError("market_priority_blocks_update_activation")
        if confirm != "ACTIVATE_VALIDATED_UPDATE":
            raise PermissionError("explicit_activation_confirmation_required")
        with self._lock:
            record = self.get(release_id)
            if record.get("status") != "VALIDATED":
                raise PermissionError("release_not_validated")
            stage = self.staging_root / str(release_id)
            self._verify_manifest(stage, record)
            live = Path(live_root).resolve()
            backup = self.backup_root / f"{release_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            moved_live = False
            try:
                if live.exists():
                    os.replace(live, backup)
                    moved_live = True
                os.replace(stage, live)
            except Exception:
                if moved_live and backup.exists() and not live.exists():
                    os.replace(backup, live)
                raise
            record.update(
                {
                    "status": "ACTIVE_RESTART_REQUIRED",
                    "activated_at": _stamp(),
                    "live_root": str(live),
                    "rollback_root": str(backup) if moved_live else None,
                    "restart_required": True,
                }
            )
            self._write_record(str(release_id), record)
            return record

    def rollback(
        self,
        release_id: str,
        *,
        market_priority_active: bool,
        confirm: str,
    ) -> dict[str, object]:
        if market_priority_active:
            raise PermissionError("market_priority_blocks_update_rollback")
        if confirm != "ROLLBACK_FAILED_UPDATE":
            raise PermissionError("explicit_rollback_confirmation_required")
        with self._lock:
            record = self.get(release_id)
            live = Path(str(record.get("live_root") or "")).resolve()
            backup_value = record.get("rollback_root")
            if not backup_value:
                raise ValueError("rollback_target_missing")
            backup = Path(str(backup_value)).resolve()
            if not backup.is_dir():
                raise ValueError("rollback_target_missing")
            failed = self.backup_root / f"failed-{release_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            if live.exists():
                os.replace(live, failed)
            os.replace(backup, live)
            record.update(
                {
                    "status": "ROLLED_BACK_RESTART_REQUIRED",
                    "rolled_back_at": _stamp(),
                    "failed_release_root": str(failed) if failed.exists() else None,
                    "restart_required": True,
                }
            )
            self._write_record(str(release_id), record)
            return record

    def get(self, release_id: str) -> dict[str, object]:
        path = self.records_root / f"{release_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid_update_record")
        return payload

    def _verify_manifest(self, stage: Path, record: dict[str, object]) -> None:
        rows = record.get("files")
        if not isinstance(rows, list):
            raise ValueError("update_manifest_missing")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid_update_manifest")
            relative = Path(str(row.get("path") or ""))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe_update_path")
            target = stage / relative
            if not target.is_file() or _hash_file(target) != row.get("sha256"):
                raise ValueError("staged_update_hash_mismatch")

    def _write_record(self, release_id: str, payload: dict[str, object]) -> None:
        target = self.records_root / f"{release_id}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
