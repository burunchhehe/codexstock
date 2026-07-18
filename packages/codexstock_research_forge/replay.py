from __future__ import annotations

import hashlib
import json
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import ExperimentRecord


class ReplayEngine:
    """Builds immutable, cursor-paged market/strategy timelines for UI replay."""

    def __init__(self, root: Path, storage: Any, microstructure: Any, microstructure_archive: Any | None = None) -> None:
        self.root = root
        self.storage = storage
        self.microstructure = microstructure
        self.microstructure_archive = microstructure_archive
        root.mkdir(parents=True, exist_ok=True)

    def create(
        self, record: ExperimentRecord, symbols: list[str], start: str, end: str,
        timeframes: list[str] | None = None, max_events: int = 50_000, microstructure_source: str = "hybrid",
    ) -> dict[str, Any]:
        normalized = sorted({str(value).upper() for value in symbols if str(value).isalnum()})
        if not normalized:
            rules = record.strategy.rules
            candidates = rules.get("symbols") if isinstance(rules.get("symbols"), list) else [rules.get("symbol")]
            normalized = sorted({str(value).upper() for value in candidates if value})
        if not normalized:
            raise ValueError("replay requires at least one symbol")
        _parse_time(start); _parse_time(end)
        if _parse_time(end) < _parse_time(start):
            raise ValueError("replay end precedes start")
        cap = max(1, min(100_000, int(max_events)))
        if microstructure_source not in {"live", "archive", "hybrid"}: raise ValueError("microstructure_source must be live, archive, or hybrid")
        frames: list[dict[str, Any]] = []
        lane_counts: dict[str, int] = {}
        truncated = False
        for timeframe in (timeframes or ["1d", "1m"]):
            remaining = cap - len(frames)
            if remaining <= 0: truncated = True; break
            result = self.storage.query(normalized, start, end, str(timeframe), remaining)
            truncated = truncated or bool(result.get("truncated"))
            for row in result["rows"]:
                frames.append(_frame(row["timestamp"], "bar", row["symbol"], {**row, "timeframe": timeframe}))
                lane_counts[f"bar:{timeframe}"] = lane_counts.get(f"bar:{timeframe}", 0) + 1
        remaining = cap - len(frames); microstructure_unique_count = 0
        if remaining > 0:
            sources = []
            if microstructure_source in {"archive", "hybrid"}:
                if self.microstructure_archive is None: raise ValueError("archive replay source is unavailable")
                sources.append(("archive", self.microstructure_archive.query(normalized, _iso(start), _iso(end), limit=remaining)))
            if microstructure_source in {"live", "hybrid"}: sources.append(("live", self.microstructure.query(normalized, _iso(start), _iso(end), limit=remaining)))
            unique: dict[str, dict[str, Any]] = {}; micro_source_counts = {}
            for source_name, result in sources:
                truncated = truncated or bool(result.get("truncated")); micro_source_counts[source_name] = len(result["events"])
                for event in result["events"]: unique[str(event["event_id"])] = event
            micro_events = sorted(unique.values(), key=lambda value: (value["timestamp"], value["event_type"], value["event_id"]))
            microstructure_unique_count = len(micro_events)
            for event in micro_events[:remaining]:
                frames.append(_frame(event["timestamp"], event["event_type"], event["symbol"], event))
                lane_counts[event["event_type"]] = lane_counts.get(event["event_type"], 0) + 1
            truncated = truncated or len(micro_events) > remaining
        else: micro_source_counts = {}
        for trade in record.result.get("trades") or []:
            timestamp = trade.get("timestamp") or trade.get("datetime") or trade.get("date")
            if timestamp and _in_range(timestamp, start, end):
                frames.append(_frame(_iso(timestamp), "trade", str(trade.get("symbol") or normalized[0]), trade))
                lane_counts["trade"] = lane_counts.get("trade", 0) + 1
        frames.sort(key=lambda value: (value["timestamp"], _priority(value["lane"]), value["event_id"]))
        if len(frames) > cap:
            frames, truncated = frames[:cap], True
        lane_counts = {}
        for frame in frames:
            key = f"bar:{frame['payload'].get('timeframe')}" if frame["lane"] == "bar" else frame["lane"]
            lane_counts[key] = lane_counts.get(key, 0) + 1
        session_id = f"replay_{uuid4().hex}"
        canonical = json.dumps(frames, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        frames_name = f"{session_id}.frames.jsonl"; index_name = f"{session_id}.index.json"
        frame_file_hash, checkpoints = self._write_frames(frames_name, frames)
        index_payload = {"schema_version": 1, "session_id": session_id, "checkpoint_interval": 1000, "checkpoints": checkpoints}
        _atomic(self.root / index_name, index_payload); index_hash = f"sha256:{_hash_file(self.root / index_name)}"
        payload = {
            "schema_version": 2, "session_id": session_id, "experiment_id": record.id,
            "symbols": normalized, "start": _iso(start), "end": _iso(end),
            "lane_counts": lane_counts, "event_count": len(frames), "truncated": truncated,
            "microstructure_source": microstructure_source, "microstructure_source_counts": micro_source_counts,
            "microstructure_unique_count": microstructure_unique_count,
            "timeline_hash": f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}",
            "frames_file": frames_name, "frames_file_hash": frame_file_hash,
            "index_file": index_name, "index_file_hash": index_hash, "checkpoint_interval": 1000,
            "read_only": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _atomic(self.root / f"{session_id}.json", payload)
        return payload

    def page(self, session_id: str, cursor: int = 0, limit: int = 500) -> dict[str, Any]:
        payload = self._load(session_id)
        cursor, limit = max(0, int(cursor)), max(1, min(5000, int(limit)))
        if payload.get("schema_version") == 2:
            return self._page_v2(payload, cursor, limit)
        frames = payload["frames"][cursor:cursor + limit]
        next_cursor = cursor + len(frames)
        state: dict[str, Any] = {"last_bar": {}, "last_tick": {}, "last_orderbook": {}, "positions": {}}
        for frame in payload["frames"][:next_cursor]:
            symbol, lane = frame["symbol"], frame["lane"]
            if lane == "bar": state["last_bar"][symbol] = frame["payload"]
            elif lane == "tick": state["last_tick"][symbol] = frame["payload"]
            elif lane == "orderbook": state["last_orderbook"][symbol] = frame["payload"]
            elif lane == "trade":
                trade = frame["payload"]
                quantity = float(trade.get("quantity") or trade.get("shares") or 0)
                side = str(trade.get("side") or trade.get("action") or "").upper()
                previous = float((state["positions"].get(symbol) or {}).get("quantity") or 0)
                signed = quantity if side in {"BUY", "ENTRY"} else -quantity if side in {"SELL", "EXIT"} else 0
                state["positions"][symbol] = {"quantity": previous + signed, "last_trade": trade}
        return {
            "ok": True, "session_id": session_id, "cursor": cursor, "next_cursor": next_cursor,
            "has_more": next_cursor < len(payload["frames"]), "frames": frames,
            "state": state, "timeline_hash": payload["timeline_hash"], "read_only": True,
        }

    def verify(self, session_id: str) -> dict[str, Any]:
        payload = self._load(session_id); errors = []; checked = 0
        if payload.get("schema_version") == 1:
            frames = payload.get("frames") or []; canonical = json.dumps(frames, ensure_ascii=False, sort_keys=True, separators=(",", ":")); actual_timeline = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"; checked = len(frames)
            if checked != int(payload.get("event_count") or 0): errors.append("event_count_mismatch")
            if actual_timeline != payload.get("timeline_hash"): errors.append("timeline_hash_mismatch")
            return {"ok": not errors, "verified": not errors, "session_id": session_id, "schema_version": 1, "checked_frames": checked, "errors": errors, "timeline_hash": actual_timeline, "read_only": True}
        frames_path = self.root / Path(str(payload.get("frames_file") or "")).name; index_path = self.root / Path(str(payload.get("index_file") or "")).name
        if not frames_path.is_file(): errors.append("frames_file_missing")
        if not index_path.is_file(): errors.append("index_file_missing")
        if errors: return {"ok": False, "verified": False, "session_id": session_id, "schema_version": 2, "checked_frames": 0, "errors": errors, "read_only": True}
        actual_frames_hash = f"sha256:{_hash_file(frames_path)}"; actual_index_hash = f"sha256:{_hash_file(index_path)}"
        if actual_frames_hash != payload.get("frames_file_hash"): errors.append("frames_file_hash_mismatch")
        if actual_index_hash != payload.get("index_file_hash"): errors.append("index_file_hash_mismatch")
        digest = hashlib.sha256(); digest.update(b"["); first = True
        with frames_path.open("rb") as handle:
            for line in handle:
                if not line.strip(): continue
                try: frame = json.loads(line.decode("utf-8")); _verify_frame(frame)
                except Exception: errors.append(f"invalid_frame:{checked}"); break
                encoded = json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                if not first: digest.update(b",")
                digest.update(encoded); first = False; checked += 1
        digest.update(b"]"); actual_timeline = f"sha256:{digest.hexdigest()}"
        if checked != int(payload.get("event_count") or 0): errors.append("event_count_mismatch")
        if actual_timeline != payload.get("timeline_hash"): errors.append("timeline_hash_mismatch")
        return {"ok": not errors, "verified": not errors, "session_id": session_id, "schema_version": 2, "checked_frames": checked, "errors": errors, "timeline_hash": actual_timeline, "frames_file_hash": actual_frames_hash, "index_file_hash": actual_index_hash, "read_only": True}

    def _load(self, session_id: str) -> dict[str, Any]:
        if not session_id.startswith("replay_") or not session_id.replace("_", "").isalnum():
            raise ValueError("invalid replay session id")
        path = self.root / f"{session_id}.json"
        if not path.is_file(): raise ValueError("replay session not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_frames(self, name: str, frames: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        path = self.root / name; temporary = path.with_suffix(path.suffix + ".tmp"); digest = hashlib.sha256(); checkpoints = []
        state = _empty_state()
        with temporary.open("wb") as handle:
            for index, frame in enumerate(frames):
                if index % 1000 == 0: checkpoints.append({"cursor": index, "offset": handle.tell(), "state": copy.deepcopy(state)})
                encoded = (json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
                handle.write(encoded); digest.update(encoded); _apply_state(state, frame)
        temporary.replace(path)
        return f"sha256:{digest.hexdigest()}", checkpoints

    def _page_v2(self, payload: dict[str, Any], cursor: int, limit: int) -> dict[str, Any]:
        event_count = int(payload["event_count"]); cursor = min(cursor, event_count); next_target = min(event_count, cursor + limit)
        index_path = self.root / Path(str(payload["index_file"])).name
        if f"sha256:{_hash_file(index_path)}" != str(payload.get("index_file_hash")): raise ValueError("replay index integrity verification failed")
        index = json.loads(index_path.read_text(encoding="utf-8")); candidates = [row for row in index.get("checkpoints", []) if int(row["cursor"]) <= cursor]
        checkpoint = candidates[-1] if candidates else {"cursor": 0, "offset": 0, "state": _empty_state()}
        state, frames, position = copy.deepcopy(checkpoint["state"]), [], int(checkpoint["cursor"])
        frames_path = self.root / Path(str(payload["frames_file"])).name
        with frames_path.open("rb") as handle:
            handle.seek(int(checkpoint["offset"]))
            while position < next_target:
                line = handle.readline()
                if not line: raise ValueError("replay frame file ended before event_count")
                frame = json.loads(line.decode("utf-8")); _verify_frame(frame)
                _apply_state(state, frame)
                if position >= cursor: frames.append(frame)
                position += 1
        next_cursor = cursor + len(frames)
        return {"ok": True, "session_id": payload["session_id"], "cursor": cursor, "next_cursor": next_cursor, "has_more": next_cursor < event_count, "frames": frames, "state": state, "timeline_hash": payload["timeline_hash"], "read_only": True, "indexed": True, "checkpoint_cursor": int(checkpoint["cursor"]), "frames_scanned": next_target - int(checkpoint["cursor"])}


def _frame(timestamp: str, lane: str, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_timestamp = _iso(timestamp)
    canonical = json.dumps({"timestamp": normalized_timestamp, "lane": lane, "symbol": symbol, "payload": payload}, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return {"event_id": hashlib.sha256(canonical.encode()).hexdigest(), "timestamp": normalized_timestamp, "lane": lane, "symbol": symbol, "payload": payload}


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _iso(value: str) -> str:
    return _parse_time(value).isoformat()


def _in_range(value: str, start: str, end: str) -> bool:
    return _parse_time(start) <= _parse_time(value) <= _parse_time(end)


def _priority(lane: str) -> int:
    return {"bar": 10, "tick": 20, "orderbook": 30, "program_flow": 40, "trade": 50}.get(lane, 99)


def _empty_state() -> dict[str, Any]: return {"last_bar": {}, "last_tick": {}, "last_orderbook": {}, "positions": {}}


def _apply_state(state: dict[str, Any], frame: dict[str, Any]) -> None:
    symbol, lane = frame["symbol"], frame["lane"]
    if lane == "bar": state["last_bar"][symbol] = frame["payload"]
    elif lane == "tick": state["last_tick"][symbol] = frame["payload"]
    elif lane == "orderbook": state["last_orderbook"][symbol] = frame["payload"]
    elif lane == "trade":
        trade = frame["payload"]; quantity = float(trade.get("quantity") or trade.get("shares") or 0); side = str(trade.get("side") or trade.get("action") or "").upper(); previous = float((state["positions"].get(symbol) or {}).get("quantity") or 0); signed = quantity if side in {"BUY", "ENTRY"} else -quantity if side in {"SELL", "EXIT"} else 0; state["positions"][symbol] = {"quantity": previous + signed, "last_trade": trade}


def _verify_frame(frame: dict[str, Any]) -> None:
    expected = _frame(frame["timestamp"], frame["lane"], frame["symbol"], frame["payload"])["event_id"]
    if frame.get("event_id") != expected: raise ValueError("replay frame integrity verification failed")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
