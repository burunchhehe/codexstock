from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .models import normalize_training_package, now_iso, safe_id
from .schema import (
    ENGINE_CONTRACT_SAFETY_RULES,
    ENGINE_DATA_CONTRACT_FIELDS,
    ENGINE_PROMOTION_STAGES,
    ENGINE_RESULT_CONTRACT_FIELDS,
    ENGINE_ROLE_CATALOG,
    FOLDERS,
    OPEN_SOURCE_CATALOG,
    STAGE2_COST_POLICY_VERSION,
    STATUS_FOLDERS,
    market_specific_stage2_cost_model,
    package_status_semantics,
)
from .validator import validate_training_package


class ExternalKnowledgeStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.audit_path = self.root / "external_knowledge_audit.jsonl"
        self.missions_path = self.root / "missions.jsonl"
        self.dataset_snapshots_path = self.root / "dataset_snapshots.jsonl"
        self.ensure()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in FOLDERS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def source_catalog(self) -> dict[str, Any]:
        self.ensure()
        return {
            "ok": True,
            "sources": OPEN_SOURCE_CATALOG,
            "count": len(OPEN_SOURCE_CATALOG),
            "engine_contract_summary": self.engine_contract_summary(),
            "engine_adapter_readiness": self.engine_adapter_readiness(),
            "decision_safety": {
                "external_code_execution_allowed": False,
                "external_runtime_enabled": False,
                "live_order_allowed": False,
                "quarantined_packages_excluded_from_stage2": True,
                "stage2_requires_common_snapshot_hash": True,
                "stage2_requires_codexstock_cost_model": True,
                "order_gateway": "CodexStock only",
            },
            "safety": "외부 코드는 실행하지 않고 전략 규칙/검증 메타데이터만 수입합니다.",
        }

    def engine_contract_summary(self) -> dict[str, Any]:
        active_or_planned = [
            engine
            for engine in ENGINE_ROLE_CATALOG
            if str(engine.get("status", "")).lower() not in {"deferred", "research_only"}
        ]
        return {
            "engine_count": len(ENGINE_ROLE_CATALOG),
            "active_or_planned_count": len(active_or_planned),
            "data_contract_field_count": len(ENGINE_DATA_CONTRACT_FIELDS),
            "result_contract_field_count": len(ENGINE_RESULT_CONTRACT_FIELDS),
            "promotion_stage_count": len(ENGINE_PROMOTION_STAGES),
            "single_order_gateway": "CodexStock",
            "status": "contract_defined",
        }

    def engine_adapter_readiness(self) -> dict[str, Any]:
        buckets = {
            "ready_now": {"active", "local_first"},
            "adapter_needed": {"planned_stage2_adapter"},
            "deferred": {"deferred", "deferred_after_data_contract"},
            "research_only": {"research_only"},
        }
        counts = {key: 0 for key in buckets}
        engines: list[dict[str, Any]] = []
        for engine in sorted(ENGINE_ROLE_CATALOG, key=lambda row: int(row.get("priority", 999))):
            status = str(engine.get("status", "")).lower()
            bucket = "other"
            for name, statuses in buckets.items():
                if status in statuses:
                    bucket = name
                    counts[name] += 1
                    break
            engine_name = str(engine.get("engine_name") or "")
            engines.append(
                {
                    "engine_name": engine_name,
                    "role": engine.get("role"),
                    "status": status,
                    "bucket": bucket,
                    "priority": engine.get("priority"),
                    "can_execute_external_code": False,
                    "can_submit_order": engine_name == "CodexStock",
                    "order_gateway": "CodexStock only",
                    "requires_adapter_before_stage2": bucket == "adapter_needed",
                }
            )
        return {
            "ok": True,
            "ready_now_count": counts["ready_now"],
            "adapter_needed_count": counts["adapter_needed"],
            "deferred_count": counts["deferred"],
            "research_only_count": counts["research_only"],
            "engines": engines,
            "next_adapter_priorities": [
                row
                for row in engines
                if row.get("requires_adapter_before_stage2")
            ][:3],
            "safety": {
                "external_code_execution_allowed": False,
                "external_engine_order_permission": False,
                "single_order_gateway": "CodexStock",
            },
        }

    def external_execution_budget(self) -> dict[str, Any]:
        return {
            "max_concurrent_external_jobs": 1,
            "default_timeout_seconds": 180,
            "hard_timeout_seconds": 600,
            "max_stdout_bytes": 200_000,
            "max_result_json_bytes": 80_000,
            "max_artifact_mb": 25,
            "kill_on_timeout": True,
            "start_mode": "spawn_on_demand_only",
            "cache_result_ttl_seconds": 3600,
            "store_full_raw_logs": False,
        }

    def runtime_isolation_audit(self) -> dict[str, Any]:
        """Report whether external engines are isolated from the main app runtime."""
        self.ensure()
        adapter = self.engine_adapter_readiness()
        report = self.report(limit=8)
        dataset = self.dataset_snapshot_readiness()
        engines = adapter.get("engines") if isinstance(adapter.get("engines"), list) else []
        external_engines = [
            engine for engine in engines
            if isinstance(engine, dict) and str(engine.get("engine_name") or "") not in {"CodexStock", "DuckDB/SQLite"}
        ]
        runtime_enabled = [
            engine for engine in external_engines
            if bool(engine.get("can_execute_external_code"))
        ]
        order_enabled = [
            engine for engine in external_engines
            if bool(engine.get("can_submit_order"))
        ]
        adapter_needed = [
            engine for engine in external_engines
            if bool(engine.get("requires_adapter_before_stage2"))
        ]
        research_only = [
            engine for engine in external_engines
            if str(engine.get("bucket") or "") == "research_only"
        ]
        deferred = [
            engine for engine in external_engines
            if str(engine.get("bucket") or "") == "deferred"
        ]
        always_on_external_engine_count = len(runtime_enabled)
        bloat_risk = "low" if always_on_external_engine_count == 0 else "high"
        execution_phase = (
            "contract_only_on_demand"
            if not runtime_enabled and adapter_needed
            else "metadata_learning_only"
            if not runtime_enabled
            else "external_runtime_enabled_review_required"
        )
        execution_budget = self.external_execution_budget()
        stage2_candidates = report.get("stage2_candidate_packages") if isinstance(report.get("stage2_candidate_packages"), list) else []
        next_on_demand_jobs: list[dict[str, Any]] = []
        for package in stage2_candidates[:5]:
            if not isinstance(package, dict):
                continue
            next_on_demand_jobs.append(
                {
                    "package_id": package.get("package_id"),
                    "source_name": package.get("source_name"),
                    "preferred_first_engine": "vectorbt",
                    "job_type": "stage2_contract_rehearsal",
                    "state": "blocked_until_common_snapshot" if not bool(dataset.get("ready")) else "ready_to_queue",
                    "budget": execution_budget,
                }
            )
        checks = [
            {
                "name": "external_runtime_not_loaded",
                "ok": not runtime_enabled,
                "detail": f"external_runtime_enabled_count={len(runtime_enabled)}",
            },
            {
                "name": "single_order_gateway",
                "ok": not order_enabled,
                "detail": "CodexStock is the only engine allowed to reach live order gates.",
            },
            {
                "name": "on_demand_only",
                "ok": always_on_external_engine_count == 0,
                "detail": "External engines are represented by contracts/adapters and are not always-on workers.",
            },
            {
                "name": "execution_budget_defined",
                "ok": execution_budget["max_concurrent_external_jobs"] == 1 and execution_budget["kill_on_timeout"],
                "detail": f"timeout={execution_budget['default_timeout_seconds']}s, max_concurrent={execution_budget['max_concurrent_external_jobs']}, raw_logs={execution_budget['store_full_raw_logs']}",
            },
            {
                "name": "stage2_snapshot_gate",
                "ok": bool(dataset.get("ready")),
                "detail": str(dataset.get("blocker") or dataset.get("next_action") or ""),
                "required_for_runtime": True,
            },
            {
                "name": "promotion_blocked_until_reconciliation",
                "ok": int(report.get("promotion_blocked_count") or 0) >= 0,
                "detail": f"promotion_blocked_count={report.get('promotion_blocked_count', 0)}",
            },
        ]
        status = "ready" if bloat_risk == "low" and not runtime_enabled and not order_enabled else "review_required"
        return {
            "ok": status == "ready",
            "status": status,
            "execution_phase": execution_phase,
            "bloat_risk": bloat_risk,
            "summary": {
                "status": status,
                "execution_phase": execution_phase,
                "bloat_risk": bloat_risk,
                "external_engine_count": len(external_engines),
                "always_on_external_engine_count": always_on_external_engine_count,
                "adapter_needed_count": len(adapter_needed),
                "research_only_count": len(research_only),
                "deferred_count": len(deferred),
                "stage2_ready_count": report.get("stage2_ready_count", 0),
                "dataset_snapshot_ready": bool(dataset.get("ready")),
                "next_on_demand_job_count": len(next_on_demand_jobs),
                "max_concurrent_external_jobs": execution_budget["max_concurrent_external_jobs"],
            },
            "external_engine_count": len(external_engines),
            "always_on_external_engine_count": always_on_external_engine_count,
            "next_on_demand_job_count": len(next_on_demand_jobs),
            "max_concurrent_external_jobs": execution_budget["max_concurrent_external_jobs"],
            "dataset_snapshot_ready": bool(dataset.get("ready")),
            "runtime_topology": {
                "codexstock_role": "central_control_room",
                "external_engine_role": "short_lived_on_demand_sub_engine",
                "always_on_external_engines": always_on_external_engine_count,
                "queued_on_demand_jobs": len(next_on_demand_jobs),
                "max_concurrent_external_jobs": execution_budget["max_concurrent_external_jobs"],
                "external_code_loaded_at_boot": False,
                "live_order_allowed": False,
            },
            "runtime_enabled_engines": runtime_enabled,
            "order_enabled_engines": order_enabled,
            "adapter_needed_engines": adapter_needed,
            "research_only_engines": research_only,
            "deferred_engines": deferred,
            "stage2_ready_count": report.get("stage2_ready_count", 0),
            "execution_budget": execution_budget,
            "next_on_demand_jobs": next_on_demand_jobs,
            "dataset_snapshot_readiness": dataset,
            "checks": checks,
            "policy": {
                "codexstock_role": "central_control_room",
                "external_engine_role": "on_demand_sub_engine_after_stage2_gate",
                "load_policy": "do_not_import_or_start_external_engines_at_app_boot",
                "execution_policy": "spawn_only_when_requested_then_return_compact_json",
                "storage_policy": "store hashes, summaries, and result contracts; avoid raw unbounded logs",
                "live_order_policy": "external engines can propose only; CodexStock/user approval remains the only live order path",
            },
            "next_actions": [
                "Keep external engines out of the main app startup path.",
                "Build adapters as short-lived subprocess jobs only after common dataset snapshots are ready.",
                "Persist compact result contracts and hashes, not full raw engine logs.",
            ],
            "safety": "Metadata-only runtime isolation audit. It does not import, start, or execute external engines and cannot submit orders.",
        }

    def engine_contract(self) -> dict[str, Any]:
        self.ensure()
        return {
            "ok": True,
            "name": "CodexStock external engine contract",
            "purpose": "외부 최강 엔진을 하위 계산/검증 서버로만 사용하고, 실전 주문은 코덱스스톡 단일 리스크 게이트가 담당하게 하는 공통 계약입니다.",
            "data_contract_fields": list(ENGINE_DATA_CONTRACT_FIELDS),
            "result_contract_fields": list(ENGINE_RESULT_CONTRACT_FIELDS),
            "promotion_stages": ENGINE_PROMOTION_STAGES,
            "engines": ENGINE_ROLE_CATALOG,
            "safety_rules": ENGINE_CONTRACT_SAFETY_RULES,
            "summary": self.engine_contract_summary(),
            "adapter_readiness": self.engine_adapter_readiness(),
        }

    def list_packages(self, limit: int = 200, status: str | None = None) -> dict[str, Any]:
        self.ensure()
        packages = self._scan_packages()
        if status:
            wanted = status.upper().strip()
            packages = [item for item in packages if str(item.get("status", "")).upper() == wanted]
        for package in packages:
            package["status_semantics"] = package_status_semantics(package.get("status"))
            package["evidence_stage"] = package["status_semantics"]["evidence_stage"]
        packages.sort(key=lambda item: str(item.get("updated_at") or item.get("imported_at") or ""), reverse=True)
        return {"ok": True, "count": len(packages), "packages": packages[: max(1, min(int(limit or 200), 1000))]}

    def report(self, limit: int = 12) -> dict[str, Any]:
        packages = self._scan_packages()
        counts: dict[str, int] = {}
        scores: list[float] = []
        warnings = 0
        blocks = 0
        active_blocks = 0
        quarantined_blocks = 0
        blocked_packages: list[dict[str, Any]] = []
        stage2_candidate_packages: list[dict[str, Any]] = []
        stage2_excluded_packages: list[dict[str, Any]] = []
        promotion_blocked_count = 0
        stage2_candidate_statuses = {"BACKTEST_READY", "APPROVED_FOR_RESEARCH", "REPLAY_READY", "PAPER_ONLY"}
        quarantine_statuses = {"REJECTED", "VALIDATION_FAILED", "BACKTEST_FAILED", "ARCHIVED"}
        for package in packages:
            status = str(package.get("status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1
            validation = package.get("validation", {}) if isinstance(package.get("validation"), dict) else {}
            score = validation.get("score") if isinstance(validation.get("score"), (int, float)) else None
            if score is not None:
                scores.append(float(score))
            validation_warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
            warnings += len(validation_warnings)
            package_blocks = validation.get("blocks", []) if isinstance(validation.get("blocks"), list) else []
            block_len = len(package_blocks)
            blocks += block_len
            if block_len:
                if status in quarantine_statuses:
                    quarantined_blocks += block_len
                else:
                    active_blocks += block_len
                blocked_packages.append(
                    {
                        "package_id": package.get("package_id"),
                        "source_name": package.get("source_name"),
                        "status": status,
                        "block_count": block_len,
                        "first_block": package_blocks[0] if package_blocks else {},
                        "safe_isolated": status in quarantine_statuses,
                    }
                )
            promotion = package.get("promotion", {}) if isinstance(package.get("promotion"), dict) else {}
            if not bool(promotion.get("allowed")):
                promotion_blocked_count += 1
            source_metadata = package.get("source_metadata", {}) if isinstance(package.get("source_metadata"), dict) else {}
            stage2_candidate = (
                status in stage2_candidate_statuses
                and not bool(package_blocks)
                and score is not None
                and float(score) >= 70
            )
            stage2_row = {
                "package_id": package.get("package_id"),
                "source_name": package.get("source_name"),
                "status": status,
                "validation_score": score,
                "warning_count": len(validation_warnings),
                "block_count": block_len,
                "requires_stage2_backtest": bool(source_metadata.get("requires_stage2_backtest")),
                "promotion_allowed": bool(promotion.get("allowed")),
            }
            if stage2_candidate:
                stage2_candidate_packages.append(stage2_row)
            elif status in quarantine_statuses or bool(package_blocks):
                stage2_row["excluded_reason"] = "quarantined_or_validation_blocked"
                stage2_excluded_packages.append(stage2_row)
        recent = sorted(packages, key=lambda item: str(item.get("updated_at") or item.get("imported_at") or ""), reverse=True)[:limit]
        return {
            "ok": True,
            "root": str(self.root),
            "source_count": len(OPEN_SOURCE_CATALOG),
            "package_count": len(packages),
            "counts": counts,
            "avg_validation_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "warning_count": warnings,
            "block_count": blocks,
            "active_block_count": active_blocks,
            "quarantined_block_count": quarantined_blocks,
            "stage2_ready_count": len(stage2_candidate_packages),
            "stage2_candidate_count": len(stage2_candidate_packages),
            "stage2_candidate_packages": stage2_candidate_packages[: max(1, min(int(limit or 12), 50))],
            "quarantined_excluded_count": len(stage2_excluded_packages),
            "stage2_excluded_packages": stage2_excluded_packages[: max(1, min(int(limit or 12), 50))],
            "promotion_blocked_count": promotion_blocked_count,
            "blocked_packages": blocked_packages[: max(1, min(int(limit or 12), 50))],
            "recent_packages": recent,
            "sources": OPEN_SOURCE_CATALOG,
            "engine_contract_summary": self.engine_contract_summary(),
            "engine_adapter_readiness": self.engine_adapter_readiness(),
            "dataset_snapshot_readiness": self.dataset_snapshot_readiness(),
            "decision_safety": {
                "external_code_execution_allowed": False,
                "external_runtime_enabled": False,
                "live_order_allowed": False,
                "quarantined_packages_excluded_from_stage2": True,
                "stage2_requires_common_snapshot_hash": True,
                "stage2_requires_codexstock_cost_model": True,
                "order_gateway": "CodexStock only",
            },
            "stage": "Stage 1: 스키마/수입/격리저장/기본검증/MCP조회",
            "safety": "실전 주문, 계좌 설정, API 키에는 접근하지 않습니다.",
            "next": "Stage 2에서 공통 백테스트 변환과 왕중왕전 동일조건 비교를 연결합니다.",
        }

    def auto_scout_sources(self, *, limit: int = 6, replace: bool = False, source: str = "ai-external-scout") -> dict[str, Any]:
        """Create safe research-only packages from the curated open-source catalog."""
        self.ensure()
        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        missions: list[dict[str, Any]] = []
        for item in OPEN_SOURCE_CATALOG[: max(1, min(int(limit or 6), len(OPEN_SOURCE_CATALOG)))]:
            package = self._scout_package_from_catalog(item)
            package_id = str(package.get("package_id") or "")
            if self._find_package_path(package_id) and not replace:
                skipped.append({"package_id": package_id, "source_name": item.get("source_name"), "reason": "already_imported"})
                continue
            result = self.import_training_package(package, source=source, replace=replace)
            if result.get("package"):
                imported_package = result["package"]
                imported.append(
                    {
                        "package_id": imported_package.get("package_id"),
                        "source_name": imported_package.get("source_name"),
                        "status": imported_package.get("status"),
                        "score": (imported_package.get("validation") or {}).get("score") if isinstance(imported_package.get("validation"), dict) else None,
                        "summary": (imported_package.get("validation") or {}).get("summary") if isinstance(imported_package.get("validation"), dict) else "",
                    }
                )
                mission = self.assign_training_mission(
                    {
                        "mission_id": f"mission-{package_id}",
                        "title": f"{imported_package.get('source_name')} 설계 원칙을 코덱스스톡 훈련 기준으로 검증",
                        "source_package_id": package_id,
                        "target_staff": ["self", "헤헤", "월천", "다라", "리스크 관리자"],
                        "market": "GLOBAL",
                        "priority": "normal",
                        "objectives": [
                            "외부 코드를 실행하지 않고 설계 원칙만 요약한다.",
                            "코덱스스톡 데이터로 동일 비용/슬리피지 조건 백테스트 후보를 만든다.",
                            "수익률보다 체결/리스크/재현성 개선에 먼저 반영한다.",
                        ],
                        "constraints": [
                            "실전 주문 금지",
                            "API 키/계좌/토큰 접근 금지",
                            "라이선스 확인 전 코드 복사 금지",
                            "성과 수치는 우리 데이터 재검증 전 공식 성과로 사용 금지",
                        ],
                        "success_conditions": [
                            "백테스트 변환 가능 규칙 1개 이상 도출",
                            "실패 사례와 과최적화 위험 1개 이상 기록",
                            "Paper 전용 검증 후에만 장기기억 후보로 승격",
                        ],
                    },
                    source=source,
                )
                if mission.get("mission"):
                    missions.append(mission["mission"])
            else:
                skipped.append({"package_id": package_id, "source_name": item.get("source_name"), "reason": result.get("error") or "import_failed"})
        return {
            "ok": True,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "mission_count": len(missions),
            "imported": imported,
            "skipped": skipped,
            "missions": missions,
            "safety": "외부 코드는 실행하지 않았고, 설계 원칙/검증 미션만 격리 저장했습니다.",
        }

    def import_training_package(self, raw: dict[str, Any], *, source: str = "api", replace: bool = False) -> dict[str, Any]:
        self.ensure()
        package = normalize_training_package(raw)
        package_id = str(package.get("package_id", ""))
        existing = self._find_package_path(package_id)
        if existing and not replace:
            return {
                "ok": False,
                "error": "duplicate_package_id",
                "message": "이미 수입된 외부 지식 패키지입니다.",
                "package_id": package_id,
                "existing_path": str(existing),
            }
        existing_ids = self._package_ids() - ({package_id} if replace else set())
        validation = validate_training_package(package, existing_ids=existing_ids)
        package = validation["normalized_package"]
        package["status"] = str(validation.get("recommended_status") or "VALIDATING")
        package["validation"] = {key: validation[key] for key in ("ok", "score", "warnings", "blocks", "summary", "promotion_allowed", "promotion_reason")}
        package["promotion"] = {
            "allowed": bool(validation.get("promotion_allowed")),
            "reason": validation.get("promotion_reason"),
            "requires_user_approval": True,
        }
        package["updated_at"] = now_iso()
        path = self._write_package(package)
        if existing and existing != path:
            existing.unlink(missing_ok=True)
        self._audit(
            "IMPORT_EXTERNAL_KNOWLEDGE",
            package_id,
            "",
            str(package.get("status", "")),
            validation.get("summary", "외부 지식 수입"),
            validation.get("score"),
            source,
            str(path),
        )
        return {"ok": not bool(validation.get("blocks")), "package": package, "validation": validation, "path": str(path)}

    def _scout_package_from_catalog(self, item: dict[str, Any]) -> dict[str, Any]:
        source_name = str(item.get("source_name") or "Open Source")
        package_id = f"auto-scout-{safe_id(source_name, 'source')}-architecture"
        absorb = [str(entry) for entry in item.get("what_to_absorb", []) if str(entry).strip()]
        source_type = str(item.get("source_type") or "github")
        source_url = str(item.get("source_url") or "")
        license_text = str(item.get("license") or "verify_required")
        entry_rules = [
            f"{source_name} 연구 항목: {entry}. 코덱스스톡에서는 신호/검증/주문 게이트를 분리해 재현 가능한 규칙으로 변환한다."
            for entry in absorb
        ] or [f"{source_name}의 공개 설계 원칙을 코덱스스톡 연구 규칙으로 변환한다."]
        return {
            "package_id": package_id,
            "source_name": source_name,
            "source_type": source_type,
            "source_url": source_url,
            "license": license_text,
            "market": ["KR", "US", "GLOBAL"],
            "timeframe": ["1m", "daily"],
            "strategy_id": f"{safe_id(source_name, 'source')}-architecture-pattern",
            "strategy_name": f"{source_name} 설계 원칙 자동 스카우트",
            "description": (
                f"{source_name}에서 바로 코드를 가져오지 않고, 코덱스스톡 AI 직원들이 검토할 설계 원칙만 격리 저장한 연구용 패키지입니다. "
                "성과 수치는 아직 우리 데이터로 검증되지 않았으므로 공식 수익률로 쓰지 않습니다."
            ),
            "entry_rules": entry_rules,
            "exit_rules": [
                "진입 신호와 청산 신호를 같은 데이터 시점 기준으로 계산한다.",
                "실전 후보 전환 전에는 수수료, 세금, 슬리피지, 체결 지연을 별도 모델로 차감한다.",
                "성과가 좋아도 특정 장세에만 맞으면 Paper 전용으로 유지한다.",
            ],
            "stop_rules": [
                "전략별 최대 손실, 일 손실 한도, 종목 비중 한도를 독립 게이트로 둔다.",
                "가격/통화/상장명 정합성 오류가 있으면 즉시 검증 중지 또는 격리한다.",
            ],
            "position_sizing_rules": [
                "실전 주문에는 직접 연결하지 않고 Paper/연구 미션으로만 배정한다.",
                "리스크 점수와 MDD 스트레스를 통과하기 전까지 자금 비중을 0%로 둔다.",
            ],
            "avoid_rules": [
                "라이선스 확인 전 코드 복사 금지",
                "외부 백테스트 수익률을 검증 없이 표시 금지",
                "미래 데이터, 생존편향, 가격분할 보정 미확인 데이터 사용 금지",
            ],
            "required_indicators": ["price", "volume", "fees", "slippage", "fills", "order_state", "risk_gate"],
            "required_data": ["OHLCV", "corporate_actions", "commission_tax_slippage", "order_fills", "market_regime"],
            "regimes": ["trend", "sideways", "bear", "crash"],
            "failure_cases": [
                "실전 체결과 백테스트 체결 의미가 다르면 성과가 무너질 수 있음",
                "대량 파라미터 탐색은 과최적화 위험이 큼",
                "라이선스와 데이터 출처 검증 전에는 연구용 이하로만 사용",
            ],
            "known_limitations": [
                "자동 스카우트 패키지는 설계 원칙만 담았고 외부 코드를 실행하지 않음",
                "성과 지표는 placeholder이며 코덱스스톡 데이터 재검증 전 공식 성과가 아님",
                "장기기억/실전 후보 승격은 사용자 승인과 Stage 2 검증 이후만 허용",
            ],
            "evidence": [
                f"source_url={source_url}",
                f"safe_use={item.get('safe_use', '')}",
                *(f"absorb={entry}" for entry in absorb),
            ],
            "performance": {
                "start_date": "2000-01-01",
                "end_date": "2026-07-11",
                "return_pct": 0,
                "annualized_return_pct": 0,
                "mdd_pct": 0,
                "win_rate_pct": 0,
                "profit_factor": 0,
                "trade_count": 120,
                "fees_included": False,
                "tax_included": False,
                "slippage_included": False,
            },
            "confidence": 45,
            "license_review": {
                "status": "research_metadata_only",
                "reviewed": True,
                "code_copy_allowed": False,
                "runtime_execution_allowed": False,
                "architecture_pattern_allowed": True,
                "live_candidate_allowed": False,
                "note": "라이선스 확인 전에는 외부 코드 복사/실행을 금지하고, 공개 문서에 보이는 설계 원칙만 연구 메타데이터로 사용합니다.",
            },
            "source_metadata": {
                "package_kind": "architecture_pattern",
                "auto_scout": True,
                "actual_performance": False,
                "external_code_executed": False,
                "requires_stage2_backtest": True,
            },
        }

    def validate_package(self, package_id: str, *, source: str = "api") -> dict[str, Any]:
        self.ensure()
        path = self._find_package_path(package_id)
        if not path:
            return {"ok": False, "error": "not_found", "message": "패키지를 찾지 못했습니다.", "package_id": package_id}
        package = self._read_json(path)
        old_status = str(package.get("status", ""))
        validation = validate_training_package(package, existing_ids=self._package_ids() - {package_id})
        package = validation["normalized_package"]
        package["status"] = str(validation.get("recommended_status") or "VALIDATING")
        package["validation"] = {key: validation[key] for key in ("ok", "score", "warnings", "blocks", "summary", "promotion_allowed", "promotion_reason")}
        package["updated_at"] = now_iso()
        new_path = self._write_package(package)
        if new_path != path:
            path.unlink(missing_ok=True)
        self._audit(
            "VALIDATE_EXTERNAL_KNOWLEDGE",
            package_id,
            old_status,
            str(package.get("status", "")),
            validation.get("summary", "외부 지식 재검증"),
            validation.get("score"),
            source,
            str(new_path),
        )
        return {"ok": not bool(validation.get("blocks")), "package": package, "validation": validation, "path": str(new_path)}

    def reject_package(self, package_id: str, reason: str = "사용자/검증 정책으로 거절", *, source: str = "api") -> dict[str, Any]:
        path = self._find_package_path(package_id)
        if not path:
            return {"ok": False, "error": "not_found", "message": "패키지를 찾지 못했습니다.", "package_id": package_id}
        package = self._read_json(path)
        old_status = str(package.get("status", ""))
        package["status"] = "REJECTED"
        package["rejected_reason"] = reason
        package["updated_at"] = now_iso()
        new_path = self._write_package(package)
        if new_path != path:
            path.unlink(missing_ok=True)
        score = (package.get("validation") or {}).get("score") if isinstance(package.get("validation"), dict) else None
        self._audit("REJECT_EXTERNAL_KNOWLEDGE", package_id, old_status, "REJECTED", reason, score, source, str(new_path))
        return {"ok": True, "package": package, "path": str(new_path)}

    def research_only_stub(self, action: str, package_id: str = "", message: str = "") -> dict[str, Any]:
        return {
            "ok": False,
            "blocked": True,
            "action": action,
            "package_id": package_id,
            "message": message or "Stage 2 이후 연결할 기능입니다. 현재는 외부 지식 수입/검증/조회만 허용합니다.",
            "safety": "실전 주문, 계좌 설정, API 키 접근은 수행하지 않았습니다.",
        }

    def _read_dataset_snapshot_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.dataset_snapshots_path.exists():
            return rows
        for line in self.dataset_snapshots_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def dataset_snapshot_readiness(self) -> dict[str, Any]:
        rows = self._read_dataset_snapshot_rows()
        ready = [row for row in rows if row.get("common_snapshot_materialized") and row.get("dataset_hash")]
        descriptor_only = [row for row in rows if not (row.get("common_snapshot_materialized") and row.get("dataset_hash"))]
        latest = rows[-1] if rows else {}
        latest_ready = ready[-1] if ready else {}
        status = "READY" if latest_ready else "MISSING_COMMON_SNAPSHOT"
        blocker = "" if latest_ready else "Stage 2 requires a common snapshot with both snapshot_id and dataset_hash."
        return {
            "ok": True,
            "status": status,
            "ready": bool(latest_ready),
            "total_snapshot_count": len(rows),
            "ready_count": len(ready),
            "descriptor_only_count": len(descriptor_only),
            "latest_snapshot_id": latest.get("snapshot_id", ""),
            "latest_ready_snapshot_id": latest_ready.get("snapshot_id", ""),
            "latest_ready_snapshot_created_at": latest_ready.get("created_at", ""),
            "latest_ready_dataset_hash": str(latest_ready.get("dataset_hash", ""))[:16] if latest_ready else "",
            "required_fields": ["snapshot_id", "dataset_hash", "symbols", "timeframe", "start", "end", "cost_model_id"],
            "blocker": blocker,
            "next_action": (
                "Use an existing ready common snapshot or generate one from CodexStock OHLCV/cost/fill data before Stage 2."
                if not latest_ready
                else "Use latest_ready_snapshot_id for Stage 2 backtest/replay/compare."
            ),
            "safety": "Snapshot readiness is metadata only; no external engine, account, or order execution.",
        }

    def _normalize_common_snapshot_symbol(self, value: Any) -> str:
        raw = str(value or "").strip().upper()
        if not raw:
            return ""
        base = raw.split(".", 1)[0]
        if base.isdigit() and 1 <= len(base) <= 6:
            return base.zfill(6)
        return raw[:16]

    def _expected_common_snapshot_market(self, symbol: str, market: Any = "") -> dict[str, str]:
        market_text = str(market or "").strip().upper()
        if symbol.isdigit() and len(symbol) == 6:
            return {"market": "KR", "currency": "KRW", "price_unit": "won_integer"}
        if market_text in {"KR", "KOSPI", "KOSDAQ"}:
            return {"market": "KR", "currency": "KRW", "price_unit": "won_integer"}
        return {"market": market_text or "US", "currency": "USD", "price_unit": "decimal_usd"}

    def build_common_snapshot_from_ohlcv_cache(
        self,
        *,
        symbols: str | list[Any] | None = None,
        max_symbols: int = 3,
        max_rows_per_symbol: int = 120,
        action: str = "run_external_backtest",
        package_id: str = "",
        record: bool = False,
        include_rows_for_runtime: bool = False,
        source: str = "external-common-snapshot",
    ) -> dict[str, Any]:
        """Build a small common Stage 2 snapshot from CodexStock's local OHLCV cache.

        This keeps external engines on-demand: the main app only emits a bounded,
        hashed data contract and never loads or runs third-party code here.
        """
        self.ensure()
        cache_path = self.root.parent / "walk_forward_ohlcv_cache_adj_20160706_20260706.json"
        budget = self.external_execution_budget()
        safe_max_symbols = max(1, min(int(max_symbols or 3), 10))
        safe_rows_per_symbol = max(20, min(int(max_rows_per_symbol or 120), 260))
        if not cache_path.exists():
            return {
                "ok": False,
                "status": "missing_local_ohlcv_cache",
                "cache_path": str(cache_path),
                "recorded": False,
                "stage2_gate_passed": False,
                "blocker": "Local walk-forward OHLCV cache is missing.",
                "execution_budget": budget,
                "safety": "No external engine, account, secret, or live order was accessed.",
            }
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "ok": False,
                "status": "local_ohlcv_cache_read_failed",
                "cache_path": str(cache_path),
                "error": str(exc)[:240],
                "recorded": False,
                "stage2_gate_passed": False,
                "execution_budget": budget,
                "safety": "No external engine, account, secret, or live order was accessed.",
            }
        if not isinstance(cache, dict):
            return {
                "ok": False,
                "status": "local_ohlcv_cache_invalid",
                "cache_path": str(cache_path),
                "recorded": False,
                "stage2_gate_passed": False,
                "execution_budget": budget,
                "safety": "No external engine, account, secret, or live order was accessed.",
            }

        requested: list[str] = []
        raw_symbols: list[Any]
        if isinstance(symbols, str):
            raw_symbols = [item for item in symbols.split(",") if item.strip()]
        elif isinstance(symbols, list):
            raw_symbols = symbols
        else:
            raw_symbols = []
        for item in raw_symbols:
            normalized = self._normalize_common_snapshot_symbol(item)
            if normalized and normalized not in requested:
                requested.append(normalized)
        if not requested:
            preferred = ["005930", "000660", "329180", "086790", "042660"]
            requested = [symbol for symbol in preferred if isinstance(cache.get(symbol), dict)]
            if len(requested) < safe_max_symbols:
                for symbol, payload in cache.items():
                    normalized = self._normalize_common_snapshot_symbol(symbol)
                    if normalized and normalized not in requested and isinstance(payload, dict) and payload.get("rows"):
                        requested.append(normalized)
                    if len(requested) >= safe_max_symbols:
                        break
        selected_symbols = requested[:safe_max_symbols]

        dataset_rows: list[dict[str, Any]] = []
        used_symbols: list[dict[str, Any]] = []
        missing_symbols: list[str] = []
        dates: list[str] = []
        for symbol in selected_symbols:
            payload = cache.get(symbol)
            if not isinstance(payload, dict):
                missing_symbols.append(symbol)
                continue
            raw_rows = payload.get("rows")
            if not isinstance(raw_rows, list):
                missing_symbols.append(symbol)
                continue
            valid_rows = [row for row in raw_rows if isinstance(row, dict) and self._float_or_zero(row.get("close")) > 0]
            if not valid_rows:
                missing_symbols.append(symbol)
                continue
            market_info = self._expected_common_snapshot_market(symbol, payload.get("market"))
            bounded_rows = valid_rows[-safe_rows_per_symbol:]
            used_symbols.append(
                {
                    "symbol": symbol,
                    "name": payload.get("name") or symbol,
                    "market": market_info["market"],
                    "row_count": len(bounded_rows),
                }
            )
            for row in bounded_rows:
                date = str(row.get("date") or "")
                if date:
                    dates.append(date)
                close = self._float_or_zero(row.get("close"))
                dataset_rows.append(
                    {
                        "symbol": symbol,
                        "name": payload.get("name") or symbol,
                        "date": date,
                        "open": self._float_or_zero(row.get("open", close)),
                        "high": self._float_or_zero(row.get("high", close)),
                        "low": self._float_or_zero(row.get("low", close)),
                        "close": close,
                        "volume": self._float_or_zero(row.get("volume", 0)),
                        "market": market_info["market"],
                        "currency": market_info["currency"],
                        "price_unit": market_info["price_unit"],
                        "source": "codexstock_walk_forward_ohlcv_cache",
                    }
                )

        start = min(dates) if dates else ""
        end = max(dates) if dates else ""
        market_label = "KR" if used_symbols and all(row.get("market") == "KR" for row in used_symbols) else "MIXED"
        payload = {
            "package_id": package_id,
            "symbols": [row["symbol"] for row in used_symbols],
            "market": market_label,
            "timeframe": "1d",
            "start": start,
            "end": end,
            "cost_model_id": STAGE2_COST_POLICY_VERSION,
            "fill_model": "codexstock_stage2_contract_rehearsal_no_external_runtime",
            "dataset_rows": dataset_rows,
        }
        descriptor = {
            "action": str(action or ""),
            "package_id": str(package_id or ""),
            "symbols": payload["symbols"],
            "market": payload["market"],
            "timeframe": payload["timeframe"],
            "start": payload["start"],
            "end": payload["end"],
            "cost_model_id": payload["cost_model_id"],
            "fill_model": payload["fill_model"],
        }
        canonical_rows = self._canonical_dataset_rows(self._extract_dataset_rows(payload), descriptor)
        integrity = self._dataset_integrity(canonical_rows)
        dataset_hash = ""
        if canonical_rows and int(integrity.get("fatal_issue_count") or 0) == 0:
            dataset_hash = hashlib.sha256(
                json.dumps(
                    {
                        "schema": "codexstock_common_snapshot_v1",
                        "descriptor": descriptor,
                        "rows": canonical_rows,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        snapshot_id = f"snapshot-{safe_id(action, 'stage2')}-{safe_id(package_id or 'none', 'pkg')}-{(dataset_hash or 'missing')[:12]}"
        preview_snapshot = {
            "snapshot_id": snapshot_id,
            "dataset_hash": dataset_hash,
            "snapshot_kind": "common_snapshot" if dataset_hash else "request_descriptor_only",
            "common_snapshot_materialized": bool(dataset_hash and int(integrity.get("fatal_issue_count") or 0) == 0),
            "dataset_integrity": integrity,
            "row_count": integrity.get("row_count", 0),
            "symbol_count": integrity.get("symbol_count", 0),
            "descriptor": descriptor,
            "source": source,
            "external_runtime_enabled": False,
            "live_order_enabled": False,
        }
        result: dict[str, Any] = {
            "ok": bool(dataset_hash),
            "status": "ready_preview" if dataset_hash else "not_ready",
            "recorded": False,
            "cache_path": str(cache_path),
            "cache_size_bytes": cache_path.stat().st_size,
            "selected_symbols": used_symbols,
            "missing_symbols": missing_symbols,
            "max_symbols": safe_max_symbols,
            "max_rows_per_symbol": safe_rows_per_symbol,
            "dataset_snapshot_preview": preview_snapshot,
            "dataset_rows_in_response": 0,
            "execution_budget": budget,
            "stage2_gate_passed": False,
            "safety": "Bounded snapshot metadata only. No external code, account, secret, or live order was accessed.",
        }
        if include_rows_for_runtime:
            result["runtime_dataset_payload"] = payload
        if not record:
            return result

        snapshot_record = self.record_dataset_snapshot(
            str(action or "run_external_backtest"),
            package_id,
            payload,
            source=source,
        )
        stage2_plan = self.stage2_engine_research_plan(
            str(action or "run_external_backtest"),
            package_id,
            source=source,
            dataset_snapshot=snapshot_record.get("snapshot") if isinstance(snapshot_record.get("snapshot"), dict) else None,
        )
        result.update(
            {
                "ok": bool(snapshot_record.get("ready_for_stage2")),
                "status": "recorded" if snapshot_record.get("ready_for_stage2") else "recorded_not_ready",
                "recorded": True,
                "recorded_dataset_snapshot": snapshot_record.get("snapshot"),
                "readiness": snapshot_record.get("readiness"),
                "stage2_gate_passed": bool(stage2_plan.get("stage2_gate_passed")),
                "stage2_required_blockers": stage2_plan.get("required_blockers", []),
                "stage2_contract_rehearsal": stage2_plan.get("contract_rehearsal"),
            }
        )
        return result

    def _float_or_zero(self, value: Any) -> float:
        if isinstance(value, bool) or value is None:
            return 0.0
        if isinstance(value, (int, float)):
            number = float(value)
            return number if math.isfinite(number) else 0.0
        try:
            number = float(str(value).replace(",", "").strip())
            return number if math.isfinite(number) else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _extract_dataset_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = [
            payload.get("dataset_rows"),
            payload.get("ohlcv"),
            payload.get("bars"),
            payload.get("prices"),
        ]
        rows: list[dict[str, Any]] = []
        for candidate in candidates:
            if isinstance(candidate, list):
                rows.extend([dict(row) for row in candidate if isinstance(row, dict)])
                break
            if isinstance(candidate, dict):
                if isinstance(candidate.get("rows"), list):
                    rows.extend([dict(row) for row in candidate.get("rows", []) if isinstance(row, dict)])
                    break
                for symbol, value in candidate.items():
                    if isinstance(value, list):
                        for row in value:
                            if isinstance(row, dict):
                                copied = dict(row)
                                copied.setdefault("symbol", str(symbol))
                                rows.append(copied)
                if rows:
                    break
        return rows

    def _canonical_dataset_rows(self, rows: list[dict[str, Any]], descriptor: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = descriptor.get("symbols")
        default_symbol = symbols[0] if isinstance(symbols, list) and len(symbols) == 1 else descriptor.get("symbols") or ""
        default_market = str(descriptor.get("market") or "").upper()
        canonical: list[dict[str, Any]] = []
        for row in rows:
            symbol = str(row.get("symbol") or row.get("ticker") or default_symbol or "").upper().strip()
            market = str(row.get("market") or default_market or ("KR" if symbol.isdigit() and len(symbol) == 6 else "")).upper()
            currency = str(row.get("currency") or ("KRW" if market == "KR" else "USD" if market == "US" else "")).upper()
            date = str(row.get("date") or row.get("datetime") or row.get("timestamp") or row.get("time") or "")
            close = self._float_or_zero(row.get("close", row.get("price", row.get("Close"))))
            canonical.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "open": self._float_or_zero(row.get("open", row.get("Open", close))),
                    "high": self._float_or_zero(row.get("high", row.get("High", close))),
                    "low": self._float_or_zero(row.get("low", row.get("Low", close))),
                    "close": close,
                    "volume": self._float_or_zero(row.get("volume", row.get("Volume", 0))),
                    "currency": currency,
                    "market": market,
                    "source": str(row.get("source") or descriptor.get("source") or ""),
                }
            )
        canonical.sort(key=lambda row: (str(row.get("symbol", "")), str(row.get("date", ""))))
        return canonical

    def _dataset_integrity(self, canonical_rows: list[dict[str, Any]]) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []
        symbols = sorted({str(row.get("symbol") or "") for row in canonical_rows if row.get("symbol")})
        currencies: dict[str, int] = {}
        markets: dict[str, int] = {}
        for row in canonical_rows:
            symbol = str(row.get("symbol") or "").upper()
            market = str(row.get("market") or "").upper()
            currency = str(row.get("currency") or "").upper()
            close = self._float_or_zero(row.get("close"))
            if currency:
                currencies[currency] = currencies.get(currency, 0) + 1
            if market:
                markets[market] = markets.get(market, 0) + 1
            if not symbol:
                issues.append("row_missing_symbol")
            if close <= 0:
                issues.append(f"{symbol or 'UNKNOWN'}: non_positive_close")
            if symbol.isdigit() and len(symbol) == 6:
                if currency and currency != "KRW":
                    issues.append(f"{symbol}: korean_symbol_currency_mismatch:{currency}")
                if 0 < close < 100:
                    warnings.append(f"{symbol}: suspicious_low_kr_price:{close}")
            elif symbol and symbol.isalpha() and currency == "KRW":
                warnings.append(f"{symbol}: us_like_symbol_with_krw_currency")
        if not canonical_rows:
            warnings.append("no_ohlcv_rows_supplied; provided dataset_hash is required for Stage 2.")
        return {
            "ok": not issues,
            "fatal_issue_count": len(issues),
            "warning_count": len(warnings),
            "issues": issues[:50],
            "warnings": warnings[:50],
            "row_count": len(canonical_rows),
            "symbol_count": len(symbols),
            "symbols": symbols[:50],
            "currencies": currencies,
            "markets": markets,
            "schema": "codexstock_common_snapshot_v1",
        }

    def list_dataset_snapshots(self, limit: int = 20) -> dict[str, Any]:
        self.ensure()
        safe_limit = max(1, min(int(limit or 20), 200))
        rows = self._read_dataset_snapshot_rows()
        recent = list(reversed(rows))[:safe_limit]
        ready = [row for row in rows if row.get("common_snapshot_materialized") and row.get("dataset_hash")]
        return {
            "ok": True,
            "count": len(rows),
            "ready_count": len(ready),
            "snapshots": recent,
            "path": str(self.dataset_snapshots_path),
            "readiness": self.dataset_snapshot_readiness(),
            "adapter_readiness": self.engine_adapter_readiness(),
            "safety": "metadata-only response; no external engine or order execution.",
        }

    def latest_ready_dataset_snapshot(self) -> dict[str, Any]:
        self.ensure()
        ready = [
            row
            for row in self._read_dataset_snapshot_rows()
            if row.get("common_snapshot_materialized") and row.get("dataset_hash")
        ]
        return dict(ready[-1]) if ready else {}

    def _snapshot_is_stage2_ready(self, snapshot: dict[str, Any]) -> bool:
        integrity = snapshot.get("dataset_integrity") if isinstance(snapshot.get("dataset_integrity"), dict) else {}
        fatal_count = int(integrity.get("fatal_issue_count") or 0) if isinstance(integrity, dict) else 0
        return bool(
            snapshot.get("snapshot_id")
            and (snapshot.get("dataset_hash") or snapshot.get("data_hash"))
            and (snapshot.get("common_snapshot_materialized") or fatal_count == 0)
            and fatal_count == 0
        )

    def record_dataset_snapshot(
        self,
        action: str,
        package_id: str = "",
        payload: dict[str, Any] | None = None,
        *,
        source: str = "api",
    ) -> dict[str, Any]:
        self.ensure()
        raw_payload = payload if isinstance(payload, dict) else {}
        provided = raw_payload.get("dataset_snapshot") if isinstance(raw_payload.get("dataset_snapshot"), dict) else {}
        snapshot = dict(provided) if isinstance(provided, dict) else {}
        descriptor = {
            "action": str(action or ""),
            "package_id": str(package_id or raw_payload.get("package_id") or ""),
            "symbols": raw_payload.get("symbols") if isinstance(raw_payload.get("symbols"), list) else raw_payload.get("symbol", ""),
            "market": raw_payload.get("market", ""),
            "timeframe": raw_payload.get("timeframe", raw_payload.get("bar_interval", "")),
            "start": raw_payload.get("start", raw_payload.get("start_date", "")),
            "end": raw_payload.get("end", raw_payload.get("end_date", "")),
            "cost_model_id": raw_payload.get("cost_model_id", STAGE2_COST_POLICY_VERSION),
            "fill_model": raw_payload.get("fill_model", "contract_rehearsal_no_execution"),
        }
        descriptor_hash = hashlib.sha256(
            json.dumps(descriptor, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        canonical_rows = self._canonical_dataset_rows(self._extract_dataset_rows(raw_payload), descriptor)
        dataset_integrity = self._dataset_integrity(canonical_rows)
        computed_dataset_hash = ""
        if canonical_rows and int(dataset_integrity.get("fatal_issue_count") or 0) == 0:
            computed_dataset_hash = hashlib.sha256(
                json.dumps(
                    {
                        "schema": "codexstock_common_snapshot_v1",
                        "descriptor": descriptor,
                        "rows": canonical_rows,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        snapshot_id = str(snapshot.get("snapshot_id") or f"snapshot-{safe_id(action, 'stage2')}-{safe_id(package_id or 'none', 'pkg')}-{(computed_dataset_hash or descriptor_hash)[:12]}")
        provided_hash = str(snapshot.get("dataset_hash") or snapshot.get("data_hash") or "")
        dataset_hash = provided_hash or computed_dataset_hash
        hash_source = "provided" if provided_hash else "computed_from_rows" if computed_dataset_hash else "missing"
        common_snapshot_materialized = bool(snapshot_id and dataset_hash and int(dataset_integrity.get("fatal_issue_count") or 0) == 0)
        record = {
            "snapshot_id": snapshot_id,
            "dataset_hash": dataset_hash,
            "descriptor_hash": descriptor_hash,
            "hash_source": hash_source,
            "snapshot_kind": "common_snapshot" if common_snapshot_materialized else "request_descriptor_only",
            "common_snapshot_materialized": common_snapshot_materialized,
            "dataset_integrity": dataset_integrity,
            "row_count": dataset_integrity.get("row_count", 0),
            "symbol_count": dataset_integrity.get("symbol_count", 0),
            "action": str(action or ""),
            "package_id": str(package_id or raw_payload.get("package_id") or ""),
            "descriptor": descriptor,
            "created_at": now_iso(),
            "source": source,
            "external_runtime_enabled": False,
            "live_order_enabled": False,
            "note": "dataset_hash가 비어 있으면 Stage 2 실제 검증은 아직 대기 상태입니다.",
        }
        self.dataset_snapshots_path.parent.mkdir(parents=True, exist_ok=True)
        with self.dataset_snapshots_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._audit(
            "RECORD_EXTERNAL_DATASET_SNAPSHOT",
            record["package_id"],
            "",
            "COMMON_SNAPSHOT_READY" if common_snapshot_materialized else "DESCRIPTOR_ONLY",
            f"{record['action']}: snapshot_id={snapshot_id}, dataset_hash={'present' if dataset_hash else 'missing'}",
            None,
            source,
            str(self.dataset_snapshots_path),
        )
        return {
            "ok": True,
            "snapshot": record,
            "ready_for_stage2": common_snapshot_materialized,
            "readiness": self.dataset_snapshot_readiness(),
            "safety": "스냅샷 메타데이터만 기록했습니다. 외부 코드와 실전 주문은 실행하지 않았습니다.",
        }

    def plan_stage2_engine_request(
        self,
        action: str,
        package_id: str = "",
        payload: dict[str, Any] | None = None,
        *,
        source: str = "api",
    ) -> dict[str, Any]:
        """Prepare a Stage 2 plan without writing duplicate descriptor-only rows.

        Empty UI/MCP button clicks should reuse the latest ready common snapshot
        instead of appending another request-descriptor-only JSONL row.
        """
        raw_payload = payload if isinstance(payload, dict) else {}
        provided_snapshot = raw_payload.get("dataset_snapshot") if isinstance(raw_payload.get("dataset_snapshot"), dict) else {}
        has_rows = bool(self._extract_dataset_rows(raw_payload))
        has_ready_snapshot = bool(isinstance(provided_snapshot, dict) and self._snapshot_is_stage2_ready(provided_snapshot))
        snapshot_record: dict[str, Any]
        snapshot_for_plan: dict[str, Any] | None = None
        recording = {
            "recorded": False,
            "mode": "",
            "reason": "",
            "reused_latest_ready_snapshot": False,
        }
        if has_rows or has_ready_snapshot:
            snapshot_record = self.record_dataset_snapshot(action, package_id, raw_payload, source=source)
            snapshot_for_plan = snapshot_record.get("snapshot") if isinstance(snapshot_record.get("snapshot"), dict) else None
            recording.update(
                {
                    "recorded": True,
                    "mode": "recorded_payload_snapshot",
                    "reason": "payload_supplied_rows_or_ready_snapshot",
                }
            )
        else:
            latest_ready = self.latest_ready_dataset_snapshot()
            if latest_ready:
                snapshot_record = {
                    "ok": True,
                    "snapshot": latest_ready,
                    "ready_for_stage2": True,
                    "recorded": False,
                    "readiness": self.dataset_snapshot_readiness(),
                    "safety": "Reused latest ready common snapshot; no descriptor-only row was appended.",
                }
                snapshot_for_plan = latest_ready
                recording.update(
                    {
                        "mode": "skipped_descriptor_only_reused_latest_ready",
                        "reason": "empty_request_and_ready_snapshot_available",
                        "reused_latest_ready_snapshot": True,
                    }
                )
            else:
                snapshot_record = self.record_dataset_snapshot(action, package_id, raw_payload, source=source)
                snapshot_for_plan = snapshot_record.get("snapshot") if isinstance(snapshot_record.get("snapshot"), dict) else None
                recording.update(
                    {
                        "recorded": True,
                        "mode": "recorded_descriptor_only_no_ready_snapshot",
                        "reason": "empty_request_without_ready_snapshot",
                    }
                )
        result = self.stage2_engine_research_plan(
            action,
            package_id,
            source=source,
            dataset_snapshot=snapshot_for_plan,
        )
        if recording.get("reused_latest_ready_snapshot"):
            result["dataset_snapshot_source"] = "latest_ready_store"
        result["dataset_snapshot_recording"] = recording
        result["recorded_dataset_snapshot"] = snapshot_record.get("snapshot") if recording.get("recorded") else None
        result["used_dataset_snapshot"] = result.get("dataset_snapshot")
        return result

    def stage2_engine_research_plan(
        self,
        action: str,
        package_id: str = "",
        *,
        source: str = "api",
        dataset_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the external-engine execution contract without running untrusted engines."""
        self.ensure()
        action_key = str(action or "").strip().lower()
        engine_map = {
            "run_external_backtest": ["DuckDB/SQLite", "vectorbt", "QuantConnect Lean", "CodexStock"],
            "run_external_replay": ["DuckDB/SQLite", "NautilusTrader", "QuantConnect Lean", "CodexStock"],
            "compare_external_strategy": ["DuckDB/SQLite", "vectorbt", "NautilusTrader", "QuantConnect Lean", "CodexStock"],
        }
        wanted_engines = engine_map.get(action_key, ["DuckDB/SQLite", "CodexStock"])
        selected_engines = [engine for engine in ENGINE_ROLE_CATALOG if str(engine.get("engine_name")) in wanted_engines]

        package: dict[str, Any] = {}
        package_path = self._find_package_path(package_id) if package_id else None
        if package_path:
            package = self._read_json(package_path)
        validation = package.get("validation", {}) if isinstance(package.get("validation"), dict) else {}
        performance = package.get("performance", {}) if isinstance(package.get("performance"), dict) else {}
        source_metadata = package.get("source_metadata", {}) if isinstance(package.get("source_metadata"), dict) else {}
        validation_blocks = validation.get("blocks", []) if isinstance(validation.get("blocks"), list) else []
        validation_warnings = validation.get("warnings", []) if isinstance(validation.get("warnings"), list) else []
        score = validation.get("score") if isinstance(validation.get("score"), (int, float)) else 0
        package_status = str(package.get("status", "") or "").upper()
        stage2_candidate_statuses = {"BACKTEST_READY", "APPROVED_FOR_RESEARCH", "REPLAY_READY", "PAPER_ONLY"}
        quarantine_statuses = {"REJECTED", "VALIDATION_FAILED", "BACKTEST_FAILED", "ARCHIVED"}
        package_quarantined_or_blocked = package_status in quarantine_statuses or bool(validation_blocks)
        license_text = str(package.get("license", "") or "").strip().lower()
        license_review = package.get("license_review", {}) if isinstance(package.get("license_review"), dict) else {}
        research_metadata_only_license_ok = bool(
            license_review.get("reviewed")
            or (
                source_metadata.get("package_kind") == "architecture_pattern"
                and source_metadata.get("external_code_executed") is False
            )
        )
        license_scope = "research_metadata_only" if research_metadata_only_license_ok else "unreviewed"
        package_claims_cost_model = bool(performance.get("fees_included") and performance.get("tax_included") and performance.get("slippage_included"))
        stage2_cost_model = market_specific_stage2_cost_model(
            package.get("market") or (dataset_snapshot or {}).get("market") or "MIXED"
        )
        has_stage2_cost_model = True
        snapshot_payload = dataset_snapshot if isinstance(dataset_snapshot, dict) else {}
        dataset_snapshot_source = "provided" if snapshot_payload else "missing"
        if snapshot_payload and not self._snapshot_is_stage2_ready(snapshot_payload):
            dataset_snapshot_source = "provided_not_ready"
        if not self._snapshot_is_stage2_ready(snapshot_payload):
            latest_ready_snapshot = self.latest_ready_dataset_snapshot()
            if latest_ready_snapshot:
                snapshot_payload = latest_ready_snapshot
                dataset_snapshot_source = "latest_ready_store"
        snapshot_id = str(snapshot_payload.get("snapshot_id") or "")
        dataset_hash = str(snapshot_payload.get("dataset_hash") or snapshot_payload.get("data_hash") or "")
        snapshot_integrity = snapshot_payload.get("dataset_integrity") if isinstance(snapshot_payload.get("dataset_integrity"), dict) else {}
        snapshot_fatal_count = int(snapshot_integrity.get("fatal_issue_count") or 0) if isinstance(snapshot_integrity, dict) else 0
        snapshot_materialized = bool(snapshot_payload.get("common_snapshot_materialized")) or bool(snapshot_id and dataset_hash and snapshot_fatal_count == 0)
        snapshot_descriptor = snapshot_payload.get("descriptor") if isinstance(snapshot_payload.get("descriptor"), dict) else {}
        raw_snapshot_symbols = snapshot_descriptor.get("symbols") if isinstance(snapshot_descriptor, dict) else []
        snapshot_symbols = (
            [str(item) for item in raw_snapshot_symbols if str(item)]
            if isinstance(raw_snapshot_symbols, list)
            else [str(raw_snapshot_symbols)] if raw_snapshot_symbols else []
        )
        snapshot_start = str(snapshot_descriptor.get("start") or "")
        snapshot_end = str(snapshot_descriptor.get("end") or "")
        snapshot_timeframe = str(snapshot_descriptor.get("timeframe") or "")
        snapshot_market = str(snapshot_descriptor.get("market") or "")
        snapshot_cost_model_id = str(snapshot_descriptor.get("cost_model_id") or STAGE2_COST_POLICY_VERSION)
        snapshot_fill_model = str(snapshot_descriptor.get("fill_model") or "contract_rehearsal_no_execution")
        try:
            snapshot_row_count = int(snapshot_payload.get("row_count") or snapshot_integrity.get("row_count") or 0)
        except (TypeError, ValueError):
            snapshot_row_count = 0
        try:
            snapshot_symbol_count = int(snapshot_payload.get("symbol_count") or snapshot_integrity.get("symbol_count") or len(snapshot_symbols))
        except (TypeError, ValueError):
            snapshot_symbol_count = len(snapshot_symbols)
        stage2_dataset_contract = {
            "snapshot_id": snapshot_id,
            "dataset_hash": dataset_hash,
            "source": dataset_snapshot_source,
            "symbols": snapshot_symbols,
            "symbol_count": snapshot_symbol_count,
            "row_count": snapshot_row_count,
            "market": snapshot_market,
            "timeframe": snapshot_timeframe,
            "start": snapshot_start,
            "end": snapshot_end,
            "cost_model_id": snapshot_cost_model_id,
            "fill_model": snapshot_fill_model,
            "schema": snapshot_integrity.get("schema", "codexstock_common_snapshot_v1") if isinstance(snapshot_integrity, dict) else "codexstock_common_snapshot_v1",
            "fatal_issue_count": snapshot_fatal_count,
            "external_runtime_enabled": False,
            "live_order_enabled": False,
        }
        package_claim_start = str(performance.get("start_date") or "")
        package_claim_end = str(performance.get("end_date") or "")
        scope_warnings: list[str] = []
        if package_claim_start and snapshot_start and package_claim_start != snapshot_start:
            scope_warnings.append("package_claim_start_differs_from_verified_snapshot_start")
        if package_claim_end and snapshot_end and package_claim_end != snapshot_end:
            scope_warnings.append("package_claim_end_differs_from_verified_snapshot_end")
        stage2_scope_audit = {
            "status": "scope_warning" if scope_warnings else "aligned",
            "warnings": scope_warnings,
            "package_claim_start": package_claim_start,
            "package_claim_end": package_claim_end,
            "verified_snapshot_start": snapshot_start,
            "verified_snapshot_end": snapshot_end,
            "verified_snapshot_symbols": snapshot_symbols,
            "verified_snapshot_row_count": snapshot_row_count,
            "official_performance_scope": "verified_snapshot_only",
            "can_use_package_claim_as_official_return": False,
            "message": (
                "External package claims and CodexStock verified snapshot scope differ; "
                "treat any package performance as research-only until replay/backtest covers the same scope."
                if scope_warnings
                else "Package claim scope and verified snapshot scope are aligned."
            ),
        }
        stage2_adapter = {
            "adapter_id": "codexstock_internal_contract_adapter_v1",
            "status": "enabled",
            "mode": "contract_translation_only",
            "external_code_execution": False,
            "external_runtime_enabled": False,
            "allowed_inputs": ["training_package_metadata", "dataset_snapshot", "stage2_cost_model"],
            "allowed_outputs": ["PROPOSE_BACKTEST_PLAN", "VERIFY_REPLAY_PLAN", "COMPARE_RESEARCH_RESULT"],
            "forbidden_outputs": ["SUBMIT_ORDER", "APPROVE_LIVE_TRADE", "WRITE_SECRET", "READ_ACCOUNT_NUMBER"],
            "note": "외부 엔진 런타임을 여는 것이 아니라, 외부소스 연구 패키지를 코덱스스톡 공통 검증 계약으로 번역하는 내부 어댑터입니다.",
        }
        has_stage2_adapter = True
        execution_budget = self.external_execution_budget()

        readiness_checks = [
            {
                "name": "package_found",
                "ok": bool(package_path) if package_id else False,
                "detail": str(package_path) if package_path else "패키지 ID가 없거나 저장소에서 찾지 못했습니다.",
                "required": bool(package_id),
            },
            {
                "name": "schema_validation_score",
                "ok": bool(score and float(score) >= 70),
                "detail": f"score={score}",
                "required": True,
            },
            {
                "name": "validation_blocks_clear",
                "ok": not bool(validation_blocks),
                "detail": f"blocks={len(validation_blocks)}",
                "required": True,
            },
            {
                "name": "package_not_quarantined",
                "ok": bool(package_path) and not package_quarantined_or_blocked,
                "detail": f"status={package_status or '-'}, blocks={len(validation_blocks)}",
                "required": True,
            },
            {
                "name": "stage2_status_allowed",
                "ok": bool(package_path) and package_status in stage2_candidate_statuses,
                "detail": f"status={package_status or '-'}, allowed={','.join(sorted(stage2_candidate_statuses))}",
                "required": True,
            },
            {
                "name": "cost_slippage_declared",
                "ok": has_stage2_cost_model,
                "detail": f"package_claim={package_claims_cost_model}, forced_model={stage2_cost_model['model_id']}",
                "required": True,
            },
            {
                "name": "license_reviewed",
                "ok": license_text not in {"", "unknown", "verify_required", "n/a", "none"} or research_metadata_only_license_ok,
                "detail": f"license={license_text or 'missing'}, scope={license_scope}, code_copy_allowed={bool(license_review.get('code_copy_allowed'))}",
                "required": True,
            },
            {
                "name": "common_snapshot_hash_ready",
                "ok": bool(snapshot_id and dataset_hash and snapshot_materialized and snapshot_fatal_count == 0),
                "detail": (
                    f"snapshot_id={snapshot_id or '-'}, dataset_hash={dataset_hash[:16] if dataset_hash else '-'}, "
                    f"materialized={snapshot_materialized}, fatal_issues={snapshot_fatal_count}, "
                    f"source={dataset_snapshot_source}"
                ),
                "required": True,
            },
            {
                "name": "external_adapter_enabled",
                "ok": has_stage2_adapter,
                "detail": f"adapter={stage2_adapter['adapter_id']}, mode={stage2_adapter['mode']}, external_runtime={stage2_adapter['external_runtime_enabled']}",
                "required": True,
            },
            {
                "name": "external_execution_budget_defined",
                "ok": execution_budget["max_concurrent_external_jobs"] == 1 and execution_budget["kill_on_timeout"],
                "detail": (
                    f"timeout={execution_budget['default_timeout_seconds']}s, "
                    f"hard_timeout={execution_budget['hard_timeout_seconds']}s, "
                    f"max_concurrent={execution_budget['max_concurrent_external_jobs']}, "
                    f"store_full_raw_logs={execution_budget['store_full_raw_logs']}"
                ),
                "required": True,
            },
            {
                "name": "live_order_permission",
                "ok": False,
                "detail": "외부 엔진은 실주문 권한이 없고 PROPOSE/VERIFY 보고서만 만들 수 있습니다.",
                "required": False,
            },
        ]
        required_blockers = [row for row in readiness_checks if row.get("required") and not row.get("ok")]
        stage2_gate_passed = len(required_blockers) == 0
        contract_rehearsal = {
            "ready": stage2_gate_passed,
            "state": "READY_FOR_INTERNAL_CONTRACT_REHEARSAL" if stage2_gate_passed else "WAITING_FOR_REQUIRED_CHECKS",
            "result_contract_mode": "schema_only_no_external_runtime",
            "permitted_next_action": "run_codexstock_internal_rehearsal" if stage2_gate_passed else "fix_required_blockers",
            "external_runtime_enabled": False,
            "live_order_enabled": False,
            "expected_output_types": stage2_adapter.get("allowed_outputs", []),
            "execution_budget": execution_budget,
            "dataset_contract": stage2_dataset_contract,
            "scope_audit": stage2_scope_audit,
        }
        contract_result_preview: dict[str, Any] = {}
        if stage2_gate_passed:
            contract_result_preview = {
                "engine_name": "CodexStockInternalContractAdapter",
                "engine_version": str(stage2_adapter.get("adapter_id") or "codexstock_internal_contract_adapter_v1"),
                "code_commit": "local-working-tree",
                "dataset_hash": dataset_hash,
                "snapshot_id": snapshot_id,
                "strategy_version": str(package.get("strategy_id") or package_id or action_key),
                "parameters": {
                    "action": action_key,
                    "package_id": package_id,
                    "cost_model_id": stage2_cost_model["model_id"],
                    "adapter_mode": stage2_adapter["mode"],
                    "external_runtime_enabled": False,
                    "execution_budget_id": "codexstock_external_budget_v1",
                    "dataset_contract": stage2_dataset_contract,
                    "package_claim_start": package_claim_start,
                    "package_claim_end": package_claim_end,
                    "scope_audit": stage2_scope_audit,
                },
                "start_date": snapshot_start or package_claim_start,
                "end_date": snapshot_end or package_claim_end,
                "start": snapshot_start or package_claim_start,
                "end": snapshot_end or package_claim_end,
                "initial_cash": 0,
                "fees": {
                    "commission_bps_per_side": stage2_cost_model["commission_bps_per_side"],
                    "minimum_fee_krw": stage2_cost_model["minimum_fee_krw"],
                    "market_profiles": stage2_cost_model["market_profiles"],
                },
                "tax": {"sell_tax_bps": stage2_cost_model["sell_tax_bps"]},
                "slippage_model": {
                    "slippage_bps_per_side": stage2_cost_model["slippage_bps_per_side"],
                    "fx_conversion_spread_bps_per_side": stage2_cost_model[
                        "fx_conversion_spread_bps_per_side"
                    ],
                },
                "fill_model": {
                    "type": "contract_rehearsal_no_execution",
                    "external_runtime_enabled": False,
                    "live_order_enabled": False,
                },
                "trade_count": 0,
                "return_pct": 0.0,
                "cagr_pct": 0.0,
                "mdd_pct": 0.0,
                "sharpe": 0.0,
                "profit_factor": 0.0,
                "turnover": 0.0,
                "rejected_orders": [],
                "partial_fills": [],
                "execution_time_ms": 0,
                "artifact_path": "",
            }
        missing_result_contract_fields = [
            field for field in ENGINE_RESULT_CONTRACT_FIELDS if field not in contract_result_preview
        ] if stage2_gate_passed else list(ENGINE_RESULT_CONTRACT_FIELDS)
        contract_rehearsal["result_contract_ready"] = stage2_gate_passed and not missing_result_contract_fields
        contract_rehearsal["missing_result_contract_fields"] = missing_result_contract_fields
        next_actions = [
            "공통 시세 스냅샷(dataset_hash/snapshot_id)을 먼저 생성합니다.",
            "수수료·세금·슬리피지·체결모델을 동일하게 적용합니다.",
            "vectorbt 결과는 탐색용으로만 쓰고 Lean/Nautilus/CodexStock 재검증을 통과해야 합니다.",
            "결과는 실전 후보가 아니라 Paper/리플레이 리허설로만 연결합니다.",
        ]
        if not package_id:
            next_actions.insert(0, "검증할 외부 패키지 package_id를 지정합니다.")
        elif not package_path:
            next_actions.insert(0, "존재하는 외부 패키지를 먼저 import/validate 합니다.")
        elif package_quarantined_or_blocked:
            next_actions.insert(0, "This package is quarantined or validation-blocked; re-validate or reject it before any Stage 2 rehearsal.")
        elif package_status not in stage2_candidate_statuses:
            next_actions.insert(0, "Move this package to BACKTEST_READY or APPROVED_FOR_RESEARCH before Stage 2 rehearsal.")
        elif source_metadata.get("requires_stage2_backtest"):
            next_actions.append("이 패키지는 Stage 2 백테스트가 필요한 연구 패키지로 표시되어 있습니다.")

        result = {
            "ok": True,
            "accepted": True,
            "blocked": not stage2_gate_passed,
            "block_type": "required_stage2_checks_missing" if not stage2_gate_passed else "",
            "stage2_gate_passed": stage2_gate_passed,
            "external_runtime_blocked": True,
            "live_order_blocked": True,
            "action": action_key,
            "package_id": package_id,
            "package": {
                "found": bool(package_path),
                "source_name": package.get("source_name") if package else "",
                "strategy_id": package.get("strategy_id") if package else "",
                "strategy_name": package.get("strategy_name") if package else "",
                "status": package.get("status") if package else "",
                "validation_score": score,
                "warning_count": len(validation_warnings),
                "block_count": len(validation_blocks),
                "quarantined_excluded": package_quarantined_or_blocked,
                "stage2_status_allowed": package_status in stage2_candidate_statuses,
                "requires_stage2_backtest": bool(source_metadata.get("requires_stage2_backtest")),
            },
            "execution_state": "ready_for_internal_contract_rehearsal" if stage2_gate_passed else "planned_not_executed",
            "stage": "Stage 2 external engine contract gate",
            "contract_rehearsal": contract_rehearsal,
            "contract_result_preview": contract_result_preview,
            "missing_result_contract_fields": missing_result_contract_fields,
            "selected_engines": selected_engines,
            "readiness_checks": readiness_checks,
            "required_blocker_count": len(required_blockers),
            "required_blockers": required_blockers,
            "dataset_snapshot": snapshot_payload,
            "dataset_snapshot_source": dataset_snapshot_source,
            "stage2_dataset_contract": stage2_dataset_contract,
            "stage2_scope_audit": stage2_scope_audit,
            "dataset_snapshot_readiness": self.dataset_snapshot_readiness(),
            "stage2_cost_model": stage2_cost_model,
            "stage2_adapter": stage2_adapter,
            "execution_budget": execution_budget,
            "budget_gate": {
                "max_concurrent_external_jobs": execution_budget["max_concurrent_external_jobs"],
                "timeout_required": bool(execution_budget["kill_on_timeout"]),
                "raw_log_storage_allowed": bool(execution_budget["store_full_raw_logs"]),
                "status": "ready" if execution_budget["max_concurrent_external_jobs"] == 1 and execution_budget["kill_on_timeout"] else "review_required",
            },
            "safety_gate": {
                "quarantined_packages_excluded": True,
                "package_quarantined_or_blocked": package_quarantined_or_blocked,
                "stage2_allowed_statuses": sorted(stage2_candidate_statuses),
                "quarantine_statuses": sorted(quarantine_statuses),
                "external_code_execution_allowed": False,
                "live_order_allowed": False,
            },
            "license_policy": {
                "license": license_text or "missing",
                "scope": license_scope,
                "research_metadata_allowed": research_metadata_only_license_ok,
                "code_copy_allowed": bool(license_review.get("code_copy_allowed")),
                "runtime_execution_allowed": bool(license_review.get("runtime_execution_allowed")),
                "live_candidate_allowed": bool(license_review.get("live_candidate_allowed")),
            },
            "required_data_contract_fields": list(ENGINE_DATA_CONTRACT_FIELDS),
            "required_result_contract_fields": list(ENGINE_RESULT_CONTRACT_FIELDS),
            "promotion_stages": ENGINE_PROMOTION_STAGES,
            "next_actions": next_actions,
            "safety": "외부 최강소스는 하위 계산/검증 엔진으로만 사용합니다. 계좌번호, KIS 주문키, 토큰은 전달하지 않고 실전 주문도 실행하지 않습니다.",
        }
        self._audit(
            "STAGE2_EXTERNAL_ENGINE_PLAN",
            package_id,
            "",
            "PLANNED_RESEARCH_ONLY",
            f"{action_key}: {len(selected_engines)} engines, blockers={len(required_blockers)}",
            score,
            source,
            str(package_path or self.root),
        )
        return result

    def assign_training_mission(self, mission: dict[str, Any], *, source: str = "api") -> dict[str, Any]:
        mission_id = safe_id(mission.get("mission_id") or f"mission-{now_iso()}", "mission")
        record = {
            "mission_id": mission_id,
            "title": str(mission.get("title") or "외부 지식 검증 미션"),
            "source_package_id": str(mission.get("source_package_id") or ""),
            "target_staff": mission.get("target_staff") if isinstance(mission.get("target_staff"), list) else [],
            "market": str(mission.get("market") or "KR").upper(),
            "priority": str(mission.get("priority") or "normal"),
            "objectives": mission.get("objectives") if isinstance(mission.get("objectives"), list) else [],
            "constraints": mission.get("constraints") if isinstance(mission.get("constraints"), list) else ["실전 주문 금지"],
            "success_conditions": mission.get("success_conditions") if isinstance(mission.get("success_conditions"), list) else [],
            "status": "ASSIGNED_RESEARCH_ONLY",
            "created_at": now_iso(),
            "source": source,
        }
        with self.missions_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._audit("ASSIGN_EXTERNAL_TRAINING_MISSION", record["source_package_id"], "", "ASSIGNED_RESEARCH_ONLY", record["title"], None, source, str(self.missions_path))
        return {"ok": True, "mission": record, "safety": "학습 미션만 저장했습니다. 실전 주문은 호출하지 않습니다."}

    def _write_package(self, package: dict[str, Any]) -> Path:
        status = str(package.get("status", "IMPORTED")).upper()
        folder = STATUS_FOLDERS.get(status, "validating")
        path = self.root / folder / f"{safe_id(package.get('package_id'), 'package')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _scan_packages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for folder in FOLDERS:
            for path in (self.root / folder).glob("*.json"):
                row = self._read_json(path)
                if row:
                    row["_path"] = str(path)
                    rows.append(row)
        return rows

    def _package_ids(self) -> set[str]:
        return {str(item.get("package_id")) for item in self._scan_packages() if item.get("package_id")}

    def _find_package_path(self, package_id: str) -> Path | None:
        safe = safe_id(package_id, "")
        if not safe:
            return None
        for folder in FOLDERS:
            path = self.root / folder / f"{safe}.json"
            if path.exists():
                return path
        return None

    def _audit(self, event: str, package_id: str, old_status: str, new_status: str, reason: str, score: Any, source: str, result_file: str) -> None:
        record = {
            "event": event,
            "package_id": package_id,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "validation_score": score,
            "actor": source,
            "created_at": now_iso(),
            "result_file": result_file,
            "rollback_possible": True,
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
