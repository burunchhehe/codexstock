from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from .microstructure import MarketEvent, MicrostructureStore


KST = timezone(timedelta(hours=9))


class MicrostructureProvider(Protocol):
    name: str
    read_only: bool
    def status(self) -> dict[str, Any]: ...
    def poll(self, symbol: str) -> dict[str, Any]: ...


@dataclass
class KisPollingMicrostructureProvider:
    bridge: Any
    name: str = "kis-readonly-polling"
    read_only: bool = True

    @classmethod
    def from_repo(cls, repo_root: Path) -> "KisPollingMicrostructureProvider":
        app_root = repo_root / "app"
        if str(app_root) not in sys.path: sys.path.insert(0, str(app_root))
        from integrations import IntegrationSettings, KisReadonlyBridge
        settings = replace(IntegrationSettings.load(repo_root), kis_readonly=True, live_trading=False)
        if not settings.kis_configured: raise ValueError("KIS quotation credentials are not configured")
        bridge = KisReadonlyBridge(settings)
        if bridge.status().get("order_allowed"): raise ValueError("KIS microstructure bridge unexpectedly allows orders")
        return cls(bridge)

    def status(self) -> dict[str, Any]:
        status = dict(self.bridge.status())
        return {"provider": self.name, "configured": bool(status.get("configured")), "read_only": True, "order_allowed": False, "mode": status.get("mode"), "capabilities": {"tick": "poll_time_conclusion", "orderbook": "poll_10_levels", "program_flow": "poll_program_trade_by_stock"}, "bridge": status}

    def poll(self, symbol: str) -> dict[str, Any]:
        events, errors = [], {}
        availability = {"tick": False, "orderbook": False, "program_flow": False}
        conclusions = self.bridge.time_conclusion(symbol=symbol, limit=60)
        if conclusions.get("ok"):
            for row in conclusions.get("rows") or []:
                events.append({"event_type": "tick", "symbol": symbol, "timestamp": row["datetime"], "source": "kis_readonly_poll", "payload": {key: row.get(key) for key in ("price", "volume", "strength", "ask", "bid", "change", "change_pct", "accumulated_volume", "change_sign")}})
            availability["tick"] = bool(conclusions.get("rows"))
        else:
            errors["tick"] = str(conclusions.get("message") or "KIS time conclusion unavailable")
            quote = self.bridge.quote(symbol=symbol, allow_real_fallback=False)
            if quote.get("ok"):
                timestamp = _market_timestamp(str(quote.get("timestamp") or ""))
                events.append({"event_type": "tick", "symbol": symbol, "timestamp": timestamp, "source": "kis_readonly_poll", "payload": {"price": quote.get("price"), "volume": None, "accumulated_volume": quote.get("volume"), "trade_value": quote.get("trade_value"), "strength": None, "fallback": "quote_snapshot"}})
                availability["tick"] = True
        orderbook = self.bridge.orderbook(symbol=symbol)
        if orderbook.get("ok"):
            events.append({"event_type": "orderbook", "symbol": symbol, "timestamp": _market_timestamp(str(orderbook.get("timestamp") or "")), "source": "kis_readonly_poll", "payload": {key: orderbook.get(key) for key in ("price", "best_ask", "best_bid", "spread", "spread_pct", "expected_price", "expected_volume", "total_ask_quantity", "total_bid_quantity", "orderbook_imbalance_pct", "levels")}})
            availability["orderbook"] = True
        else: errors["orderbook"] = str(orderbook.get("message") or "KIS orderbook unavailable")
        try:
            payload = self.bridge._get(
                "/uapi/domestic-stock/v1/quotations/program-trade-by-stock", "FHPPG04650101",
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}, timeout=8,
            )
            if str(payload.get("rt_cd")) != "0": raise ValueError(str(payload.get("msg1") or payload.get("msg_cd") or "KIS program-flow response error"))
            rows = payload.get("output") or []
            if isinstance(rows, dict): rows = [rows]
            for row in rows:
                if not isinstance(row, dict): continue
                events.append({"event_type": "program_flow", "symbol": symbol, "timestamp": _market_timestamp(str(row.get("bsop_hour") or "")), "source": "kis_readonly_poll", "payload": {
                    "price": _number(row.get("stck_prpr")), "accumulated_volume": _number(row.get("acml_vol")),
                    "sell_quantity": _number(row.get("whol_smtn_seln_vol")), "buy_quantity": _number(row.get("whol_smtn_shnu_vol")), "net_buy_quantity": _number(row.get("whol_smtn_ntby_qty")),
                    "sell_amount": _number(row.get("whol_smtn_seln_tr_pbmn")), "buy_amount": _number(row.get("whol_smtn_shnu_tr_pbmn")), "net_buy_amount": _number(row.get("whol_smtn_ntby_tr_pbmn")),
                    "net_buy_quantity_change": _number(row.get("whol_ntby_vol_icdc")), "net_buy_amount_change": _number(row.get("whol_ntby_tr_pbmn_icdc")),
                }})
            availability["program_flow"] = bool(rows)
            if not rows: errors["program_flow"] = "KIS program-flow returned no rows"
        except Exception as exc: errors["program_flow"] = f"{type(exc).__name__}: {exc}"
        events.sort(key=lambda value: (value["event_type"], value["timestamp"]))
        return {"ok": bool(events), "symbol": symbol, "events": events, "availability": availability, "errors": errors, "polled_at": datetime.now(timezone.utc).isoformat()}


class MicrostructureWorker:
    def __init__(self, root: Path, store: MicrostructureStore) -> None:
        self.root = root
        self.store = store
        root.mkdir(parents=True, exist_ok=True)

    def start(
        self, provider: MicrostructureProvider, symbols: list[str], interval_seconds: float = 1.0,
        max_cycles: int = 1, gap_seconds: int = 10,
        progress: Callable[[float, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        normalized = sorted({str(value).upper() for value in symbols})
        if not normalized or len(normalized) > 100 or any(not value.isalnum() for value in normalized): raise ValueError("worker requires 1..100 alphanumeric symbols")
        if not provider.read_only or provider.status().get("order_allowed"): raise ValueError("microstructure worker accepts read-only providers only")
        interval_seconds = max(0.05, min(60.0, float(interval_seconds)))
        max_cycles = max(0, min(100_000, int(max_cycles)))
        job = {"schema_version": 1, "worker_id": f"micro_{uuid4().hex}", "provider": provider.name, "provider_status": provider.status(), "symbols": normalized, "interval_seconds": interval_seconds, "max_cycles": max_cycles, "gap_seconds": gap_seconds, "status": "RUNNING", "cycle_count": 0, "poll_count": 0, "accepted_events": 0, "duplicate_events": 0, "stale_overlap_events": 0, "failed_polls": 0, "availability": {}, "errors": {}, "created_at": datetime.now(timezone.utc).isoformat()}
        self._save(job)
        return self._run(job, provider, progress, cancelled)

    def resume(self, worker_id: str, provider: MicrostructureProvider, max_cycles: int | None = None, progress=None, cancelled=None) -> dict[str, Any]:
        job = self.get(worker_id)
        if job["provider"] != provider.name: raise ValueError("worker provider does not match checkpoint")
        if max_cycles is not None: job["max_cycles"] = max(0, min(100_000, int(max_cycles)))
        job["status"] = "RUNNING"; job["resume_count"] = int(job.get("resume_count") or 0) + 1
        return self._run(job, provider, progress, cancelled)

    def status(self, worker_id: str | None = None) -> dict[str, Any]:
        if worker_id: return {"ok": True, "worker": self.get(worker_id)}
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.root.glob("micro_*.json"))]
        return {"ok": True, "worker_count": len(rows), "workers": rows[-50:]}

    def get(self, worker_id: str) -> dict[str, Any]:
        if not worker_id.startswith("micro_") or not worker_id.replace("_", "").isalnum(): raise ValueError("invalid microstructure worker id")
        path = self.root / f"{worker_id}.json"
        if not path.is_file(): raise ValueError("microstructure worker not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _run(self, job: dict[str, Any], provider: MicrostructureProvider, progress, cancelled) -> dict[str, Any]:
        target_cycles = int(job["max_cycles"])
        cycles_this_run = 0
        while target_cycles == 0 or cycles_this_run < target_cycles:
            if cancelled and cancelled(): job["status"] = "CANCELLED"; break
            cycle_started = time.monotonic()
            for symbol in job["symbols"]:
                if cancelled and cancelled(): job["status"] = "CANCELLED"; break
                try:
                    result = provider.poll(symbol); job["poll_count"] += 1
                    job["availability"][symbol] = result.get("availability") or {}
                    if result.get("events"):
                        fresh, stale = self._fresh_events(result["events"])
                        job["stale_overlap_events"] += stale
                        if fresh:
                            ingested = self.store.ingest(fresh, int(job["gap_seconds"]))
                            job["accepted_events"] += int(ingested["accepted"]); job["duplicate_events"] += int(ingested["duplicates"])
                    if result.get("errors"): job["errors"][symbol] = result["errors"]
                    if not result.get("ok"): job["failed_polls"] += 1
                except Exception as exc:
                    job["failed_polls"] += 1; job["errors"][symbol] = {"worker": f"{type(exc).__name__}: {exc}"}
                job["last_symbol"] = symbol; job["last_poll_at"] = datetime.now(timezone.utc).isoformat(); self._save(job)
            cycles_this_run += 1; job["cycle_count"] += 1
            if progress and target_cycles: progress(min(99, cycles_this_run / target_cycles * 99), f"microstructure_cycle_{cycles_this_run}_of_{target_cycles}")
            self._save(job)
            if target_cycles == 0 or cycles_this_run < target_cycles:
                remaining = interval_seconds = max(0.0, float(job["interval_seconds"]) - (time.monotonic() - cycle_started))
                while remaining > 0:
                    if cancelled and cancelled(): job["status"] = "CANCELLED"; break
                    sleep_for = min(0.25, remaining); time.sleep(sleep_for); remaining -= sleep_for
                if job.get("status") == "CANCELLED": break
        if job.get("status") == "RUNNING": job["status"] = "COMPLETED"
        job["finished_at"] = datetime.now(timezone.utc).isoformat(); self._save(job)
        return {"ok": job["status"] == "COMPLETED" and job["failed_polls"] == 0, "worker": job, "store": self.store.status()}

    def _fresh_events(self, values: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        fresh, stale = [], 0
        streams = self.store.state.get("streams") if isinstance(self.store.state.get("streams"), dict) else {}
        for value in values:
            event = MarketEvent.parse(value)
            last = str((streams.get(event.stream_id) or {}).get("last_timestamp") or "")
            if last and datetime.fromisoformat(event.timestamp) < datetime.fromisoformat(last): stale += 1
            else: fresh.append(value)
        return fresh, stale

    def _save(self, job: dict[str, Any]) -> None:
        job["updated_at"] = datetime.now(timezone.utc).isoformat(); path = self.root / f"{job['worker_id']}.json"; temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)


def _market_timestamp(raw: str) -> str:
    digits = "".join(value for value in raw if value.isdigit())
    now = datetime.now(KST)
    if len(digits) >= 6:
        return now.replace(hour=int(digits[:2]), minute=int(digits[2:4]), second=int(digits[4:6]), microsecond=0).isoformat()
    return now.isoformat()


def _number(value: Any) -> float:
    try: return float(str(value or "0").replace(",", ""))
    except (TypeError, ValueError): return 0.0
