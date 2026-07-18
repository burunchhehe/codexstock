from __future__ import annotations

import json
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .collection import CollectionManager, MockMarketDataProvider
from .indicators import calculate


def run_concurrency_soak(
    storage: Any, collection: CollectionManager, output_root: Path,
    backtest: Callable[[], Any] | None = None, iterations: int = 20,
) -> dict[str, Any]:
    """Concurrent writer/read/compute/backtest gate with structured evidence and cleanup."""
    iterations = max(2, min(100, int(iterations)))
    output_root.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    measurements: dict[str, Any] = {}

    def write_storage() -> dict[str, Any]:
        started = time.perf_counter(); rows_written = 0
        first = datetime(2035, 1, 1, tzinfo=timezone.utc)
        for batch in range(iterations):
            rows = []
            for offset in range(100):
                timestamp = first + timedelta(minutes=batch * 100 + offset)
                close = 100.0 + (batch * 100 + offset) / 100
                rows.append({"symbol": "SOAK001", "timestamp": timestamp.isoformat(), "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1000, "source": "soak:test"})
            storage.ingest(rows, "1m", "soak")
            rows_written += len(rows)
        return {"rows": rows_written, "seconds": time.perf_counter() - started}

    def read_storage() -> dict[str, Any]:
        started = time.perf_counter(); rows = 0
        for _ in range(iterations * 2):
            rows += storage.query(["005930"], "2016-01-01", "2027-01-01", "1d", 5000)["count"]
        return {"rows_returned": rows, "queries": iterations * 2, "seconds": time.perf_counter() - started}

    def compute_indicators() -> dict[str, Any]:
        started = time.perf_counter()
        rows = [{"open": 100 + i / 100, "high": 102 + i / 100, "low": 98 + i / 100, "close": 100 + i / 100, "volume": 1000 + i % 10} for i in range(10_000)]
        for _ in range(iterations):
            calculate("RSI", rows, {"period": 14}); calculate("MACD", rows, {"fast": 12, "slow": 26, "signal": 9})
        return {"indicator_runs": iterations * 2, "rows_per_run": len(rows), "seconds": time.perf_counter() - started}

    def collect_mock() -> dict[str, Any]:
        started = time.perf_counter(); jobs = 0
        for index in range(iterations):
            result = collection.start(MockMarketDataProvider(), [f"SOAK{index:04d}"], "1d", "2024-01-01", "2024-01-10")
            if not result["ok"]: raise RuntimeError("mock collection failed during soak")
            jobs += 1
        return {"jobs": jobs, "seconds": time.perf_counter() - started}

    def run_backtests() -> dict[str, Any]:
        if backtest is None: return {"runs": 0, "seconds": 0.0}
        started = time.perf_counter()
        for _ in range(max(2, iterations // 2)): backtest()
        return {"runs": max(2, iterations // 2), "seconds": time.perf_counter() - started}

    workloads = {"storage_write": write_storage, "storage_read": read_storage, "indicator_compute": compute_indicators, "collection": collect_mock, "backtest": run_backtests}
    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=5, thread_name_prefix="forge-soak") as executor:
            futures = {executor.submit(function): name for name, function in workloads.items()}
            for future in as_completed(futures):
                name = futures[future]
                try: measurements[name] = future.result()
                except Exception as exc: errors.append({"workload": name, "type": type(exc).__name__, "message": str(exc)})
    finally:
        connection = storage._connect()
        try: connection.execute("DELETE FROM bars WHERE source = 'soak:test'")
        finally: connection.close()
    payload = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "iterations": iterations, "elapsed_seconds": round(time.perf_counter() - started, 6), "measurements": measurements, "errors": errors, "passed": not errors}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")); payload["evidence_hash"] = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
    path = output_root / "concurrency_latest.json"; temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)
    payload["path"] = str(path)
    return payload
