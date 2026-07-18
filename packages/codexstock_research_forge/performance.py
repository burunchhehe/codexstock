from __future__ import annotations

import hashlib
import json
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .indicators import calculate, INDICATORS


PARAMETERS = {
    "SMA": {"period": 20}, "EMA": {"period": 20}, "WMA": {"period": 20},
    "RSI": {"period": 14}, "BOLLINGER": {"period": 20, "deviations": 2},
    "ENVELOPE": {"period": 20, "percent": 0.06}, "ATR": {"period": 14},
    "ADX": {"period": 14}, "CCI": {"period": 20}, "ROC": {"period": 10},
    "MACD": {"fast": 12, "slow": 26, "signal": 9}, "STOCHASTIC": {"period": 14, "smooth": 3},
    "WILLIAMS_R": {"period": 14}, "MFI": {"period": 14}, "OBV": {}, "VWAP": {},
}


def run_performance_benchmark(storage: Any, output_root: Path, indicator_row_count: int = 100_000, archive: Any | None = None) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    count = max(1_000, min(250_000, int(indicator_row_count)))
    measurements = []

    started = time.perf_counter()
    query = storage.query([], "1900-01-01T00:00:00+00:00", "2100-01-01T00:00:00+00:00", "1d", 100_000)
    query_seconds = time.perf_counter() - started
    measurements.append({"name": "duckdb_bounded_query", "rows": query["count"], "seconds": round(query_seconds, 6), "threshold_seconds": 2.0, "passed": query_seconds <= 2.0})

    rows = _synthetic_rows(count)
    started = time.perf_counter()
    last_values = {}
    for name in INDICATORS:
        result = calculate(name, rows, PARAMETERS[name])
        last_values[name] = {key: next((value for value in reversed(series) if value is not None), None) for key, series in result["outputs"].items()}
    indicator_seconds = time.perf_counter() - started
    peak_bytes = _peak_rss_bytes()
    digest = hashlib.sha256(json.dumps(last_values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    measurements.append({"name": "all_indicators", "indicators": len(INDICATORS), "rows_per_indicator": count, "seconds": round(indicator_seconds, 6), "peak_bytes": peak_bytes, "result_hash": f"sha256:{digest}", "threshold_seconds": 15.0, "threshold_peak_bytes": 750_000_000, "passed": indicator_seconds <= 15.0 and peak_bytes <= 750_000_000})
    if archive is not None and int(archive.status().get("row_count") or 0) > 0:
        measurements.append(_archive_concurrency(archive))
    payload = {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"backend": storage.doctor(), "indicator_count": len(INDICATORS)},
        "measurements": measurements, "passed": all(row["passed"] for row in measurements),
    }
    payload["evidence_hash"] = _payload_hash(payload)
    path = output_root / "latest.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    payload["path"] = str(path)
    return payload


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps({key: value for key, value in payload.items() if key not in {"evidence_hash", "path"}}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _archive_concurrency(archive: Any, runs: int = 10, workers: int = 5, limit: int = 10_000) -> dict[str, Any]:
    inventory = archive.inventory(); symbol = inventory["symbols"][0]; day = inventory["days"][0]
    start, end = f"{day}T00:00:00+09:00", f"{day}T23:59:59.999999+09:00"
    def query_once() -> dict[str, Any]:
        started = time.perf_counter(); result = archive.query([symbol], start, end, inventory["event_types"], limit)
        ids = [str(row.get("event_id") or "") for row in result["events"]]
        digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        return {"seconds": time.perf_counter() - started, "count": result["count"], "matched": result["matched"], "result_hash": f"sha256:{digest}"}
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="archive-benchmark") as executor:
        futures = [executor.submit(query_once) for _ in range(runs)]
        for future in as_completed(futures):
            try: results.append(future.result())
            except Exception as exc: errors.append({"type": type(exc).__name__, "message": str(exc)[:500]})
    seconds = sorted(row["seconds"] for row in results); hashes = sorted({row["result_hash"] for row in results}); counts = sorted({(row["count"], row["matched"]) for row in results})
    passed = len(results) == runs and not errors and len(hashes) == 1 and len(counts) == 1 and max(seconds, default=float("inf")) <= 5.0
    return {"name": "microstructure_archive_concurrent_reads", "symbol": symbol, "day": day, "event_types": inventory["event_types"], "runs": runs, "workers": workers, "limit": limit, "errors": errors, "min_seconds": round(min(seconds), 6) if seconds else None, "median_seconds": round(seconds[len(seconds) // 2], 6) if seconds else None, "max_seconds": round(max(seconds), 6) if seconds else None, "unique_result_hashes": hashes, "unique_count_pairs": [list(value) for value in counts], "threshold_max_seconds": 5.0, "passed": passed}


def _synthetic_rows(count: int) -> list[dict[str, float]]:
    rows = []
    for index in range(count):
        close = 50_000.0 + index * 0.1 + (index % 17 - 8) * 2.0
        rows.append({"open": close - 1, "high": close + 5, "low": close - 5, "close": close, "volume": 1000.0 + index % 100})
    return rows


def _peak_rss_bytes() -> int:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = wintypes.HANDLE
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        get_memory.restype = wintypes.BOOL
        handle = get_process()
        if get_memory(handle, ctypes.byref(counters), counters.cb):
            return int(counters.PeakWorkingSetSize)
        return 0
    import resource
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if value > 10_000_000 else value * 1024
