from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4


class MarketDataProvider(Protocol):
    name: str
    network_required: bool
    throttle_seconds: float

    def list_symbols(self) -> list[str]: ...
    def fetch_daily_bars(self, symbol: str, start: str, end: str) -> list[dict[str, Any]]: ...
    def fetch_minute_bars(self, symbol: str, interval: int, start: str, end: str) -> list[dict[str, Any]]: ...


class ProviderResponseError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0, retry_after: float | None = None) -> None:
        super().__init__(message); self.status_code = int(status_code); self.retry_after = retry_after


@dataclass
class MockMarketDataProvider:
    name: str = "mock"
    network_required: bool = False
    throttle_seconds: float = 0.0

    def list_symbols(self) -> list[str]:
        return ["005930", "000660", "035420"]

    def fetch_daily_bars(self, symbol: str, start: str, end: str) -> list[dict[str, Any]]:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        rows, cursor = [], first
        base = 50_000 + sum(ord(value) for value in symbol) * 10
        index = 0
        while cursor <= last:
            if cursor.weekday() < 5:
                close = float(base + index * 17 + ((index % 7) - 3) * 40)
                rows.append(_bar(symbol, datetime.combine(cursor, datetime.min.time(), timezone.utc), close, index))
                index += 1
            cursor += timedelta(days=1)
        return rows

    def fetch_minute_bars(self, symbol: str, interval: int, start: str, end: str) -> list[dict[str, Any]]:
        if interval not in {1, 3, 5, 10, 15, 30, 60}:
            raise ValueError("unsupported minute interval")
        day = date.fromisoformat(start)
        base_time = datetime(day.year, day.month, day.day, 0, 0, tzinfo=timezone.utc)
        base = 50_000 + sum(ord(value) for value in symbol) * 10
        return [_bar(symbol, base_time + timedelta(minutes=index * interval), float(base + index * 5), index) for index in range(60)]


@dataclass
class KisReadOnlyProvider:
    """Read-only adapter over CodexStock's existing KIS quotation bridge."""

    bridge: Any
    symbols: list[str]
    name: str = "kis-readonly"
    network_required: bool = True
    throttle_seconds: float = 0.1

    @classmethod
    def from_repo(cls, repo_root: Path, symbols: list[str]) -> "KisReadOnlyProvider":
        app_root = repo_root / "app"
        if str(app_root) not in sys.path:
            sys.path.insert(0, str(app_root))
        from integrations import IntegrationSettings, KisReadonlyBridge

        settings = IntegrationSettings.load(repo_root)
        if not settings.kis_configured:
            raise ValueError("KIS quotation credentials are not configured")
        settings = replace(settings, kis_readonly=True, live_trading=False)
        bridge = KisReadonlyBridge(settings)
        provider = cls(bridge, _symbols(symbols, 1000), throttle_seconds=max(0.05, settings.kis_quote_throttle_ms / 1000))
        if bridge.status().get("order_allowed"):
            raise ValueError("KIS bridge unexpectedly reports order capability")
        return provider

    def list_symbols(self) -> list[str]:
        return list(self.symbols)

    def status(self) -> dict[str, Any]:
        status = dict(self.bridge.status())
        status.update({"provider_adapter": self.name, "research_only": True, "network_required": True})
        return status

    def fetch_daily_bars(self, symbol: str, start: str, end: str) -> list[dict[str, Any]]:
        result = self.bridge.daily_chart(symbol=symbol, start_date=start, end_date=end, allow_real_fallback=False)
        return self._rows(result, symbol, minute=False)

    def fetch_minute_bars(self, symbol: str, interval: int, start: str, end: str) -> list[dict[str, Any]]:
        if interval != 1:
            raise ValueError("KIS read-only provider currently supplies raw 1-minute bars only")
        if start != end:
            raise ValueError("KIS minute collection is limited to one trading date per job")
        result = self.bridge.minute_chart(symbol=symbol, include_past=True, limit=30)
        return self._rows(result, symbol, minute=True)

    @staticmethod
    def _rows(result: dict[str, Any], symbol: str, *, minute: bool) -> list[dict[str, Any]]:
        if not result.get("ok"):
            raise ProviderResponseError(
                str(result.get("message") or "KIS quotation request failed"),
                int(result.get("status_code") or result.get("http_status") or 0),
                float(result["retry_after"]) if result.get("retry_after") is not None else None,
            )
        output = []
        for row in result.get("rows") or []:
            if not isinstance(row, dict):
                continue
            copied = dict(row)
            copied["symbol"] = symbol
            copied["timestamp"] = copied.get("datetime") if minute else f"{copied.get('date')}T00:00:00+09:00"
            output.append(copied)
        return output


class CollectionManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.jobs_root = root / "jobs"
        self.bars_root = root / "bars"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.bars_root.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        provider: MarketDataProvider,
        symbols: list[str],
        timeframe: str,
        start: str,
        end: str,
        *,
        interval: int = 1,
        max_symbols: int = 1000,
        retry_max_attempts: int = 3,
        retry_base_seconds: float = 0.25,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        normalized = _symbols(symbols or provider.list_symbols(), max_symbols)
        date.fromisoformat(start)
        date.fromisoformat(end)
        if end < start:
            raise ValueError("collection end date precedes start date")
        if timeframe not in {"1d", "minute"}:
            raise ValueError("timeframe must be 1d or minute")
        if not 1 <= int(retry_max_attempts) <= 10 or not 0 <= float(retry_base_seconds) <= 30:
            raise ValueError("retry policy must use 1..10 attempts and 0..30 base seconds")
        job = {
            "schema_version": 1,
            "job_id": f"collection_{uuid4().hex}",
            "provider": provider.name,
            "provider_network_required": provider.network_required,
            "timeframe": timeframe,
            "interval": interval,
            "start": start,
            "end": end,
            "symbols": normalized,
            "completed_symbols": [],
            "failed_symbols": {},
            "retry_count": 0,
            "retry_policy": {"max_attempts": int(retry_max_attempts), "base_seconds": float(retry_base_seconds), "max_seconds": 30.0},
            "transient_retry_count": 0,
            "retry_events": [],
            "provider_cursor": None,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_job(job)
        return self._run(job, provider, progress_callback, cancel_requested)

    def resume(
        self, job_id: str, provider: MarketDataProvider,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        job = self.get(job_id)
        if job["provider"] != provider.name:
            raise ValueError("collection provider does not match checkpoint")
        job["retry_count"] = int(job.get("retry_count") or 0) + 1
        job["status"] = "RUNNING"
        return self._run(job, provider, progress_callback, cancel_requested)

    def get(self, job_id: str) -> dict[str, Any]:
        if not job_id.startswith("collection_") or not job_id.replace("_", "").isalnum():
            raise ValueError("invalid collection job id")
        path = self.jobs_root / f"{job_id}.json"
        if not path.is_file():
            raise ValueError("collection job not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def status(self, job_id: str | None = None) -> dict[str, Any]:
        if job_id:
            return {"ok": True, "job": self.get(job_id)}
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.jobs_root.glob("collection_*.json"))]
        return {"ok": True, "job_count": len(rows), "jobs": rows[-50:]}

    def storage_summary(self) -> dict[str, Any]:
        files = list(self.bars_root.rglob("*.json"))
        return {"ok": True, "bar_files": len(files), "bytes": sum(path.stat().st_size for path in files), "root": str(self.bars_root)}

    def _run(
        self, job: dict[str, Any], provider: MarketDataProvider,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        job["status"] = "RUNNING"
        self._save_job(job)
        completed = set(job.get("completed_symbols") or [])
        failed = dict(job.get("failed_symbols") or {})
        last_call = 0.0
        total = len(job["symbols"])
        for index, symbol in enumerate(job["symbols"]):
            if symbol in completed:
                continue
            if cancel_requested and cancel_requested():
                job["status"] = "CANCELLED"
                job["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._save_job(job)
                return {"ok": False, "cancelled": True, "job": job}
            try:
                policy = job.get("retry_policy") or {"max_attempts": 1, "base_seconds": 0, "max_seconds": 0}
                rows = None
                symbol_attempts = 0
                for attempt in range(1, int(policy.get("max_attempts") or 1) + 1):
                    delay = max(0.0, float(getattr(provider, "throttle_seconds", 0.0)) - (time.monotonic() - last_call))
                    if delay > 0: time.sleep(delay)
                    symbol_attempts = attempt
                    try:
                        if job["timeframe"] == "1d":
                            rows = provider.fetch_daily_bars(symbol, job["start"], job["end"])
                            partition = "1d"
                        else:
                            rows = provider.fetch_minute_bars(symbol, int(job["interval"]), job["start"], job["end"])
                            partition = f"{int(job['interval'])}m"
                        last_call = time.monotonic()
                        break
                    except Exception as exc:
                        last_call = time.monotonic()
                        category, retryable, retry_after = _provider_error(exc)
                        event = {"symbol": symbol, "attempt": attempt, "category": category, "retryable": retryable, "error": str(exc), "at": datetime.now(timezone.utc).isoformat()}
                        job["retry_events"] = (list(job.get("retry_events") or []) + [event])[-5000:]
                        if not retryable or attempt >= int(policy.get("max_attempts") or 1): raise
                        backoff = min(float(policy.get("max_seconds") or 30), retry_after if retry_after is not None else float(policy.get("base_seconds") or 0) * (2 ** (attempt - 1)))
                        event["backoff_seconds"] = backoff
                        job["transient_retry_count"] = int(job.get("transient_retry_count") or 0) + 1
                        self._save_job(job)
                        if backoff > 0: time.sleep(backoff)
                if rows is None: raise RuntimeError("provider retry loop produced no result")
                normalized = _normalize(rows, symbol, provider.name)
                self._save_bars(partition, symbol, normalized, job)
                completed.add(symbol)
                failed.pop(symbol, None)
                job["provider_cursor"] = symbol
            except Exception as exc:
                failed[symbol] = {"error": str(exc), "attempts": int(failed.get(symbol, {}).get("attempts") or 0) + max(1, locals().get("symbol_attempts", 1)), "classification": _provider_error(exc)[0]}
            job["completed_symbols"] = sorted(completed)
            job["failed_symbols"] = failed
            job["last_completed_symbol"] = job["provider_cursor"]
            self._save_job(job)
            if progress_callback:
                progress_callback(10.0 + (index + 1) / total * 85.0, f"collected_{index + 1}_of_{total}")
        job["status"] = "COMPLETED" if not failed else "PARTIAL"
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._save_job(job)
        return {"ok": job["status"] == "COMPLETED", "job": job}

    def _save_bars(self, timeframe: str, symbol: str, rows: list[dict[str, Any]], job: dict[str, Any]) -> None:
        target = self.bars_root / timeframe / f"{symbol}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload = {
            "schema_version": 1,
            "symbol": symbol,
            "timeframe": timeframe,
            "provider": job["provider"],
            "collection_job_id": job["job_id"],
            "row_count": len(rows),
            "content_hash": f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}",
            "rows": rows,
        }
        _atomic(target, payload)

    def _save_job(self, job: dict[str, Any]) -> None:
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic(self.jobs_root / f"{job['job_id']}.json", job)


def _normalize(rows: list[dict[str, Any]], symbol: str, source: str) -> list[dict[str, Any]]:
    output = []
    last = ""
    for value in rows:
        timestamp = str(value.get("timestamp") or value.get("date") or "")
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        timestamp = parsed.astimezone(timezone.utc).isoformat()
        if timestamp <= last:
            raise ValueError("provider bars are duplicated or out of order")
        prices = [float(value[key]) for key in ("open", "high", "low", "close")]
        volume = float(value.get("volume") or 0)
        if not all(math.isfinite(item) and item > 0 for item in prices) or prices[1] < max(prices) or prices[2] > min(prices) or volume < 0:
            raise ValueError("provider returned invalid OHLCV")
        output.append({"symbol": symbol, "timestamp": timestamp, "open": prices[0], "high": prices[1], "low": prices[2], "close": prices[3], "volume": volume, "source": source, "collected_at": datetime.now(timezone.utc).isoformat()})
        last = timestamp
    if not output:
        raise ValueError("provider returned no bars")
    return output


def _symbols(values: list[str], limit: int) -> list[str]:
    output = []
    for value in values:
        symbol = str(value).upper()
        if not symbol.isalnum():
            raise ValueError("collection symbols must be alphanumeric")
        if symbol not in output:
            output.append(symbol)
    if not output or len(output) > max(1, min(5000, int(limit))):
        raise ValueError("collection symbol count is empty or exceeds max_symbols")
    return output


def _provider_error(exc: Exception) -> tuple[str, bool, float | None]:
    text = str(exc).lower()
    status_code = int(getattr(exc, "status_code", 0) or 0)
    retry_after = getattr(exc, "retry_after", None)
    retry_after = float(retry_after) if retry_after is not None else None
    if status_code == 429 or any(token in text for token in ("429", "rate limit", "too many requests", "호출 제한", "초당 거래건수")):
        return "RATE_LIMIT", True, retry_after
    if status_code in {408, 425, 500, 502, 503, 504} or any(token in text for token in ("timeout", "timed out", "connection", "temporar", "network", "502", "503", "504")):
        return "TRANSIENT_NETWORK", True, retry_after
    return "PERMANENT_PROVIDER_ERROR", False, retry_after


def _bar(symbol: str, timestamp: datetime, close: float, index: int) -> dict[str, Any]:
    return {"symbol": symbol, "timestamp": timestamp.isoformat(), "open": close - 10, "high": close + 30, "low": close - 30, "close": close, "volume": 1000 + index}


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
