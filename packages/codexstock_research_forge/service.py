from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .adapters import BacktestAdapter, MockBacktestAdapter
from .experiments import ExperimentRegistry
from .models import ExperimentRecord, ExperimentStatus, ResearchPolicy, StrategyDefinition
from .validation import validate_experiment_evidence
from .analytics import compare_records, optimized_walk_forward, parameter_robustness, walk_forward
from .reports import export_report, replay_payload, verify_report
from .microstructure import MicrostructureStore
from .microstructure_archive import MicrostructureArchive
from .universe import PointInTimeUniverseHistory, UniverseStore
from .collection import CollectionManager
from .storage import AnalyticalStorage
from .jobs import AsyncJobManager
from .replay import ReplayEngine
from .performance import run_performance_benchmark
from .custom_indicators import CustomIndicatorRegistry
from .soak import run_concurrency_soak
from tempfile import TemporaryDirectory
from .microstructure_worker import MicrostructureWorker
from .hts_validation import HtsReferenceRegistry
from .lifecycle import ResearchLifecycle
from .readiness import evaluate_readiness
from .corporate_actions import CorporateActionRegistry
from .instrument_contracts import contract_manifest, normalize_instrument_dataset_contract
from .shards import ResearchShardCoordinator
from .stability import EngineStabilityLedger


@dataclass
class ResearchForge:
    registry: ExperimentRegistry
    adapter: BacktestAdapter
    policy: ResearchPolicy = ResearchPolicy()

    @classmethod
    def local(cls, root: Path, adapter: BacktestAdapter | None = None) -> "ResearchForge":
        return cls(ExperimentRegistry(root / "experiments"), adapter or MockBacktestAdapter())

    def status(self) -> dict[str, Any]:
        self.policy.assert_safe()
        records = list(self.registry.list())
        return {
            "ok": True,
            "engine": "CodexStock Research Forge",
            "version": __version__,
            "policy": {
                "decision_scope": self.policy.decision_scope,
                "live_order_allowed": self.policy.live_order_allowed,
                "requires_codexstock_validation": self.policy.requires_codexstock_validation,
            },
            "adapter": self.adapter.name,
            "experiment_count": len(records),
            "network_checked": False,
        }

    def doctor(self) -> dict[str, Any]:
        from .indicators import manifest as indicator_manifest

        checks = [
            {"id": "policy_research_only", "ok": self.policy.decision_scope == "research_only"},
            {"id": "live_order_blocked", "ok": not self.policy.live_order_allowed},
            {"id": "codexstock_validation_required", "ok": self.policy.requires_codexstock_validation},
            {"id": "registry_writable", "ok": self.registry.root.exists() and self.registry.root.is_dir()},
            {"id": "adapter_available", "ok": bool(self.adapter.name)},
            {"id": "indicator_engine", "ok": len(indicator_manifest()["indicators"]) >= 6},
            {"id": "microstructure_store", "ok": self.microstructure().status()["ok"]},
            {"id": "universe_store", "ok": self.universe().status()["ok"]},
            {"id": "async_job_store", "ok": self.jobs().status()["ok"]},
            {"id": "analytical_storage", "ok": self.storage().doctor()["ok"]},
            {"id": "corporate_action_registry", "ok": self.corporate_actions().status()["ok"]},
            {"id": "instrument_contracts", "ok": contract_manifest()["contract_count"] >= 4},
            {"id": "distributed_shard_store", "ok": self.shards().root.is_dir()},
            {"id": "engine_stability_ledger", "ok": self.stability().path.parent.is_dir()},
            {"id": "hts_reference_registry", "ok": self.hts_references().status()["ok"]},
            {"id": "mcp_surface", "ok": len(self.manifest()["tools"]) >= 20},
        ]
        return {"ok": all(item["ok"] for item in checks), "checks": checks, "network_checked": False}

    def manifest(self) -> dict[str, Any]:
        return {
            "name": "codexstock-research-forge-mcp",
            "version": __version__,
            "mode": "local-read-and-research-only",
            "tools": [
                "research_forge_status",
                "research_forge_doctor",
                "research_forge_readiness",
                "research_forge_mcp_manifest",
                "research_corporate_action_adjust",
                "research_corporate_action_status",
                "research_corporate_action_register",
                "research_corporate_action_register_verified",
                "research_corporate_action_query",
                "research_corporate_action_adjust_registered",
                "research_corporate_action_reconcile",
                "research_instrument_contracts",
                "research_instrument_validate",
                "research_shard_batch_create",
                "research_shard_claim",
                "research_shard_heartbeat",
                "research_shard_finish",
                "research_shard_status",
                "research_stability_record",
                "research_stability_audit",
                "research_strategy_validate",
                "research_experiment_create",
                "research_experiment_get",
                "research_experiment_list",
                "research_backtest_run",
                "research_walk_forward_run",
                "research_robustness_run",
                "research_experiment_compare",
                "research_replay_get",
                "research_replay_create",
                "research_replay_page",
                "research_replay_verify",
                "research_report_export",
                "research_report_verify",
                "research_microstructure_status",
                "research_microstructure_quality",
                "research_microstructure_ingest",
                "research_microstructure_archive_status",
                "research_microstructure_archive_export",
                "research_microstructure_archive_verify",
                "research_microstructure_archive_query",
                "research_indicator_list",
                "research_indicator_calculate",
                "research_indicator_verify",
                "research_universe_status",
                "research_universe_register",
                "research_universe_query",
                "research_universe_validate",
                "research_universe_integrity",
                "research_collection_status",
                "research_collection_start",
                "research_collection_resume",
                "research_collection_storage_summary",
                "research_provider_status",
                "research_universe_sync_krx",
                "research_universe_sync_kind",
                "research_universe_sync_global_history",
                "research_universe_history_status",
                "research_universe_history_query",
                "research_universe_history_code_change",
                "research_strict_walk_forward_run",
                "research_storage_status",
                "research_storage_import_collection",
                "research_storage_import_legacy_ohlcv",
                "research_storage_query",
                "research_storage_export_parquet",
                "research_async_submit",
                "research_async_status",
                "research_async_cancel",
                "research_async_retry",
                "research_async_resume_interrupted",
                "research_performance_run",
                "research_execution_manifest",
                "research_execution_compare",
                "research_custom_indicator_register",
                "research_custom_indicator_list",
                "research_custom_indicator_calculate",
                "research_multitimeframe_backtest",
                "research_concurrency_soak",
                "research_microstructure_provider_status",
                "research_microstructure_worker_start",
                "research_microstructure_worker_status",
                "research_microstructure_worker_resume",
                "research_realtime_status",
                "research_realtime_start",
                "research_realtime_resume",
                "research_realtime_runs",
                "research_hts_reference_register",
                "research_hts_csv_template",
                "research_hts_csv_import",
                "research_hts_reference_status",
                "research_lifecycle_readiness",
                "research_lifecycle_review",
                "research_lifecycle_history",
            ],
        }

    def create_experiment(
        self,
        strategy: StrategyDefinition,
        data_snapshot: dict[str, Any],
        execution_model: dict[str, Any],
    ) -> ExperimentRecord:
        errors = strategy.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if not data_snapshot.get("dataset_id"):
            raise ValueError("data_snapshot.dataset_id is required for reproducibility")
        symbols = strategy.rules.get("symbols") if isinstance(strategy.rules.get("symbols"), list) else [
            strategy.rules.get("symbol") or data_snapshot.get("symbol")
        ]
        contract_snapshot = dict(data_snapshot)
        if not any(symbols) and self.adapter.name == "mock":
            symbols = ["005930"]
            contract_snapshot["instrument_contract_symbol_source"] = "mock_adapter_default"
        instrument_contract = normalize_instrument_dataset_contract(
            contract_snapshot,
            [str(value) for value in symbols if value],
        )
        if not instrument_contract["passed"]:
            raise ValueError(
                "instrument dataset contract failed: "
                + ", ".join(str(value) for value in instrument_contract["errors"])
            )
        record = ExperimentRecord(
            strategy,
            instrument_contract["normalized_snapshot"],
            execution_model,
            code_version=__version__,
            backtest_adapter=self.adapter.name,
        )
        self.registry.save(record)
        return record

    def run_backtest(self, experiment_id: str) -> ExperimentRecord:
        self.policy.assert_safe()
        record = self.registry.get(experiment_id)
        instrument_contract = self._instrument_contract_evidence(record)
        if not instrument_contract["passed"]:
            raise ValueError(
                "instrument dataset contract failed: "
                + ", ".join(str(value) for value in instrument_contract["errors"])
            )
        record.data_snapshot = instrument_contract["normalized_snapshot"]
        if record.backtest_adapter not in {"unknown", self.adapter.name}:
            raise ValueError(
                f"experiment is pinned to adapter {record.backtest_adapter}, not {self.adapter.name}"
            )
        record.status = ExperimentStatus.BACKTESTING
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.registry.save(record)
        try:
            record.result = self.adapter.run(record.strategy.to_dict() if hasattr(record.strategy, "to_dict") else {
                "name": record.strategy.name,
                "version": record.strategy.version,
                "rules": record.strategy.rules,
            }, record.data_snapshot, record.execution_model)
            record.validation = validate_experiment_evidence(
                record.data_snapshot,
                record.execution_model,
                record.result,
                self._universe_evidence(record),
            )
            record.status = ExperimentStatus.VALIDATION
        except Exception as exc:
            record.status = ExperimentStatus.FAILED
            record.result = {"error": str(exc), "adapter": self.adapter.name}
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.registry.save(record)
        return record

    def run_walk_forward(self, experiment_id: str, folds: int = 4) -> ExperimentRecord:
        record = self.registry.get(experiment_id)
        self._assert_adapter(record)
        record.validation["walk_forward"] = walk_forward(record, self.adapter.run, folds)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.registry.save(record)
        return record

    def run_strict_walk_forward(
        self,
        experiment_id: str,
        folds: int = 3,
        fast_values: list[int] | None = None,
        slow_values: list[int] | None = None,
        purge_days: int = 0,
        embargo_days: int = 0,
        purge_rows: int = 0,
        embargo_rows: int = 0,
    ) -> ExperimentRecord:
        record = self.registry.get(experiment_id)
        self._assert_adapter(record)
        record.validation["strict_walk_forward"] = optimized_walk_forward(
            record, self.adapter.run, folds, fast_values, slow_values, purge_days, embargo_days, purge_rows, embargo_rows
        )
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.registry.save(record)
        return record

    def run_robustness(self, experiment_id: str, radius: int = 2) -> ExperimentRecord:
        record = self.registry.get(experiment_id)
        self._assert_adapter(record)
        record.validation["parameter_robustness"] = parameter_robustness(record, self.adapter.run, radius)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.registry.save(record)
        return record

    def compare(self, experiment_ids: list[str]) -> dict[str, Any]:
        if len(experiment_ids) < 2:
            raise ValueError("at least two experiment ids are required")
        return compare_records([self.registry.get(value) for value in experiment_ids[:20]])

    def replay(self, experiment_id: str, limit: int = 500) -> dict[str, Any]:
        return replay_payload(self.registry.get(experiment_id), limit)

    def replay_engine(self) -> ReplayEngine:
        return ReplayEngine(self.registry.root.parent / "replays", self.storage(), self.microstructure(), self.microstructure_archive())

    def export(self, experiment_id: str) -> dict[str, Any]:
        return export_report(self.registry.get(experiment_id), self.registry.root.parent / "reports")

    def verify_export(self, experiment_id: str) -> dict[str, Any]:
        return verify_report(self.registry.get(experiment_id), self.registry.root.parent / "reports")

    def microstructure(self) -> MicrostructureStore:
        return MicrostructureStore(self.registry.root.parent / "microstructure")

    def microstructure_archive(self) -> MicrostructureArchive:
        return MicrostructureArchive(self.registry.root.parent / "microstructure")

    def microstructure_worker(self) -> MicrostructureWorker:
        return MicrostructureWorker(self.registry.root.parent / "microstructure_workers", self.microstructure())

    def universe(self) -> UniverseStore:
        return UniverseStore(self.registry.root.parent / "universes")

    def universe_history(self) -> PointInTimeUniverseHistory:
        return PointInTimeUniverseHistory(self.registry.root.parent / "universes")

    def collection(self) -> CollectionManager:
        return CollectionManager(self.registry.root.parent / "collection")

    def storage(self) -> AnalyticalStorage:
        return AnalyticalStorage(self.registry.root.parent / "analytical_storage")

    def jobs(self) -> AsyncJobManager:
        # Personal-PC default: one heavy research workload at a time so the
        # CodexStock UI and market monitoring remain responsive.
        return AsyncJobManager(self.registry.root.parent / "async_jobs", max_workers=1)

    def benchmark(self, indicator_row_count: int = 100_000) -> dict[str, Any]:
        return run_performance_benchmark(self.storage(), self.registry.root.parent / "benchmarks", indicator_row_count, self.microstructure_archive())

    def custom_indicators(self) -> CustomIndicatorRegistry:
        return CustomIndicatorRegistry(self.registry.root.parent / "custom_indicators")

    def hts_references(self) -> HtsReferenceRegistry:
        return HtsReferenceRegistry(self.registry.root.parent / "hts_references")

    def corporate_actions(self) -> CorporateActionRegistry:
        return CorporateActionRegistry(self.registry.root.parent / "corporate_actions")

    def shards(self) -> ResearchShardCoordinator:
        return ResearchShardCoordinator(self.registry.root.parent / "distributed_shards")

    def stability(self) -> EngineStabilityLedger:
        return EngineStabilityLedger(self.registry.root.parent / "stability" / "engine_snapshots.jsonl")

    def readiness(self, external: dict[str, Any] | None = None) -> dict[str, Any]:
        return evaluate_readiness(self, external)

    def lifecycle(self) -> ResearchLifecycle:
        return ResearchLifecycle(self.registry.root.parent / "lifecycle")

    def lifecycle_readiness(self, experiment_id: str) -> dict[str, Any]:
        record = self.registry.get(experiment_id); verification = self.verify_export(experiment_id)
        if verification.get("errors") == ["manifest_missing"]:
            self.export(experiment_id); verification = self.verify_export(experiment_id)
        contract = self._instrument_contract_evidence(record)
        return self.lifecycle().readiness(
            record,
            verification,
            supplemental_checks=[{
                "id": "instrument_contract_valid",
                "ok": contract.get("passed") is True,
            }],
            supplemental_evidence={"instrument_contract": contract},
        )

    def review_experiment(self, experiment_id: str, action: str, reviewer: str, rationale: str, confirmation: str = "") -> dict[str, Any]:
        record = self.registry.get(experiment_id); verification = self.verify_export(experiment_id)
        if verification.get("errors") == ["manifest_missing"]:
            self.export(experiment_id); verification = self.verify_export(experiment_id)
        contract = self._instrument_contract_evidence(record)
        decision = self.lifecycle().review(
            record,
            action,
            reviewer,
            rationale,
            verification,
            confirmation,
            supplemental_checks=[{
                "id": "instrument_contract_valid",
                "ok": contract.get("passed") is True,
            }],
            supplemental_evidence={"instrument_contract": contract},
        )
        self.registry.save(record); report = self.export(experiment_id); card = self.lifecycle().create_card(record, decision, report)
        return {"ok": True, "experiment": record.to_dict(), "decision": decision, "research_card": card, "report": report}

    def auto_nominate_verified_paper(
        self,
        experiment_id: str,
        *,
        scheduler_id: str,
        rationale: str,
    ) -> dict[str, Any]:
        record = self.registry.get(experiment_id)
        verification = self.verify_export(experiment_id)
        if verification.get("errors") == ["manifest_missing"]:
            self.export(experiment_id)
            verification = self.verify_export(experiment_id)
        contract = self._instrument_contract_evidence(record)
        decision = self.lifecycle().auto_nominate_verified_paper(
            record,
            verification,
            scheduler_id=scheduler_id,
            rationale=rationale,
            supplemental_checks=[{
                "id": "instrument_contract_valid",
                "ok": contract.get("passed") is True,
            }],
            supplemental_evidence={"instrument_contract": contract},
        )
        self.registry.save(record)
        report = self.export(experiment_id)
        card = self.lifecycle().create_card(record, decision, report)
        return {
            "ok": True,
            "experiment": record.to_dict(),
            "decision": decision,
            "research_card": card,
            "report": report,
            "paper_only": True,
            "live_order_allowed": False,
        }

    def concurrency_soak(self, iterations: int = 20) -> dict[str, Any]:
        candidates = [record for record in self.registry.list() if record.backtest_adapter == self.adapter.name and record.result]
        callback = None
        if candidates:
            record = candidates[-1]
            strategy = {"name": record.strategy.name, "version": record.strategy.version, "description": record.strategy.description, "rules": record.strategy.rules}
            callback = lambda: self.adapter.run(strategy, record.data_snapshot, record.execution_model)
        with TemporaryDirectory(prefix="research-forge-soak-") as directory:
            return run_concurrency_soak(self.storage(), CollectionManager(Path(directory) / "collection"), self.registry.root.parent / "benchmarks", callback, iterations)

    def _universe_evidence(self, record: ExperimentRecord) -> dict[str, Any] | None:
        dataset_id = str(record.data_snapshot.get("universe_dataset_id") or "")
        if not dataset_id:
            return None
        rules = record.strategy.rules
        symbols = rules.get("symbols") if isinstance(rules.get("symbols"), list) else [rules.get("symbol")]
        symbols = [str(value).upper() for value in symbols if value]
        return self.universe().validate_period(
            dataset_id,
            symbols,
            str(record.data_snapshot.get("start_date") or ""),
            str(record.data_snapshot.get("end_date") or ""),
        )

    def _instrument_contract_evidence(self, record: ExperimentRecord) -> dict[str, Any]:
        symbols = record.strategy.rules.get("symbols") if isinstance(record.strategy.rules.get("symbols"), list) else [
            record.strategy.rules.get("symbol") or record.data_snapshot.get("symbol")
        ]
        return normalize_instrument_dataset_contract(
            record.data_snapshot,
            [str(value) for value in symbols if value],
        )

    def _assert_adapter(self, record: ExperimentRecord) -> None:
        self.policy.assert_safe()
        if record.backtest_adapter not in {"unknown", self.adapter.name}:
            raise ValueError(f"experiment is pinned to adapter {record.backtest_adapter}, not {self.adapter.name}")
