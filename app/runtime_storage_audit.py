from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path


BACKUP_NAME_RE = re.compile(r"^(?P<source>.+\.jsonl)\.\d{8}-\d{6}\.bak$", re.IGNORECASE)


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _contract_pins(index_path: Path | None, backup_dir: Path) -> tuple[set[Path], list[str]]:
    if not index_path or not index_path.is_file():
        return set(), []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), ["contract_index_invalid"]
    entries = payload.get("entries") if isinstance(payload, dict) else {}
    pins: set[Path] = set()
    missing: list[str] = []
    for entry in entries.values() if isinstance(entries, dict) else []:
        if not isinstance(entry, dict):
            continue
        raw_path = str(entry.get("source_backup_path") or "").strip()
        if not raw_path:
            continue
        candidate = _safe_resolve(Path(raw_path))
        if candidate.parent != backup_dir:
            missing.append(raw_path)
        elif candidate.is_file():
            pins.add(candidate)
        else:
            missing.append(raw_path)
    return pins, missing[:20]


def _tail_jsonl_benchmark(path: Path, sample_bytes: int = 256 * 1024) -> dict[str, object]:
    started = time.perf_counter()
    parsed = 0
    invalid = 0
    sampled = 0
    try:
        with path.open("rb") as handle:
            size = path.stat().st_size
            handle.seek(max(0, size - sample_bytes))
            raw = handle.read(sample_bytes)
        lines = raw.splitlines()
        if size > sample_bytes and lines:
            lines = lines[1:]
        for line in lines[-50:]:
            if not line.strip():
                continue
            sampled += 1
            try:
                value = json.loads(line.decode("utf-8"))
                if isinstance(value, dict):
                    parsed += 1
                else:
                    invalid += 1
            except (UnicodeError, json.JSONDecodeError):
                invalid += 1
        status = "ok" if invalid == 0 else "invalid_tail_rows"
        error = ""
    except OSError as exc:
        status = "read_error"
        error = str(exc)[:240]
    return {
        "path": str(path),
        "size_mb": round(path.stat().st_size / (1024 * 1024), 2) if path.is_file() else 0,
        "status": status,
        "sampled_rows": sampled,
        "parsed_rows": parsed,
        "invalid_rows": invalid,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "error": error,
    }


def tail_jsonl_benchmark(path: Path, sample_bytes: int = 256 * 1024) -> dict[str, object]:
    """Public read-only tail benchmark used by storage health checks."""
    return _tail_jsonl_benchmark(path, sample_bytes=sample_bytes)


def recheck_slow_jsonl_tail_benchmarks(
    payload: dict[str, object],
    *,
    slow_threshold_ms: float = 250.0,
) -> dict[str, object]:
    """Retry only slow tail reads so concurrent inventory I/O does not create false alarms."""
    updated = dict(payload)
    rows = payload.get("jsonl_tail_benchmarks")
    if not isinstance(rows, list):
        return updated
    checked_rows: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        elapsed_ms = float(row.get("elapsed_ms") or 0.0)
        if elapsed_ms < slow_threshold_ms or not str(row.get("path") or ""):
            checked_rows.append(row)
            continue
        retry = _tail_jsonl_benchmark(Path(str(row["path"])))
        retry["initial_elapsed_ms"] = elapsed_ms
        retry["retry_performed"] = True
        checked_rows.append(retry)
    max_elapsed_ms = max(
        (float(row.get("elapsed_ms") or 0.0) for row in checked_rows),
        default=0.0,
    )
    updated["jsonl_tail_benchmarks"] = checked_rows
    updated["max_jsonl_tail_ms"] = round(max_elapsed_ms, 2)
    updated["jsonl_tail_slow"] = max_elapsed_ms >= slow_threshold_ms
    return updated


def audit_runtime_storage(
    root: Path,
    *,
    data_root: Path,
    contract_index_path: Path | None = None,
    largest_limit: int = 20,
) -> dict[str, object]:
    """Build a read-only inventory and evidence-preserving backup retention plan."""
    started = time.perf_counter()
    root = _safe_resolve(root)
    data_root = _safe_resolve(data_root)
    backup_dir = _safe_resolve(data_root / "backups" / "jsonl_compaction")
    top_dirs: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    extensions: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    largest: list[tuple[int, str]] = []
    jsonl_files: list[tuple[int, Path]] = []
    scan_errors: list[str] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        size = int(entry.stat(follow_symlinks=False).st_size)
                        path = Path(entry.path)
                        relative = path.relative_to(root)
                        top = relative.parts[0] if relative.parts else "<root>"
                        extension = path.suffix.lower() or "<none>"
                        top_dirs[top][0] += size
                        top_dirs[top][1] += 1
                        extensions[extension][0] += size
                        extensions[extension][1] += 1
                        largest.append((size, str(path)))
                        if extension == ".jsonl" and (path == data_root or data_root in path.parents):
                            jsonl_files.append((size, path))
                    except (OSError, ValueError) as exc:
                        if len(scan_errors) < 20:
                            scan_errors.append(str(exc)[:240])
        except OSError as exc:
            if len(scan_errors) < 20:
                scan_errors.append(str(exc)[:240])

    backup_paths = sorted(
        (_safe_resolve(path) for path in backup_dir.glob("*.bak") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    ) if backup_dir.is_dir() else []
    pins, missing_pins = _contract_pins(contract_index_path, backup_dir)
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in backup_paths:
        match = BACKUP_NAME_RE.match(path.name)
        groups[match.group("source") if match else path.stem].append(path)

    preserved: dict[Path, set[str]] = defaultdict(set)
    for source, paths in groups.items():
        del source
        preserved[max(paths, key=lambda path: (path.stat().st_size, path.stat().st_mtime_ns))].add("largest_baseline")
        preserved[max(paths, key=lambda path: (path.stat().st_mtime_ns, path.name))].add("newest_incremental")
    for path in pins:
        if path in backup_paths:
            preserved[path].add("replay_contract_pin")
    removable = [path for path in backup_paths if path not in preserved]
    backup_bytes = sum(path.stat().st_size for path in backup_paths)
    reclaimable_bytes = sum(path.stat().st_size for path in removable)

    jsonl_benchmarks = [
        _tail_jsonl_benchmark(path)
        for _size, path in sorted(jsonl_files, reverse=True)[:8]
    ]
    benchmark_summary = recheck_slow_jsonl_tail_benchmarks(
        {"jsonl_tail_benchmarks": jsonl_benchmarks}
    )
    jsonl_benchmarks = list(benchmark_summary["jsonl_tail_benchmarks"])
    max_jsonl_tail_ms = float(benchmark_summary["max_jsonl_tail_ms"])
    total_bytes = sum(values[0] for values in top_dirs.values())
    retention_ok = not missing_pins and not scan_errors and all(preserved.get(path) for path in backup_paths if path not in removable)
    status = "ready" if retention_ok else "review_required"
    return {
        "ok": retention_ok,
        "status": status,
        "root": str(root),
        "data_root": str(data_root),
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / (1024**3), 3),
        "file_count": sum(values[1] for values in top_dirs.values()),
        "scan_elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "scan_error_count": len(scan_errors),
        "scan_errors": scan_errors,
        "top_directories": {
            name: {"bytes": values[0], "gb": round(values[0] / (1024**3), 3), "file_count": values[1]}
            for name, values in sorted(top_dirs.items(), key=lambda item: item[1][0], reverse=True)
        },
        "largest_extensions": {
            name: {"bytes": values[0], "gb": round(values[0] / (1024**3), 3), "file_count": values[1]}
            for name, values in sorted(extensions.items(), key=lambda item: item[1][0], reverse=True)[:12]
        },
        "largest_files": [
            {"path": path, "size_mb": round(size / (1024 * 1024), 2)}
            for size, path in sorted(largest, reverse=True)[: max(1, largest_limit)]
        ],
        "backup_retention": {
            "backup_dir": str(backup_dir),
            "backup_count": len(backup_paths),
            "backup_bytes": backup_bytes,
            "backup_gb": round(backup_bytes / (1024**3), 3),
            "group_count": len(groups),
            "preserved_count": len(preserved),
            "contract_pinned_count": len(pins),
            "missing_contract_pin_count": len(missing_pins),
            "missing_contract_pins": missing_pins,
            "removable_count": len(removable),
            "reclaimable_bytes": reclaimable_bytes,
            "reclaimable_mb": round(reclaimable_bytes / (1024 * 1024), 2),
            "preserved": [
                {
                    "name": path.name,
                    "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                    "reasons": sorted(reasons),
                }
                for path, reasons in sorted(preserved.items(), key=lambda item: item[0].name)
            ],
            "removable": [
                {"name": path.name, "size_mb": round(path.stat().st_size / (1024 * 1024), 2)}
                for path in removable
            ],
            "rule": "Preserve each group's largest baseline, newest incremental, and every replay-contract-pinned backup.",
        },
        "jsonl_tail_benchmarks": jsonl_benchmarks,
        "max_jsonl_tail_ms": round(max_jsonl_tail_ms, 2),
        "jsonl_tail_slow": bool(benchmark_summary["jsonl_tail_slow"]),
        "dry_run_only": True,
        "cleanup_applied": False,
        "live_order_allowed": False,
        "safety": "Read-only inventory and retention plan. No file is modified or deleted.",
    }
