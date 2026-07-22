"""Durable heartbeat evidence for proving uninterrupted sidecar operation."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def _now() -> datetime:
    return datetime.now().astimezone()


class RuntimeEvidenceLedger:
    def __init__(self, path: Path, session_id: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or uuid.uuid4().hex
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    mode TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime_heartbeats (
                    session_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    cycle INTEGER NOT NULL,
                    ok INTEGER NOT NULL,
                    PRIMARY KEY(session_id, observed_at)
                );
                CREATE INDEX IF NOT EXISTS idx_runtime_heartbeats_time
                    ON runtime_heartbeats(observed_at);
                """
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def heartbeat(self, mode: str, cycle: int, ok: bool, observed_at: datetime | None = None) -> str:
        stamp = (observed_at or _now()).isoformat(timespec="milliseconds")
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO runtime_sessions(session_id,started_at,last_heartbeat_at,mode) VALUES(?,?,?,?)",
                (self.session_id, stamp, stamp, mode),
            )
            db.execute(
                "UPDATE runtime_sessions SET last_heartbeat_at=?,mode=? WHERE session_id=?",
                (stamp, mode, self.session_id),
            )
            db.execute(
                "INSERT OR REPLACE INTO runtime_heartbeats(session_id,observed_at,cycle,ok) VALUES(?,?,?,?)",
                (self.session_id, stamp, int(cycle), 1 if ok else 0),
            )
        return stamp


def audit_runtime_evidence(path: Path, max_gap_seconds: float = 90.0) -> dict[str, object]:
    path = Path(path)
    if not path.exists():
        return {"ok": False, "reason": "runtime_evidence_missing", "continuous_hours": 0.0, "heartbeat_count": 0}
    try:
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """SELECT h.session_id,h.observed_at,h.cycle,h.ok,s.mode
               FROM runtime_heartbeats h
               JOIN runtime_sessions s ON s.session_id=h.session_id
               ORDER BY h.observed_at"""
        ).fetchall()
        db.close()
    except sqlite3.Error as exc:
        return {"ok": False, "reason": f"runtime_evidence_error:{exc}", "continuous_hours": 0.0, "heartbeat_count": 0}
    parsed = [
        (
            str(row["session_id"]), datetime.fromisoformat(row["observed_at"]),
            int(row["cycle"]), bool(row["ok"]), str(row["mode"]),
        )
        for row in rows
    ]
    if not parsed:
        return {"ok": False, "reason": "runtime_evidence_empty", "continuous_hours": 0.0, "heartbeat_count": 0}
    current_session = parsed[-1][0]
    segment_start = parsed[-1][1]
    previous = parsed[-1][1]
    previous_cycle = parsed[-1][2]
    latest_failed = not parsed[-1][3]
    current_mode = parsed[-1][4]
    future_seconds = (parsed[-1][1] - _now()).total_seconds()
    latest_from_future = future_seconds > 5.0
    max_observed_gap = 0.0
    sequence_break_detected = False
    continuous_heartbeat_count = 0
    first = True
    for session_id, stamp, cycle, ok, mode in reversed(parsed):
        if session_id != current_session:
            break
        gap = (previous - stamp).total_seconds()
        max_observed_gap = max(max_observed_gap, gap)
        if gap > max_gap_seconds:
            break
        if not first and cycle >= previous_cycle:
            sequence_break_detected = True
            break
        if not ok:
            break
        continuous_heartbeat_count += 1
        segment_start = stamp
        previous = stamp
        previous_cycle = cycle
        first = False
    continuous_hours = max(0.0, (parsed[-1][1] - segment_start).total_seconds() / 3600)
    if latest_from_future:
        continuous_hours = 0.0
        continuous_heartbeat_count = 0
    return {
        "ok": not latest_failed and not latest_from_future,
        "reason": (
            "heartbeat_from_future" if latest_from_future
            else "failed_heartbeat" if latest_failed
            else "continuous"
        ),
        "continuous_hours": round(continuous_hours, 6),
        "heartbeat_count": continuous_heartbeat_count,
        "total_heartbeat_count": len(parsed),
        "max_allowed_gap_seconds": float(max_gap_seconds),
        "max_observed_gap_seconds": round(max_observed_gap, 3),
        "current_session_id": current_session,
        "current_mode": current_mode,
        "latest_cycle": parsed[-1][2],
        "sequence_break_detected": sequence_break_detected,
        "future_seconds": round(max(0.0, future_seconds), 3),
        "continuous_started_at": segment_start.isoformat(timespec="milliseconds"),
        "latest_heartbeat_at": parsed[-1][1].isoformat(timespec="milliseconds"),
    }
