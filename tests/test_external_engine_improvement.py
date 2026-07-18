from __future__ import annotations

import json
import tempfile
import unittest
from math import isfinite
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.external_engine_improvement import ExternalEngineImprovementStore


class ExternalEngineImprovementTests(unittest.TestCase):
    @staticmethod
    def _result(engine_id: str, *, quality: bool = True) -> dict[str, object]:
        contracts = {
            "vectorbt": (
                "codexstock_vectorbt_portfolio_scenarios_v1",
                "evaluate_portfolio_scenarios",
            ),
            "qlib": (
                "codexstock_qlib_rolling_model_comparison_v1",
                "evaluate_rolling_model_comparison",
            ),
            "openbb": (
                "codexstock_openbb_fundamental_macro_calendar_v1",
                "crosscheck_fundamental_macro_calendar",
            ),
            "lean": (
                "codexstock_lean_market_lifecycle_v1",
                "validate_market_lifecycle",
            ),
            "nautilus": (
                "codexstock_nautilus_execution_stress_v1",
                "evaluate_execution_stress",
            ),
        }
        schema, action = contracts[engine_id]
        return {
            "ok": True,
            "schema": schema,
            "action": action,
            "engine_name": engine_id,
            "snapshot_id": "snapshot-1",
            "dataset_hash": "dataset-1",
            "result_hash": "a" * 64,
            "quality_gate": {
                "passed": quality,
                "domain_check_passed": quality,
            },
            "process_returncode": 0,
            "promotion_allowed": False,
            "live_order_allowed": False,
        }

    def test_valid_result_is_recorded_but_remains_research_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            evidence = store.validate_engine_result(
                cycle_id="cycle-1",
                engine_id="vectorbt",
                result=self._result("vectorbt"),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            rows = [
                json.loads(line)
                for line in store.runs_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertTrue(evidence["contract_passed"])
        self.assertTrue(evidence["learning_eligible"])
        self.assertFalse(evidence["live_order_allowed"])
        self.assertFalse(evidence["promotion_allowed"])
        self.assertEqual(evidence["evidence_hash"], rows[0]["evidence_hash"])

    def test_live_order_or_missing_hash_is_contract_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            unsafe = self._result("qlib")
            unsafe["live_order_allowed"] = True
            unsafe["result_hash"] = ""
            evidence = store.validate_engine_result(
                cycle_id="cycle-2",
                engine_id="qlib",
                result=unsafe,
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )

        self.assertFalse(evidence["contract_passed"])
        self.assertFalse(evidence["learning_eligible"])
        self.assertIn("live_order_boundary_missing", evidence["contract_errors"])
        self.assertIn("invalid_result_hash", evidence["contract_errors"])

    def test_candidate_score_requires_two_independent_strategy_engines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            vectorbt = store.validate_engine_result(
                cycle_id="cycle-3",
                engine_id="vectorbt",
                result=self._result("vectorbt"),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            one_engine = store.finalize_cycle(
                cycle_id="cycle-3-single",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[vectorbt],
            )
            qlib = store.validate_engine_result(
                cycle_id="cycle-4",
                engine_id="qlib",
                result=self._result("qlib"),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            two_engines = store.finalize_cycle(
                cycle_id="cycle-4",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[vectorbt, qlib],
            )
            overlay = store.learning_overlay("005930")

        self.assertEqual(0.0, one_engine["verified_lesson"]["candidate_score_delta"])
        self.assertTrue(two_engines["verified_lesson"]["strategy_corroborated"])
        self.assertGreater(two_engines["verified_lesson"]["candidate_score_delta"], 0.0)
        self.assertLessEqual(two_engines["verified_lesson"]["candidate_score_delta"], 2.0)
        self.assertLessEqual(overlay["score_delta"], 2.0)
        self.assertFalse(overlay["direct_order_authority"])

    def test_quality_failure_is_queued_for_retraining_not_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            failed = store.validate_engine_result(
                cycle_id="cycle-5",
                engine_id="nautilus",
                result=self._result("nautilus", quality=False),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            final = store.finalize_cycle(
                cycle_id="cycle-5",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[failed],
            )

        self.assertFalse(failed["learning_eligible"])
        self.assertEqual(0.0, final["verified_lesson"]["candidate_score_delta"])
        self.assertEqual("FINALIZING", final["state"]["status"])
        self.assertEqual("COMPLETED", final["status"])
        self.assertEqual(1, len(final["retraining_tasks"]))
        self.assertFalse(final["retraining_tasks"][0]["live_order_allowed"])
        self.assertFalse(final["retraining_tasks"][0]["promotion_allowed"])

    def test_mcp_exposes_improvement_status_and_research_only_run(self) -> None:
        from app import codexstock_mcp_server as mcp_server

        names = {str(tool.get("name") or "") for tool in mcp_server.TOOLS}
        self.assertIn("codexstock_external_improvement_status", names)
        self.assertIn("codexstock_external_improvement_run", names)
        self.assertIn("codexstock_external_improvement_status", mcp_server.ASK_AGENT_ROUTABLE_TOOLS)
        self.assertIn("codexstock_external_improvement_run", mcp_server.ASK_AGENT_ROUTABLE_TOOLS)

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "state": {"status": "IDLE"},
                "live_order_allowed": False,
                "promotion_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_external_improvement_status",
                {"lesson_limit": 3, "task_limit": 7},
            )

        http_json.assert_called_once_with(
            "GET",
            "/api/external-engines/improvement-loop/status",
            {"lesson_limit": 3, "task_limit": 7},
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["promotion_allowed"])

    def test_mcp_improvement_run_is_bounded_and_never_receives_order_arguments(self) -> None:
        from app import codexstock_mcp_server as mcp_server

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={
                "ok": True,
                "status": "QUEUED",
                "live_order_allowed": False,
                "promotion_allowed": False,
            },
        ) as http_json:
            result = mcp_server._call_tool(
                "codexstock_external_improvement_run",
                {
                    "symbols": "005930,000660",
                    "max_symbols": 99,
                    "rows": 9999,
                    "fold_count": 99,
                    "timeout_seconds": 9999,
                    "account": "must-not-forward",
                    "order": {"side": "BUY"},
                },
            )

        submitted = http_json.call_args.kwargs["payload"]
        self.assertEqual(10, submitted["max_symbols"])
        self.assertEqual(520, submitted["rows"])
        self.assertEqual(8, submitted["fold_count"])
        self.assertEqual(600, submitted["timeout_seconds"])
        self.assertNotIn("account", submitted)
        self.assertNotIn("order", submitted)
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertFalse(payload["promotion_allowed"])

    def test_mcp_status_prefers_terminal_resolution_over_stale_queue_rows(self) -> None:
        from app import codexstock_mcp_server as mcp_server

        payload = mcp_server._external_improvement_status_summary(
            {
                "ok": True,
                "state": {
                    "status": "COMPLETED",
                    "suppressed_exhausted_task_count": 2,
                    "retraining_resolution": {
                        "claimed_count": 3,
                        "resolved_count": 1,
                        "retry_queued_count": 0,
                        "exhausted_count": 2,
                        "active_count": 0,
                        "resolved": [
                            {"task_id": "lean-1", "engine_id": "lean", "status": "RESOLVED", "attempt_count": 3}
                        ],
                        "retry_queued": [],
                        "exhausted": [
                            {"task_id": "openbb-1", "engine_id": "openbb", "status": "EXHAUSTED", "attempt_count": 3},
                            {"task_id": "qlib-1", "engine_id": "qlib", "status": "EXHAUSTED", "attempt_count": 3},
                        ],
                    },
                },
                "latest_retraining_tasks": [
                    {"task_id": "lean-1", "engine_id": "lean", "status": "QUEUED"},
                    {"task_id": "openbb-1", "engine_id": "openbb", "status": "QUEUED"},
                    {"task_id": "qlib-1", "engine_id": "qlib", "status": "QUEUED"},
                ],
                "active_retraining_tasks": [],
            }
        )

        statuses = {
            row["engine_id"]: row["status"]
            for row in payload["latest_retraining_tasks"]
        }
        self.assertEqual(
            {"lean": "RESOLVED", "openbb": "EXHAUSTED", "qlib": "EXHAUSTED"},
            statuses,
        )
        self.assertEqual(2, payload["state"]["suppressed_exhausted_task_count"])
        self.assertEqual(2, len(payload["state"]["retraining_resolution"]["exhausted"]))

    def test_agent_improvement_question_routes_to_actual_loop_status(self) -> None:
        from app import codexstock_mcp_server as mcp_server

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={"ok": True, "state": {"status": "COMPLETED"}},
        ) as http_json:
            result = mcp_server._agent_local_fallback(
                "외부엔진 전략개선 루프와 재훈련 대기 상태 알려줘",
                max_chars=12000,
            )

        http_json.assert_called_once_with("GET", "/api/external-engines/improvement-loop/status")
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual("mcp-local-external-improvement-status", payload["handled_by"])

    def test_real_kis_orderbook_shape_is_normalized_without_nan(self) -> None:
        from app import stock_suite_app as stock_app

        with tempfile.TemporaryDirectory() as directory:
            events_root = Path(directory) / "events"
            path = events_root / "orderbook" / "2026-07-13" / "005930.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = []
            for second in range(3):
                rows.append(
                    {
                        "event_id": f"event-{second}",
                        "event_type": "orderbook",
                        "symbol": "005930",
                        "timestamp": f"2026-07-13T06:34:5{second}+00:00",
                        "source": "kis_readonly_websocket",
                        "payload": {
                            "asks": [[255000.0, 84389.0]],
                            "bids": [[254500.0, 64286.0]],
                            "expected_price": float("nan"),
                        },
                    }
                )
            path.write_text(
                "\n".join(json.dumps(row, allow_nan=True) for row in rows) + "\n",
                encoding="utf-8",
            )
            forge = SimpleNamespace(
                microstructure=lambda: SimpleNamespace(events_root=events_root),
            )
            with patch.object(stock_app, "RESEARCH_FORGE", forge):
                normalized = stock_app._external_improvement_orderbook_events(["005930"], limit=20)

        self.assertEqual(3, len(normalized))
        for row in normalized:
            payload = row["payload"]
            self.assertEqual("005930", row["symbol"])
            self.assertTrue(all(isfinite(float(value)) for value in payload.values()))
            self.assertNotIn("expected_price", payload)

    def test_lean_universe_bridge_emits_worker_and_source_date_fields(self) -> None:
        from app import stock_suite_app as stock_app

        universe = SimpleNamespace(
            status=lambda: {
                "datasets": [
                    {
                        "dataset_id": "official-universe",
                        "evidence": {
                            "coverage_start": "2016-01-01",
                            "coverage_end": "2026-12-31",
                            "includes_delisted": True,
                            "historical_query_allowed": True,
                            "grade": "official_listing_interval_history",
                        },
                    }
                ]
            },
            get=lambda dataset_id: {
                "content_hash": "sha256:test",
                "evidence": {"includes_delisted": True},
                "records": [
                    {
                        "symbol": "005930",
                        "listing_date": "1975-06-11",
                        "delisting_date": None,
                        "market": "KOSPI",
                        "security_type": "COMMON",
                    },
                    {
                        "symbol": "123456",
                        "listing_date": "2010-01-01",
                        "delisting_date": "2024-12-31",
                        "market": "KOSDAQ",
                        "security_type": "COMMON",
                    },
                ],
            },
        )
        forge = SimpleNamespace(universe=lambda: universe)
        with patch.object(stock_app, "RESEARCH_FORGE", forge):
            intervals, evidence = stock_app._external_improvement_universe_intervals(
                ["005930", "123456"],
                "2024-01-01",
                "2024-12-31",
            )

        self.assertTrue(evidence["ok"])
        self.assertEqual("1975-06-11", intervals[0]["start_date"])
        self.assertEqual(intervals[0]["start_date"], intervals[0]["listing_date"])
        self.assertIsNone(intervals[0]["end_date"])
        self.assertFalse(intervals[0]["delisted"])
        self.assertEqual("2024-12-31", intervals[1]["end_date"])
        self.assertEqual(intervals[1]["end_date"], intervals[1]["delisting_date"])
        self.assertTrue(intervals[1]["delisted"])

    def test_nonfinite_engine_report_fields_are_safely_persisted_as_null(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            result = self._result("nautilus")
            result["scenarios"] = [{"name": "partial_fill", "optional_metric": float("nan")}]
            evidence = store.validate_engine_result(
                cycle_id="cycle-nan",
                engine_id="nautilus",
                result=result,
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            persisted = json.loads(store.runs_path.read_text(encoding="utf-8").splitlines()[0])

        self.assertTrue(evidence["contract_passed"])
        self.assertIsNone(persisted["result_summary"].get("scenarios", [{}])[0].get("optional_metric"))

    def test_retraining_task_is_claimed_once_and_resolved_by_next_verified_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            failed = store.validate_engine_result(
                cycle_id="cycle-failed",
                engine_id="nautilus",
                result=self._result("nautilus", quality=False),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            first = store.finalize_cycle(
                cycle_id="cycle-failed",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[failed],
            )
            duplicate = store.finalize_cycle(
                cycle_id="cycle-failed-again",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[failed],
            )
            claimed = store.claim_retraining_tasks(cycle_id="cycle-recheck")
            passed = store.validate_engine_result(
                cycle_id="cycle-recheck",
                engine_id="nautilus",
                result=self._result("nautilus", quality=True),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            resolution = store.resolve_retraining_tasks(
                cycle_id="cycle-recheck",
                claimed_tasks=claimed,
                evidences=[passed],
            )
            status = store.status(task_limit=10)
            queue_rows = store.retraining_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(first["retraining_tasks"][0]["task_id"], duplicate["retraining_tasks"][0]["task_id"])
        self.assertEqual(1, len(queue_rows))
        self.assertEqual(1, len(claimed))
        self.assertEqual("CLAIMED", claimed[0]["status"])
        self.assertEqual(1, claimed[0]["attempt_count"])
        self.assertEqual(1, resolution["resolved_count"])
        self.assertEqual(0, resolution["active_count"])
        self.assertEqual([], status["active_retraining_tasks"])
        self.assertEqual("RESOLVED", status["latest_retraining_tasks"][0]["status"])

    def test_retraining_failure_requeues_then_exhausts_at_bounded_attempt_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExternalEngineImprovementStore(Path(directory))
            failed = store.validate_engine_result(
                cycle_id="cycle-seed",
                engine_id="qlib",
                result=self._result("qlib", quality=False),
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
            )
            store.finalize_cycle(
                cycle_id="cycle-seed",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[failed],
            )
            resolutions = []
            for attempt in range(1, 4):
                cycle_id = f"cycle-retry-{attempt}"
                claimed = store.claim_retraining_tasks(cycle_id=cycle_id)
                self.assertEqual(1, len(claimed))
                self.assertEqual(attempt, claimed[0]["attempt_count"])
                resolutions.append(
                    store.resolve_retraining_tasks(
                        cycle_id=cycle_id,
                        claimed_tasks=claimed,
                        evidences=[failed],
                    )
                )
            repeated = store.finalize_cycle(
                cycle_id="cycle-after-exhaustion",
                symbols=["005930"],
                snapshot_id="snapshot-1",
                dataset_hash="dataset-1",
                evidences=[failed],
            )
            queue_rows = [
                json.loads(line)
                for line in store.retraining_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            status = store.status(task_limit=10)
            fourth_claim = store.claim_retraining_tasks(cycle_id="cycle-no-fourth-attempt")

        self.assertEqual(1, resolutions[0]["retry_queued_count"])
        self.assertEqual(1, resolutions[1]["retry_queued_count"])
        self.assertEqual(1, resolutions[2]["exhausted_count"])
        self.assertEqual(0, resolutions[2]["active_count"])
        self.assertEqual(1, len(queue_rows))
        self.assertEqual(0, repeated["state"]["new_retraining_task_count"])
        self.assertEqual(1, repeated["state"]["suppressed_exhausted_task_count"])
        self.assertEqual("EXHAUSTED", status["latest_retraining_tasks"][0]["status"])
        self.assertEqual([], status["active_retraining_tasks"])
        self.assertEqual([], fourth_claim)


if __name__ == "__main__":
    unittest.main()
