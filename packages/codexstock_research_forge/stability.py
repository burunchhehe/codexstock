from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class EngineStabilityLedger:
    _lock = threading.RLock()

    def __init__(self, path: Path) -> None:
        self.path = path; path.parent.mkdir(parents=True, exist_ok=True)

    def record_dashboard(self, dashboard: dict[str, Any], min_interval_seconds: int = 300) -> dict[str, Any]:
        engines = dashboard.get("engines") if isinstance(dashboard.get("engines"), list) else []
        if not engines:
            raise ValueError("engine stability snapshot requires engine rows")
        observed_at = str(dashboard.get("generated_at") or datetime.now(timezone.utc).isoformat())
        normalized = [_engine_row(row) for row in engines if isinstance(row, dict)]
        if not normalized or len({row["engine_id"] for row in normalized}) != len(normalized):
            raise ValueError("engine stability snapshot contains missing or duplicate ids")
        normalized.sort(key=lambda row: row["engine_id"])
        snapshot_hash = _hash({"observed_at": observed_at, "engines": normalized})
        with self._lock:
            rows, invalid = self._read_verified()
            if invalid:
                return {"ok": False, "recorded": False, "invalid_lines": invalid, "reason": "ledger_integrity_failed"}
            if rows and rows[-1]["snapshot_hash"] == snapshot_hash:
                return {"ok": True, "recorded": False, "reason": "same_snapshot", "evidence_hash": rows[-1]["evidence_hash"]}
            if rows:
                age = (datetime.now(timezone.utc) - _time(rows[-1]["recorded_at"])).total_seconds()
                previous_states = [(row["engine_id"], row["operational_state"], row["contract_hash"]) for row in rows[-1]["engines"]]
                current_states = [(row["engine_id"], row["operational_state"], row["contract_hash"]) for row in normalized]
                if age < max(1, int(min_interval_seconds)) and previous_states == current_states:
                    return {"ok": True, "recorded": False, "reason": "interval_not_elapsed", "evidence_hash": rows[-1]["evidence_hash"]}
            payload = {
                "schema_version": 1, "recorded_at": datetime.now(timezone.utc).isoformat(),
                "observed_at": observed_at, "snapshot_hash": snapshot_hash,
                "previous_evidence_hash": rows[-1]["evidence_hash"] if rows else None,
                "engines": normalized, "engine_count": len(normalized),
                "research_only": True, "live_order_allowed": False,
            }
            payload["evidence_hash"] = _hash(payload)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            return {"ok": True, "recorded": True, "evidence_hash": payload["evidence_hash"], "engine_count": len(normalized)}

    def audit(self, window_days: int = 30, max_gap_seconds: int = 900) -> dict[str, Any]:
        with self._lock: rows, invalid = self._read_verified()
        now = datetime.now(timezone.utc); cutoff = now - timedelta(days=max(1, min(3650, int(window_days))))
        selected = [row for row in rows if _time(row["recorded_at"]) >= cutoff]
        per_engine: dict[str, list[dict[str, Any]]] = {}
        for snapshot in selected:
            for engine in snapshot["engines"]: per_engine.setdefault(engine["engine_id"], []).append({"recorded_at": snapshot["recorded_at"], **engine})
        engine_audits = []
        for engine_id, samples in sorted(per_engine.items()):
            healthy = sum(row["operational_state"] == "normal" for row in samples)
            gaps = [(_time(right["recorded_at"]) - _time(left["recorded_at"])).total_seconds() for left, right in zip(samples, samples[1:])]
            contracts = {row["contract_hash"] for row in samples}
            consecutive_failures = 0; maximum_consecutive_failures = 0
            for row in samples:
                consecutive_failures = 0 if row["operational_state"] == "normal" else consecutive_failures + 1
                maximum_consecutive_failures = max(maximum_consecutive_failures, consecutive_failures)
            engine_audits.append({
                "engine_id": engine_id, "sample_count": len(samples),
                "normal_sample_count": healthy, "normal_ratio_pct": round(healthy / len(samples) * 100, 3),
                "max_observed_gap_seconds": round(max(gaps), 3) if gaps else None,
                "gap_within_limit": bool(gaps and max(gaps) <= max_gap_seconds) if len(samples) > 1 else None,
                "contract_version_count": len(contracts), "contract_drift_detected": len(contracts) > 1,
                "maximum_consecutive_non_normal": maximum_consecutive_failures,
                "latest_state": samples[-1]["operational_state"], "latest_root_cause": samples[-1]["root_cause_code"],
            })
        observed_span_seconds = (
            (_time(selected[-1]["recorded_at"]) - _time(selected[0]["recorded_at"])).total_seconds()
            if len(selected) >= 2 else 0.0
        )
        required_span_seconds = max(0, int(window_days) - 1) * 86_400
        enough_history = bool(
            len(selected) >= 2
            and engine_audits
            and observed_span_seconds >= required_span_seconds
            and all(row["sample_count"] >= 2 for row in engine_audits)
        )
        regressions = [row["engine_id"] for row in engine_audits if row["contract_drift_detected"] or row["maximum_consecutive_non_normal"] >= 3]
        payload = {
            "ok": not invalid and not regressions, "schema_version": 1,
            "status": "invalid" if invalid else "regression_detected" if regressions else "verified" if enough_history else "collecting_evidence",
            "window_days": window_days, "max_gap_seconds": max_gap_seconds,
            "snapshot_count": len(selected), "total_snapshot_count": len(rows), "engine_count": len(engine_audits),
            "observed_span_seconds": round(observed_span_seconds, 3), "required_span_seconds": required_span_seconds,
            "enough_history": enough_history, "regression_engine_ids": regressions,
            "invalid_lines": invalid, "engines": engine_audits,
            "evidence_chain_head": rows[-1]["evidence_hash"] if rows else None,
            "research_only": True, "live_order_allowed": False,
        }
        payload["audit_hash"] = _hash(payload)
        return payload

    def _read_verified(self) -> tuple[list[dict[str, Any]], list[int]]:
        if not self.path.is_file(): return [], []
        rows, invalid, previous = [], [], None
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                payload = json.loads(line); stored = payload.pop("evidence_hash", "")
                if payload.get("schema_version") != 1 or stored != _hash(payload) or payload.get("previous_evidence_hash") != previous: raise ValueError
                payload["evidence_hash"] = stored; _time(payload["recorded_at"]); rows.append(payload); previous = stored
            except (json.JSONDecodeError, KeyError, TypeError, ValueError): invalid.append(number)
        return rows, invalid


def _engine_row(row: dict[str, Any]) -> dict[str, Any]:
    engine_id = str(row.get("engine_id") or row.get("engine_name") or "")
    if not engine_id: raise ValueError("engine id is required")
    lifecycle = row.get("capability_lifecycle") if isinstance(row.get("capability_lifecycle"), dict) else {}
    contract = {
        "engine_id": engine_id, "engine_commit": str(row.get("engine_commit") or ""),
        "engine_version": str(row.get("engine_version") or ""), "runtime_mode": str(row.get("runtime_mode") or ""),
        "highest_stage": str(lifecycle.get("highest_achieved_stage") or ""),
        "live_order_allowed": bool(row.get("live_order_allowed", False)),
    }
    return {
        "engine_id": engine_id, "connected": bool(row.get("connected")),
        "runtime_connected": bool(row.get("runtime_connected")), "formal_connected": bool(row.get("formal_connected")),
        "adapter_ready": bool(row.get("adapter_ready")), "current_usable": bool(row.get("current_usable")),
        "operational_state": str(row.get("operational_state") or "unknown"),
        "root_cause_code": str(row.get("root_cause_code") or ""), "contract_hash": _hash(contract),
    }


def _hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")); return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")); return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
