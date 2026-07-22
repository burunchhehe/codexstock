from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .execution import resolve_execution_model
from .models import ExperimentRecord, ExperimentStatus


_LOCK = threading.RLock()
CONFIRMATION = "I_CONFIRM_RESEARCH_ONLY_PAPER_CANDIDATE"


class ResearchLifecycle:
    """Human-confirmed research state machine with hash-chained decisions and handoff cards."""

    def __init__(self, root: Path) -> None:
        self.root = root; self.log_path = root / "decisions.jsonl"; self.cards_root = root / "cards"
        root.mkdir(parents=True, exist_ok=True); self.cards_root.mkdir(parents=True, exist_ok=True)

    def readiness(
        self,
        record: ExperimentRecord,
        report_verification: dict[str, Any],
        supplemental_checks: list[dict[str, Any]] | None = None,
        supplemental_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        strict = record.validation.get("strict_walk_forward") if isinstance(record.validation.get("strict_walk_forward"), dict) else {}
        robustness = record.validation.get("parameter_robustness") if isinstance(record.validation.get("parameter_robustness"), dict) else {}
        attribution = record.result.get("benchmark_attribution") if isinstance(record.result.get("benchmark_attribution"), dict) else {}
        regimes = record.result.get("regime_performance") if isinstance(record.result.get("regime_performance"), dict) else {}
        regime_rows = list((regimes.get("summary") or {}).values()) if isinstance(regimes.get("summary"), dict) else []
        max_drawdown = float(record.result.get("max_drawdown_pct") or 0)
        mode = resolve_execution_model(record.execution_model)["execution_mode"]
        try: declared_horizon = int(record.strategy.rules.get("label_horizon_rows") or 0); applied_purge_rows = int(strict.get("purge_rows") or 0); horizon_covered = 0 <= declared_horizon <= 10_000 and applied_purge_rows >= declared_horizon
        except (TypeError, ValueError): horizon_covered = False
        checks = [
            {"id": "validation_passed", "ok": bool(record.validation.get("passed"))},
            {"id": "strict_walk_forward_passed", "ok": bool((strict.get("summary") or {}).get("passed"))},
            {"id": "no_walk_forward_leakage", "ok": not bool((strict.get("summary") or {}).get("temporal_leakage_detected")) and strict.get("parameter_selection_uses_oos") is False},
            {"id": "label_horizon_purge_covered", "ok": horizon_covered},
            {"id": "parameter_robustness_passed", "ok": bool((robustness.get("summary") or {}).get("robust"))},
            {"id": "non_optimistic_execution", "ok": mode in {"REALISTIC", "CONSERVATIVE", "CUSTOM"}},
            {"id": "trades_observed", "ok": int(record.result.get("trade_count") or 0) > 0},
            {"id": "dataset_hash_recorded", "ok": str(record.result.get("dataset_hash") or "").startswith("sha256:")},
            {"id": "no_multitimeframe_future_violation", "ok": int((record.result.get("multi_timeframe") or {}).get("future_information_violations") or 0) == 0},
            {"id": "report_bundle_verified", "ok": bool(report_verification.get("ok"))},
            {"id": "benchmark_attribution_present", "ok": str(attribution.get("evidence_hash") or "").startswith("sha256:")},
            {"id": "positive_geometric_excess_return", "ok": float(attribution.get("geometric_excess_return_pct") or 0) > 0},
            {"id": "positive_information_ratio", "ok": attribution.get("information_ratio") is not None and float(attribution.get("information_ratio")) > 0},
            {"id": "maximum_drawdown_within_50pct", "ok": max_drawdown > -50},
            {"id": "no_catastrophic_regime_loss", "ok": bool(regime_rows) and min(float(row.get("strategy_compounded_return_pct") or 0) for row in regime_rows) > -80},
        ]
        checks.extend(
            {"id": str(row.get("id") or ""), "ok": row.get("ok") is True}
            for row in (supplemental_checks or [])
            if isinstance(row, dict) and str(row.get("id") or "")
        )
        blockers = [row["id"] for row in checks if not row["ok"]]
        return {
            "eligible_for_manual_paper_nomination": not blockers,
            "automatic_promotion": False,
            "execution_mode": mode,
            "checks": checks,
            "blockers": blockers,
            "report_verification": report_verification,
            "integrated_evidence": dict(supplemental_evidence or {}),
        }

    def review(
        self, record: ExperimentRecord, action: str, reviewer: str, rationale: str,
        report_verification: dict[str, Any], confirmation: str = "",
        supplemental_checks: list[dict[str, Any]] | None = None,
        supplemental_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = action.upper(); reviewer = reviewer.strip(); rationale = rationale.strip()
        if action not in {"NOMINATE_PAPER", "REJECT", "NEEDS_MORE_DATA", "ARCHIVE"}: raise ValueError("unsupported research review action")
        if not reviewer or len(reviewer) > 100 or not rationale or len(rationale) > 2000: raise ValueError("reviewer and rationale are required")
        before = record.status
        if before in {ExperimentStatus.BACKTESTING}: raise ValueError("cannot review an experiment while backtesting")
        readiness = self.readiness(
            record,
            report_verification,
            supplemental_checks=supplemental_checks,
            supplemental_evidence=supplemental_evidence,
        )
        if action == "NOMINATE_PAPER":
            if before != ExperimentStatus.VALIDATION: raise ValueError("only VALIDATION experiments can be nominated")
            if not readiness["eligible_for_manual_paper_nomination"]: raise ValueError("paper nomination blockers: " + ", ".join(readiness["blockers"]))
            if confirmation != CONFIRMATION: raise ValueError("manual research-only confirmation phrase is required")
            after = ExperimentStatus.PAPER_CANDIDATE
        elif action == "REJECT":
            if before in {ExperimentStatus.ARCHIVED, ExperimentStatus.REJECTED}: raise ValueError("terminal experiment cannot be rejected again")
            after = ExperimentStatus.REJECTED
        elif action == "NEEDS_MORE_DATA":
            if before not in {ExperimentStatus.VALIDATION, ExperimentStatus.FAILED}: raise ValueError("NEEDS_MORE_DATA requires VALIDATION or FAILED state")
            after = ExperimentStatus.DATA_CHECK
        else:
            if before == ExperimentStatus.ARCHIVED: raise ValueError("experiment is already archived")
            after = ExperimentStatus.ARCHIVED
        record.status = after; record.updated_at = datetime.now(timezone.utc).isoformat()
        decision = {"schema_version": 1, "decision_id": f"decision_{uuid4().hex}", "experiment_id": record.id, "action": action, "before_status": before.value, "after_status": after.value, "reviewer": reviewer, "rationale": rationale, "manual_confirmation": action == "NOMINATE_PAPER", "readiness": readiness, "live_order_allowed": False, "created_at": datetime.now(timezone.utc).isoformat()}
        return self._append(decision)

    def auto_nominate_verified_paper(
        self,
        record: ExperimentRecord,
        report_verification: dict[str, Any],
        *,
        scheduler_id: str,
        rationale: str,
        supplemental_checks: list[dict[str, Any]] | None = None,
        supplemental_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Nominate a fully verified experiment for Paper evidence without granting live authority."""
        scheduler_id = scheduler_id.strip()
        rationale = rationale.strip()
        if not scheduler_id or len(scheduler_id) > 100 or not rationale or len(rationale) > 2000:
            raise ValueError("scheduler_id and rationale are required")
        if record.status != ExperimentStatus.VALIDATION:
            raise ValueError("only VALIDATION experiments can be auto-nominated")
        readiness = self.readiness(
            record,
            report_verification,
            supplemental_checks=supplemental_checks,
            supplemental_evidence=supplemental_evidence,
        )
        if not readiness["eligible_for_manual_paper_nomination"]:
            raise ValueError("paper nomination blockers: " + ", ".join(readiness["blockers"]))

        before = record.status
        record.status = ExperimentStatus.PAPER_CANDIDATE
        record.updated_at = datetime.now(timezone.utc).isoformat()
        decision = {
            "schema_version": 1,
            "decision_id": f"decision_{uuid4().hex}",
            "experiment_id": record.id,
            "action": "AUTO_NOMINATE_VERIFIED_PAPER",
            "before_status": before.value,
            "after_status": record.status.value,
            "reviewer": scheduler_id,
            "rationale": rationale,
            "manual_confirmation": False,
            "nomination_mode": "automatic_verified_paper_only",
            "readiness": readiness,
            "paper_only": True,
            "automatic_live_promotion": False,
            "live_order_allowed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._append(decision)

    def create_card(self, record: ExperimentRecord, decision: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
        card = {"schema_version": 1, "card_id": f"research_card_{uuid4().hex}", "experiment_id": record.id, "strategy": {"name": record.strategy.name, "version": record.strategy.version, "rules": record.strategy.rules}, "status": record.status.value, "dataset": record.data_snapshot, "execution_model": record.execution_model, "performance": {**{key: record.result.get(key) for key in ("total_return_pct", "max_drawdown_pct", "trade_count", "final_equity")}, "benchmark_attribution": record.result.get("benchmark_attribution"), "regime_performance": record.result.get("regime_performance")}, "validation": record.validation, "decision": decision, "report": report, "meeting_instruction": "Independent CodexStock review required; this card never authorizes an order.", "research_only": True, "live_order_allowed": False, "created_at": datetime.now(timezone.utc).isoformat()}
        canonical = json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":")); card["card_hash"] = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        path = self.cards_root / f"{card['card_id']}.json"; self._atomic(path, card)
        return {key: value for key, value in card.items() if key not in {"validation"}}

    def history(self, experiment_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        rows = []
        if self.log_path.is_file():
            rows = [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        chain_ok, previous = True, "GENESIS"
        for row in rows:
            stored = row["decision_hash"]; candidate = dict(row); candidate.pop("decision_hash", None)
            expected = f"sha256:{hashlib.sha256(json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"
            chain_ok = chain_ok and row.get("previous_hash") == previous and stored == expected; previous = stored
        if experiment_id: rows = [row for row in rows if row["experiment_id"] == experiment_id]
        return {"ok": chain_ok, "chain_verified": chain_ok, "decision_count": len(rows), "decisions": rows[-max(1, min(500, int(limit))):]}

    def _append(self, decision: dict[str, Any]) -> dict[str, Any]:
        with _LOCK:
            previous = "GENESIS"
            if self.log_path.is_file():
                lines = [line for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if lines: previous = json.loads(lines[-1])["decision_hash"]
            decision["previous_hash"] = previous
            canonical = json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(",", ":")); decision["decision_hash"] = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
            with self.log_path.open("a", encoding="utf-8", newline="\n") as handle: handle.write(json.dumps(decision, ensure_ascii=False, sort_keys=True) + "\n")
        return decision

    @staticmethod
    def _atomic(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp"); temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(path)
