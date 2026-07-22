from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


IMPROVEMENT_CONTRACT_SCHEMA = "codexstock_external_improvement_contract_v1"
IMPROVEMENT_CYCLE_SCHEMA = "codexstock_external_improvement_cycle_v1"
VERIFIED_LESSON_SCHEMA = "codexstock_external_verified_lesson_v1"
RETRAINING_TASK_SCHEMA = "codexstock_external_retraining_task_v1"
RETRAINING_EVENT_SCHEMA = "codexstock_external_retraining_event_v1"

_ACTIVE_RETRAINING_STATUSES = {"QUEUED", "RETRY_QUEUED", "CLAIMED"}
_CLAIMABLE_RETRAINING_STATUSES = {"QUEUED", "RETRY_QUEUED"}
_TERMINAL_RETRAINING_STATUSES = {"RESOLVED", "EXHAUSTED", "SUPERSEDED"}
_RETRAINING_CLAIM_LEASE = timedelta(hours=6)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ENGINE_CONTRACTS: dict[str, dict[str, str]] = {
    "vectorbt": {
        "schema": "codexstock_vectorbt_portfolio_scenarios_v1",
        "action": "evaluate_portfolio_scenarios",
        "domain": "portfolio_robustness",
    },
    "qlib": {
        "schema": "codexstock_qlib_rolling_model_comparison_v1",
        "action": "evaluate_rolling_model_comparison",
        "domain": "rolling_oos_model_selection",
    },
    "openbb": {
        "schema": "codexstock_openbb_fundamental_macro_calendar_v1",
        "action": "crosscheck_fundamental_macro_calendar",
        "domain": "fundamental_macro_calendar_integrity",
    },
    "lean": {
        "schema": "codexstock_lean_market_lifecycle_v1",
        "action": "validate_market_lifecycle",
        "domain": "market_lifecycle_integrity",
    },
    "nautilus": {
        "schema": "codexstock_nautilus_execution_stress_v1",
        "action": "evaluate_execution_stress",
        "domain": "execution_realism",
    },
}

_MUTATION_COUNTER_KEYS = {
    "account_mutation_count",
    "live_order_count",
    "order_api_call_count",
    "orders_transmitted",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_hash(value: Any) -> str:
    material = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        result = float(value or 0.0)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if result != result or result in {float("inf"), float("-inf")}:
        return 0.0
    return result


def _bounded(value: Any, *, depth: int = 0) -> Any:
    if depth >= 5:
        return "<depth-limited>"
    if isinstance(value, dict):
        return {
            str(key)[:120]: _bounded(item, depth=depth + 1)
            for key, item in list(value.items())[:120]
        }
    if isinstance(value, list):
        return [_bounded(item, depth=depth + 1) for item in value[:120]]
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (bool, int)) or value is None:
        return value
    return str(value)[:500]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, allow_nan=False, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _read_jsonl(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.is_file() or limit <= 0:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _find_mutation_counts(value: Any, path: str = "") -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key) in _MUTATION_COUNTER_KEYS and _safe_int(item) > 0:
                matches.append({"path": child_path, "value": _safe_int(item)})
            matches.extend(_find_mutation_counts(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value[:200]):
            matches.extend(_find_mutation_counts(item, f"{path}[{index}]"))
    return matches


def _quality_blockers(quality_gate: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key, value in quality_gate.items():
        if key == "passed":
            continue
        if isinstance(value, bool) and not value:
            blockers.append(str(key))
    return blockers


class ExternalEngineImprovementStore:
    """Persist and gate research-only sub-engine results.

    The store deliberately has no broker dependency. It can create research and
    retraining evidence only; it cannot promote a strategy or submit an order.
    """

    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root) / "external_engine_improvement"
        self.state_path = self.root / "state.json"
        self.runs_path = self.root / "runs.jsonl"
        self.lessons_path = self.root / "verified_lessons.jsonl"
        self.retraining_path = self.root / "retraining_queue.jsonl"
        self.retraining_events_path = self.root / "retraining_events.jsonl"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)

    def start_cycle(
        self,
        *,
        cycle_id: str,
        symbols: list[str],
        snapshot_id: str,
        dataset_hash: str,
        requested_by: str,
    ) -> dict[str, Any]:
        state = {
            "schema": IMPROVEMENT_CYCLE_SCHEMA,
            "cycle_id": str(cycle_id),
            "status": "RUNNING",
            "started_at": _now_iso(),
            "finished_at": "",
            "phase": "prepare_common_snapshot",
            "phase_index": 0,
            "phase_count": len(_ENGINE_CONTRACTS),
            "progress_pct": 0.0,
            "symbols": [str(item).upper() for item in symbols[:20]],
            "snapshot_id": str(snapshot_id),
            "dataset_hash": str(dataset_hash),
            "requested_by": str(requested_by)[:120],
            "engine_results": [],
            "quality_pass_count": 0,
            "contract_pass_count": 0,
            "verified_lesson_count": 0,
            "retraining_task_count": 0,
            "active_retraining_task_count": len(self.active_retraining_tasks(limit=100)),
            "claimed_retraining_task_count": 0,
            "claimed_retraining_tasks": [],
            "retraining_resolution": {},
            "live_order_allowed": False,
            "promotion_allowed": False,
        }
        with self._lock:
            _atomic_write(self.state_path, state)
        return state

    def update_cycle(self, **changes: Any) -> dict[str, Any]:
        with self._lock:
            state = _read_json(self.state_path)
            if not state:
                state = {
                    "schema": IMPROVEMENT_CYCLE_SCHEMA,
                    "status": "IDLE",
                    "live_order_allowed": False,
                    "promotion_allowed": False,
                }
            state.update(_bounded(changes))
            state["live_order_allowed"] = False
            state["promotion_allowed"] = False
            _atomic_write(self.state_path, state)
            return state

    def validate_engine_result(
        self,
        *,
        cycle_id: str,
        engine_id: str,
        result: dict[str, Any],
        snapshot_id: str,
        dataset_hash: str,
    ) -> dict[str, Any]:
        engine_key = str(engine_id).lower().strip()
        contract = _ENGINE_CONTRACTS.get(engine_key)
        errors: list[str] = []
        if contract is None:
            errors.append("unsupported_engine")
            contract = {"schema": "", "action": "", "domain": "unknown"}
        if not isinstance(result, dict):
            result = {}
            errors.append("result_must_be_object")

        actual_schema = str(result.get("schema") or "")
        actual_action = str(result.get("action") or "")
        if actual_schema != contract["schema"]:
            errors.append("schema_mismatch")
        if actual_action != contract["action"]:
            errors.append("action_mismatch")
        if result.get("live_order_allowed") is not False:
            errors.append("live_order_boundary_missing")
        if result.get("promotion_allowed") is not False:
            errors.append("automatic_promotion_boundary_missing")
        if result.get("score_allowed") is True:
            errors.append("direct_score_write_not_allowed")
        if "process_returncode" in result and _safe_int(result.get("process_returncode")) != 0:
            errors.append("external_process_failed")

        actual_snapshot_id = str(result.get("snapshot_id") or "")
        actual_dataset_hash = str(result.get("dataset_hash") or "")
        if snapshot_id and actual_snapshot_id != snapshot_id:
            errors.append("snapshot_id_mismatch")
        if dataset_hash and actual_dataset_hash != dataset_hash:
            errors.append("dataset_hash_mismatch")

        result_hash = str(result.get("result_hash") or "").lower()
        if not _HASH_PATTERN.fullmatch(result_hash):
            errors.append("invalid_result_hash")
        mutation_counts = _find_mutation_counts(result)
        if mutation_counts:
            errors.append("account_or_order_mutation_detected")

        quality_gate = result.get("quality_gate")
        if not isinstance(quality_gate, dict):
            quality_gate = {}
            errors.append("quality_gate_missing")
        quality_passed = quality_gate.get("passed") is True
        execution_ok = result.get("ok") is True
        contract_passed = not errors
        learning_eligible = contract_passed and execution_ok and quality_passed
        quality_blockers = _quality_blockers(quality_gate)
        if not quality_passed and not quality_blockers:
            quality_blockers.append("quality_gate_not_passed")

        evidence = {
            "schema": IMPROVEMENT_CONTRACT_SCHEMA,
            "recorded_at": _now_iso(),
            "cycle_id": str(cycle_id),
            "engine_id": engine_key,
            "domain": contract["domain"],
            "expected_schema": contract["schema"],
            "actual_schema": actual_schema,
            "expected_action": contract["action"],
            "actual_action": actual_action,
            "snapshot_id": actual_snapshot_id,
            "dataset_hash": actual_dataset_hash,
            "result_hash": result_hash,
            "execution_ok": execution_ok,
            "quality_gate_passed": quality_passed,
            "contract_passed": contract_passed,
            "learning_eligible": learning_eligible,
            "contract_errors": errors,
            "quality_blockers": quality_blockers,
            "mutation_counts": mutation_counts,
            "result_summary": self._result_summary(engine_key, result),
            "live_order_allowed": False,
            "promotion_allowed": False,
            "direct_score_write_allowed": False,
        }
        evidence["evidence_hash"] = _canonical_hash(evidence)
        with self._lock:
            self._append_jsonl(self.runs_path, evidence)
        return evidence

    def finalize_cycle(
        self,
        *,
        cycle_id: str,
        symbols: list[str],
        snapshot_id: str,
        dataset_hash: str,
        evidences: list[dict[str, Any]],
    ) -> dict[str, Any]:
        accepted = [row for row in evidences if row.get("learning_eligible") is True]
        strategy_support = [
            row for row in accepted if row.get("engine_id") in {"vectorbt", "qlib"}
        ]
        independent_engine_count = len({str(row.get("engine_id")) for row in accepted})
        strategy_corroborated = len(strategy_support) >= 2
        score_delta = min(2.0, 0.5 * independent_engine_count) if strategy_corroborated else 0.0
        normalized_symbols = sorted({str(item).upper().strip() for item in symbols if str(item).strip()})

        engine_lessons = [self._engine_lesson(row) for row in evidences]
        cycle_material = {
            "cycle_id": str(cycle_id),
            "snapshot_id": str(snapshot_id),
            "dataset_hash": str(dataset_hash),
            "evidence_hashes": sorted(str(row.get("evidence_hash") or "") for row in evidences),
        }
        cycle_hash = _canonical_hash(cycle_material)
        prior_hashes = {
            str(row.get("cycle_hash") or "") for row in _read_jsonl(self.lessons_path, limit=500)
        }
        duplicate = cycle_hash in prior_hashes
        verified_lesson = {
            "schema": VERIFIED_LESSON_SCHEMA,
            "created_at": _now_iso(),
            "cycle_id": str(cycle_id),
            "cycle_hash": cycle_hash,
            "snapshot_id": str(snapshot_id),
            "dataset_hash": str(dataset_hash),
            "symbols": normalized_symbols[:20],
            "engine_count": len(evidences),
            "contract_pass_count": sum(1 for row in evidences if row.get("contract_passed") is True),
            "quality_pass_count": len(accepted),
            "independent_engine_count": independent_engine_count,
            "strategy_corroborated": strategy_corroborated,
            "candidate_score_delta_cap": 2.0,
            "candidate_score_delta": score_delta,
            "candidate_score_delta_by_symbol": {
                symbol: score_delta for symbol in normalized_symbols[:20]
            } if score_delta else {},
            "engine_lessons": engine_lessons,
            "learning_memory_eligible": bool(accepted),
            "direct_order_authority": False,
            "automatic_promotion": False,
            "duplicate": duplicate,
            "safety": "Research evidence only. It cannot submit orders or promote strategies.",
        }
        verified_lesson["lesson_hash"] = _canonical_hash(verified_lesson)

        with self._lock:
            materialized_tasks = self._materialized_retraining_tasks()
            active_by_engine = {
                str(row.get("engine_id") or ""): row
                for row in materialized_tasks
                if row.get("status") in _ACTIVE_RETRAINING_STATUSES
            }
            exhausted_by_issue = {
                str(row.get("issue_signature") or ""): row
                for row in materialized_tasks
                if row.get("status") == "EXHAUSTED" and row.get("issue_signature")
            }
            retraining_tasks: list[dict[str, Any]] = []
            new_retraining_tasks: list[dict[str, Any]] = []
            suppressed_exhausted_tasks: list[dict[str, Any]] = []
            for evidence in evidences:
                if evidence.get("learning_eligible") is True:
                    continue
                engine_id = str(evidence.get("engine_id") or "")
                task = active_by_engine.get(engine_id)
                if task is None:
                    candidate = self._retraining_task(cycle_id, evidence)
                    task = exhausted_by_issue.get(str(candidate.get("issue_signature") or ""))
                    if task is None:
                        task = candidate
                        active_by_engine[engine_id] = task
                        new_retraining_tasks.append(task)
                    else:
                        suppressed_exhausted_tasks.append(task)
                retraining_tasks.append(task)
            if not duplicate:
                self._append_jsonl(self.lessons_path, verified_lesson)
            for task in new_retraining_tasks:
                self._append_jsonl(self.retraining_path, task)

        terminal_status = "COMPLETED" if all(row.get("execution_ok") for row in evidences) else "COMPLETED_WITH_BLOCKERS"
        final_state = self.update_cycle(
            status="FINALIZING",
            terminal_status=terminal_status,
            phase="persist_verified_lessons",
            phase_index=len(_ENGINE_CONTRACTS),
            progress_pct=98.0,
            finished_at="",
            engine_results=[
                {
                    "engine_id": row.get("engine_id"),
                    "execution_ok": row.get("execution_ok"),
                    "quality_gate_passed": row.get("quality_gate_passed"),
                    "contract_passed": row.get("contract_passed"),
                    "evidence_hash": row.get("evidence_hash"),
                    "blockers": list(row.get("contract_errors") or []) + list(row.get("quality_blockers") or []),
                }
                for row in evidences
            ],
            contract_pass_count=verified_lesson["contract_pass_count"],
            quality_pass_count=verified_lesson["quality_pass_count"],
            verified_lesson_count=0 if duplicate else 1,
            retraining_task_count=len(retraining_tasks),
            new_retraining_task_count=len(new_retraining_tasks),
            suppressed_exhausted_task_count=len(suppressed_exhausted_tasks),
            active_retraining_task_count=len(self.active_retraining_tasks(limit=100)),
            strategy_corroborated=strategy_corroborated,
            candidate_score_delta=score_delta,
            cycle_hash=cycle_hash,
        )
        return {
            "ok": bool(evidences) and all(row.get("contract_passed") for row in evidences),
            "status": terminal_status,
            "terminal_status": terminal_status,
            "state": final_state,
            "verified_lesson": verified_lesson,
            "retraining_tasks": retraining_tasks,
            "live_order_allowed": False,
            "promotion_allowed": False,
        }

    def fail_cycle(self, *, error: str, phase: str) -> dict[str, Any]:
        return self.update_cycle(
            status="FAILED",
            phase=str(phase),
            finished_at=_now_iso(),
            error=str(error)[:1000],
            live_order_allowed=False,
            promotion_allowed=False,
        )

    def active_retraining_tasks(self, *, limit: int = 10) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit or 10), 100))
        with self._lock:
            active = [
                row
                for row in self._materialized_retraining_tasks()
                if row.get("status") in _ACTIVE_RETRAINING_STATUSES
            ]
        return list(reversed(active))[:bounded_limit]

    def claim_retraining_tasks(
        self,
        *,
        cycle_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Claim one pending task per engine for this bounded research cycle."""

        normalized_cycle_id = str(cycle_id).strip()
        bounded_limit = max(1, min(int(limit or 5), len(_ENGINE_CONTRACTS)))
        now = datetime.now(timezone.utc)
        claimed: list[dict[str, Any]] = []
        with self._lock:
            tasks = self._materialized_retraining_tasks()
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in tasks:
                if row.get("status") not in _ACTIVE_RETRAINING_STATUSES:
                    continue
                engine_id = str(row.get("engine_id") or "")
                if engine_id in _ENGINE_CONTRACTS:
                    grouped.setdefault(engine_id, []).append(row)

            for engine_id in sorted(grouped):
                rows = grouped[engine_id]
                selected = rows[-1]
                for duplicate in rows[:-1]:
                    self._append_retraining_event(
                        duplicate,
                        status="SUPERSEDED",
                        event_type="SUPERSEDED_BY_NEWER_ENGINE_TASK",
                        superseded_by=selected.get("task_id"),
                        resolved_cycle_id=normalized_cycle_id,
                    )

                status = str(selected.get("status") or "")
                if status == "CLAIMED":
                    if str(selected.get("claimed_cycle_id") or "") == normalized_cycle_id:
                        claimed.append(selected)
                        continue
                    if not self._claim_is_stale(selected, now=now):
                        continue
                elif status not in _CLAIMABLE_RETRAINING_STATUSES:
                    continue

                attempt_count = _safe_int(selected.get("attempt_count"))
                max_attempts = max(1, _safe_int(selected.get("max_attempts")) or 3)
                if attempt_count >= max_attempts:
                    self._append_retraining_event(
                        selected,
                        status="EXHAUSTED",
                        event_type="ATTEMPT_LIMIT_REACHED_BEFORE_CLAIM",
                        resolved_cycle_id=normalized_cycle_id,
                    )
                    continue
                claimed_task = self._append_retraining_event(
                    selected,
                    status="CLAIMED",
                    event_type="CLAIMED_BY_IMPROVEMENT_CYCLE",
                    attempt_count=attempt_count + 1,
                    claimed_at=now.isoformat(timespec="seconds"),
                    claimed_cycle_id=normalized_cycle_id,
                    lease_expires_at=(now + _RETRAINING_CLAIM_LEASE).isoformat(timespec="seconds"),
                )
                claimed.append(claimed_task)
                if len(claimed) >= bounded_limit:
                    break

        active_count = len(self.active_retraining_tasks(limit=100))
        self.update_cycle(
            claimed_retraining_task_count=len(claimed),
            claimed_retraining_tasks=[self._task_summary(row) for row in claimed],
            active_retraining_task_count=active_count,
        )
        return claimed

    def resolve_retraining_tasks(
        self,
        *,
        cycle_id: str,
        claimed_tasks: list[dict[str, Any]],
        evidences: list[dict[str, Any]],
        failure_reason: str = "",
    ) -> dict[str, Any]:
        """Resolve claimed tasks from same-engine evidence or queue a bounded retry."""

        normalized_cycle_id = str(cycle_id).strip()
        evidence_by_engine = {
            str(row.get("engine_id") or ""): row
            for row in evidences
            if isinstance(row, dict) and row.get("engine_id")
        }
        resolved_rows: list[dict[str, Any]] = []
        retried_rows: list[dict[str, Any]] = []
        exhausted_rows: list[dict[str, Any]] = []
        with self._lock:
            latest_by_id = {
                str(row.get("task_id") or ""): row
                for row in self._materialized_retraining_tasks()
            }
            for originally_claimed in claimed_tasks:
                task_id = str(originally_claimed.get("task_id") or "")
                task = latest_by_id.get(task_id, originally_claimed)
                if task.get("status") != "CLAIMED":
                    continue
                if str(task.get("claimed_cycle_id") or "") != normalized_cycle_id:
                    continue
                engine_id = str(task.get("engine_id") or "")
                evidence = evidence_by_engine.get(engine_id)
                evidence_hash = evidence.get("evidence_hash") if isinstance(evidence, dict) else ""
                blockers = []
                if isinstance(evidence, dict):
                    blockers = list(evidence.get("contract_errors") or []) + list(
                        evidence.get("quality_blockers") or []
                    )
                elif failure_reason:
                    blockers = [str(failure_reason)[:500]]
                else:
                    blockers = ["same_engine_evidence_missing"]

                if isinstance(evidence, dict) and evidence.get("learning_eligible") is True:
                    updated = self._append_retraining_event(
                        task,
                        status="RESOLVED",
                        event_type="RESOLVED_BY_VERIFIED_ENGINE_EVIDENCE",
                        resolved_at=_now_iso(),
                        resolved_cycle_id=normalized_cycle_id,
                        resolution_evidence_hash=evidence_hash,
                        resolution_blockers=[],
                    )
                    resolved_rows.append(updated)
                    continue

                attempt_count = _safe_int(task.get("attempt_count"))
                max_attempts = max(1, _safe_int(task.get("max_attempts")) or 3)
                if attempt_count >= max_attempts:
                    updated = self._append_retraining_event(
                        task,
                        status="EXHAUSTED",
                        event_type="RETRAINING_ATTEMPTS_EXHAUSTED",
                        resolved_at=_now_iso(),
                        resolved_cycle_id=normalized_cycle_id,
                        resolution_evidence_hash=evidence_hash,
                        resolution_blockers=blockers,
                    )
                    exhausted_rows.append(updated)
                else:
                    updated = self._append_retraining_event(
                        task,
                        status="RETRY_QUEUED",
                        event_type="RETRY_QUEUED_AFTER_FAILED_RECHECK",
                        last_attempt_at=_now_iso(),
                        last_attempt_cycle_id=normalized_cycle_id,
                        latest_evidence_hash=evidence_hash,
                        resolution_blockers=blockers,
                    )
                    retried_rows.append(updated)

        active_count = len(self.active_retraining_tasks(limit=100))
        summary = {
            "cycle_id": normalized_cycle_id,
            "claimed_count": len(claimed_tasks),
            "resolved_count": len(resolved_rows),
            "retry_queued_count": len(retried_rows),
            "exhausted_count": len(exhausted_rows),
            "active_count": active_count,
            "resolved": [self._task_resolution_summary(row) for row in resolved_rows],
            "retry_queued": [self._task_resolution_summary(row) for row in retried_rows],
            "exhausted": [self._task_resolution_summary(row) for row in exhausted_rows],
            "live_order_allowed": False,
            "promotion_allowed": False,
        }
        self.update_cycle(
            retraining_resolution=summary,
            active_retraining_task_count=active_count,
        )
        return summary

    def status(self, *, lesson_limit: int = 5, task_limit: int = 10) -> dict[str, Any]:
        state = _read_json(self.state_path)
        if not state:
            state = {
                "schema": IMPROVEMENT_CYCLE_SCHEMA,
                "status": "IDLE",
                "progress_pct": 0.0,
                "live_order_allowed": False,
                "promotion_allowed": False,
            }
        materialized_tasks = self._materialized_retraining_tasks()
        active_tasks = [
            row for row in materialized_tasks if row.get("status") in _ACTIVE_RETRAINING_STATUSES
        ]
        recent_tasks = list(reversed(materialized_tasks))[:max(1, min(int(task_limit or 10), 100))]
        state["active_retraining_task_count"] = len(active_tasks)
        return {
            "ok": True,
            "state": state,
            "latest_verified_lessons": list(reversed(_read_jsonl(self.lessons_path, lesson_limit))),
            "latest_retraining_tasks": [self._task_summary(row) for row in recent_tasks],
            "active_retraining_tasks": [
                self._task_summary(row) for row in list(reversed(active_tasks))[:max(1, min(int(task_limit or 10), 100))]
            ],
            "paths": {
                "state": str(self.state_path),
                "runs": str(self.runs_path),
                "verified_lessons": str(self.lessons_path),
                "retraining_queue": str(self.retraining_path),
                "retraining_events": str(self.retraining_events_path),
            },
            "contract": {
                "schema": IMPROVEMENT_CONTRACT_SCHEMA,
                "engines": sorted(_ENGINE_CONTRACTS),
                "strategy_corroboration_minimum": 2,
                "candidate_score_delta_cap": 2.0,
                "direct_order_authority": False,
                "automatic_promotion": False,
            },
            "live_order_allowed": False,
            "promotion_allowed": False,
        }

    def learning_overlay(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").upper().strip()
        lessons = list(reversed(_read_jsonl(self.lessons_path, limit=100)))
        evidence: list[dict[str, Any]] = []
        score_delta = 0.0
        for row in lessons:
            if row.get("duplicate") is True or row.get("learning_memory_eligible") is not True:
                continue
            delta_by_symbol = row.get("candidate_score_delta_by_symbol")
            if not isinstance(delta_by_symbol, dict) or normalized not in delta_by_symbol:
                continue
            delta = max(-2.0, min(2.0, _safe_float(delta_by_symbol.get(normalized))))
            if not delta:
                continue
            score_delta = delta
            evidence.append(
                {
                    "lesson_hash": row.get("lesson_hash"),
                    "cycle_id": row.get("cycle_id"),
                    "quality_pass_count": row.get("quality_pass_count"),
                    "independent_engine_count": row.get("independent_engine_count"),
                    "score_delta": delta,
                }
            )
            break
        return {
            "symbol": normalized,
            "score_delta": score_delta,
            "evidence": evidence,
            "score_delta_cap": 2.0,
            "direct_order_authority": False,
        }

    def latest_learning_lessons(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = _read_jsonl(self.lessons_path, max(1, min(int(limit or 10), 100)))
        return list(reversed([row for row in rows if row.get("duplicate") is not True]))

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(",", ":"), default=str)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _materialized_retraining_tasks(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in _read_jsonl(self.retraining_path, limit=10000) + _read_jsonl(
            self.retraining_events_path,
            limit=20000,
        ):
            task_id = str(row.get("task_id") or "")
            if not task_id:
                continue
            if task_id not in latest:
                order.append(task_id)
                latest[task_id] = {}
            latest[task_id].update(_bounded(row))
        rows = [latest[task_id] for task_id in order]
        for row in rows:
            if not row.get("issue_signature"):
                row["issue_signature"] = self._task_issue_signature(row)
        return rows

    def _append_retraining_event(
        self,
        task: dict[str, Any],
        *,
        status: str,
        event_type: str,
        **changes: Any,
    ) -> dict[str, Any]:
        updated = {
            **task,
            **_bounded(changes),
            "schema": RETRAINING_TASK_SCHEMA,
            "event_schema": RETRAINING_EVENT_SCHEMA,
            "event_type": str(event_type),
            "status": str(status),
            "updated_at": _now_iso(),
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }
        self._append_jsonl(self.retraining_events_path, updated)
        return updated

    @staticmethod
    def _claim_is_stale(task: dict[str, Any], *, now: datetime) -> bool:
        value = str(task.get("lease_expires_at") or task.get("claimed_at") or "")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if task.get("lease_expires_at"):
            return parsed <= now
        return parsed + _RETRAINING_CLAIM_LEASE <= now

    @staticmethod
    def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
        status = str(task.get("status") or "")
        resolved = status in {"RESOLVED", "SUPERSEDED"}
        original_contract_errors = list(task.get("contract_errors") or [])
        original_quality_blockers = list(task.get("quality_blockers") or [])
        current_blockers = list(task.get("resolution_blockers") or [])
        return {
            "task_id": task.get("task_id"),
            "engine_id": task.get("engine_id"),
            "status": status,
            "requested_action": task.get("requested_action"),
            "attempt_count": _safe_int(task.get("attempt_count")),
            "max_attempts": max(1, _safe_int(task.get("max_attempts")) or 3),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "claimed_cycle_id": task.get("claimed_cycle_id"),
            "last_attempt_cycle_id": task.get("last_attempt_cycle_id"),
            "resolved_cycle_id": task.get("resolved_cycle_id"),
            "current_contract_errors": [] if resolved else original_contract_errors,
            "current_quality_blockers": current_blockers if resolved else original_quality_blockers,
            "original_contract_errors": original_contract_errors,
            "original_quality_blockers": original_quality_blockers,
            "resolution_blockers": current_blockers,
            "currently_healthy": bool(resolved and not current_blockers),
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    @staticmethod
    def _task_resolution_summary(task: dict[str, Any]) -> dict[str, Any]:
        status = str(task.get("status") or "")
        historical_blockers = list(task.get("contract_errors") or []) + list(
            task.get("quality_blockers") or []
        )
        blockers = list(task.get("resolution_blockers") or [])
        if status not in {"RESOLVED", "SUPERSEDED"} and not blockers:
            blockers = historical_blockers
        return {
            "task_id": task.get("task_id"),
            "engine_id": task.get("engine_id"),
            "status": status,
            "attempt_count": _safe_int(task.get("attempt_count")),
            "max_attempts": max(1, _safe_int(task.get("max_attempts")) or 3),
            "blocker_summary": ",".join(str(item) for item in blockers)[:1000],
            "historical_blocker_summary": ",".join(str(item) for item in historical_blockers)[:1000],
            "currently_healthy": bool(status in {"RESOLVED", "SUPERSEDED"} and not blockers),
            "resolved_cycle_id": task.get("resolved_cycle_id"),
            "last_attempt_cycle_id": task.get("last_attempt_cycle_id"),
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    def _result_summary(self, engine_id: str, result: dict[str, Any]) -> dict[str, Any]:
        common = {
            "engine_name": result.get("engine_name"),
            "action": result.get("action"),
            "research_verdict": result.get("research_verdict"),
            "decision": result.get("decision"),
            "runtime_elapsed_ms": result.get("runtime_elapsed_ms"),
            "execution_time_ms": result.get("execution_time_ms"),
            "quality_gate": _bounded(result.get("quality_gate") or {}),
            "capability_evidence": _bounded(result.get("capability_evidence") or []),
            "error": str(result.get("error") or "")[:1000],
        }
        if engine_id == "vectorbt":
            scenarios = result.get("scenarios") if isinstance(result.get("scenarios"), list) else []
            first_scenario = scenarios[0] if scenarios and isinstance(scenarios[0], dict) else {}
            common.update({
                "fast_window": result.get("fast_window") or first_scenario.get("fast_window"),
                "slow_window": result.get("slow_window") or first_scenario.get("slow_window"),
                "scenario_count": result.get("scenario_count"),
                "profitable_scenario_count": result.get("profitable_scenario_count"),
                "scenarios": _bounded(scenarios),
            })
        elif engine_id == "qlib":
            common.update({
                "selected_research_model": result.get("selected_research_model"),
                "model_count": result.get("model_count"),
                "fold_count": result.get("fold_count"),
                "models": _bounded(result.get("models") or []),
            })
        elif engine_id == "openbb":
            common.update({
                "fundamental_results": _bounded(result.get("fundamental_results") or []),
                "macro_results": _bounded(result.get("macro_results") or []),
                "corporate_action_history": _bounded(result.get("corporate_action_history") or {}),
                "economic_calendar_evidence": _bounded(result.get("economic_calendar_evidence") or {}),
            })
        elif engine_id == "lean":
            common.update({
                "point_in_time_universe_evidence": _bounded(result.get("point_in_time_universe_evidence") or {}),
                "exchange_calendar_evidence": _bounded(result.get("exchange_calendar_evidence") or {}),
                "corporate_action_evidence": _bounded(result.get("corporate_action_evidence") or {}),
                "delisting_evidence": _bounded(result.get("delisting_evidence") or {}),
                "brokerage_evidence": _bounded(result.get("brokerage_evidence") or {}),
            })
        elif engine_id == "nautilus":
            common.update({
                "orderbook_evidence": _bounded(result.get("orderbook_evidence") or {}),
                "scenarios": _bounded(result.get("scenarios") or []),
            })
        return common

    def _engine_lesson(self, evidence: dict[str, Any]) -> dict[str, Any]:
        engine_id = str(evidence.get("engine_id") or "")
        passed = evidence.get("learning_eligible") is True
        summary = evidence.get("result_summary") if isinstance(evidence.get("result_summary"), dict) else {}
        lesson: dict[str, Any] = {
            "engine_id": engine_id,
            "domain": evidence.get("domain"),
            "accepted": passed,
            "evidence_hash": evidence.get("evidence_hash"),
            "quality_blockers": evidence.get("quality_blockers") or [],
            "contract_errors": evidence.get("contract_errors") or [],
            "score_effect": "advisory_only",
        }
        if engine_id == "vectorbt":
            lesson["action"] = "retain_robust_parameters" if passed else "retune_cost_latency_robust_parameters"
            lesson["parameters"] = {
                "fast_window": summary.get("fast_window"),
                "slow_window": summary.get("slow_window"),
            }
        elif engine_id == "qlib":
            lesson["action"] = "queue_blind_holdout" if passed else "retrain_rolling_oos_models"
            lesson["selected_model"] = summary.get("selected_research_model")
        elif engine_id == "openbb":
            lesson["action"] = "retain_point_in_time_context" if passed else "repair_point_in_time_data_context"
        elif engine_id == "lean":
            lesson["action"] = "retain_lifecycle_rules" if passed else "repair_universe_calendar_or_brokerage_rules"
        elif engine_id == "nautilus":
            lesson["action"] = "retain_execution_stress_model" if passed else "tighten_fill_latency_and_unfilled_assumptions"
        return lesson

    def _retraining_task(self, cycle_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        requested_action = self._engine_lesson(evidence).get("action")
        task_material = {
            "cycle_id": str(cycle_id),
            "engine_id": evidence.get("engine_id"),
            "evidence_hash": evidence.get("evidence_hash"),
            "contract_errors": evidence.get("contract_errors") or [],
            "quality_blockers": evidence.get("quality_blockers") or [],
        }
        task_id = f"ext-retrain-{_canonical_hash(task_material)[:20]}"
        issue_signature = self._task_issue_signature(
            {
                **task_material,
                "requested_action": requested_action,
            }
        )
        return {
            "schema": RETRAINING_TASK_SCHEMA,
            "task_id": task_id,
            "created_at": _now_iso(),
            "status": "QUEUED",
            "attempt_count": 0,
            **task_material,
            "requested_action": requested_action,
            "issue_signature": issue_signature,
            "max_attempts": 3,
            "score_allowed": False,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    @staticmethod
    def _task_issue_signature(task: dict[str, Any]) -> str:
        material = {
            "engine_id": str(task.get("engine_id") or ""),
            "requested_action": str(task.get("requested_action") or ""),
            "contract_errors": sorted(str(item) for item in task.get("contract_errors") or []),
            "quality_blockers": sorted(str(item) for item in task.get("quality_blockers") or []),
        }
        return _canonical_hash(material)


__all__ = [
    "ExternalEngineImprovementStore",
    "IMPROVEMENT_CONTRACT_SCHEMA",
    "IMPROVEMENT_CYCLE_SCHEMA",
    "RETRAINING_TASK_SCHEMA",
    "RETRAINING_EVENT_SCHEMA",
    "VERIFIED_LESSON_SCHEMA",
]
