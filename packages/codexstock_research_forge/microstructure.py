from __future__ import annotations

import hashlib
import json
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EVENT_TYPES = {"tick", "orderbook", "program_flow"}


@dataclass(frozen=True)
class MarketEvent:
    event_type: str
    symbol: str
    timestamp: str
    source: str
    payload: dict[str, Any]

    @classmethod
    def parse(cls, value: dict[str, Any]) -> "MarketEvent":
        event_type = str(value.get("event_type") or "")
        symbol = str(value.get("symbol") or "").upper()
        source = str(value.get("source") or "")
        timestamp = str(value.get("timestamp") or "")
        payload = value.get("payload")
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported microstructure event_type: {event_type}")
        if not symbol or not symbol.isalnum():
            raise ValueError("microstructure symbol must be alphanumeric")
        if not source or not source.replace("_", "").replace("-", "").isalnum():
            raise ValueError("microstructure source is required")
        if not isinstance(payload, dict):
            raise ValueError("microstructure payload must be an object")
        parsed = _timestamp(timestamp)
        return cls(event_type, symbol, parsed.isoformat(), source, dict(payload))

    @property
    def stream_id(self) -> str:
        return f"{self.source}:{self.event_type}:{self.symbol}"

    @property
    def event_id(self) -> str:
        canonical = json.dumps(
            {"event_type": self.event_type, "symbol": self.symbol, "timestamp": self.timestamp, "source": self.source, "payload": self.payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "source": self.source,
            "payload": self.payload,
        }


class MicrostructureStore:
    """Local append-only event store designed for a separate collector process."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.events_root = root / "events"
        self.state_path = root / "checkpoint.json"
        self.events_root.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def ingest(self, values: Iterable[dict[str, Any]], gap_seconds: int = 10) -> dict[str, Any]:
        events = [MarketEvent.parse(value) for value in values]
        if not events:
            raise ValueError("at least one event is required")
        gap_seconds = max(1, min(3600, int(gap_seconds)))
        accepted, duplicates, gaps = 0, 0, []
        seen_in_batch: set[str] = set()
        buffers: dict[Path, list[str]] = {}
        working_state = copy.deepcopy(self.state)
        streams = working_state.setdefault("streams", {})
        for event in events:
            stream = streams.setdefault(event.stream_id, {"count": 0, "duplicate_count": 0, "gap_count": 0})
            event_id = event.event_id
            recent_ids = list(stream.get("recent_event_ids") or [])
            if event_id in seen_in_batch or event_id in recent_ids:
                duplicates += 1
                stream["duplicate_count"] = int(stream.get("duplicate_count") or 0) + 1
                continue
            current = _timestamp(event.timestamp)
            last_raw = str(stream.get("last_timestamp") or "")
            if last_raw:
                last = _timestamp(last_raw)
                delta = (current - last).total_seconds()
                if delta < 0:
                    raise ValueError(f"timestamp regression for {event.stream_id}: {event.timestamp} < {last_raw}")
                if delta > gap_seconds:
                    gap = {"stream_id": event.stream_id, "from": last.isoformat(), "to": current.isoformat(), "seconds": delta}
                    gaps.append(gap)
                    stream["gap_count"] = int(stream.get("gap_count") or 0) + 1
                    stream["last_gap"] = gap
            day = current.date().isoformat()
            target = self.events_root / event.event_type / day / f"{event.symbol}.jsonl"
            buffers.setdefault(target, []).append(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            recent_ids.append(event_id)
            stream.update({
                "last_timestamp": current.isoformat(),
                "last_event_id": event_id,
                "recent_event_ids": recent_ids[-256:],
                "count": int(stream.get("count") or 0) + 1,
            })
            seen_in_batch.add(event_id)
            accepted += 1
        for target, lines in buffers.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                for line in lines:
                    handle.write(line + "\n")
        working_state.update(
            {
                "schema_version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "total_accepted": int(self.state.get("total_accepted") or 0) + accepted,
                "total_duplicates": int(self.state.get("total_duplicates") or 0) + duplicates,
                "network_checked": False,
            }
        )
        self.state = working_state
        self._save_state()
        return {"ok": True, "accepted": accepted, "duplicates": duplicates, "gaps": gaps, "checkpoint": self.status()}

    def status(self) -> dict[str, Any]:
        streams = self.state.get("streams") if isinstance(self.state.get("streams"), dict) else {}
        return {
            "ok": True,
            "mode": "local_append_only",
            "event_types": sorted(EVENT_TYPES),
            "stream_count": len(streams),
            "total_accepted": int(self.state.get("total_accepted") or 0),
            "total_duplicates": int(self.state.get("total_duplicates") or 0),
            "updated_at": self.state.get("updated_at"),
            "network_checked": False,
            "live_order_allowed": False,
        }

    def quality(self) -> dict[str, Any]:
        streams = self.state.get("streams") if isinstance(self.state.get("streams"), dict) else {}
        rows = []
        for stream_id, value in sorted(streams.items()):
            row = dict(value) if isinstance(value, dict) else {}
            row["stream_id"] = stream_id
            rows.append(row)
        return {
            "ok": all(int(row.get("gap_count") or 0) == 0 for row in rows),
            "streams": rows,
            "gap_stream_count": sum(int(row.get("gap_count") or 0) > 0 for row in rows),
            "duplicate_count": sum(int(row.get("duplicate_count") or 0) for row in rows),
        }

    def query(
        self, symbols: list[str], start: str, end: str,
        event_types: list[str] | None = None, limit: int = 10_000,
    ) -> dict[str, Any]:
        selected_symbols = {str(value).upper() for value in symbols}
        if not selected_symbols or any(not value.isalnum() for value in selected_symbols):
            raise ValueError("microstructure query requires alphanumeric symbols")
        selected_types = set(event_types or EVENT_TYPES)
        if not selected_types.issubset(EVENT_TYPES):
            raise ValueError("unsupported microstructure event type")
        first, last = _timestamp(start), _timestamp(end)
        if last < first:
            raise ValueError("microstructure query end precedes start")
        cap = max(1, min(100_000, int(limit)))
        events: list[dict[str, Any]] = []
        matched = 0
        for event_type in sorted(selected_types):
            for symbol in sorted(selected_symbols):
                for path in sorted((self.events_root / event_type).glob(f"*/{symbol}.jsonl")):
                    day = path.parent.name
                    try:
                        day_value = datetime.fromisoformat(day).replace(tzinfo=timezone.utc).date()
                    except ValueError:
                        continue
                    if day_value < first.date() or day_value > last.date():
                        continue
                    with path.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            event = json.loads(line)
                            timestamp = _timestamp(str(event.get("timestamp") or ""))
                            if first <= timestamp <= last:
                                matched += 1
                                if len(events) < cap:
                                    events.append(event)
        events.sort(key=lambda value: (value["timestamp"], value["event_type"], value["event_id"]))
        return {"ok": True, "count": len(events), "events": events, "truncated": matched > cap, "matched": matched}

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {"schema_version": 1, "streams": {}, "total_accepted": 0, "total_duplicates": 0}
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("unsupported microstructure checkpoint")
        return payload

    def _save_state(self) -> None:
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_path)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("microstructure timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)
