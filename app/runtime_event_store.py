from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable


JsonRow = dict[str, object]
MirrorCallback = Callable[[Path, JsonRow], object]


def parse_jsonl_lines(lines: list[str]) -> list[JsonRow]:
    rows: list[JsonRow] = []
    for line in lines:
        clean = line.strip().lstrip("\ufeff")
        if not clean:
            continue
        try:
            item = json.loads(clean)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def read_jsonl_tail(path: Path, limit: int) -> list[JsonRow]:
    """Read only the end of a large JSONL file when the caller needs recent rows."""
    if limit <= 0 or not path.exists():
        return []
    try:
        file_size = path.stat().st_size
    except OSError:
        return []
    if file_size <= 0:
        return []
    chunk_size = min(file_size, max(64 * 1024, min(limit, 2000) * 4096))
    max_chunk = file_size
    while chunk_size <= max_chunk:
        start = max(0, file_size - chunk_size)
        try:
            with path.open("rb") as handle:
                handle.seek(start)
                data = handle.read(file_size - start)
        except OSError:
            return []
        lines = data.decode("utf-8", errors="ignore").splitlines()
        if start > 0 and lines:
            lines = lines[1:]
        rows = parse_jsonl_lines(lines)
        if len(rows) >= limit or start == 0:
            return rows[-limit:]
        if chunk_size >= file_size:
            return rows[-limit:]
        chunk_size = min(file_size, chunk_size * 2)
    return []


def read_jsonl(path: Path, limit: int | None = None) -> list[JsonRow]:
    if not path.exists():
        return []
    if limit and limit > 0:
        return read_jsonl_tail(path, int(limit))
    return parse_jsonl_lines(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def append_jsonl(path: Path, payload: JsonRow, mirror: MirrorCallback | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    if mirror is not None:
        mirror(path, payload)


def compact_jsonl(path: Path, max_rows: int = 600) -> None:
    rows = read_jsonl(path)
    if len(rows) <= max_rows:
        return
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows[-max_rows:]) + "\n",
        encoding="utf-8",
    )


def jsonl_event_first_value(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return ""


def jsonl_event_nested_value(payload: dict[str, object], *paths: tuple[str, ...]) -> str:
    for path in paths:
        current: object = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, "", [], {}):
            return str(current)
    return ""


def jsonl_payload_hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def runtime_event_index_payload(path: Path, payload: dict[str, object]) -> dict[str, object]:
    """Return the compact payload stored in the SQLite lookup index."""
    if path.name == "historical_paper_replays.jsonl":
        return {
            "id": payload.get("id"),
            "generated_at": payload.get("generated_at"),
            "source": payload.get("source"),
            "symbols": payload.get("symbols", []),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "strategy_mode": payload.get("strategy_mode"),
            "strategy_label": payload.get("strategy_label"),
            "strategy_owner": payload.get("strategy_owner"),
            "initial_cash": payload.get("initial_cash"),
            "final_equity": payload.get("final_equity"),
            "total_return_pct": payload.get("total_return_pct"),
            "max_drawdown_pct": payload.get("max_drawdown_pct"),
            "trade_count": payload.get("trade_count"),
            "closed_trade_count": payload.get("closed_trade_count"),
            "win_rate_pct": payload.get("win_rate_pct"),
            "replay_days": payload.get("replay_days"),
            "cycles_per_day": payload.get("cycles_per_day"),
            "compressed_training_hours": payload.get("compressed_training_hours"),
            "trade_journal_count": payload.get("trade_journal_count"),
            "trade_action_count": payload.get("trade_action_count"),
            "trade_journal_path": payload.get("trade_journal_path"),
            "trade_journal_markdown_path": payload.get("trade_journal_markdown_path"),
            "summary": payload.get("summary"),
            "safety": "SQLite index keeps only replay summaries. Curves and full trade journals stay in source files.",
        }
    if path.name == "ai_staff_meetings.jsonl":
        decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
        top = payload.get("top_candidate") if isinstance(payload.get("top_candidate"), dict) else {}
        quality = payload.get("dialogue_quality") if isinstance(payload.get("dialogue_quality"), dict) else {}
        frame = payload.get("decision_frame") if isinstance(payload.get("decision_frame"), dict) else {}
        return {
            "id": payload.get("id"),
            "created_at": payload.get("created_at"),
            "source": payload.get("source"),
            "quick": bool(payload.get("quick")),
            "agenda": payload.get("agenda"),
            "top_candidate": {
                "symbol": top.get("symbol"),
                "name": top.get("name"),
                "score": top.get("score"),
                "gate": top.get("gate"),
            },
            "decision": {
                "label": decision.get("label"),
                "confidence": decision.get("confidence"),
                "execution_bias": decision.get("execution_bias"),
            },
            "decision_brief": payload.get("decision_brief") if isinstance(payload.get("decision_brief"), dict) else {},
            "decision_frame": {
                "observation": frame.get("observation", [])[:4] if isinstance(frame.get("observation"), list) else [],
                "thesis": frame.get("thesis", [])[:3] if isinstance(frame.get("thesis"), list) else [],
                "risk_checks": frame.get("risk_checks", [])[:4] if isinstance(frame.get("risk_checks"), list) else [],
                "action_plan": frame.get("action_plan", [])[:5] if isinstance(frame.get("action_plan"), list) else [],
                "verification_needed": frame.get("verification_needed", [])[:5]
                if isinstance(frame.get("verification_needed"), list)
                else [],
                "verification_count": frame.get("verification_count")
                if isinstance(frame.get("verification_count"), int)
                else len(frame.get("verification_needed", []))
                if isinstance(frame.get("verification_needed"), list)
                else 0,
                "execution_state": frame.get("execution_state"),
                "machine_summary": frame.get("machine_summary") if isinstance(frame.get("machine_summary"), dict) else {},
            },
            "dialogue_quality": quality,
            "structured_dialogue": payload.get("structured_dialogue", [])[:6]
            if isinstance(payload.get("structured_dialogue"), list)
            else [],
            "next_actions": payload.get("next_actions", [])[:5] if isinstance(payload.get("next_actions"), list) else [],
            "real_execution": payload.get("real_execution"),
            "note": payload.get("note") if isinstance(payload.get("note"), dict) else {},
            "safety": "SQLite index keeps only AI meeting summaries, decisions, and structure. Full messages remain in JSONL.",
        }
    return {
        "index_payload_version": "compact_v1",
        "id": payload.get("id"),
        "type": payload.get("type") or payload.get("kind") or payload.get("event"),
        "generated_at": payload.get("generated_at"),
        "created_at": payload.get("created_at"),
        "source": payload.get("source"),
        "status": payload.get("status") or payload.get("state"),
        "symbol": payload.get("symbol") or payload.get("ticker"),
        "name": payload.get("name"),
        "summary": payload.get("summary"),
        "headline": payload.get("headline"),
        "message": payload.get("message"),
        "safety": payload.get("safety"),
    }


def jsonl_event_payload_date(payload: dict[str, object]) -> str:
    created_at = jsonl_event_first_value(
        payload,
        "generated_at",
        "created_at",
        "submitted_at",
        "detected_at",
        "updated_at",
        "date",
    )
    return str(created_at or "")[:10] if created_at else ""


def jsonl_event_payload_symbol(payload: dict[str, object]) -> str:
    symbol = jsonl_event_first_value(payload, "symbol", "pdno", "ticker")
    if not symbol:
        symbol = jsonl_event_nested_value(payload, ("ticket", "symbol"), ("top", "symbol"), ("active", "symbol"))
    return str(symbol or "").upper().strip()


def jsonl_event_status_value(payload: dict[str, object]) -> str:
    return jsonl_event_first_value(payload, "status", "state", "tone", "mode").upper().strip()


def filter_jsonl_event_rows(
    rows: list[dict[str, object]],
    *,
    event_date: str = "",
    symbol: str = "",
    status: str = "",
) -> list[dict[str, object]]:
    target_date = str(event_date or "").strip()
    target_symbol = str(symbol or "").upper().strip()
    target_status = str(status or "").upper().strip()
    filtered: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if target_date and jsonl_event_payload_date(row) != target_date:
            continue
        if target_symbol and jsonl_event_payload_symbol(row) != target_symbol:
            continue
        if target_status and jsonl_event_status_value(row) != target_status:
            continue
        filtered.append(row)
    return filtered


def dedupe_jsonl_event_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = jsonl_payload_hash(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
