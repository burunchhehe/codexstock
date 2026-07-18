from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import codexstock_mcp_server
from app import stock_suite_app as suite


class ExternalSignalStage2BridgeTests(unittest.TestCase):
    def _paths(self, directory: str) -> dict[str, Path]:
        root = Path(directory)
        return {
            "latest": root / "latest.json",
            "snapshot": root / "snapshot.json",
            "queue": root / "queue.jsonl",
            "verification": root / "verification.jsonl",
            "results": root / "stage2-results.jsonl",
            "job": root / "stage2-job.json",
        }

    def _patch_paths(self, paths: dict[str, Path]):
        return patch.multiple(
            suite,
            EXTERNAL_SIGNAL_LATEST_FILE=paths["latest"],
            EXTERNAL_SIGNAL_STAGE2_SNAPSHOT_FILE=paths["snapshot"],
            EXTERNAL_SIGNAL_VERIFICATION_QUEUE_FILE=paths["queue"],
            EXTERNAL_SIGNAL_VERIFICATION_RESULT_FILE=paths["verification"],
            EXTERNAL_SIGNAL_STAGE2_RESULT_FILE=paths["results"],
            EXTERNAL_SIGNAL_STAGE2_JOB_STATE_FILE=paths["job"],
        )

    def _seed_ready_job(self, paths: dict[str, Path]) -> None:
        report_signature = "a" * 64
        dataset_hash = "b" * 64
        paths["latest"].write_text(
            json.dumps(
                {
                    "report_signature": report_signature,
                    "report": {
                        "generated_at": "2026-07-17T09:00:00+09:00",
                        "signals": [
                            {
                                "signal_id": "signal-005930-20260717",
                                "symbol": "005930",
                                "name": "Samsung Electronics",
                                "theme": "semiconductor",
                                "confidence": 0.91,
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        paths["snapshot"].write_text(
            json.dumps(
                {
                    "ready": True,
                    "report_signature": report_signature,
                    "snapshot_id": "snapshot-ready-1",
                    "dataset_hash": dataset_hash,
                    "symbols": ["005930"],
                }
            ),
            encoding="utf-8",
        )
        request = {
            "dedupe_key": "2026-07-17T09:00:00+09:00:signal-005930-20260717",
            "report_signature": report_signature,
            "signal_id": "signal-005930-20260717",
            "symbol": "005930",
            "name": "Samsung Electronics",
            "theme": "semiconductor",
            "confidence": 0.91,
            "status": "PENDING_CODEXSTOCK_CHECKS",
            "stage2_snapshot_id": "snapshot-ready-1",
            "stage2_dataset_hash": dataset_hash,
            "live_order_allowed": False,
            "news_verification": {
                "status": "EVIDENCE_READY_FOR_STAGE2",
                "checks": {
                    "original_body_evidence_passed": True,
                    "multi_source_evidence_passed": True,
                    "official_disclosure_gate_passed": True,
                },
            },
        }
        paths["queue"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        validation = {
            "dedupe_key": request["dedupe_key"],
            "report_signature": report_signature,
            "signal_id": request["signal_id"],
            "symbol": "005930",
            "status": "SNAPSHOT_VERIFIED_PENDING_STAGE2_RESULT",
            "stage2_snapshot_id": "snapshot-ready-1",
            "stage2_dataset_hash": dataset_hash,
            "snapshot_validation": {"passed": True},
            "live_order_allowed": False,
        }
        paths["verification"].write_text(json.dumps(validation) + "\n", encoding="utf-8")

    def _accepted_payload(self, job: dict[str, object]) -> dict[str, object]:
        fill_hash = "c" * 64
        evidence = {
            "fill_ledger_hash": fill_hash,
            "entry_exit_return_reason_evidence": {"passed": True},
            "return_reconciliation_evidence": {"passed": True},
            "exit_reason_alignment_evidence": {"passed": True},
            "fee_tax_slippage_evidence": {"passed": True},
            "unit_currency_audit_evidence": {"passed": True},
            "no_live_order_evidence": {"passed": True},
        }
        return {
            "stage2_job_id": job["stage2_job_id"],
            "contract_hash_echo": job["contract_hash"],
            "snapshot_id_echo": job["required_snapshot_id"],
            "dataset_hash_echo": job["required_dataset_hash"],
            "external_engine_name": "nautilustrader",
            "external_run_id": f"run:{job['contract_hash_prefix']}:signal-005930:1784240000",
            "external_runtime_mode_echo": "spawn_on_demand_only",
            "external_runtime_budget_evidence": {
                "actual_runtime_seconds": 2.5,
                "timeout_seconds": job["timeout_seconds"],
                "max_concurrent_external_jobs": 1,
            },
            "external_runtime_cleanup_evidence": {
                "cleanup_completed": True,
                "resident_process_count": 0,
                "temp_artifact_bytes": 0,
                "max_temp_artifact_bytes": job["max_temp_artifact_bytes"],
            },
            "validation_grade": "A",
            "engine_result": {
                "ok": True,
                "decision": "VERIFY_ONLY",
                "live_order_allowed": False,
                "snapshot_id": job["required_snapshot_id"],
                "dataset_hash": job["required_dataset_hash"],
                "result_hash": "d" * 64,
                "stage2_evidence_by_symbol": {"005930": evidence},
            },
        }

    def test_intraday_freshness_uses_report_cadence(self) -> None:
        now = datetime(2026, 7, 17, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        fresh = suite._external_signal_report_freshness(
            "2026-07-17T09:00:00+09:00",
            now=now,
        )
        stale = suite._external_signal_report_freshness(
            "2026-07-17T06:00:00+09:00",
            now=now,
        )

        self.assertTrue(fresh["fresh"])
        self.assertFalse(stale["fresh"])
        self.assertEqual(180, stale["max_age_minutes"])
        self.assertFalse(stale["candidate_pool_allowed"])
        self.assertFalse(stale["live_order_allowed"])

    def test_queue_contract_is_deterministic_and_on_demand_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory)
            self._seed_ready_job(paths)
            now = datetime(2026, 7, 17, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            with self._patch_paths(paths):
                first = suite.build_external_signal_stage2_queue(limit=20, now=now)
                second = suite.build_external_signal_stage2_queue(limit=20, now=now)

        self.assertEqual("ready", first["status"])
        self.assertEqual(1, first["ready_count"])
        self.assertEqual(
            first["next_ready_job"]["contract_hash"],
            second["next_ready_job"]["contract_hash"],
        )
        self.assertEqual("explicit_on_demand_only", first["execution_policy"])
        self.assertFalse(first["next_ready_job"]["score_allowed"])
        self.assertFalse(first["next_ready_job"]["live_order_allowed"])

    def test_stale_report_blocks_stage2_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory)
            self._seed_ready_job(paths)
            now = datetime(2026, 7, 17, 13, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            with self._patch_paths(paths):
                queue = suite.build_external_signal_stage2_queue(limit=20, now=now)

        self.assertEqual("blocked", queue["status"])
        self.assertEqual(0, queue["ready_count"])
        self.assertEqual(1, queue["blocker_counts"]["external_signal_report_stale"])

    def test_result_gate_accepts_exact_evidence_without_score_or_order_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory)
            self._seed_ready_job(paths)
            now = datetime(2026, 7, 17, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            with self._patch_paths(paths):
                queue = suite.build_external_signal_stage2_queue(limit=20, now=now)
                payload = self._accepted_payload(queue["next_ready_job"])
                result, status = suite.receive_external_signal_stage2_result(payload, now=now)
                completed = suite.build_external_signal_stage2_queue(limit=20, now=now)

        self.assertEqual(200, status)
        self.assertTrue(result["accepted_for_candidate_pool"])
        self.assertFalse(result["score_allowed"])
        self.assertFalse(result["live_order_allowed"])
        self.assertEqual("idle_all_completed", completed["status"])
        self.assertEqual(1, completed["completed_count"])

    def test_result_gate_rejects_hash_mismatch_and_live_order_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory)
            self._seed_ready_job(paths)
            now = datetime(2026, 7, 17, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            with self._patch_paths(paths):
                queue = suite.build_external_signal_stage2_queue(limit=20, now=now)
                payload = self._accepted_payload(queue["next_ready_job"])
                payload["contract_hash_echo"] = "e" * 64
                payload["engine_result"]["live_order_allowed"] = True
                result, status = suite.receive_external_signal_stage2_result(payload, now=now)

        self.assertEqual(409, status)
        self.assertFalse(result["accepted_for_candidate_pool"])
        self.assertIn("contract_hash_echo_mismatch", result["blockers"])
        self.assertIn("external_engine_live_order_boundary_failed", result["blockers"])

    def test_result_gate_rejects_incomplete_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory)
            self._seed_ready_job(paths)
            now = datetime(2026, 7, 17, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            with self._patch_paths(paths):
                queue = suite.build_external_signal_stage2_queue(limit=20, now=now)
                payload = self._accepted_payload(queue["next_ready_job"])
                payload["external_runtime_budget_evidence"].pop("actual_runtime_seconds")
                payload["external_runtime_cleanup_evidence"].pop("max_temp_artifact_bytes")
                result, status = suite.receive_external_signal_stage2_result(payload, now=now)

        self.assertEqual(409, status)
        self.assertFalse(result["accepted_for_candidate_pool"])
        self.assertIn("external_runtime_budget_evidence_incomplete", result["blockers"])
        self.assertIn("external_runtime_cleanup_evidence_incomplete", result["blockers"])

    def test_empty_historical_stage2_queue_is_healthy_idle(self) -> None:
        audit = {
            "stage2_handoff": {
                "stage2_snapshot_ready": True,
                "stage2_candidate_package_count": 6,
                "ready_count": 0,
                "blocked_count": 0,
                "duplicate_job_count": 0,
                "ready_queue_preview_count": 0,
                "contract_expected_outputs": [],
            }
        }
        with patch.object(suite, "_cached_tournament_reconciliation_health_audit", return_value=audit):
            queue_probe = suite._stage2_handoff_queue_feature_probe()
            gate_probe = suite._stage2_result_gate_feature_probe()

        self.assertTrue(queue_probe["ok"])
        self.assertEqual("idle_no_pending_jobs", queue_probe["status"])
        self.assertTrue(gate_probe["ok"])
        self.assertEqual("idle_no_pending_contract", gate_probe["status"])

    def test_on_demand_runner_falls_back_to_vectorbt_when_nautilus_cannot_load(self) -> None:
        stage2_job_id = "external-signal-stage2:005930:fallback"
        snapshot_id = "snapshot-fallback"
        dataset_hash = "b" * 64
        job = {
            "state": "ready_to_queue",
            "stage2_job_id": stage2_job_id,
            "symbol": "005930",
            "snapshot_symbols": ["005930"],
            "required_snapshot_id": snapshot_id,
            "required_dataset_hash": dataset_hash,
            "timeout_seconds": 180,
            "max_temp_artifact_bytes": 25_000_000,
            "contract_hash": "c" * 64,
            "contract_hash_prefix": "c" * 12,
            "replay_id": "signal-005930",
        }
        snapshot = {
            "ok": True,
            "runtime_dataset_payload": {"dataset_rows": [{"symbol": "005930"}]},
            "dataset_snapshot_preview": {
                "snapshot_id": snapshot_id,
                "dataset_hash": dataset_hash,
            },
        }
        evidence = {
            "validation_grade": "A",
            "fill_ledger_hash": "d" * 64,
        }
        vectorbt_result = {
            "ok": True,
            "decision": "VERIFY_ONLY",
            "live_order_allowed": False,
            "snapshot_id": snapshot_id,
            "dataset_hash": dataset_hash,
            "result_hash": "e" * 64,
            "stage2_evidence_by_symbol": {"005930": evidence},
        }
        with (
            patch.object(suite, "build_external_signal_stage2_queue", return_value={"jobs": [job]}),
            patch.object(
                suite.EXTERNAL_KNOWLEDGE,
                "build_common_snapshot_from_ohlcv_cache",
                return_value=snapshot,
            ),
            patch.object(
                suite.NAUTILUS_RUNTIME,
                "run_replay",
                return_value={
                    "ok": False,
                    "error": "runtime_dll_blocked",
                    "live_order_allowed": False,
                },
            ) as nautilus_run,
            patch.object(suite.VECTORBT_RUNTIME, "run_backtest", return_value=vectorbt_result) as vectorbt_run,
            patch.object(suite, "_external_signal_stage2_job_update", return_value={}),
            patch.object(
                suite,
                "receive_external_signal_stage2_result",
                return_value=({"accepted_for_candidate_pool": True}, 200),
            ) as result_gate,
        ):
            result = suite._run_external_signal_stage2_job_sync(stage2_job_id)

        self.assertTrue(result["ok"])
        self.assertEqual("vectorbt", result["engine_name"])
        self.assertEqual(2, len(result["engine_attempts"]))
        nautilus_run.assert_called_once()
        vectorbt_run.assert_called_once()
        submitted = result_gate.call_args.args[0]
        self.assertEqual("vectorbt", submitted["external_engine_name"])
        self.assertEqual("codexstock-on-demand-vectorbt-fallback", submitted["source"])
        self.assertFalse(submitted["engine_result"]["live_order_allowed"])

    def test_mcp_exposes_stage2_bridge_tools(self) -> None:
        names = {str(tool.get("name") or "") for tool in codexstock_mcp_server.TOOLS}
        self.assertTrue(
            {
                "codexstock_external_signal_stage2_queue",
                "codexstock_external_signal_stage2_result",
                "codexstock_external_signal_stage2_run",
                "codexstock_external_signal_stage2_status",
            }.issubset(names)
        )


if __name__ == "__main__":
    unittest.main()
