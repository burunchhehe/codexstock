from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .adapters import AnalyticalStorageBacktestAdapter, CodexStockNativeBacktestAdapter, LocalOhlcvBacktestAdapter, MockBacktestAdapter
from .models import StrategyDefinition
from .service import ResearchForge
from .indicators import calculate as calculate_indicator, manifest as indicator_manifest, verify as verify_indicator
from .collection import KisReadOnlyProvider, MockMarketDataProvider
from .universe import KindOfficialUniverseProvider, KrxGlobalListingHistoryProvider, KrxOpenApiUniverseProvider
from .execution import compare_execution_modes, execution_manifest, simulate_long_only
from .multitimeframe import evaluate_multitimeframe
from .microstructure_worker import KisPollingMicrostructureProvider
from .realtime import ReliableKisRealtimeCollector, WebsocketClientTransport, realtime_run_history, request_approval_key
from .corporate_actions import OfficialCorporateActionEvidenceProvider, adjust_split_history
from .hts_csv import import_csv as import_hts_csv, template as hts_csv_template
from .instrument_contracts import contract_manifest, validate_instrument_snapshot


RESEARCH_TOOL_NAMES = (
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
)


def build_forge(runtime_root: Path, repo_root: Path, adapter_name: str = "ohlcv") -> ResearchForge:
    forge_root = runtime_root if runtime_root.name == "research_forge" or (runtime_root / "experiments").is_dir() else runtime_root / "research_forge"
    if adapter_name == "native":
        adapter = CodexStockNativeBacktestAdapter(repo_root / "app")
    elif adapter_name == "analytical":
        adapter = AnalyticalStorageBacktestAdapter(forge_root / "analytical_storage", forge_root / "custom_indicators")
    elif adapter_name == "ohlcv":
        adapter = LocalOhlcvBacktestAdapter(repo_root / "data")
    else:
        adapter = MockBacktestAdapter()
    return ResearchForge.local(forge_root, adapter=adapter)


def call_research_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    runtime_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    if name not in RESEARCH_TOOL_NAMES:
        raise ValueError(f"unknown Research Forge tool: {name}")
    adapter_name = str(arguments.get("adapter") or "ohlcv")
    if adapter_name not in {"native", "ohlcv", "analytical", "mock"}:
        raise ValueError("adapter must be native, ohlcv, analytical, or mock")
    forge = build_forge(runtime_root, repo_root, adapter_name)
    if name == "research_forge_status":
        return forge.status()
    if name == "research_forge_doctor":
        return forge.doctor()
    if name == "research_forge_readiness":
        import importlib.util
        from integrations import IntegrationSettings

        settings = IntegrationSettings.load(repo_root)
        return forge.readiness({
            "kis_configured": settings.kis_configured,
            "websocket_available": importlib.util.find_spec("websocket") is not None,
        })
    if name == "research_forge_mcp_manifest":
        return forge.manifest()
    if name == "research_corporate_action_adjust":
        rows, actions = arguments.get("rows"), arguments.get("actions")
        if not isinstance(rows, list) or not isinstance(actions, list):
            raise ValueError("rows and actions must be arrays")
        return adjust_split_history(rows, actions)
    if name == "research_corporate_action_status":
        return forge.corporate_actions().status()
    if name == "research_corporate_action_register":
        actions = arguments.get("actions")
        if not isinstance(actions, list): raise ValueError("actions must be an array")
        return {"ok": True, "dataset": forge.corporate_actions().register(str(arguments.get("dataset_id") or ""), str(arguments.get("symbol") or ""), actions, bool(arguments.get("complete_history")))}
    if name == "research_corporate_action_register_verified":
        actions = arguments.get("actions")
        if not isinstance(actions, list): raise ValueError("actions must be an array")
        verification = OfficialCorporateActionEvidenceProvider().verify(actions, float(arguments.get("timeout_seconds") or 15), int(arguments.get("max_document_bytes") or 10_000_000), int(arguments.get("attempts") or 3))
        dataset = forge.corporate_actions().register(
            str(arguments.get("dataset_id") or ""), str(arguments.get("symbol") or ""), verification["actions"],
            bool(arguments.get("complete_history")), True,
            str(arguments.get("history_start") or ""), str(arguments.get("history_end") or ""),
        )
        return {"ok": True, "dataset": dataset, "source_verification": {key: verification[key] for key in ("documents", "document_count", "verified_at", "network_checked", "read_only", "order_allowed")}}
    if name == "research_corporate_action_query":
        return forge.corporate_actions().query(str(arguments.get("dataset_id") or ""), str(arguments.get("start") or ""), str(arguments.get("end") or ""))
    if name == "research_corporate_action_adjust_registered":
        rows = arguments.get("rows")
        if not isinstance(rows, list): raise ValueError("rows must be an array")
        return forge.corporate_actions().adjust(str(arguments.get("dataset_id") or ""), rows)
    if name == "research_corporate_action_reconcile":
        symbols = arguments.get("symbols")
        if not isinstance(symbols, list): raise ValueError("symbols must be an array")
        return forge.corporate_actions().reconcile([str(value) for value in symbols], str(arguments.get("coverage_start") or ""), str(arguments.get("coverage_end") or ""))
    if name == "research_instrument_contracts":
        return contract_manifest()
    if name == "research_instrument_validate":
        return validate_instrument_snapshot(_object(arguments.get("snapshot"), "snapshot"))
    if name == "research_shard_batch_create":
        payloads = arguments.get("payloads")
        if not isinstance(payloads, list): raise ValueError("payloads must be an array")
        return forge.shards().create_batch(str(arguments.get("job_type") or ""), payloads)
    if name == "research_shard_claim":
        return forge.shards().claim(str(arguments.get("batch_id") or ""), str(arguments.get("worker_id") or ""), int(arguments.get("lease_seconds") or 300))
    if name == "research_shard_heartbeat":
        return forge.shards().heartbeat(str(arguments.get("batch_id") or ""), str(arguments.get("shard_id") or ""), str(arguments.get("worker_token") or ""))
    if name == "research_shard_finish":
        result = arguments.get("result")
        if result is not None and not isinstance(result, dict): raise ValueError("result must be an object")
        return forge.shards().finish(str(arguments.get("batch_id") or ""), str(arguments.get("shard_id") or ""), str(arguments.get("worker_token") or ""), result=result, error=str(arguments.get("error") or ""), retryable=bool(arguments.get("retryable")))
    if name == "research_shard_status":
        return forge.shards().status(str(arguments.get("batch_id") or ""))
    if name == "research_stability_record":
        return forge.stability().record_dashboard(_object(arguments.get("dashboard"), "dashboard"), int(arguments.get("min_interval_seconds") or 300))
    if name == "research_stability_audit":
        return forge.stability().audit(int(arguments.get("window_days") or 30), int(arguments.get("max_gap_seconds") or 900))
    if name == "research_strategy_validate":
        strategy = _strategy(arguments.get("strategy"))
        errors = strategy.validate()
        return {"ok": not errors, "errors": errors, "strategy": _strategy_payload(strategy)}
    if name == "research_execution_manifest":
        return {"ok": True, **execution_manifest()}
    if name == "research_execution_compare":
        rows, entry, exit_values = arguments.get("rows"), arguments.get("entry_signals"), arguments.get("exit_signals")
        if not isinstance(rows, list) or not isinstance(entry, list) or not isinstance(exit_values, list):
            raise ValueError("rows, entry_signals, and exit_signals must be arrays")
        return {"ok": True, "comparison": compare_execution_modes(rows, [bool(value) for value in entry], [bool(value) for value in exit_values], _object(arguments.get("base_model"), "base_model", required=False))}
    if name == "research_experiment_create":
        record = forge.create_experiment(
            _strategy(arguments.get("strategy")),
            _object(arguments.get("data_snapshot"), "data_snapshot"),
            _object(arguments.get("execution_model"), "execution_model", required=False),
        )
        return {"ok": True, "experiment": record.to_dict()}
    if name == "research_experiment_get":
        return {"ok": True, "experiment": forge.registry.get(str(arguments.get("experiment_id") or "")).to_dict()}
    if name == "research_experiment_list":
        limit = max(1, min(200, int(arguments.get("limit") or 20)))
        records = [record.to_dict() for record in forge.registry.list()]
        return {"ok": True, "experiments": records[-limit:], "count": len(records)}
    if name == "research_lifecycle_readiness":
        readiness = forge.lifecycle_readiness(str(arguments.get("experiment_id") or ""))
        return {"ok": True, "readiness": readiness}
    if name == "research_lifecycle_review":
        return forge.review_experiment(str(arguments.get("experiment_id") or ""), str(arguments.get("action") or ""), str(arguments.get("reviewer") or ""), str(arguments.get("rationale") or ""), str(arguments.get("confirmation") or ""))
    if name == "research_lifecycle_history":
        return forge.lifecycle().history(str(arguments.get("experiment_id") or "") or None, int(arguments.get("limit") or 100))
    if name == "research_experiment_compare":
        values = arguments.get("experiment_ids")
        if not isinstance(values, list):
            raise ValueError("experiment_ids must be an array")
        return {"ok": True, "comparison": forge.compare([str(value) for value in values])}
    if name == "research_replay_get":
        return {"ok": True, "replay": forge.replay(str(arguments.get("experiment_id") or ""), int(arguments.get("limit") or 500))}
    if name == "research_replay_create":
        symbols, timeframes = arguments.get("symbols"), arguments.get("timeframes")
        if symbols is not None and not isinstance(symbols, list): raise ValueError("symbols must be an array")
        if timeframes is not None and not isinstance(timeframes, list): raise ValueError("timeframes must be an array")
        record = forge.registry.get(str(arguments.get("experiment_id") or ""))
        replay = forge.replay_engine().create(
            record, [str(value) for value in (symbols or [])], str(arguments.get("start") or ""),
            str(arguments.get("end") or ""), [str(value) for value in timeframes] if timeframes else None,
            int(arguments.get("max_events") or 50000), str(arguments.get("microstructure_source") or "hybrid"),
        )
        return {"ok": True, "replay": replay}
    if name == "research_replay_page":
        return forge.replay_engine().page(str(arguments.get("session_id") or ""), int(arguments.get("cursor") or 0), int(arguments.get("limit") or 500))
    if name == "research_replay_verify":
        return forge.replay_engine().verify(str(arguments.get("session_id") or ""))
    if name == "research_report_export":
        return {"ok": True, "report": forge.export(str(arguments.get("experiment_id") or ""))}
    if name == "research_report_verify":
        verification = forge.verify_export(str(arguments.get("experiment_id") or ""))
        return {"ok": verification["ok"], "verification": verification}
    if name == "research_microstructure_status":
        return forge.microstructure().status()
    if name == "research_microstructure_provider_status":
        try: return {"ok": True, **KisPollingMicrostructureProvider.from_repo(repo_root).status()}
        except Exception as exc: return {"ok": False, "provider": "kis-readonly-polling", "configured": False, "read_only": True, "order_allowed": False, "message": str(exc)}
    if name == "research_microstructure_worker_status":
        return forge.microstructure_worker().status(str(arguments.get("worker_id") or "") or None)
    if name == "research_microstructure_worker_start":
        symbols = arguments.get("symbols")
        if not isinstance(symbols, list): raise ValueError("symbols must be an array")
        provider = KisPollingMicrostructureProvider.from_repo(repo_root)
        return forge.microstructure_worker().start(provider, [str(value) for value in symbols], float(arguments.get("interval_seconds") or 1), int(arguments.get("max_cycles") if arguments.get("max_cycles") is not None else 1), int(arguments.get("gap_seconds") or 10))
    if name == "research_microstructure_worker_resume":
        provider = KisPollingMicrostructureProvider.from_repo(repo_root)
        return forge.microstructure_worker().resume(str(arguments.get("worker_id") or ""), provider, int(arguments["max_cycles"]) if arguments.get("max_cycles") is not None else None)
    if name == "research_realtime_status":
        import importlib.util, sys
        if str(repo_root / "app") not in sys.path: sys.path.insert(0, str(repo_root / "app"))
        from integrations import IntegrationSettings
        settings = IntegrationSettings.load(repo_root); dependency = importlib.util.find_spec("websocket") is not None
        checkpoint_path = forge.registry.root.parent / "realtime" / "checkpoint.json"; checkpoint = None
        if checkpoint_path.is_file():
            import json
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        return {"ok": bool(settings.kis_configured and dependency), "provider": "kis-readonly-websocket", "configured": settings.kis_configured, "dependency_available": dependency, "read_only": True, "order_allowed": False, "tr_ids": ["H0STCNT0", "H0STASP0"], "checkpoint_path": str(checkpoint_path), "collector": checkpoint}
    if name == "research_realtime_start":
        import sys
        from dataclasses import replace
        if str(repo_root / "app") not in sys.path: sys.path.insert(0, str(repo_root / "app"))
        from integrations import IntegrationSettings, KIS_MOCK_BASE_URL, KIS_REAL_BASE_URL
        settings = replace(IntegrationSettings.load(repo_root), kis_readonly=True, live_trading=False)
        if not settings.kis_configured: raise ValueError("KIS quotation credentials are not configured")
        symbols = arguments.get("symbols")
        if not isinstance(symbols, list): raise ValueError("symbols must be an array")
        base_url = settings.kis_base_url or (KIS_MOCK_BASE_URL if settings.kis_use_mock else KIS_REAL_BASE_URL)
        approval = request_approval_key(base_url, settings.kis_app_key, settings.kis_app_secret)
        ws_url = "ws://ops.koreainvestment.com:31000" if settings.kis_use_mock else "ws://ops.koreainvestment.com:21000"
        collector = ReliableKisRealtimeCollector(forge.registry.root.parent / "realtime", forge.microstructure(), lambda: WebsocketClientTransport(ws_url), approval)
        max_messages = int(arguments["max_messages"]) if arguments.get("max_messages") is not None else 1000
        return collector.run([str(value) for value in symbols], max_messages, int(arguments.get("max_reconnects") or 20), float(arguments.get("heartbeat_timeout") or 30), duration_seconds=float(arguments.get("duration_seconds") or 0))
    if name == "research_realtime_resume":
        import sys
        from dataclasses import replace
        if str(repo_root / "app") not in sys.path: sys.path.insert(0, str(repo_root / "app"))
        from integrations import IntegrationSettings, KIS_MOCK_BASE_URL, KIS_REAL_BASE_URL
        settings = replace(IntegrationSettings.load(repo_root), kis_readonly=True, live_trading=False)
        if not settings.kis_configured: raise ValueError("KIS quotation credentials are not configured")
        base_url = settings.kis_base_url or (KIS_MOCK_BASE_URL if settings.kis_use_mock else KIS_REAL_BASE_URL)
        approval = request_approval_key(base_url, settings.kis_app_key, settings.kis_app_secret)
        ws_url = "ws://ops.koreainvestment.com:31000" if settings.kis_use_mock else "ws://ops.koreainvestment.com:21000"
        collector = ReliableKisRealtimeCollector(forge.registry.root.parent / "realtime", forge.microstructure(), lambda: WebsocketClientTransport(ws_url), approval)
        return collector.resume_interrupted(int(arguments.get("max_reconnects") or 20), float(arguments.get("heartbeat_timeout") or 30))
    if name == "research_realtime_runs":
        return realtime_run_history(forge.registry.root.parent / "realtime", int(arguments.get("limit") or 50))
    if name == "research_microstructure_quality":
        return forge.microstructure().quality()
    if name == "research_microstructure_ingest":
        events = arguments.get("events")
        if not isinstance(events, list):
            raise ValueError("events must be an array")
        return forge.microstructure().ingest(events, int(arguments.get("gap_seconds") or 10))
    if name == "research_microstructure_archive_status":
        return forge.microstructure_archive().status()
    if name == "research_microstructure_archive_export":
        return forge.microstructure_archive().export_incremental(int(arguments.get("max_source_files") or 0))
    if name == "research_microstructure_archive_verify":
        return forge.microstructure_archive().verify()
    if name == "research_microstructure_archive_query":
        symbols, event_types = arguments.get("symbols"), arguments.get("event_types")
        if not isinstance(symbols, list): raise ValueError("symbols must be an array")
        if event_types is not None and not isinstance(event_types, list): raise ValueError("event_types must be an array")
        return forge.microstructure_archive().query([str(value) for value in symbols], str(arguments.get("start") or ""), str(arguments.get("end") or ""), [str(value) for value in event_types] if event_types else None, int(arguments.get("limit") or 10000))
    if name == "research_indicator_list":
        manifest_payload = indicator_manifest(); evidence = forge.hts_references().status()
        for profile in manifest_payload["profiles"]:
            dynamic = evidence["profiles"].get(profile["name"])
            if dynamic and profile["name"] in {"LS_HTS", "KIWOOM_HTS", "KIS"}:
                profile["verified_indicators"] = dynamic["verified_indicators"]
                profile["fully_verified_by_exports"] = dynamic["fully_verified"]
        return {"ok": True, **manifest_payload, "hts_evidence_package_count": evidence["package_count"]}
    if name == "research_indicator_calculate":
        rows = arguments.get("rows")
        if not isinstance(rows, list):
            raise ValueError("rows must be an array")
        return {"ok": True, "calculation": calculate_indicator(str(arguments.get("indicator") or ""), rows, _object(arguments.get("parameters"), "parameters", required=False), str(arguments.get("profile") or "STANDARD"))}
    if name == "research_indicator_verify":
        rows, expected = arguments.get("rows"), arguments.get("expected")
        if not isinstance(rows, list) or not isinstance(expected, dict):
            raise ValueError("rows must be an array and expected must be an object")
        verification = verify_indicator(str(arguments.get("indicator") or ""), rows, _object(arguments.get("parameters"), "parameters", required=False), expected, str(arguments.get("profile") or "STANDARD"), float(arguments.get("tolerance") or 1e-6))
        return {"ok": verification["passed"], "verification": verification}
    if name == "research_hts_reference_register":
        evidence = forge.hts_references().register(_object(arguments.get("package"), "package"))
        return {"ok": evidence["passed"], "evidence": evidence}
    if name == "research_hts_csv_template":
        return hts_csv_template(str(arguments.get("profile") or ""), str(arguments.get("indicator") or ""))
    if name == "research_hts_csv_import":
        imported = import_hts_csv(str(arguments.get("csv_text") or ""), _object(arguments.get("metadata"), "metadata"))
        evidence = forge.hts_references().register(imported["package"])
        return {"ok": evidence["passed"], "import": {key: imported[key] for key in ("row_count", "reference_row_count", "source_file_hash", "profile", "indicator")}, "evidence": evidence}
    if name == "research_hts_reference_status":
        return forge.hts_references().status(str(arguments.get("profile") or "") or None)
    if name == "research_custom_indicator_register":
        return {"ok": True, "indicator": forge.custom_indicators().register(_object(arguments.get("definition"), "definition"))}
    if name == "research_custom_indicator_list":
        return forge.custom_indicators().list()
    if name == "research_custom_indicator_calculate":
        rows = arguments.get("rows")
        if not isinstance(rows, list): raise ValueError("rows must be an array")
        return {"ok": True, "calculation": forge.custom_indicators().calculate(str(arguments.get("name") or ""), str(arguments.get("version") or ""), rows)}
    if name == "research_multitimeframe_backtest":
        rows_by_context = arguments.get("rows_by_context")
        if not isinstance(rows_by_context, dict) or any(not isinstance(value, list) for value in rows_by_context.values()): raise ValueError("rows_by_context must be an object of arrays")
        rules = _object(arguments.get("rules"), "rules")
        evaluated = evaluate_multitimeframe(rules, rows_by_context, forge.custom_indicators())
        result = simulate_long_only(evaluated.pop("rows"), evaluated.pop("entry_signals"), evaluated.pop("exit_signals"), _object(arguments.get("execution_model"), "execution_model"))
        return {"ok": True, "alignment": evaluated, "result": result, "research_only": True}
    if name == "research_universe_status":
        return forge.universe().status()
    if name == "research_universe_register":
        records = arguments.get("records")
        if not isinstance(records, list):
            raise ValueError("records must be an array")
        return {"ok": True, "dataset": forge.universe().register(str(arguments.get("dataset_id") or ""), records, str(arguments.get("source") or ""))}
    if name == "research_universe_query":
        return {"ok": True, "universe": forge.universe().query(str(arguments.get("dataset_id") or ""), str(arguments.get("as_of") or ""), arguments.get("markets") if isinstance(arguments.get("markets"), list) else None, arguments.get("security_types") if isinstance(arguments.get("security_types"), list) else None)}
    if name == "research_universe_validate":
        symbols = arguments.get("symbols")
        if not isinstance(symbols, list):
            raise ValueError("symbols must be an array")
        evidence = forge.universe().validate_period(str(arguments.get("dataset_id") or ""), [str(value).upper() for value in symbols], str(arguments.get("start_date") or ""), str(arguments.get("end_date") or ""))
        return {"ok": evidence["passed"], "evidence": evidence}
    if name == "research_universe_integrity":
        return forge.universe().integrity(str(arguments.get("dataset_id") or ""))
    if name == "research_universe_sync_krx":
        app_root = repo_root / "app"
        import sys
        if str(app_root) not in sys.path:
            sys.path.insert(0, str(app_root))
        from integrations import IntegrationSettings
        settings = IntegrationSettings.load(repo_root)
        provider = KrxOpenApiUniverseProvider(settings.krx_api_key, settings.krx_base_url or "https://data-dbg.krx.co.kr/svc/apis")
        markets = arguments.get("markets")
        if markets is not None and not isinstance(markets, list):
            raise ValueError("markets must be an array")
        as_of = str(arguments.get("as_of") or "")
        snapshot = provider.fetch_snapshot(as_of, [str(value) for value in markets] if markets else None)
        dataset_id = str(arguments.get("dataset_id") or f"krx-snapshot-{as_of}")
        registered = forge.universe().register(dataset_id, snapshot["records"], snapshot["source"], snapshot["evidence"])
        return {"ok": True, "dataset": registered, "snapshot": {key: value for key, value in snapshot.items() if key != "records"}}
    if name == "research_universe_sync_kind":
        snapshot = KindOfficialUniverseProvider().fetch_snapshot(str(arguments.get("as_of") or "") or None)
        dataset_id = str(arguments.get("dataset_id") or f"kind-snapshot-{snapshot['as_of']}")
        registered = forge.universe().register(dataset_id, snapshot["records"], snapshot["source"], snapshot["evidence"])
        history_id = str(arguments.get("history_id") or "")
        history = None
        if history_id:
            try:
                forge.universe_history().get(history_id)
                history = forge.universe_history().append_snapshot(history_id, snapshot)
            except ValueError as exc:
                if "not found" not in str(exc): raise
                history = forge.universe_history().create_baseline(history_id, snapshot)
        return {"ok": True, "dataset": registered, "history": history, "snapshot": {key: value for key, value in snapshot.items() if key != "records"}}
    if name == "research_universe_sync_global_history":
        start, end = str(arguments.get("start") or ""), str(arguments.get("end") or "")
        history = KrxGlobalListingHistoryProvider().fetch_history(start, end)
        dataset_id = str(arguments.get("dataset_id") or f"krx-global-history-{start.replace('-', '')}-{end.replace('-', '')}")
        registered = forge.universe().register(dataset_id, history["records"], history["source"], history["evidence"])
        evidence_root = forge.registry.root.parent / "evidence" / "krx"; evidence_root.mkdir(parents=True, exist_ok=True)
        evidence_path = evidence_root / f"{dataset_id}.json"; temporary = evidence_path.with_suffix(".json.tmp")
        import json
        temporary.write_text(json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(evidence_path)
        summary = {key: value for key, value in history.items() if key not in {"records", "source_chunks"}}
        return {"ok": True, "dataset": registered, "history": summary, "evidence_path": str(evidence_path), "source_chunks": history["source_chunks"]}
    if name == "research_universe_history_status":
        return forge.universe_history().status()
    if name == "research_universe_history_query":
        return {"ok": True, "universe": forge.universe_history().query(str(arguments.get("history_id") or ""), str(arguments.get("as_of") or ""))}
    if name == "research_universe_history_code_change":
        return forge.universe_history().record_official_code_change(
            str(arguments.get("history_id") or ""), str(arguments.get("effective_date") or ""),
            str(arguments.get("old_symbol") or ""), _object(arguments.get("new_record"), "new_record"),
            str(arguments.get("source_url") or ""), str(arguments.get("source_hash") or ""),
        )
    if name == "research_collection_status":
        return forge.collection().status(str(arguments.get("job_id") or "") or None)
    if name == "research_collection_storage_summary":
        return forge.collection().storage_summary()
    if name == "research_provider_status":
        provider_name = str(arguments.get("provider") or "kis")
        if provider_name == "mock":
            provider = MockMarketDataProvider()
            return {"ok": True, "provider": provider.name, "configured": True, "network_required": False, "order_allowed": False}
        try:
            provider = KisReadOnlyProvider.from_repo(repo_root, ["005930"])
            return {"ok": True, **provider.status()}
        except Exception as exc:
            return {"ok": False, "provider": "kis-readonly", "configured": False, "network_checked": False, "order_allowed": False, "message": str(exc)}
    if name == "research_collection_start":
        provider_name = str(arguments.get("provider") or "mock")
        symbols = arguments.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            raise ValueError("symbols must be an array")
        normalized_symbols = [str(value) for value in (symbols or [])]
        provider = KisReadOnlyProvider.from_repo(repo_root, normalized_symbols) if provider_name == "kis" else MockMarketDataProvider()
        return forge.collection().start(provider, normalized_symbols, str(arguments.get("timeframe") or "1d"), str(arguments.get("start") or ""), str(arguments.get("end") or ""), interval=int(arguments.get("interval") or 1), max_symbols=int(arguments.get("max_symbols") or 1000), retry_max_attempts=int(arguments.get("retry_max_attempts") or 3), retry_base_seconds=float(arguments.get("retry_base_seconds") if arguments.get("retry_base_seconds") is not None else 0.25))
    if name == "research_collection_resume":
        job_id = str(arguments.get("job_id") or "")
        job = forge.collection().get(job_id)
        provider = KisReadOnlyProvider.from_repo(repo_root, list(job.get("symbols") or [])) if job.get("provider") == "kis-readonly" else MockMarketDataProvider()
        return forge.collection().resume(job_id, provider)
    if name == "research_storage_status":
        doctor = forge.storage().doctor()
        return {"ok": doctor["ok"], "doctor": doctor, "summary": forge.storage().summary() if doctor["ok"] else {}}
    if name == "research_storage_import_collection":
        return forge.storage().import_collection(forge.collection().root)
    if name == "research_storage_import_legacy_ohlcv":
        symbols = arguments.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            raise ValueError("symbols must be an array")
        cache_name = str(arguments.get("cache_name") or "walk_forward_ohlcv_cache_adj_20160706_20260706.json")
        if Path(cache_name).name != cache_name:
            raise ValueError("cache_name must be a file name inside the repository data directory")
        return forge.storage().import_legacy_ohlcv(
            repo_root / "data" / cache_name,
            [str(value) for value in (symbols or [])],
            int(arguments.get("max_symbols") or 0),
        )
    if name == "research_storage_query":
        symbols = arguments.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            raise ValueError("symbols must be an array")
        return forge.storage().query([str(value) for value in (symbols or [])], str(arguments.get("start") or ""), str(arguments.get("end") or ""), str(arguments.get("timeframe") or "1d"), int(arguments.get("limit") or 10000))
    if name == "research_storage_export_parquet":
        return forge.storage().export_parquet()
    if name == "research_async_status":
        return forge.jobs().status(str(arguments.get("job_id") or "") or None, int(arguments.get("limit") or 50))
    if name == "research_async_cancel":
        return {"ok": True, "job": forge.jobs().cancel(str(arguments.get("job_id") or ""))}
    if name == "research_async_submit":
        job_type = str(arguments.get("job_type") or "")
        if job_type not in {"backtest", "strict_walk_forward", "collection", "microstructure"}:
            raise ValueError("job_type must be backtest, strict_walk_forward, collection, or microstructure")
        payload = _validate_async_submit_payload(
            job_type,
            _object(arguments.get("payload"), "payload"),
            forge,
        )
        payload["adapter"] = adapter_name
        return {"ok": True, "job": forge.jobs().submit(job_type, payload, _async_handler(job_type, runtime_root, repo_root))}
    if name == "research_async_retry":
        job_id = str(arguments.get("job_id") or "")
        existing = forge.jobs().get(job_id)
        return {"ok": True, "job": forge.jobs().retry(job_id, _async_handler(str(existing["type"]), runtime_root, repo_root))}
    if name == "research_async_resume_interrupted":
        manager = forge.jobs()
        recovery = manager.recover_orphaned_running(float(arguments.get("orphan_grace_seconds") or 30))
        resumed = manager.resume_interrupted(lambda job_type: _async_handler(job_type, runtime_root, repo_root), int(arguments.get("limit") or 20))
        return {"ok": recovery["ok"] and resumed["ok"], "orphan_recovery": recovery, "resume": resumed}
    if name == "research_performance_run":
        benchmark = forge.benchmark(int(arguments.get("indicator_row_count") or 100000))
        return {"ok": benchmark["passed"], "benchmark": benchmark}
    if name == "research_concurrency_soak":
        soak = forge.concurrency_soak(int(arguments.get("iterations") or 20))
        return {"ok": soak["passed"], "soak": soak}
    if name == "research_walk_forward_run":
        record = forge.run_walk_forward(
            str(arguments.get("experiment_id") or ""), int(arguments.get("folds") or 4)
        )
        return {"ok": True, "experiment": record.to_dict()}
    if name == "research_strict_walk_forward_run":
        fast_values = arguments.get("fast_values")
        slow_values = arguments.get("slow_values")
        if fast_values is not None and not isinstance(fast_values, list):
            raise ValueError("fast_values must be an array")
        if slow_values is not None and not isinstance(slow_values, list):
            raise ValueError("slow_values must be an array")
        record = forge.run_strict_walk_forward(
            str(arguments.get("experiment_id") or ""),
            int(arguments.get("folds") or 3),
            [int(value) for value in fast_values] if fast_values else None,
            [int(value) for value in slow_values] if slow_values else None,
            int(arguments.get("purge_days") or 0),
            int(arguments.get("embargo_days") or 0),
            int(arguments.get("purge_rows") or 0),
            int(arguments.get("embargo_rows") or 0),
        )
        return {"ok": True, "experiment": record.to_dict()}
    if name == "research_robustness_run":
        record = forge.run_robustness(
            str(arguments.get("experiment_id") or ""), int(arguments.get("radius") or 2)
        )
        return {"ok": True, "experiment": record.to_dict()}
    record = forge.run_backtest(str(arguments.get("experiment_id") or ""))
    return {"ok": record.status.value != "FAILED", "experiment": record.to_dict()}


def _object(value: Any, label: str, *, required: bool = True) -> dict[str, Any]:
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _validate_async_submit_payload(
    job_type: str,
    payload: dict[str, Any],
    forge: ResearchForge,
) -> dict[str, Any]:
    normalized = dict(payload)
    if job_type in {"backtest", "strict_walk_forward"}:
        experiment_id = str(normalized.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError(f"{job_type} requires a non-empty experiment_id")
        forge.registry.get(experiment_id)
        normalized["experiment_id"] = experiment_id
        if job_type == "strict_walk_forward":
            for key in ("fast_values", "slow_values"):
                if normalized.get(key) is not None and not isinstance(normalized.get(key), list):
                    raise ValueError(f"{key} must be an array")
            for key, maximum in (
                ("purge_days", 365),
                ("embargo_days", 365),
                ("purge_rows", 10_000),
                ("embargo_rows", 10_000),
            ):
                value = int(normalized.get(key) or 0)
                if not 0 <= value <= maximum:
                    raise ValueError(f"{key} must be between 0 and {maximum}")
                normalized[key] = value
        return normalized

    symbols = normalized.get("symbols")
    if symbols is not None and not isinstance(symbols, list):
        raise ValueError("symbols must be an array")
    if isinstance(symbols, list):
        normalized_symbols = [str(value).strip().upper() for value in symbols]
        if any(not value or not value.isalnum() for value in normalized_symbols):
            raise ValueError("symbols must contain only non-empty alphanumeric values")
        normalized["symbols"] = list(dict.fromkeys(normalized_symbols))

    if job_type == "microstructure":
        normalized_symbols = normalized.get("symbols") or []
        if not 1 <= len(normalized_symbols) <= 100:
            raise ValueError("microstructure requires 1..100 symbols")
        interval_seconds = float(normalized.get("interval_seconds") or 1)
        max_cycles = int(normalized.get("max_cycles") if normalized.get("max_cycles") is not None else 1)
        gap_seconds = int(normalized.get("gap_seconds") or 10)
        if not 0.05 <= interval_seconds <= 60:
            raise ValueError("interval_seconds must be between 0.05 and 60")
        if not 0 <= max_cycles <= 100_000:
            raise ValueError("max_cycles must be between 0 and 100000")
        if not 1 <= gap_seconds <= 3600:
            raise ValueError("gap_seconds must be between 1 and 3600")
        normalized.update(
            {
                "interval_seconds": interval_seconds,
                "max_cycles": max_cycles,
                "gap_seconds": gap_seconds,
            }
        )
        return normalized

    provider = str(normalized.get("provider") or "mock").strip().lower()
    if provider not in {"mock", "kis"}:
        raise ValueError("collection provider must be mock or kis")
    start = str(normalized.get("start") or "").strip()
    end = str(normalized.get("end") or "").strip()
    if not start or not end:
        raise ValueError("collection requires start and end dates in YYYY-MM-DD format")
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        raise ValueError("collection start and end must be ISO dates in YYYY-MM-DD format") from None
    if end_date < start_date:
        raise ValueError("collection end date precedes start date")
    timeframe = str(normalized.get("timeframe") or "1d").strip().lower()
    if timeframe not in {"1d", "minute"}:
        raise ValueError("collection timeframe must be 1d or minute")
    retry_max_attempts = int(normalized.get("retry_max_attempts") or 3)
    retry_base_seconds = float(
        normalized.get("retry_base_seconds")
        if normalized.get("retry_base_seconds") is not None
        else 0.25
    )
    if not 1 <= retry_max_attempts <= 10 or not 0 <= retry_base_seconds <= 30:
        raise ValueError("retry policy must use 1..10 attempts and 0..30 base seconds")
    normalized.update(
        {
            "provider": provider,
            "start": start,
            "end": end,
            "timeframe": timeframe,
            "retry_max_attempts": retry_max_attempts,
            "retry_base_seconds": retry_base_seconds,
        }
    )
    return normalized


def _async_handler(job_type: str, runtime_root: Path, repo_root: Path):
    def run(payload: dict[str, Any], progress, cancelled) -> dict[str, Any]:
        if cancelled():
            return {"cancelled": True}
        progress(5, "validated")
        adapter = str(payload.pop("adapter", "ohlcv"))
        if job_type == "backtest":
            progress(15, "backtest_running")
            return call_research_tool("research_backtest_run", {**payload, "adapter": adapter}, runtime_root=runtime_root, repo_root=repo_root)
        if job_type == "strict_walk_forward":
            progress(10, "walk_forward_running")
            return call_research_tool("research_strict_walk_forward_run", {**payload, "adapter": adapter}, runtime_root=runtime_root, repo_root=repo_root)
        if job_type == "microstructure":
            symbols = payload.get("symbols")
            if not isinstance(symbols, list): raise ValueError("microstructure symbols must be an array")
            provider = KisPollingMicrostructureProvider.from_repo(repo_root)
            forge = build_forge(runtime_root, repo_root, adapter)
            return forge.microstructure_worker().start(provider, [str(value) for value in symbols], float(payload.get("interval_seconds") or 1), int(payload.get("max_cycles") if payload.get("max_cycles") is not None else 0), int(payload.get("gap_seconds") or 10), progress, cancelled)
        progress(10, "collection_running")
        forge = build_forge(runtime_root, repo_root, adapter)
        provider_name = str(payload.get("provider") or "mock")
        symbols = payload.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            raise ValueError("symbols must be an array")
        normalized = [str(value) for value in (symbols or [])]
        provider = KisReadOnlyProvider.from_repo(repo_root, normalized) if provider_name == "kis" else MockMarketDataProvider()
        return forge.collection().start(
            provider, normalized, str(payload.get("timeframe") or "1d"),
            str(payload.get("start") or ""), str(payload.get("end") or ""),
            interval=int(payload.get("interval") or 1), max_symbols=int(payload.get("max_symbols") or 1000),
            retry_max_attempts=int(payload.get("retry_max_attempts") or 3),
            retry_base_seconds=float(payload.get("retry_base_seconds") if payload.get("retry_base_seconds") is not None else 0.25),
            progress_callback=progress, cancel_requested=cancelled,
        )
    return run


def _strategy(value: Any) -> StrategyDefinition:
    payload = _object(value, "strategy")
    return StrategyDefinition(
        name=str(payload.get("name") or ""),
        version=str(payload.get("version") or ""),
        description=str(payload.get("description") or ""),
        rules=_object(payload.get("rules"), "strategy.rules"),
    )


def _strategy_payload(strategy: StrategyDefinition) -> dict[str, Any]:
    return {
        "name": strategy.name,
        "version": strategy.version,
        "description": strategy.description,
        "rules": strategy.rules,
    }
