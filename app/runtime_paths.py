from __future__ import annotations

import os
import json
import hashlib
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


USER_DATA_ENV_KEY = "CODEXSTOCK_USER_DATA_DIR"
USE_REPO_DATA_ENV_KEY = "CODEXSTOCK_USE_REPO_DATA"
RUNTIME_ROOT_CONTRACT_ENV_KEY = "CODEXSTOCK_RUNTIME_ROOT_CONTRACT"
RUNTIME_ROOT_CONTRACT_SCHEMA = "codexstock.runtime-root-contract.v1"
RUNTIME_ROOT_CONTRACT_FILENAME = "codexstock_runtime_root.json"


def legacy_data_root(repo_root: Path) -> Path:
    return Path(repo_root) / "data"


def runtime_root_contract_path(repo_root: Path) -> Path:
    configured = os.getenv(RUNTIME_ROOT_CONTRACT_ENV_KEY, "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else Path(repo_root) / path
    return Path(repo_root) / "runtime" / RUNTIME_ROOT_CONTRACT_FILENAME


def _contract_hash(payload: dict[str, object]) -> str:
    material = dict(payload)
    material.pop("contract_hash", None)
    canonical = json.dumps(
        material,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _account_independent_root_allowed(path: Path, repo_root: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser().absolute()
    if not resolved.is_absolute() or str(resolved).startswith(("\\\\", "//")):
        return False
    if resolved.name.lower() != "data" or resolved.parent.name.lower() != "codexstock":
        return False
    return not is_inside(resolved, Path(repo_root))


def read_runtime_root_contract(repo_root: Path) -> dict[str, object]:
    path = runtime_root_contract_path(repo_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "valid": False,
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }
    if not isinstance(payload, dict) or payload.get("schema") != RUNTIME_ROOT_CONTRACT_SCHEMA:
        return {"valid": False, "path": str(path), "error": "contract_schema_mismatch"}
    stored_hash = str(payload.get("contract_hash") or "")
    if len(stored_hash) != 64 or stored_hash != _contract_hash(payload):
        return {"valid": False, "path": str(path), "error": "contract_hash_mismatch"}
    user_data_root = Path(str(payload.get("user_data_root") or "")).expanduser()
    if not _account_independent_root_allowed(user_data_root, repo_root):
        return {"valid": False, "path": str(path), "error": "contract_root_not_allowed"}
    engine_root = Path(str(payload.get("engine_root") or "")).expanduser()
    if engine_root != user_data_root.parent / "engines":
        return {"valid": False, "path": str(path), "error": "contract_engine_root_mismatch"}
    python_executable = Path(str(payload.get("python_executable") or "")).expanduser()
    if not python_executable.is_absolute() or python_executable.name.lower() not in {
        "python.exe",
        "python",
        "python3",
    }:
        return {"valid": False, "path": str(path), "error": "contract_python_path_invalid"}
    return {"valid": True, "path": str(path), **payload}


def ensure_runtime_root_contract(
    repo_root: Path,
    user_data_root: Path,
    *,
    python_executable: Path | None = None,
) -> dict[str, object]:
    root = Path(user_data_root).expanduser()
    if not _account_independent_root_allowed(root, repo_root):
        return {
            "valid": False,
            "written": False,
            "error": "contract_root_not_allowed",
            "user_data_root": str(root),
        }
    root.mkdir(parents=True, exist_ok=True)
    executable = Path(python_executable or sys.executable).expanduser().absolute()
    payload: dict[str, object] = {
        "schema": RUNTIME_ROOT_CONTRACT_SCHEMA,
        "user_data_root": str(root.absolute()),
        "runtime_root": str(root.parent.absolute()),
        "engine_root": str((root.parent / "engines").absolute()),
        "python_executable": str(executable),
        "owner_profile": str(root.parent.parent.parent.parent.absolute()),
        "contains_secrets": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["contract_hash"] = _contract_hash(payload)
    path = runtime_root_contract_path(repo_root)
    existing = read_runtime_root_contract(repo_root)
    if (
        existing.get("valid") is True
        and existing.get("user_data_root") == payload["user_data_root"]
        and existing.get("python_executable") == payload["python_executable"]
    ):
        return {**existing, "written": False}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    return {"valid": True, "written": True, "path": str(path), **payload}


def runtime_root_resolution(repo_root: Path) -> dict[str, object]:
    raw = os.getenv(USER_DATA_ENV_KEY, "").strip()
    if raw:
        return {
            "source": "explicit_environment",
            "user_data_root": str(Path(raw).expanduser()),
            "execution_account_independent": True,
            "contract": read_runtime_root_contract(repo_root),
        }
    use_repo_data = os.getenv(USE_REPO_DATA_ENV_KEY, "").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }
    if use_repo_data:
        return {
            "source": "explicit_repo_opt_in",
            "user_data_root": str(legacy_data_root(repo_root)),
            "execution_account_independent": False,
            "contract": read_runtime_root_contract(repo_root),
        }
    contract = read_runtime_root_contract(repo_root)
    if contract.get("valid") is True:
        return {
            "source": "verified_runtime_root_contract",
            "user_data_root": str(contract["user_data_root"]),
            "execution_account_independent": True,
            "contract": contract,
        }
    return {
        "source": "current_account_default",
        "user_data_root": str(default_user_data_root()),
        "execution_account_independent": False,
        "contract": contract,
    }


def configured_user_data_root(repo_root: Path | None = None) -> Path | None:
    raw = os.getenv(USER_DATA_ENV_KEY, "").strip()
    if not raw:
        use_repo_data = os.getenv(USE_REPO_DATA_ENV_KEY, "").strip().lower() in {"1", "true", "yes", "y", "on"}
        if use_repo_data:
            return None
        if repo_root is not None:
            contract = read_runtime_root_contract(repo_root)
            if contract.get("valid") is True:
                return Path(str(contract["user_data_root"]))
        return default_user_data_root()
    return Path(raw).expanduser()


def default_user_data_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "CodexStock" / "data"
    try:
        return Path.home() / ".codexstock" / "data"
    except RuntimeError:
        # Service accounts and environment-sanitized tests may have no home.
        # Keep the fallback outside the source tree instead of failing status reads.
        return Path(tempfile.gettempdir()) / "CodexStock" / "data"


def active_data_root(repo_root: Path) -> Path:
    return configured_user_data_root(repo_root) or legacy_data_root(repo_root)


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child_resolved = child.resolve()
    except OSError:
        child_resolved = child.absolute()
    try:
        parent_resolved = parent.resolve()
    except OSError:
        parent_resolved = parent.absolute()
    try:
        return child_resolved == parent_resolved or parent_resolved in child_resolved.parents
    except RuntimeError:
        return str(child_resolved).startswith(str(parent_resolved))


def runtime_data_path(path: Path, repo_root: Path) -> Path:
    path = Path(path)
    legacy_root = legacy_data_root(repo_root)
    active_root = active_data_root(repo_root)
    try:
        rel = path.resolve().relative_to(legacy_root.resolve())
    except (OSError, ValueError):
        return path
    if active_root.resolve() == legacy_root.resolve():
        return path
    target = active_root / rel
    if not target.exists() and path.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file():
                shutil.copy2(path, target)
        except OSError:
            pass
    return target


def bootstrap_user_data_dir(default_dir: Path, active_dir: Path) -> None:
    default_dir = Path(default_dir)
    active_dir = Path(active_dir)
    if not default_dir.exists():
        return
    active_dir.mkdir(parents=True, exist_ok=True)
    for source in default_dir.iterdir():
        if not source.is_file():
            continue
        target = active_dir / source.name
        if target.exists():
            continue
        try:
            target.write_bytes(source.read_bytes())
        except OSError:
            continue


def bootstrap_user_data_tree(default_dir: Path, active_dir: Path, marker_name: str = ".codexstock-migrated.json") -> dict[str, object]:
    """Copy a legacy runtime tree once without replacing newer user data."""
    default_dir = Path(default_dir)
    active_dir = Path(active_dir)
    marker = active_dir / marker_name
    if marker.is_file() or not default_dir.is_dir() or default_dir.resolve() == active_dir.resolve():
        return {"ok": True, "copied_files": 0, "copied_bytes": 0, "skipped": True}
    active_dir.mkdir(parents=True, exist_ok=True)
    copied_files = 0
    copied_bytes = 0
    errors: list[str] = []
    for source in default_dir.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(default_dir)
        target = active_dir / relative
        if target.exists():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied_files += 1
            copied_bytes += source.stat().st_size
        except OSError as exc:
            errors.append(f"{relative}: {exc}")
    payload = {
        "schema_version": 1,
        "source": str(default_dir.resolve()),
        "target": str(active_dir.resolve()),
        "copied_files": copied_files,
        "copied_bytes": copied_bytes,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors[:20],
    }
    if not errors:
        marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": not errors, **payload}
