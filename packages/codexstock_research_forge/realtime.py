from __future__ import annotations

import json
import hashlib
import math
import os
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from .microstructure import MicrostructureStore


KST = timezone(timedelta(hours=9))
TICK_TR_ID = "H0STCNT0"
ORDERBOOK_TR_ID = "H0STASP0"

TICK_COLUMNS = (
    "symbol", "time", "price", "change_sign", "change", "change_pct", "weighted_price", "open", "high", "low",
    "ask", "bid", "volume", "accumulated_volume", "accumulated_value", "sell_count", "buy_count", "net_buy_count",
    "strength", "sell_quantity", "buy_quantity", "conclusion_code", "buy_ratio", "prior_volume_ratio", "open_time",
    "open_sign", "open_change", "high_time", "high_sign", "high_change", "low_time", "low_sign", "low_change",
    "business_date", "market_open_code", "halted", "ask_quantity", "bid_quantity", "total_ask_quantity",
    "total_bid_quantity", "turnover", "prior_same_time_volume", "prior_same_time_ratio", "hour_code", "market_code", "vi_price",
)
ORDERBOOK_COLUMNS = (
    "symbol", "time", "hour_code", *[f"ask_{i}" for i in range(1, 11)], *[f"bid_{i}" for i in range(1, 11)],
    *[f"ask_quantity_{i}" for i in range(1, 11)], *[f"bid_quantity_{i}" for i in range(1, 11)],
    "total_ask_quantity", "total_bid_quantity", "overtime_total_ask_quantity", "overtime_total_bid_quantity",
    "expected_price", "expected_quantity", "expected_volume", "expected_change", "expected_change_sign", "expected_change_pct",
    "accumulated_volume", "total_ask_change", "total_bid_change", "overtime_ask_change", "overtime_bid_change", "deal_code",
    "kmid_price", "kmid_total_quantity", "kmid_code",
)


class WebSocketTransport(Protocol):
    def send(self, value: str) -> None: ...
    def recv(self, timeout: float) -> str: ...
    def close(self) -> None: ...


class WebsocketClientTransport:
    """Thin optional websocket-client adapter; it exposes no order operation."""
    def __init__(self, url: str, connect_timeout: float = 10.0) -> None:
        try: import websocket
        except ImportError as exc: raise RuntimeError("KIS realtime requires the optional 'realtime' dependency") from exc
        self.socket = websocket.create_connection(url, timeout=connect_timeout, enable_multithread=True)

    def send(self, value: str) -> None: self.socket.send(value)
    def recv(self, timeout: float) -> str:
        self.socket.settimeout(timeout); value = self.socket.recv()
        if isinstance(value, bytes): return value.decode("utf-8")
        return str(value)
    def close(self) -> None: self.socket.close()


def request_approval_key(base_url: str, app_key: str, app_secret: str, timeout: float = 10.0) -> str:
    if not app_key or not app_secret: raise ValueError("KIS app key and secret are required")
    body = json.dumps({"grant_type": "client_credentials", "appkey": app_key, "secretkey": app_secret}).encode("utf-8")
    request = urllib.request.Request(base_url.rstrip("/") + "/oauth2/Approval", data=body, headers={"content-type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(request, timeout=max(1.0, float(timeout))) as response:
        payload = json.loads(response.read().decode("utf-8"))
    key = str(payload.get("approval_key") or "")
    if not key: raise RuntimeError(str(payload.get("error_description") or payload.get("message") or "KIS websocket approval key missing"))
    return key


def subscription_message(approval_key: str, tr_id: str, symbol: str, subscribe: bool = True) -> str:
    if tr_id not in {TICK_TR_ID, ORDERBOOK_TR_ID}: raise ValueError("unsupported read-only KIS realtime TR")
    if not symbol.isdigit() or len(symbol) != 6: raise ValueError("KIS realtime symbol must be six digits")
    if not approval_key: raise ValueError("KIS websocket approval key is required")
    return json.dumps({"header": {"approval_key": approval_key, "custtype": "P", "tr_type": "1" if subscribe else "2", "content-type": "utf-8"}, "body": {"input": {"tr_id": tr_id, "tr_key": symbol}}}, ensure_ascii=False, separators=(",", ":"))


def parse_kis_frame(raw: str, received_at: str | None = None) -> dict[str, Any]:
    text = str(raw or "")
    if not text: raise ValueError("empty KIS websocket frame")
    if text.lstrip().startswith("{"):
        payload = json.loads(text)
        tr_id = str((payload.get("header") or {}).get("tr_id") or "")
        return {"kind": "heartbeat" if tr_id.upper() == "PINGPONG" else "control", "tr_id": tr_id, "payload": payload, "events": []}
    parts = text.split("|", 3)
    if len(parts) != 4 or parts[0] not in {"0", "1"}: raise ValueError("invalid KIS websocket data envelope")
    tr_id, count_text, body = parts[1], parts[2], parts[3]
    if tr_id not in {TICK_TR_ID, ORDERBOOK_TR_ID}: return {"kind": "unsupported", "tr_id": tr_id, "events": []}
    columns = TICK_COLUMNS if tr_id == TICK_TR_ID else ORDERBOOK_COLUMNS
    values = body.split("^"); count = int(count_text)
    if count < 1 or len(values) != count * len(columns):
        raise ValueError(f"KIS {tr_id} field count mismatch: expected {count * len(columns)}, got {len(values)}")
    received = datetime.fromisoformat(received_at) if received_at else datetime.now(timezone.utc)
    events = []
    for index in range(count):
        row = dict(zip(columns, values[index * len(columns):(index + 1) * len(columns)]))
        timestamp = _timestamp(row, received)
        if tr_id == TICK_TR_ID:
            event = {"event_type": "tick", "symbol": row["symbol"], "timestamp": timestamp, "source": "kis_readonly_websocket", "payload": {
                "price": _number(row["price"]), "volume": _number(row["volume"]), "accumulated_volume": _number(row["accumulated_volume"]),
                "accumulated_value": _number(row["accumulated_value"]), "strength": _number(row["strength"]), "ask": _number(row["ask"]),
                "bid": _number(row["bid"]), "change": _number(row["change"]), "change_pct": _number(row["change_pct"]),
                "halted": row["halted"], "vi_price": _number(row["vi_price"]), "tr_id": tr_id,
            }}
        else:
            asks = [[_number(row[f"ask_{level}"]), _number(row[f"ask_quantity_{level}"])] for level in range(1, 11)]
            bids = [[_number(row[f"bid_{level}"]), _number(row[f"bid_quantity_{level}"])] for level in range(1, 11)]
            event = {"event_type": "orderbook", "symbol": row["symbol"], "timestamp": timestamp, "source": "kis_readonly_websocket", "payload": {"asks": asks, "bids": bids, "total_ask_quantity": _number(row["total_ask_quantity"]), "total_bid_quantity": _number(row["total_bid_quantity"]), "expected_price": _number(row["expected_price"]), "expected_volume": _number(row["expected_volume"]), "kmid_price": _number(row["kmid_price"]), "kmid_total_quantity": _number(row["kmid_total_quantity"]), "kmid_code": row["kmid_code"], "tr_id": tr_id}}
        events.append(event)
    return {"kind": "data", "tr_id": tr_id, "record_count": count, "events": events}


@dataclass
class ReliableKisRealtimeCollector:
    root: Path
    store: MicrostructureStore
    transport_factory: Callable[[], WebSocketTransport]
    approval_key: str

    def run(self, symbols: list[str], max_messages: int = 0, max_reconnects: int = 20, heartbeat_timeout: float = 30.0, cancelled: Callable[[], bool] | None = None, duration_seconds: float = 0.0) -> dict[str, Any]:
        normalized = sorted(set(str(value) for value in symbols))
        if not normalized or len(normalized) > 40: raise ValueError("KIS realtime collector requires 1..40 symbols")
        for symbol in normalized: subscription_message(self.approval_key, TICK_TR_ID, symbol)
        duration_seconds = max(0.0, min(86400.0, float(duration_seconds)))
        if int(max_messages) <= 0 and duration_seconds <= 0: raise ValueError("realtime collection requires max_messages or duration_seconds")
        self.root.mkdir(parents=True, exist_ok=True)
        lease = self._claim(float(heartbeat_timeout))
        state = self._load(); run_started = datetime.now(timezone.utc).isoformat(); run_started_monotonic = time.monotonic(); run_id = f"realtime_run_{uuid4().hex}"
        initial_connections = int(state.get("connection_count") or 0); initial_restores = int(state.get("subscription_restore_count") or 0)
        state.update({"schema_version": 1, "status": "RUNNING", "symbols": normalized, "read_only": True, "order_allowed": False, "max_messages": int(max_messages), "requested_duration_seconds": duration_seconds, "heartbeat_timeout": float(heartbeat_timeout), "last_error": None, "run_started_at": run_started, "run_id": run_id, "run_message_count": 0, "run_data_messages": 0, "run_accepted_events": 0, "run_duplicate_events": 0, "run_reconnect_count": 0})
        messages_this_run = 0; reconnects_this_run = 0; recovered_errors_this_run = 0; accepted_this_run = 0; duplicates_this_run = 0; data_this_run = 0; heartbeats_this_run = 0; gaps_this_run = 0; boundary_gaps_this_run = 0; seen_streams: set[str] = set(); transport = None; connected_once = False
        deadline = time.monotonic() + duration_seconds if duration_seconds > 0 else None
        def active() -> bool: return (int(max_messages) <= 0 or messages_this_run < int(max_messages)) and (deadline is None or time.monotonic() < deadline)
        try:
            while active():
                if cancelled and cancelled(): state["status"] = "CANCELLED"; break
                try:
                    transport = self.transport_factory()
                    if connected_once:
                        # The first observation on each restored subscription is a
                        # connection boundary, not evidence of an in-session loss.
                        seen_streams.clear()
                    connected_once = True
                    state["connection_count"] = int(state.get("connection_count") or 0) + 1
                    for symbol in normalized:
                        transport.send(subscription_message(self.approval_key, TICK_TR_ID, symbol))
                        transport.send(subscription_message(self.approval_key, ORDERBOOK_TR_ID, symbol))
                    state["subscription_restore_count"] = int(state.get("subscription_restore_count") or 0) + len(normalized) * 2
                    if state.get("last_error"):
                        state["last_recovered_error"] = state["last_error"]; state["last_error"] = None
                        state["last_recovery_at"] = datetime.now(timezone.utc).isoformat(); recovered_errors_this_run += 1
                    self._save(state)
                    while active():
                        if cancelled and cancelled(): state["status"] = "CANCELLED"; break
                        remaining = (deadline - time.monotonic()) if deadline is not None else float(heartbeat_timeout)
                        raw = transport.recv(max(0.1, min(max(1.0, float(heartbeat_timeout)), remaining)))
                        parsed = parse_kis_frame(raw)
                        state["last_receive_at"] = datetime.now(timezone.utc).isoformat()
                        if parsed["kind"] == "heartbeat":
                            transport.send(raw); state["heartbeat_count"] = int(state.get("heartbeat_count") or 0) + 1; heartbeats_this_run += 1
                        elif parsed["kind"] == "data":
                            result = self.store.ingest(parsed["events"], gap_seconds=max(1, int(heartbeat_timeout)))
                            state["accepted_events"] = int(state.get("accepted_events") or 0) + int(result["accepted"])
                            state["duplicate_events"] = int(state.get("duplicate_events") or 0) + int(result["duplicates"])
                            state["data_messages"] = int(state.get("data_messages") or 0) + 1
                            for gap in result["gaps"]:
                                if str(gap.get("stream_id")) in seen_streams: gaps_this_run += 1
                                else: boundary_gaps_this_run += 1
                            seen_streams.update(f"{event['source']}:{event['event_type']}:{event['symbol']}" for event in parsed["events"])
                            accepted_this_run += int(result["accepted"]); duplicates_this_run += int(result["duplicates"]); data_this_run += 1
                            state["run_accepted_events"] = accepted_this_run; state["run_duplicate_events"] = duplicates_this_run; state["run_data_messages"] = data_this_run
                        messages_this_run += 1; state["message_count"] = int(state.get("message_count") or 0) + 1; state["run_message_count"] = messages_this_run; self._save(state)
                    if state.get("status") == "CANCELLED" or not active(): break
                except Exception as exc:
                    if not active(): break
                    reconnects_this_run += 1; state["reconnect_count"] = int(state.get("reconnect_count") or 0) + 1; state["run_reconnect_count"] = reconnects_this_run
                    state["last_error"] = {"type": type(exc).__name__, "message": str(exc), "at": datetime.now(timezone.utc).isoformat()}; self._save(state)
                    if reconnects_this_run > max(0, int(max_reconnects)): state["status"] = "FAILED"; break
                    time.sleep(min(5.0, 0.1 * (2 ** min(reconnects_this_run, 5))))
                finally:
                    if transport is not None:
                        try: transport.close()
                        except Exception: pass
                        transport = None
            if state.get("status") == "RUNNING": state["status"] = "COMPLETED"
        finally:
            try:
                elapsed = max(0.0, time.monotonic() - run_started_monotonic); connections_this_run = int(state.get("connection_count") or 0) - initial_connections; restores_this_run = int(state.get("subscription_restore_count") or 0) - initial_restores
                expected_restores = connections_this_run * len(normalized) * 2; recovery_ok = state["status"] == "COMPLETED" and connections_this_run >= 1 and restores_this_run >= expected_restores
                duration_completed = duration_seconds <= 0 or elapsed + 0.05 >= duration_seconds
                completion_reason = "cancelled" if state["status"] == "CANCELLED" else "failed" if state["status"] == "FAILED" else "duration_reached" if duration_seconds > 0 and duration_completed else "message_limit_reached" if int(max_messages) > 0 and messages_this_run >= int(max_messages) else "completed"
                # Provider retransmission is acceptable because MicrostructureStore rejects identical
                # event IDs. Losslessness is governed by gaps and reconnect recovery, while the raw
                # duplicate count remains explicit evidence.
                in_session_ok = gaps_this_run == 0 and recovery_ok
                state["last_run"] = {"run_id": run_id, "started_at": run_started, "finished_at": datetime.now(timezone.utc).isoformat(), "requested_duration_seconds": duration_seconds, "elapsed_seconds": round(elapsed, 6), "duration_completed": duration_completed, "completion_reason": completion_reason, "messages": messages_this_run, "data_messages": data_this_run, "accepted_events": accepted_this_run, "duplicate_events": duplicates_this_run, "reconnects": reconnects_this_run, "recovered_errors": recovered_errors_this_run, "connections": connections_this_run, "subscription_restores": restores_this_run, "reconnect_recovery_ok": recovery_ok, "heartbeats": heartbeats_this_run, "in_session_gap_count": gaps_this_run, "session_boundary_gap_count": boundary_gaps_this_run, "in_session_quality_ok": in_session_ok, "continuous_quality_ok": in_session_ok and boundary_gaps_this_run == 0}
                state["last_run_evidence"] = self._write_run_evidence(state)
                state["updated_at"] = datetime.now(timezone.utc).isoformat(); self._save(state)
            finally: self._release(lease)
        return {"ok": state["status"] == "COMPLETED", "collector": state, "run_quality": state["last_run"], "quality": self.store.quality()}

    def _load(self) -> dict[str, Any]:
        path = self.root / "checkpoint.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def _save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = datetime.now(timezone.utc).isoformat(); path = self.root / "checkpoint.json"; temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)

    def _claim(self, heartbeat_timeout: float) -> Path:
        checkpoint = self._load()
        if checkpoint.get("status") == "RUNNING":
            try: age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(checkpoint.get("updated_at")))).total_seconds()
            except (TypeError, ValueError): age = 0.0
            if age < max(120.0, heartbeat_timeout * 3): raise RuntimeError("another realtime collector has a fresh RUNNING checkpoint")
        lease = self.root / "collector.lease"
        try:
            lease.mkdir(); (lease / "owner.json").write_text(json.dumps({"pid": os.getpid(), "claimed_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8"); return lease
        except FileExistsError:
            try: owner = json.loads((lease / "owner.json").read_text(encoding="utf-8"))
            except Exception: raise RuntimeError("realtime collector lease exists without readable owner")
            if _process_alive(int(owner.get("pid") or 0)): raise RuntimeError("another realtime collector owns the lease")
            try: (lease / "owner.json").unlink(); lease.rmdir()
            except OSError as exc: raise RuntimeError("stale realtime collector lease could not be reclaimed") from exc
            return self._claim(heartbeat_timeout)

    @staticmethod
    def _release(lease: Path) -> None:
        try: (lease / "owner.json").unlink(); lease.rmdir()
        except FileNotFoundError: pass

    def _write_run_evidence(self, state: dict[str, Any]) -> dict[str, Any]:
        quality = self.store.quality(); streams = []
        for row in quality["streams"]:
            if str(row.get("stream_id") or "").startswith("kis_readonly_websocket:"):
                streams.append({key: row.get(key) for key in ("stream_id", "count", "duplicate_count", "gap_count", "last_timestamp", "last_event_id")})
        payload = {"schema_version": 1, "run": dict(state["last_run"]), "status": state["status"], "symbols": list(state["symbols"]), "provider": "kis-readonly-websocket", "read_only": True, "order_allowed": False, "stream_summaries": streams}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")); payload["evidence_hash"] = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        runs = self.root / "runs"; runs.mkdir(parents=True, exist_ok=True); path = runs / f"{state['last_run']['run_id']}.json"
        if path.exists(): raise RuntimeError("realtime run evidence already exists")
        temporary = path.with_suffix(".json.tmp"); temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)
        return {"path": str(path), "evidence_hash": payload["evidence_hash"]}


def realtime_run_history(root: Path, limit: int = 50) -> dict[str, Any]:
    rows, invalid = [], []
    for path in sorted((root / "runs").glob("realtime_run_*.json")) if (root / "runs").is_dir() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8")); stored = str(payload.pop("evidence_hash"))
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")); expected = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
            if stored != expected or not _valid_run_evidence(payload, path):
                invalid.append(path.name)
                continue
            payload["evidence_hash"] = stored; payload["path"] = str(path); payload["evidence_verified"] = True
            payload["quality_scope"] = {
                "run_quality_fields": "current_run_only",
                "stream_summaries": "cumulative_store_state_at_run_finish",
                "qualification_uses": "run.in_session_gap_count and run.in_session_quality_ok",
            }
            rows.append(payload)
        except Exception: invalid.append(path.name)
    status_counts: dict[str, int] = {}
    for row in rows: status_counts[str(row["status"])] = status_counts.get(str(row["status"]), 0) + 1
    completed_data_runs = sum(
        row["status"] == "COMPLETED"
        and int(row["run"].get("data_messages") or 0) > 0
        and int(row["run"].get("accepted_events") or 0) > 0
        and bool(row["run"].get("in_session_quality_ok"))
        and bool(row.get("stream_summaries"))
        for row in rows
    )
    return {"ok": not invalid, "verified": not invalid, "run_count": len(rows), "completed_data_run_count": completed_data_runs, "status_counts": status_counts, "invalid_files": invalid, "runs": rows[-max(1, min(500, int(limit))):]}


def _valid_run_evidence(payload: dict[str, Any], path: Path) -> bool:
    if payload.get("schema_version") != 1 or payload.get("status") not in {"COMPLETED", "FAILED", "CANCELLED"}:
        return False
    if payload.get("provider") != "kis-readonly-websocket" or payload.get("read_only") is not True or payload.get("order_allowed") is not False:
        return False
    symbols, streams, run = payload.get("symbols"), payload.get("stream_summaries"), payload.get("run")
    if not isinstance(symbols, list) or not symbols or not all(isinstance(value, str) and value for value in symbols) or not isinstance(streams, list) or not isinstance(run, dict):
        return False
    run_id = str(run.get("run_id") or "")
    run_suffix = run_id.removeprefix("realtime_run_")
    if len(run_suffix) != 32 or any(char not in "0123456789abcdef" for char in run_suffix.lower()) or path.name != f"{run_id}.json":
        return False
    try:
        started = datetime.fromisoformat(str(run["started_at"])); finished = datetime.fromisoformat(str(run["finished_at"]))
        if started.tzinfo is None or finished.tzinfo is None or finished < started: return False
        wall_elapsed = (finished - started).total_seconds()
        if "elapsed_seconds" in run:
            raw_elapsed = run["elapsed_seconds"]
            if isinstance(raw_elapsed, bool) or not isinstance(raw_elapsed, (int, float)): return False
            elapsed = float(raw_elapsed)
            if not math.isfinite(elapsed): return False
            if elapsed < 0 or abs(elapsed - wall_elapsed) > max(5.0, wall_elapsed * 0.01): return False
        if "requested_duration_seconds" in run:
            raw_requested = run["requested_duration_seconds"]
            if isinstance(raw_requested, bool) or not isinstance(raw_requested, (int, float)) or not math.isfinite(float(raw_requested)) or float(raw_requested) < 0: return False
        if "duration_completed" in run and not isinstance(run["duration_completed"], bool): return False
        if "completion_reason" in run and run["completion_reason"] not in {"duration_reached", "message_limit_reached", "completed", "cancelled", "failed"}: return False
        if run.get("completion_reason") == "duration_reached":
            requested = float(run.get("requested_duration_seconds") or 0); elapsed = float(run.get("elapsed_seconds") or wall_elapsed)
            if requested <= 0 or run.get("duration_completed") is not True or elapsed + 0.05 < requested: return False
        for key in ("messages", "data_messages", "accepted_events", "duplicate_events", "reconnects"):
            if isinstance(run[key], bool) or not isinstance(run[key], int) or run[key] < 0: return False
    except (KeyError, TypeError, ValueError):
        return False
    if not isinstance(run.get("in_session_quality_ok"), bool):
        return False
    seen: set[str] = set()
    for stream in streams:
        if not isinstance(stream, dict): return False
        stream_id, event_id, timestamp = str(stream.get("stream_id") or ""), str(stream.get("last_event_id") or ""), str(stream.get("last_timestamp") or "")
        parts = stream_id.split(":")
        if len(parts) != 3 or parts[0] != "kis_readonly_websocket" or parts[1] not in {"tick", "orderbook"} or parts[2] not in symbols or stream_id in seen: return False
        seen.add(stream_id)
        try:
            count, duplicates, gaps = stream["count"], stream["duplicate_count"], stream["gap_count"]
            if any(isinstance(value, bool) or not isinstance(value, int) for value in (count, duplicates, gaps)): return False
            if count < 0 or duplicates < 0 or gaps < 0: return False
            stream_time = datetime.fromisoformat(timestamp)
            if stream_time.tzinfo is None: return False
        except (KeyError, TypeError, ValueError): return False
        if len(event_id) != 64 or any(char not in "0123456789abcdef" for char in event_id.lower()): return False
    if payload.get("status") == "COMPLETED" and int(run["data_messages"]) > 0 and not streams:
        return False
    return True


def _timestamp(row: dict[str, str], received: datetime) -> str:
    day = row.get("business_date") or received.astimezone(KST).strftime("%Y%m%d"); clock = "".join(ch for ch in row.get("time", "") if ch.isdigit()).zfill(6)[-6:]
    try: return datetime.strptime(day + clock, "%Y%m%d%H%M%S").replace(tzinfo=KST).isoformat()
    except ValueError: return received.astimezone(KST).isoformat()


def _number(value: Any) -> float:
    try: return float(str(value or "0").replace(",", ""))
    except (TypeError, ValueError): return 0.0


def _process_alive(pid: int) -> bool:
    if pid <= 0: return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle: return False
        ctypes.windll.kernel32.CloseHandle(handle); return True
    try: os.kill(pid, 0); return True
    except PermissionError: return True
    except (ProcessLookupError, OSError): return False
