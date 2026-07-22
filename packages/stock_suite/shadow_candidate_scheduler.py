"""Persisted scheduler for forward-only Shadow candidate evidence."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping, Sequence


def eligible_shadow_candidates(lanes: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Select only six-digit Korean candidates already passed by the upstream gate."""
    selected: list[Mapping[str, object]] = []
    for row in lanes:
        symbol = str(row.get("symbol") or "").strip()
        gate = str(row.get("gate") or row.get("risk_gate_status") or "").upper().strip()
        if len(symbol) == 6 and symbol.isdigit() and gate == "PASSED":
            selected.append(row)
    return selected


def _read(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    try:
        for attempt in range(40):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def run_shadow_candidate_tick(
    *,
    state_file: Path,
    market_open: bool,
    candidates: Sequence[Mapping[str, object]],
    create_candidate: Callable[[Mapping[str, object]], Mapping[str, object]],
    now: datetime | None = None,
    cadence_seconds: int = 1800,
    max_per_day: int = 10,
) -> dict[str, object]:
    observed_at = now or datetime.now().astimezone()
    if observed_at.tzinfo is None:
        raise ValueError("shadow candidate scheduler clock must include a timezone")
    today = observed_at.date().isoformat()
    state = _read(Path(state_file))
    if state.get("date") != today:
        state = {
            "date": today,
            "emitted_count": 0,
            "next_index": 0,
            "observed_symbols": [],
        }
    base = {
        "ok": True,
        "schema": "codexstock.shadow-candidate-scheduler.v1",
        "checked_at": observed_at.isoformat(timespec="seconds"),
        "market_open": bool(market_open),
        "real_order_allowed": False,
        "approval_created": False,
        "emitted_count": int(state.get("emitted_count") or 0),
        "max_per_day": int(max_per_day),
    }
    if not market_open:
        state.update({
            "last_checked_at": observed_at.isoformat(timespec="seconds"),
            "last_status": "MARKET_CLOSED",
            "market_open": False,
        })
        _write(Path(state_file), state)
        return {**base, "status": "MARKET_CLOSED", "published": False}
    if int(state.get("emitted_count") or 0) >= int(max_per_day):
        state.update({
            "last_checked_at": observed_at.isoformat(timespec="seconds"),
            "last_status": "DAILY_EVIDENCE_LIMIT_REACHED",
            "market_open": True,
        })
        _write(Path(state_file), state)
        return {**base, "status": "DAILY_EVIDENCE_LIMIT_REACHED", "published": False}
    next_attempt = _parse(state.get("next_attempt_at"))
    if next_attempt and observed_at < next_attempt:
        state.update({
            "last_checked_at": observed_at.isoformat(timespec="seconds"),
            "last_status": "CADENCE_WAIT",
            "market_open": True,
        })
        _write(Path(state_file), state)
        return {
            **base,
            "status": "CADENCE_WAIT",
            "published": False,
            "next_attempt_at": next_attempt.isoformat(timespec="seconds"),
        }
    unique: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for candidate in candidates:
        symbol = str(candidate.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        unique.append(candidate)
    if not unique:
        state.update({
            "last_checked_at": observed_at.isoformat(timespec="seconds"),
            "last_attempt_at": observed_at.isoformat(timespec="seconds"),
            "next_attempt_at": (observed_at + timedelta(minutes=5)).isoformat(timespec="seconds"),
            "last_status": "NO_CANDIDATE",
            "market_open": True,
        })
        _write(Path(state_file), state)
        return {**base, "status": "NO_CANDIDATE", "published": False}

    index = int(state.get("next_index") or 0) % len(unique)
    selected = unique[index]
    symbol = str(selected.get("symbol") or "").upper().strip()
    try:
        ticket = dict(create_candidate(selected))
        shadow_signal = ticket.get("shadow_signal") if isinstance(ticket.get("shadow_signal"), dict) else {}
        published = shadow_signal.get("published") is True
        status = "PUBLISHED" if published else "PUBLISH_BLOCKED"
        error = "" if published else str(shadow_signal.get("reason") or ticket.get("risk_status") or "blocked")
    except Exception as exc:
        ticket = {}
        published = False
        status = "ERROR"
        error = f"{type(exc).__name__}: {exc}"[:500]

    retry_seconds = max(60, int(cadence_seconds)) if published else 300
    observed_symbols = [str(value) for value in state.get("observed_symbols", []) if str(value)]
    if published and symbol not in observed_symbols:
        observed_symbols.append(symbol)
    state.update({
        "last_checked_at": observed_at.isoformat(timespec="seconds"),
        "last_attempt_at": observed_at.isoformat(timespec="seconds"),
        "next_attempt_at": (observed_at + timedelta(seconds=retry_seconds)).isoformat(timespec="seconds"),
        "last_status": status,
        "last_symbol": symbol,
        "last_ticket_id": ticket.get("id", ""),
        "last_error": error,
        "next_index": (index + 1) % len(unique),
        "observed_symbols": observed_symbols,
        "market_open": True,
    })
    if published:
        state["emitted_count"] = int(state.get("emitted_count") or 0) + 1
    _write(Path(state_file), state)
    return {
        **base,
        "status": status,
        "published": published,
        "symbol": symbol,
        "ticket_id": ticket.get("id", ""),
        "risk_status": ticket.get("risk_status", ""),
        "shadow_signal": ticket.get("shadow_signal", {}),
        "error": error,
        "emitted_count": int(state.get("emitted_count") or 0),
        "observed_symbols": observed_symbols,
        "next_attempt_at": state.get("next_attempt_at"),
        "real_order_allowed": False,
        "approval_created": bool(ticket.get("approval_token")),
    }
