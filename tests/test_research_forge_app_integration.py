from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app import stock_suite_app
from app.runtime_paths import bootstrap_user_data_tree


class ResearchForgeAppIntegrationTests(unittest.TestCase):
    def test_status_contract_is_connected_and_research_only(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "app.stock_suite_app.RESEARCH_FORGE_STORAGE_STATUS_CACHE_FILE",
                Path(directory) / "forge-status-cache.json",
            ),
            patch(
                "app.stock_suite_app.RESEARCH_FORGE_STORAGE_STATUS_CACHE",
                {"saved_at": 0.0, "scope": "", "payload": {}},
            ),
        ):
            payload = stock_suite_app.build_research_forge_status(include_readiness=False)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["connected"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertEqual(payload["max_concurrent_heavy_jobs"], 1)
        self.assertGreaterEqual(payload["analytical_row_count"], 1)

    def test_external_engine_dashboard_contains_research_forge(self) -> None:
        payload = stock_suite_app.build_external_engine_dashboard()
        rows = [row for row in payload["engines"] if row.get("engine_id") == "codexstock-research-forge"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["adapter_ready"])
        self.assertTrue(rows[0]["round_trip_verified"])
        self.assertTrue(rows[0]["formal_connected"])
        self.assertEqual("normal", rows[0]["operational_state"])
        self.assertEqual("codexstock_integration_audit", rows[0]["connection_proof_type"])
        self.assertFalse(rows[0]["recheck_due"])
        self.assertFalse(rows[0]["live_order_allowed"])
        self.assertIn("실전 주문 권한 없음", rows[0]["safety"])

    def test_research_forge_integration_audit_refreshes_on_demand_connection_proof(self) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        evidence = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "codexstock-research-forge",
                "status": "ready",
                "connected": True,
                "heavy_compute_policy": "on_demand_only",
                "runtime": {
                    "integration_audit": {
                        "ok": True,
                        "status": "integrated",
                        "generated_at": now,
                    },
                },
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
        )

        self.assertTrue(evidence["round_trip_verified"])
        self.assertTrue(evidence["success_evidence_fresh"])
        self.assertTrue(evidence["formal_connected"])
        self.assertFalse(evidence["recheck_due"])
        self.assertEqual("formal_connected", evidence["connection_stage"])
        self.assertEqual(
            "codexstock_integration_audit",
            evidence["connection_proof_type"],
        )

    def test_external_engine_dashboard_contains_knowledge_curator(self) -> None:
        payload = stock_suite_app._build_external_engine_dashboard_uncached()
        rows = [row for row in payload["engines"] if row.get("engine_id") == "knowledge-curator"]
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["connected"])
        self.assertTrue(rows[0]["round_trip_verified"])
        self.assertFalse(rows[0]["live_order_allowed"])
        self.assertEqual(10, payload["summary"]["engine_count"])

    def test_operating_focus_status_exposes_real_priority_percentages(self) -> None:
        focus = {
            "mode": "MARKET_EXECUTION_FOCUS",
            "market_open": True,
            "market_phase": "regular",
            "market_priority_active": True,
            "trading_focus_pct": 100,
            "research_focus_pct": 0,
            "heavy_research_allowed": False,
            "large_batch_jobs_allowed": False,
        }
        with patch.object(stock_suite_app, "build_operating_focus", return_value=focus):
            payload = stock_suite_app.build_operating_focus_status()
        self.assertEqual("매매 집중", payload["label"])
        self.assertEqual(100, payload["trading_focus_pct"])
        self.assertEqual(0, payload["research_focus_pct"])
        self.assertTrue(payload["focus_verified"])

    def test_external_engine_dashboard_force_bypasses_short_cache(self) -> None:
        fresh = {"ok": True, "schema": "fresh-external-engine-dashboard"}
        with patch.object(
            stock_suite_app.EXTERNAL_ENGINE_DASHBOARD_CACHE,
            "refresh_now",
            return_value=fresh,
        ) as refresh_now, patch.object(
            stock_suite_app.EXTERNAL_ENGINE_DASHBOARD_CACHE,
            "get",
        ) as cached_get:
            payload = stock_suite_app.build_external_engine_dashboard(force=True)

        self.assertEqual(fresh, payload)
        refresh_now.assert_called_once_with()
        cached_get.assert_not_called()

    def test_external_engine_dashboard_cache_rejects_another_account_runtime_tree(self) -> None:
        foreign_root = Path(r"C:\windows\system32\config\systemprofile\AppData\Local\CodexStock\engines")
        runtime_names = {
            "kis_trading_mcp",
            "vectorbt",
            "nautilus_trader",
            "quantconnect_lean",
            "openbb",
            "qlib",
            "backtrader",
            "freqtrade",
            "vnpy",
            "finrl",
        }
        payload = {
            "ok": True,
            "schema": "codexstock_external_engine_dashboard_v1",
            "runtime_scope": {
                "expected_engine_root": str(foreign_root),
                "engine_runtime_roots": {
                    name: str(foreign_root / name)
                    for name in runtime_names
                },
                "execution_account_independent": True,
            },
            "engines": [{
                "engine_id": "vectorbt",
                "live_order_allowed": False,
                "runtime_connected": True,
                "formal_connected": True,
                "connection_truth": {
                    "runtime_connected": True,
                    "round_trip_verified": True,
                    "proof_fresh": True,
                    "current_usable": True,
                    "formal_connected": True,
                },
                "success_evidence_ttl_seconds": 172800,
                "success_evidence_fresh": True,
                "recheck_due": False,
                "lightweight_recheck_at": datetime.now().astimezone().isoformat(),
                "lightweight_recheck_passed": True,
                "heavy_round_trip_recheck_started": False,
            }],
            "on_demand_audit": {"live_order_allowed": False},
            "sequential_execution_contract": {
                "mode": "one_heavy_engine_at_a_time",
                "configured_order": ["openbb", "lean", "vectorbt"],
                "max_concurrent_heavy_jobs": 1,
                "ledger_paths": {"ledger": "safe.jsonl"},
                "live_order_allowed": False,
            },
        }

        self.assertFalse(
            stock_suite_app._external_engine_dashboard_durable_cache_valid(payload)
        )

    def test_external_engine_dashboard_cache_accepts_only_current_safe_runtime_tree(self) -> None:
        if not stock_suite_app._external_engine_runtime_scope().get(
            "execution_account_independent"
        ):
            self.skipTest("private runtime-root contract is not included in the public repository")
        payload = {
            "ok": True,
            "schema": "codexstock_external_engine_dashboard_v1",
            "runtime_scope": stock_suite_app._external_engine_runtime_scope(),
            "engines": [{
                "engine_id": "vectorbt",
                "live_order_allowed": False,
                "runtime_connected": True,
                "formal_connected": True,
                "connection_truth": {
                    "runtime_connected": True,
                    "round_trip_verified": True,
                    "proof_fresh": True,
                    "current_usable": True,
                    "formal_connected": True,
                },
                "success_evidence_ttl_seconds": 172800,
                "success_evidence_fresh": True,
                "recheck_due": False,
                "lightweight_recheck_at": datetime.now().astimezone().isoformat(),
                "lightweight_recheck_passed": True,
                "heavy_round_trip_recheck_started": False,
            }],
            "on_demand_audit": {"live_order_allowed": False},
            "sequential_execution_contract": {
                "mode": "one_heavy_engine_at_a_time",
                "configured_order": ["openbb", "lean", "vectorbt"],
                "max_concurrent_heavy_jobs": 1,
                "ledger_paths": {"ledger": "safe.jsonl"},
                "live_order_allowed": False,
            },
        }

        self.assertTrue(
            stock_suite_app._external_engine_dashboard_durable_cache_valid(payload)
        )

    def test_external_engine_dashboard_cache_rejects_legacy_payload_without_sequential_contract(self) -> None:
        payload = {
            "ok": True,
            "schema": "codexstock_external_engine_dashboard_v1",
            "runtime_scope": stock_suite_app._external_engine_runtime_scope(),
            "engines": [{"engine_id": "vectorbt", "live_order_allowed": False}],
            "on_demand_audit": {"live_order_allowed": False},
        }

        self.assertFalse(
            stock_suite_app._external_engine_dashboard_durable_cache_valid(payload)
        )

    def test_external_engine_dashboard_verifies_on_demand_heavy_compute(self) -> None:
        if not stock_suite_app._external_engine_runtime_scope().get(
            "execution_account_independent"
        ):
            self.skipTest("private runtime-root contract is not included in the public repository")
        payload = stock_suite_app._build_external_engine_dashboard_uncached()
        audit = payload["on_demand_audit"]

        self.assertTrue(audit["ok"])
        self.assertEqual("passed", audit["status"])
        self.assertEqual(10, audit["verified_engine_count"])
        self.assertEqual(6, audit["spawn_on_demand_engine_count"])
        self.assertEqual(0, audit["persistent_heavy_engine_count"])
        self.assertFalse(audit["live_order_allowed"])
        self.assertTrue(payload["runtime_scope"]["execution_account_independent"])
        self.assertEqual(10, payload["runtime_scope"]["runtime_root_count"])
        self.assertTrue(
            stock_suite_app._external_engine_dashboard_durable_cache_valid(payload)
        )
        self.assertEqual("passed", payload["summary"]["on_demand_contract_status"])
        self.assertEqual(
            payload["summary"]["engine_count"],
            sum(payload["summary"]["operational_counts"].values()),
        )
        self.assertTrue(
            all(row.get("last_checked_at") for row in payload["engines"])
        )
        self.assertTrue(
            all(
                row.get("last_success_at")
                for row in payload["engines"]
                if row.get("formal_connected")
            )
        )
        self.assertEqual(
            sum(1 for row in payload["engines"] if row.get("runtime_connected")),
            payload["summary"]["connected_count"],
        )
        self.assertEqual(
            sum(1 for row in payload["engines"] if row.get("formal_connected")),
            payload["summary"]["formal_connected_count"],
        )
        self.assertGreaterEqual(
            payload["summary"]["connected_count"],
            payload["summary"]["formal_connected_count"],
        )
        self.assertTrue(payload["snapshot_id"].startswith("ops-"))
        self.assertTrue(
            all(row.get("snapshot_id") == payload["snapshot_id"] for row in payload["engines"])
        )
        self.assertEqual(
            payload["summary"]["engine_count"],
            sum(payload["summary"]["lifecycle_counts"].values()),
        )
        self.assertTrue(
            all(
                row.get("capability_lifecycle", {}).get("schema")
                == "codexstock_capability_lifecycle_v1"
                for row in payload["engines"]
            )
        )
        self.assertEqual(
            1,
            payload["sequential_execution_contract"]["max_concurrent_heavy_jobs"],
        )
        self.assertFalse(payload["sequential_execution_contract"]["live_order_allowed"])

    def test_external_engine_on_demand_audit_blocks_unsafe_runtime(self) -> None:
        engines = [
            {
                "engine_id": "unsafe-engine",
                "execution_policy": "heavy_always_on_daemon",
                "heavy_compute_policy": "always_on",
                "resident_component": True,
                "active_heavy_job_count": 2,
                "max_concurrent_heavy_jobs": 1,
                "live_order_allowed": True,
                "runtime": {"runtime_mode": "daemon"},
            }
        ]

        audit = stock_suite_app.build_external_engine_on_demand_audit(
            engines,
            max_concurrent_jobs=1,
        )

        self.assertFalse(audit["ok"])
        self.assertEqual("blocked", audit["status"])
        self.assertGreaterEqual(audit["blocker_count"], 4)
        self.assertEqual(1, audit["persistent_heavy_engine_count"])
        self.assertFalse(audit["live_order_allowed"])

    def test_market_priority_resource_gate_blocks_active_heavy_engine(self) -> None:
        focus = {"market_priority_active": True, "market_phase": "regular"}
        engine_dashboard = {
            "on_demand_audit": {
                "schema": "codexstock_external_engine_on_demand_audit_v1",
                "status": "passed",
                "active_heavy_job_count": 1,
                "persistent_heavy_engine_count": 0,
                "max_concurrent_external_jobs": 1,
            }
        }
        sqlite_audit = {
            "status": "ready",
            "summary": {"problem_sqlite_count": 0, "max_query_ms": 12.5},
        }

        gate = stock_suite_app.build_market_priority_resource_gate(
            focus=focus,
            engine_dashboard=engine_dashboard,
            sqlite_audit=sqlite_audit,
        )

        self.assertFalse(gate["ok"])
        self.assertEqual("defer_heavy_work", gate["status"])
        self.assertIn("market_priority_active_heavy_engine_running", gate["blockers"])
        self.assertTrue(gate["defer_heavy_work_now"])
        self.assertFalse(gate["live_order_allowed"])

    def test_storage_runtime_stability_gate_passes_on_demand_and_sqlite_ready(self) -> None:
        engine_dashboard = {
            "on_demand_audit": {
                "schema": "codexstock_external_engine_on_demand_audit_v1",
                "status": "passed",
                "active_heavy_job_count": 0,
                "persistent_heavy_engine_count": 0,
                "max_concurrent_external_jobs": 1,
            }
        }
        sqlite_audit = {
            "status": "ready",
            "summary": {"problem_sqlite_count": 0, "max_query_ms": 12.5},
        }

        gate = stock_suite_app.build_storage_runtime_stability_gate(
            engine_dashboard=engine_dashboard,
            sqlite_audit=sqlite_audit,
        )

        self.assertTrue(gate["ok"])
        self.assertEqual("ready", gate["status"])
        self.assertEqual("sqlite_first_jsonl_tail_fallback", gate["read_mode"])
        self.assertEqual("heavy_engines_on_demand_only", gate["engine_runtime_contract"])
        self.assertTrue(gate["heavy_work_allowed"])
        self.assertFalse(gate["live_order_allowed"])

    def test_storage_runtime_stability_gate_accepts_large_healthy_sqlite(self) -> None:
        engine_dashboard = {
            "on_demand_audit": {
                "schema": "codexstock_external_engine_on_demand_audit_v1",
                "status": "passed",
                "active_heavy_job_count": 0,
                "persistent_heavy_engine_count": 0,
                "max_concurrent_external_jobs": 1,
            }
        }
        sqlite_audit = {
            "ok": True,
            "status": "ready_large_healthy",
            "summary": {
                "problem_sqlite_count": 0,
                "maintenance_advisory_count": 1,
                "max_query_ms": 8.5,
            },
        }

        gate = stock_suite_app.build_storage_runtime_stability_gate(
            engine_dashboard=engine_dashboard,
            sqlite_audit=sqlite_audit,
        )

        self.assertTrue(gate["ok"])
        self.assertNotIn("sqlite_storage_not_ready", gate["blockers"])
        self.assertTrue(gate["heavy_work_allowed"])

    def test_storage_runtime_stability_gate_blocks_slow_sqlite_or_resident_heavy_engine(self) -> None:
        engine_dashboard = {
            "on_demand_audit": {
                "schema": "codexstock_external_engine_on_demand_audit_v1",
                "status": "blocked",
                "active_heavy_job_count": 2,
                "persistent_heavy_engine_count": 1,
                "max_concurrent_external_jobs": 1,
            }
        }
        sqlite_audit = {
            "status": "ready",
            "summary": {"problem_sqlite_count": 0, "max_query_ms": 410.0},
        }

        gate = stock_suite_app.build_storage_runtime_stability_gate(
            engine_dashboard=engine_dashboard,
            sqlite_audit=sqlite_audit,
            max_query_ms_allowed=250.0,
        )

        self.assertFalse(gate["ok"])
        self.assertEqual("review_required", gate["status"])
        self.assertIn("persistent_heavy_engine_detected", gate["blockers"])
        self.assertIn("external_engine_global_concurrency_exceeded", gate["blockers"])
        self.assertIn("sqlite_query_latency_exceeded", gate["blockers"])
        self.assertFalse(gate["heavy_work_allowed"])
        self.assertFalse(gate["unverified_result_affects_score"])
        self.assertFalse(gate["unverified_result_affects_live_candidate"])

    def test_market_priority_defers_openbb_crosscheck(self) -> None:
        focus = {"market_priority_active": True, "market_phase": "regular"}
        gate = {
            "ok": True,
            "schema": "codexstock_market_priority_resource_gate_v1",
            "defer_heavy_work_now": True,
        }
        with (
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch("app.stock_suite_app.build_market_priority_resource_gate", return_value=gate),
        ):
            deferred = stock_suite_app._market_priority_deferred_request(
                "POST",
                "/api/external-engines/openbb/crosscheck",
            )

        self.assertIsNotNone(deferred)
        self.assertEqual("DEFERRED_MARKET_PRIORITY", deferred["status"])
        self.assertEqual(gate, deferred["resource_gate"])
        self.assertFalse(deferred["live_order_allowed"])

    def test_stale_external_report_is_connected_warning_not_engine_failure(self) -> None:
        inbox = {
            "file_poller": {
                "running": True,
                "status": "SOURCE_STALE",
                "source_json_valid": True,
                "source_age_minutes": 400,
                "last_imported_at": "2026-07-14T13:13:40+09:00",
            },
            "summary": {},
            "verification_queue": {},
            "recent_receipts": [{"receipt_id": "receipt-1"}],
        }
        with (
            patch("app.stock_suite_app.external_signal_inbox_status", return_value=inbox),
            patch("app.stock_suite_app._external_search_latest_job", return_value={}),
        ):
            payload = stock_suite_app._build_external_engine_dashboard_uncached()
        scout = next(row for row in payload["engines"] if row.get("engine_id") == "external-info-scout")
        self.assertTrue(scout["connected"])
        self.assertTrue(scout["runtime_connected"])
        self.assertTrue(scout["adapter_ready"])
        self.assertTrue(scout["round_trip_verified"])
        self.assertFalse(scout["formal_connected"])
        self.assertEqual("round_trip_proven_evidence_stale", scout["connection_stage"])
        self.assertEqual("warning", scout["status"])
        self.assertFalse(scout["last_attempt_failed"])
        self.assertEqual("delayed", scout["operational_state"])
        self.assertEqual("연결됨·보고서 오래됨", scout["status_label"])
        self.assertEqual("external_report_stale", scout["root_cause_code"])
        self.assertEqual("high_research", scout["importance_level"])
        self.assertEqual("no_direct_order_impact", scout["order_impact"])
        self.assertTrue(scout["degraded_but_order_safe"])
        self.assertIn("background scan", scout["recovery_action"])
        self.assertEqual(1, payload["summary"]["warning_count"])

    def test_adapter_installation_is_not_counted_as_formal_connection(self) -> None:
        pending = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "vectorbt",
                "status": "ready",
                "connected": True,
                "runtime": {"last_run": {}},
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
        )
        proven = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "vectorbt",
                "status": "ready",
                "connected": True,
                "runtime": {
                    "last_run": {
                        "ok": True,
                        "finished_at_epoch": datetime.now().timestamp(),
                        "snapshot_id": "snapshot-1",
                    }
                },
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
        )
        failed = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "vectorbt",
                "engine_name": "vectorbt",
                "status": "ready",
                "connected": True,
                "runtime": {
                    "engine_name": "vectorbt",
                    "last_run": {"ok": False, "finished_at_epoch": 1_720_000_001},
                },
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
        )

        self.assertTrue(pending["adapter_ready"])
        self.assertTrue(pending["connected"])
        self.assertTrue(pending["runtime_connected"])
        self.assertFalse(pending["round_trip_verified"])
        self.assertFalse(pending["formal_connected"])
        self.assertTrue(proven["round_trip_verified"])
        self.assertTrue(proven["formal_connected"])
        self.assertTrue(proven["last_success_at"])
        self.assertTrue(failed["last_attempt_failed"])
        self.assertEqual(["vectorbt"], failed["failed_components"])
        self.assertEqual("round_trip_failed", failed["connection_stage"])

    def test_external_engine_stale_success_requires_bounded_recheck(self) -> None:
        stale_epoch = (datetime.now().astimezone() - timedelta(days=3)).timestamp()
        evidence = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "vectorbt",
                "engine_name": "vectorbt",
                "status": "ready",
                "connected": True,
                "heavy_compute_policy": "on_demand_only",
                "runtime": {
                    "engine_name": "vectorbt",
                    "last_run": {"ok": True, "finished_at_epoch": stale_epoch},
                },
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
        )

        self.assertTrue(evidence["round_trip_verified"])
        self.assertTrue(evidence["connected"])
        self.assertTrue(evidence["runtime_connected"])
        self.assertFalse(evidence["success_evidence_fresh"])
        self.assertFalse(evidence["formal_connected"])
        self.assertEqual("round_trip_proven_evidence_stale", evidence["connection_stage"])
        self.assertTrue(evidence["recheck_due"])
        self.assertTrue(evidence["lightweight_recheck_passed"])
        self.assertFalse(evidence["heavy_round_trip_recheck_started"])
        self.assertEqual(48 * 60 * 60, evidence["success_evidence_ttl_seconds"])

    def test_external_engine_diagnosis_distinguishes_order_gateway_from_research_delay(self) -> None:
        kis = stock_suite_app._external_engine_operational_diagnosis(
            {
                "engine_id": "kis-trading-mcp",
                "connection_stage": "adapter_ready_round_trip_pending",
                "connection_blockers": ["successful_round_trip_evidence_missing"],
                "runtime": {"blockers": ["paper_auth_missing"]},
                "live_order_allowed": False,
            },
            operational_state="verification_pending",
        )
        research = stock_suite_app._external_engine_operational_diagnosis(
            {
                "engine_id": "vectorbt",
                "connection_stage": "adapter_ready_round_trip_pending",
                "connection_blockers": ["successful_round_trip_evidence_missing"],
                "live_order_allowed": False,
            },
            operational_state="verification_pending",
        )

        self.assertEqual("round_trip_evidence_missing", kis["root_cause_code"])
        self.assertEqual("order_critical", kis["importance_level"])
        self.assertEqual("order_gateway_unavailable", kis["order_impact"])
        self.assertFalse(kis["degraded_but_order_safe"])
        self.assertIn("paper_auth_missing", kis["diagnosis_blockers"])
        self.assertEqual("round_trip_evidence_missing", research["root_cause_code"])
        self.assertEqual("research_critical", research["importance_level"])
        self.assertEqual("no_direct_order_impact", research["order_impact"])
        self.assertTrue(research["degraded_but_order_safe"])

    def test_external_engine_health_surface_carries_root_cause_and_recovery_action(self) -> None:
        dashboard = {
            "ok": True,
            "generated_at": "2026-07-18T09:00:00+09:00",
            "summary": {"engine_count": 1},
            "engines": [
                {
                    "engine_id": "vectorbt",
                    "display_name": "vectorbt",
                    "status": "preparing",
                    "operational_state": "verification_pending",
                    "connection_stage": "adapter_ready_round_trip_pending",
                    "root_cause_code": "round_trip_evidence_missing",
                    "root_cause": "Adapter exists but proof is missing.",
                    "diagnosis_blockers": ["successful_round_trip_evidence_missing"],
                    "importance_level": "research_critical",
                    "order_impact": "no_direct_order_impact",
                    "recovery_action": "Run vectorbt smoke proof.",
                    "degraded_but_order_safe": True,
                    "last_checked_at": "2026-07-18T09:00:00+09:00",
                    "last_success_at": "",
                }
            ],
        }

        surface = stock_suite_app._compact_external_engine_health_surface(dashboard)
        engine = surface["engines"][0]

        self.assertEqual("round_trip_evidence_missing", engine["root_cause_code"])
        self.assertEqual("Adapter exists but proof is missing.", engine["root_cause"])
        self.assertEqual(["successful_round_trip_evidence_missing"], engine["diagnosis_blockers"])
        self.assertEqual("research_critical", engine["importance_level"])
        self.assertEqual("no_direct_order_impact", engine["order_impact"])
        self.assertTrue(engine["degraded_but_order_safe"])
        self.assertEqual("Run vectorbt smoke proof.", engine["next_action"])

    def test_verified_improvement_cycle_proves_specialist_formal_connection(self) -> None:
        evidence = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "openbb",
                "status": "idle",
                "connected": False,
                "runtime": {"last_run": {}},
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
            improvement_status={
                "state": {
                    "cycle_id": "cycle-verified",
                    "status": "COMPLETED",
                    "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "engine_results": [
                        {
                            "engine_id": "openbb",
                            "execution_ok": True,
                            "contract_passed": True,
                            "quality_gate_passed": False,
                        }
                    ],
                }
            },
        )

        self.assertTrue(evidence["adapter_ready"])
        self.assertTrue(evidence["round_trip_verified"])
        self.assertTrue(evidence["formal_connected"])
        self.assertEqual("formal_connected", evidence["connection_stage"])
        self.assertEqual("verified_improvement_cycle_round_trip", evidence["connection_proof_type"])
        self.assertEqual("cycle-verified", evidence["improvement_cycle_id"])
        self.assertFalse(evidence["latest_improvement_quality_gate_passed"])

    def test_newer_worker_failure_supersedes_older_improvement_proof(self) -> None:
        failure_epoch = datetime.fromisoformat(
            "2026-07-18T15:00:00+09:00"
        ).timestamp()
        evidence = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "openbb",
                "engine_name": "OpenBB",
                "status": "ready",
                "connected": True,
                "heavy_compute_policy": "on_demand_only",
                "runtime": {
                    "engine_name": "OpenBB",
                    "last_run": {
                        "ok": False,
                        "finished_at_epoch": failure_epoch,
                    },
                },
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
            improvement_status={
                "state": {
                    "cycle_id": "cycle-old-success",
                    "status": "COMPLETED",
                    "finished_at": "2026-07-17T15:00:00+09:00",
                    "engine_results": [{
                        "engine_id": "openbb",
                        "execution_ok": True,
                        "contract_passed": True,
                        "quality_gate_passed": True,
                    }],
                },
            },
        )

        self.assertFalse(evidence["formal_connected"])
        self.assertEqual("round_trip_failed", evidence["connection_stage"])
        self.assertEqual("failed", evidence["latest_attempt_outcome"])
        self.assertTrue(evidence["improvement_proof_superseded_by_newer_failure"])
        self.assertEqual("NEWER_FAILURE_INVALIDATED_PROOF", evidence["evidence_freshness_status"])

    def test_old_on_demand_success_requires_reverification(self) -> None:
        evidence = stock_suite_app._external_engine_formal_connection_evidence(
            {
                "engine_id": "vectorbt",
                "status": "ready",
                "connected": True,
                "heavy_compute_policy": "on_demand_only",
                "runtime": {
                    "last_run": {
                        "ok": True,
                        "finished_at_epoch": 1_600_000_000,
                    }
                },
            },
            forge_jobs=[],
            scout_poller={},
            scout_inbox={},
            kis_gateway={},
        )

        self.assertFalse(evidence["formal_connected"])
        self.assertEqual("round_trip_proven_evidence_stale", evidence["connection_stage"])
        self.assertGreater(evidence["evidence_age_seconds"], 0)
        self.assertEqual(
            "ROUND_TRIP_PROOF_STALE_RECHECK_DUE",
            evidence["evidence_freshness_status"],
        )
        self.assertTrue(evidence["recheck_due"])

    def test_research_bundle_requires_all_four_subengines(self) -> None:
        now_epoch = datetime.now().timestamp()
        partial_runs = {
            "Backtrader": {"ok": True, "finished_at_epoch": now_epoch - 3},
            "Freqtrade": {"ok": True, "finished_at_epoch": now_epoch - 2},
            "vn.py": {"ok": True, "finished_at_epoch": now_epoch - 1},
            "FinRL": {},
        }
        complete_runs = {
            **partial_runs,
            "FinRL": {"ok": True, "finished_at_epoch": now_epoch},
        }

        def evidence(runs):
            return stock_suite_app._external_engine_formal_connection_evidence(
                {
                    "engine_id": "freqtrade-vn-py-backtrader-finrl",
                    "status": "ready",
                    "connected": True,
                    "runtime": {
                        "adapter_progress": {"connected": 4, "total": 4},
                        "subengine_last_runs": runs,
                    },
                },
                forge_jobs=[],
                scout_poller={},
                scout_inbox={},
                kis_gateway={},
            )

        self.assertFalse(evidence(partial_runs)["formal_connected"])
        self.assertTrue(evidence(complete_runs)["formal_connected"])
        self.assertEqual(
            "all_subengines_successful_round_trip",
            evidence(complete_runs)["connection_proof_type"],
        )

    def test_mcp_exposes_all_research_forge_tools_without_live_scope(self) -> None:
        from app import codexstock_mcp_server

        self.assertEqual(94, len(codexstock_mcp_server.RESEARCH_TOOL_NAMES))
        tool_names = {str(row.get("name")) for row in codexstock_mcp_server.TOOLS}
        self.assertTrue(set(codexstock_mcp_server.RESEARCH_TOOL_NAMES).issubset(tool_names))
        self.assertIn("codexstock_research_forge_integration_audit", tool_names)
        self.assertFalse(any("live_order" in name for name in codexstock_mcp_server.RESEARCH_TOOL_NAMES))

    def test_research_forge_integration_audit_proves_capability_consumption(self) -> None:
        payload = stock_suite_app.build_research_forge_integration_audit()

        self.assertTrue(payload["ok"])
        self.assertEqual("integrated", payload["status"])
        self.assertEqual(payload["capability_count"], payload["recognized_capability_count"])
        self.assertEqual(payload["gateway_tool_count"], payload["manifest_tool_count"])
        self.assertEqual(
            payload["gateway_tool_count"],
            payload["mcp_exposed_research_tool_count"],
        )
        self.assertEqual([], payload["blockers"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_order_allowed"])
        capability_ids = {row["id"] for row in payload["capabilities"]}
        self.assertIn("instrument_contracts", capability_ids)
        self.assertIn("paper_candidate_handoff", capability_ids)

    def test_legacy_tree_migration_is_non_destructive_and_one_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "legacy"
            target = root / "active"
            (source / "nested").mkdir(parents=True)
            (source / "nested" / "evidence.json").write_text("legacy", encoding="utf-8")
            (target / "nested").mkdir(parents=True)
            (target / "nested" / "evidence.json").write_text("user", encoding="utf-8")
            (source / "new.bin").write_bytes(b"123")

            first = bootstrap_user_data_tree(source, target, marker_name=".done.json")
            second = bootstrap_user_data_tree(source, target, marker_name=".done.json")

            self.assertTrue(first["ok"])
            self.assertEqual(first["copied_files"], 1)
            self.assertEqual((target / "nested" / "evidence.json").read_text(encoding="utf-8"), "user")
            self.assertTrue(second["skipped"])


if __name__ == "__main__":
    unittest.main()
