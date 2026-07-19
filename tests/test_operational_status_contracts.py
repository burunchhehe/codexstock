import json
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import app.stock_suite_app as stock_app


class OperationalStatusContractTests(unittest.TestCase):
    @staticmethod
    def _forward_observation_rows(start: date, end: date) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        previous_hash = ""
        for index, session_date in enumerate(
            stock_app._promotion_forward_session_dates(start, end),
            start=1,
        ):
            row: dict[str, object] = {
                "schema": "codexstock_promotion_forward_observation_v1",
                "id": f"PFO-TEST-{index:04d}",
                "observed_date": session_date.isoformat(),
                "observed_at": f"{session_date.isoformat()}T16:00:00+09:00",
                "source": "unit-test",
                "result_status": "no_due_candidate",
                "market_session_verified": True,
                "post_market_window_verified": True,
                "operating_focus_mode": "DAILY_REVIEW_FOCUS",
                "eligible_candidate_count": 0,
                "created_rehearsal_count": 0,
                "filled_rehearsal_count": 0,
                "candidate_result_count": 0,
                "candidate_result_digest": [],
                "candidate_result_hash": stock_app._promotion_forward_candidate_digest_hash([]),
                "previous_observation_hash": previous_hash,
                "paper_only": True,
                "live_order_allowed": False,
                "real_execution": "BLOCKED",
            }
            row["observation_hash"] = stock_app._promotion_forward_observation_hash(row)
            previous_hash = str(row["observation_hash"])
            rows.append(row)
        return rows

    def test_runtime_deployment_freshness_detects_source_change_after_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "stock_suite_app.py"
            source.write_text("version = 1\n", encoding="utf-8")
            loaded_stat = source.stat()
            current = stock_app.build_runtime_deployment_freshness_status(
                source_path=source,
                loaded_mtime_ns=loaded_stat.st_mtime_ns,
                loaded_size_bytes=loaded_stat.st_size,
                loaded_at="2026-07-17T13:33:09+09:00",
            )
            source.write_text("version = 2\nchanged = True\n", encoding="utf-8")
            stale = stock_app.build_runtime_deployment_freshness_status(
                source_path=source,
                loaded_mtime_ns=loaded_stat.st_mtime_ns,
                loaded_size_bytes=loaded_stat.st_size,
                loaded_at="2026-07-17T13:33:09+09:00",
            )

        self.assertTrue(current["ok"])
        self.assertEqual("current", current["status"])
        self.assertFalse(current["restart_required"])
        self.assertFalse(current["live_order_allowed"])
        self.assertFalse(stale["ok"])
        self.assertEqual("restart_required", stale["status"])
        self.assertTrue(stale["source_changed_since_runtime_start"])
        self.assertTrue(stale["restart_required"])
        self.assertIn("runtime_loaded_source_outdated", stale["blockers"])
        self.assertFalse(stale["live_order_allowed"])

    def test_quote_reference_restores_raw_price_when_recent_official_anchor_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memory_path = root / "memory.json"
            verified_path = root / "verified.json"
            missing_screener = root / "missing-screener.json"
            missing_radar = root / "missing-radar.json"
            memory_path.write_text(
                json.dumps({"top_candidates": [{"symbol": "000660", "price": 1_842_000}]}),
                encoding="utf-8",
            )
            verified_path.write_text("{}", encoding="utf-8")
            anchor = {
                "symbol": "000660",
                "price": 1_842_000,
                "source": "KIS_VERIFIED_CACHE",
                "verified_quote_age_seconds": 30,
            }
            with (
                patch.object(stock_app, "AGENT_SCREENER_CACHE_FILE", missing_screener),
                patch.object(stock_app, "AGENT_RADAR_CACHE_FILE", missing_radar),
                patch.object(stock_app, "AGENT_MEMORY_FILE", memory_path),
                patch.object(stock_app, "VERIFIED_QUOTE_CACHE_FILE", verified_path),
                patch("app.stock_suite_app._load_verified_official_quote", return_value=anchor),
            ):
                stock_app.QUOTE_REFERENCE_CANDIDATE_CACHE.clear()
                stock_app.QUOTE_REFERENCE_SOURCE_CACHE.clear()
                result = stock_app.quote_reference_candidates("000660", max_items=3)

        self.assertEqual(1_842_000, result[0]["price"])
        self.assertEqual(1, result[0]["scale_divisor"])
        self.assertEqual("official_anchor_match", result[0]["confidence"])
        self.assertEqual(1_842_000, result[0]["official_anchor_price"])

    def test_quote_reference_keeps_scaled_guess_when_official_anchor_is_far_away(self):
        row = {
            "price": 184_200,
            "raw_price": 1_842_000,
            "scale_divisor": 10,
            "confidence": "scaled",
        }
        result = stock_app._reconcile_quote_reference_with_official_anchor(
            row,
            {"price": 300_000, "source": "KIS_VERIFIED_CACHE"},
        )

        self.assertEqual(row, result)

    def test_quote_health_separates_official_marks_from_safe_fallback_quarantine(self):
        official_audit = {"ok": True, "summary": {"status": "ok"}}
        official_snapshot = {"ok": True, "summary": {"status": "ok"}, "rows": [], "marks": {}}
        fallback_snapshot = {
            "ok": True,
            "summary": {"status": "watch"},
            "marks": {},
            "rows": [
                {
                    "symbol": "NVDA",
                    "unit_status": "watch",
                    "official_mark_eligible": False,
                    "source": "MARKET_CACHE",
                }
            ],
        }
        with (
            patch.object(stock_app, "QUOTE_HEALTH_BUNDLE_CACHE", None),
            patch("app.stock_suite_app.build_quote_unit_audit", return_value=official_audit) as quote_audit,
            patch(
                "app.stock_suite_app.build_common_quote_snapshot",
                side_effect=[official_snapshot, fallback_snapshot],
            ) as snapshots,
        ):
            result = stock_app._quote_health_probe_bundle(ttl_seconds=0)

        self.assertEqual(["005930", "000660"], quote_audit.call_args.kwargs["symbols"])
        self.assertEqual(["005930", "000660"], snapshots.call_args_list[0].kwargs["symbols"])
        self.assertEqual(["NVDA"], snapshots.call_args_list[1].kwargs["symbols"])
        self.assertEqual("safe_quarantine", result["fallback_quarantine"]["status"])
        self.assertTrue(result["fallback_quarantine"]["ok"])

    def test_position_health_keeps_raw_watch_detail_but_ignores_safe_missing_mark(self):
        raw = {
            "ok": True,
            "summary": {"status": "watch", "active_position_blocker_count": 0},
            "blocked": [],
            "watch": [
                {
                    "symbol": "005930",
                    "issues": [],
                    "warnings": ["common_quote_snapshot_not_official_mark"],
                }
            ],
        }
        with patch("app.stock_suite_app.build_position_unit_audit", return_value=raw):
            result = stock_app._position_unit_health_probe()

        self.assertTrue(result["ok"])
        self.assertEqual("ready_with_safe_quarantine", result["status"])
        self.assertEqual("watch", result["raw_summary"]["status"])
        self.assertEqual("watch", result["summary"]["audit_status"])
        self.assertEqual(0, result["summary"]["actionable_watch_count"])

    def test_position_health_keeps_actionable_value_warning_degraded(self):
        raw = {
            "ok": True,
            "summary": {"status": "watch", "active_position_blocker_count": 0},
            "blocked": [],
            "watch": [
                {
                    "symbol": "005930",
                    "issues": [],
                    "warnings": ["value_quantity_price_mismatch_ratio:7.00"],
                }
            ],
        }
        with patch("app.stock_suite_app.build_position_unit_audit", return_value=raw):
            result = stock_app._position_unit_health_probe()

        self.assertFalse(result["ok"])
        self.assertEqual("review_required", result["status"])
        self.assertEqual(1, result["summary"]["actionable_watch_count"])

    def test_stopped_replay_worker_is_scheduled_not_broken_outside_large_batch_window(self):
        status = {"ok": True, "status": "stopped", "running": False, "busy": False}
        with patch(
            "app.stock_suite_app.build_operating_focus",
            return_value={
                "mode": "MARKET_PRIORITY",
                "large_batch_jobs_allowed": False,
                "market_priority_active": True,
                "large_batch_schedule": "weekend",
            },
        ):
            result = stock_app._scheduled_replay_worker_health_probe(lambda: status, "test worker")

        self.assertTrue(result["ok"])
        self.assertTrue(result["intentionally_paused"])
        self.assertEqual("stopped", result["raw_status"])
        self.assertEqual("scheduled_for_market_closed_day", result["status"])

    def test_stopped_replay_worker_stays_degraded_when_large_batch_is_allowed(self):
        status = {"ok": True, "status": "stopped", "running": False, "busy": False}
        with patch(
            "app.stock_suite_app.build_operating_focus",
            return_value={"large_batch_jobs_allowed": True, "market_priority_active": False},
        ):
            result = stock_app._scheduled_replay_worker_health_probe(lambda: status, "test worker")

        self.assertFalse(result["intentionally_paused"])
        self.assertEqual("stopped", result["status"])

    def test_finished_replay_worker_is_healthy_idle_even_in_large_batch_window(self):
        status = {
            "ok": True,
            "status": "stopped",
            "running": False,
            "busy": False,
            "last_result": {"ok": True, "status": "queue_complete"},
        }
        with patch(
            "app.stock_suite_app.build_operating_focus",
            return_value={"large_batch_jobs_allowed": True, "market_priority_active": False},
        ):
            result = stock_app._scheduled_replay_worker_health_probe(lambda: status, "test worker")

        self.assertTrue(result["ok"])
        self.assertTrue(result["completed_idle"])
        self.assertFalse(result["intentionally_paused"])
        self.assertEqual("completed_idle", result["status"])

    def test_radar_health_reads_fresh_cache_without_network_collection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "radar.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "saved_at": time.time(),
                        "payload": {
                            "generated_at": "2026-07-17T11:00:00+09:00",
                            "symbols": ["005930"],
                            "news": [{"symbol": "005930", "source_status": "ready", "message": "정상"}],
                            "financials": [{"symbol": "005930"}],
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stock_app, "AGENT_RADAR_CACHE_FILE", cache_path),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={"market_priority_active": True},
                ),
                patch("app.stock_suite_app.build_agent_radar") as network_collection,
            ):
                result = stock_app._agent_radar_health_probe()

        network_collection.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertTrue(result["fresh"])
        self.assertEqual("ready_cached", result["status"])
        self.assertEqual(0, result["news_source_warning_count"])
        self.assertFalse(result["network_called"])

    def test_radar_health_preserves_real_news_source_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "radar.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "saved_at": time.time(),
                        "payload": {
                            "generated_at": "2026-07-17T11:00:00+09:00",
                            "symbols": ["005930"],
                            "news": [
                                {
                                    "symbol": "005930",
                                    "source_status": "error",
                                    "message": "read timeout",
                                }
                            ],
                            "financials": [{"symbol": "005930"}],
                        },
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(stock_app, "AGENT_RADAR_CACHE_FILE", cache_path),
                patch(
                    "app.stock_suite_app.build_operating_focus",
                    return_value={"market_priority_active": True},
                ),
            ):
                result = stock_app._agent_radar_health_probe()

        self.assertTrue(result["ok"])
        self.assertEqual("ready_cached_with_source_warnings", result["status"])
        self.assertEqual(1, result["news_source_warning_count"])

    def test_live_risk_monitor_restore_requires_current_authorization_and_live_path(self):
        policy = {
            "delegated_live_autonomy_enabled": True,
            "live_pilot_enabled": True,
            "live_execution_enabled": True,
            "emergency_halt": False,
            "day_halted": False,
        }
        with patch("app.stock_suite_app.build_delegated_live_authorization", return_value={"valid_today": True}):
            self.assertTrue(stock_app._delegated_risk_monitor_should_restore(policy))
        with patch("app.stock_suite_app.build_delegated_live_authorization", return_value={"valid_today": False}):
            self.assertFalse(stock_app._delegated_risk_monitor_should_restore(policy))
        with patch("app.stock_suite_app.build_delegated_live_authorization", return_value={"valid_today": True}):
            self.assertFalse(stock_app._delegated_risk_monitor_should_restore({**policy, "day_halted": True}))
            self.assertFalse(stock_app._delegated_risk_monitor_should_restore({**policy, "live_execution_enabled": False}))

    def test_quick_worker_board_reports_complete_seven_worker_roster(self):
        now = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        meeting = {
            "created_at": now,
            "top_candidate": {"symbol": "005930", "name": "삼성전자"},
        }
        daemon = SimpleNamespace(
            running=False,
            current_activity={},
            last_error="",
            thread=None,
        )
        memory = {
            "vault": "runtime-vault",
            "cycle_count": 3,
            "top_candidates": [{"symbol": "005930", "name": "삼성전자", "score": 72}],
            "historical_replay_attempt_count": 8,
            "historical_replay_unique_context_count": 5,
            "paper_rehearsal_memory_count": 4,
            "market_reflection_memory_count": 2,
            "capital_challenge_memory_count": 1,
            "latest_paper_rehearsal_memory": {"created_at": now},
            "latest_market_reflection_memory": {"created_at": now},
            "knowledge_graph": {"node_count": 6, "edge_count": 7, "updated_at": now},
        }
        minute = {
            "ok": True,
            "created_at": now,
            "count": 5,
            "top": {"symbol": "005930", "name": "삼성전자"},
            "message": "최근 분봉 점검 완료",
        }
        broker = {"ok": True, "created_at": now, "count": 0, "latest_line": "체결 0건", "message": "체결 점검"}
        account = {"ok": True, "snapshot_at": now, "change_count": 0, "message": "변화 없음"}

        with (
            patch.object(stock_app, "AI_WORKER_STATUS_QUICK_CACHE", None),
            patch.object(stock_app, "AI_DAEMON", daemon),
            patch("app.stock_suite_app.build_operating_focus", return_value={"market_priority_active": False, "market_open": False}),
            patch(
                "app.stock_suite_app.recent_ai_staff_meeting_snapshot",
                return_value={
                    "latest": meeting,
                    "manual_quick": meeting,
                    "auto": meeting,
                },
            ),
            patch("app.stock_suite_app.latest_live_account_change_quick_summary", return_value=account),
            patch("app.stock_suite_app.latest_intraday_minute_check_quick_summary", return_value=minute),
            patch("app.stock_suite_app.latest_broker_execution_check_quick_summary", return_value=broker),
            patch.object(stock_app.MEMORY, "summary", return_value=memory),
            patch.object(stock_app.OPS, "approvals", return_value=[]),
            patch.object(stock_app.OPS, "pending_telegram_outbox", return_value=[]),
            patch("app.stock_suite_app._today_live_submits", return_value=[]),
        ):
            result = stock_app.build_ai_worker_status_quick(ttl_seconds=0)

        expected = set(stock_app.AI_RUNTIME_WORKER_IDS)
        self.assertEqual(expected, {row["id"] for row in result["workers"]})
        self.assertEqual(7, result["summary"]["total"])
        self.assertTrue(result["roster"]["complete"])
        self.assertEqual([], result["roster"]["missing_ids"])
        self.assertIs(result["workers"], result["worker_board"]["workers"])
        self.assertFalse(result["current_task"]["real_order_allowed"])
        self.assertTrue(result["snapshot_id"].startswith("ops-"))
        self.assertEqual(result["snapshot_id"], result["worker_board"]["snapshot_id"])
        self.assertEqual(result["sequence_number"], result["worker_board"]["sequence_number"])
        self.assertEqual("ai_worker_status_quick", result["source_component"])
        self.assertTrue(result["expires_at"])

    def test_live_execution_authority_separates_capable_enabled_and_authorized(self):
        trading_date = stock_app.today_kst()
        policy = {
            "live_execution_enabled": True,
            "delegated_live_autonomy_enabled": True,
            "delegated_live_authorization_confirmed": True,
            "delegated_live_authorized_date": trading_date,
            "delegated_live_authorized_at": f"{trading_date}T08:00:00+09:00",
            "delegated_live_authorization_source": "unit-test",
            "emergency_halt": False,
            "buy_blocked": False,
            "day_halted": False,
        }
        with patch.object(stock_app.OPS, "autotrade_policy", return_value=policy):
            result = stock_app.build_live_execution_authority_contract()

        self.assertEqual("CAPABLE", result["capability_status"])
        self.assertEqual("ENABLED", result["enablement_status"])
        self.assertEqual("ENABLED", result["delegation_status"])
        self.assertEqual("AUTHORIZED_TODAY", result["authorization_status"])
        self.assertTrue(result["delegated_submission_gate_open"])
        self.assertTrue(result["not_an_order_decision"])

    def test_meeting_snapshot_reads_tail_once_and_reuses_unchanged_cache(self):
        rows = [
            {
                "id": "auto-1",
                "source": "daemon-cycle",
                "note": {"source_group": "auto"},
            },
            {
                "id": "manual-1",
                "source": "manual-command",
                "quick": True,
                "note": {"source_group": "manual"},
            },
            {
                "id": "latest-1",
                "source": "daemon-cycle",
                "note": {"source_group": "auto"},
            },
        ]
        with (
            patch.object(stock_app, "AI_STAFF_MEETING_SNAPSHOT_CACHE", None),
            patch(
                "app.stock_suite_app._ai_staff_meeting_file_signature",
                return_value=(123, 456),
            ),
            patch("app.stock_suite_app._read_jsonl", return_value=rows) as reader,
        ):
            first = stock_app.recent_ai_staff_meeting_snapshot()
            second = stock_app.recent_ai_staff_meeting_snapshot()

        self.assertEqual(1, reader.call_count)
        self.assertEqual("latest-1", first["latest"]["id"])
        self.assertEqual("manual-1", first["manual_quick"]["id"])
        self.assertEqual("latest-1", first["auto"]["id"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])

        compact = stock_app._compact_ai_staff_meeting_for_status(
            {
                **rows[-1],
                "messages": [{"message": "x" * 100_000}],
                "top_candidate": {"symbol": "005930", "name": "삼성전자", "score": 72},
                "decision": {"label": "보류", "confidence": 0.5},
                "next_actions": ["재검증"],
            }
        )
        self.assertNotIn("messages", compact)
        self.assertEqual("005930", compact["top_candidate"]["symbol"])
        self.assertEqual("보류", compact["decision"]["label"])
        self.assertLess(len(json.dumps(compact, ensure_ascii=False)), 10_000)

    def test_python_thread_activity_exposes_names_without_variables(self):
        result = stock_app.build_python_thread_activity()

        self.assertTrue(result["ok"])
        self.assertFalse(result["variables_exposed"])
        self.assertFalse(result["live_order_allowed"])
        self.assertTrue(any(row["name"] == "MainThread" for row in result["threads"]))
        self.assertTrue(all("stack" in row for row in result["threads"]))

    def test_agent_memory_summary_uses_small_durable_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memory = stock_app.AgentMemory(root / "vault", root / "memory.json")
            memory.save(
                {
                    "cycles": [
                        {"id": f"cycle-{index}", "payload": "x" * 1000}
                        for index in range(20)
                    ],
                    "candidates": {
                        "005930": {"symbol": "005930", "score": 72},
                    },
                    "lessons": ["lesson"],
                    "historical_replay_memories": [
                        {
                            "strategy_id": "ma",
                            "start_date": "2020-01-01",
                            "end_date": "2020-12-31",
                            "symbols": ["005930"],
                            "repetition_count": 3,
                        }
                    ],
                }
            )
            first = memory.summary()
            memory._summary_cache = None
            with patch.object(
                memory,
                "load",
                side_effect=AssertionError("full memory must not be reparsed"),
            ):
                second = memory.summary()
            persisted = json.loads(memory.summary_path.read_text(encoding="utf-8"))
            summary_size = memory.summary_path.stat().st_size
            memory_size = memory.json_path.stat().st_size

        self.assertEqual(20, first["cycle_count"])
        self.assertEqual(3, second["historical_replay_attempt_count"])
        self.assertEqual(
            "codexstock_agent_memory_summary_cache_v1",
            persisted["schema"],
        )
        self.assertLess(summary_size, memory_size)

    def test_quick_worker_status_singleflights_concurrent_builds(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def build(ttl_seconds=15):
            calls.append(ttl_seconds)
            entered.set()
            release.wait(2)
            return {"ok": True, "workers": [], "cache_ttl_seconds": ttl_seconds}

        with (
            patch.object(stock_app, "AI_WORKER_STATUS_QUICK_CACHE", None),
            patch(
                "app.stock_suite_app._build_ai_worker_status_quick_uncached",
                side_effect=build,
            ),
        ):
            first = threading.Thread(
                target=lambda: results.append(
                    stock_app.build_ai_worker_status_quick(ttl_seconds=60)
                )
            )
            second = threading.Thread(
                target=lambda: results.append(
                    stock_app.build_ai_worker_status_quick(ttl_seconds=60)
                )
            )
            first.start()
            self.assertTrue(entered.wait(1))
            second.start()
            release.set()
            first.join(2)
            second.join(2)

        self.assertEqual([60], calls)
        self.assertEqual(2, len(results))
        self.assertEqual(1, sum(1 for row in results if row.get("cached") is True))

    def test_normalizer_exposes_missing_worker_contract(self):
        result = stock_app._normalize_ai_worker_board(
            {"workers": [{"id": "researcher", "name": "연구 AI"}]},
            running=False,
        )

        self.assertFalse(result["roster"]["complete"])
        self.assertIn("operator", result["roster"]["missing_ids"])

    def test_normalizer_does_not_call_stale_workers_active(self):
        old = (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=2)).isoformat(timespec="seconds")
        recent = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        result = stock_app._normalize_ai_worker_board(
            {
                "workers": [
                    {"id": "researcher", "updated_at": recent},
                    {"id": "research_market", "last_evidence_at": old},
                    {"id": "operator", "last_evidence_at": old},
                    {"id": "risk", "last_evidence_at": old},
                ]
            },
            running=True,
        )
        by_id = {row["id"]: row for row in result["workers"]}

        self.assertEqual("working", by_id["researcher"]["status_code"])
        for worker_id in ("research_market", "operator", "risk"):
            self.assertEqual("stale", by_id[worker_id]["status_code"])
            self.assertFalse(by_id[worker_id]["is_active"])
            self.assertEqual("근거 갱신 필요", by_id[worker_id]["state"])
            self.assertEqual("STALE", by_id[worker_id]["evidence_freshness_status"])
            self.assertFalse(by_id[worker_id]["decision_eligible"])
            self.assertEqual("evidence_older_than_role_threshold", by_id[worker_id]["status_reason"])
        self.assertEqual(3, result["status_counts"]["stale"])
        self.assertTrue(result["evidence_freshness"]["all_active_statuses_truthful"])

    def test_normalizer_uses_stricter_market_hour_thresholds(self):
        ten_minutes_old = (
            datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(minutes=10)
        ).isoformat(timespec="seconds")
        result = stock_app._normalize_ai_worker_board(
            {
                "market_execution_focus": True,
                "workers": [
                    {"id": "research_market", "last_evidence_at": ten_minutes_old},
                    {"id": "research_fundamental", "last_evidence_at": ten_minutes_old},
                    {"id": "operator", "last_evidence_at": ten_minutes_old},
                    {"id": "risk", "last_evidence_at": ten_minutes_old},
                ],
            },
            running=True,
        )
        by_id = {row["id"]: row for row in result["workers"]}

        self.assertEqual("stale", by_id["research_market"]["status_code"])
        self.assertEqual(300, by_id["research_market"]["evidence_threshold_seconds"])
        self.assertEqual("working", by_id["research_fundamental"]["status_code"])
        self.assertTrue(by_id["research_fundamental"]["decision_eligible"])
        self.assertEqual("stale", by_id["operator"]["status_code"])
        self.assertEqual(180, by_id["operator"]["evidence_threshold_seconds"])
        self.assertEqual("stale", by_id["risk"]["status_code"])
        self.assertEqual(300, by_id["risk"]["evidence_threshold_seconds"])

    def test_kis_gateway_shares_codexstock_user_runtime_root(self):
        runtime_root = stock_app.USER_DATA_ROOT.parent

        self.assertEqual(runtime_root / "engines" / "kis_trading_mcp", stock_app.KIS_TRADING_MCP_GATEWAY.engine_root)
        self.assertEqual(runtime_root / "secrets" / "kis_mcp.env", stock_app.KIS_TRADING_MCP_GATEWAY.secret_env_file)
        self.assertEqual(runtime_root / "runtime", stock_app.KIS_TRADING_MCP_GATEWAY.runtime_root)

    @staticmethod
    def _verified_rehearsal_row(*, row_id: str, candidate_id: str, created_at: str) -> dict:
        price = 70_000.0
        quote_row = {
            "symbol": "005930",
            "market": "KR",
            "currency": "KRW",
            "price": price,
            "source": "KIS_LIVE",
            "updated_at": created_at,
            "unit_status": "ok",
            "temporal_status": "ok",
            "official_mark_eligible": True,
        }
        quote_row_hash = stock_app._common_quote_snapshot_hash([quote_row])
        entry_evidence = {
            "schema": "codexstock_promotion_rehearsal_entry_quote_v1",
            "symbol": "005930",
            "price": price,
            "currency": "KRW",
            "quote_unit": "KRW_per_share",
            "observed_at": created_at,
            "snapshot_hash": quote_row_hash,
            "quote_row": quote_row,
            "quote_row_hash": quote_row_hash,
            "unit_status": "ok",
            "temporal_status": "ok",
            "official_mark_eligible": True,
            "paper_only": True,
            "live_order_allowed": False,
        }
        entry_evidence["evidence_hash"] = stock_app._promotion_rehearsal_entry_evidence_hash(
            entry_evidence
        )
        return {
            "id": row_id,
            "created_at": created_at,
            "candidate_id": candidate_id,
            "symbol": "005930",
            "ticket_id": f"ticket-{row_id}",
            "ticket_status": "PAPER_FILLED",
            "quantity": 1,
            "price": price,
            "paper_only": True,
            "live_order_allowed": False,
            "real_execution": "BLOCKED",
            "entry_quote_evidence": entry_evidence,
        }

    @staticmethod
    def _verified_promotion_candidate(
        candidate_id: str,
        symbol: str = "005930",
        experiment_id: str = "",
    ) -> dict:
        candidate = {
            "id": candidate_id,
            "symbol": symbol,
            "first_paper_session_date": "2026-07-16",
            "promotion": {
                "stage": "PAPER_READY",
                "blockers": [],
                "automatic_promotion": False,
            },
            "paper_only": True,
            "live_order_allowed": False,
        }
        evidence = {
            "schema": "codexstock_promotion_candidate_validation_v2",
            "candidate_id": candidate_id,
            "symbol": symbol,
            "created_at": "2026-07-15T16:00:00+09:00",
            "data_end_date": "2026-07-14",
            "first_paper_session_date": "2026-07-16",
            "source_engine": "research_forge",
            "experiment_id": experiment_id or "exp_" + candidate_id.replace("-", "_").lower(),
            "experiment_status": "PAPER_CANDIDATE",
            "adapter": "codexstock-analytical-multitimeframe-v1",
            "data_mode": "historical_provider",
            "dataset_id": "verified-test-dataset",
            "dataset_hash": "sha256:" + "a" * 64,
            "row_count": 2520,
            "data_quality": {
                "strict_temporal_order": True,
                "duplicate_dates": 0,
                "invalid_ohlc_rows": 0,
            },
            "point_in_time_universe_passed": True,
            "point_in_time_universe_dataset_id": "pit-universe-test",
            "adjusted_prices": True,
            "signal_timing": "close_t",
            "fill_timing": "open_t_plus_delay",
            "execution_model": {
                "execution_mode": "REALISTIC",
                "costs_declared": True,
                "liquidity_model_declared": True,
                "order_delay_bars": 1,
            },
            "validation": {
                "passed": True,
                "strict_walk_forward_passed": True,
                "no_walk_forward_leakage": True,
                "label_horizon_purge_covered": True,
                "parameter_robustness_passed": True,
            },
            "lifecycle": {
                "eligible_for_manual_paper_nomination": True,
                "automatic_promotion": False,
                "report_bundle_verified": True,
                "blockers": [],
            },
            "paper_only": True,
            "live_order_allowed": False,
        }
        evidence["evidence_hash"] = stock_app._promotion_candidate_validation_evidence_hash(evidence)
        candidate["validation_evidence"] = evidence
        return candidate

    @staticmethod
    def _rehearsal_artifacts(rows: list[dict]) -> tuple[list[dict], list[dict]]:
        tickets: list[dict] = []
        candidates: dict[str, dict] = {}
        for row in rows:
            ticket_id = str(row.get("ticket_id") or "")
            candidate_id = str(row.get("candidate_id") or "")
            if not ticket_id or not candidate_id or not isinstance(row.get("entry_quote_evidence"), dict):
                continue
            evidence = row["entry_quote_evidence"]
            tickets.append(
                {
                    "id": ticket_id,
                    "status": "PAPER_FILLED",
                    "mode": "paper",
                    "side": "BUY",
                    "symbol": row["symbol"],
                    "quantity": row["quantity"],
                    "price": row["price"],
                    "risk_status": "PASSED",
                    "real_execution": "BLOCKED",
                    "guard": "paper_only_no_broker_order",
                    "metadata": {
                        "candidate_id": candidate_id,
                        "entry_quote_evidence": evidence,
                        "paper_only": True,
                        "live_order_allowed": False,
                    },
                }
            )
            candidates[candidate_id] = OperationalStatusContractTests._verified_promotion_candidate(
                candidate_id,
                row["symbol"],
            )
        return tickets, list(candidates.values())

    def test_promotion_rehearsal_evidence_excludes_legacy_and_candidate_day_duplicates(self):
        legacy = {
            "id": "legacy",
            "created_at": "2026-07-15T16:00:00+09:00",
            "candidate_id": "candidate-a",
            "symbol": "005930",
            "ticket_status": "PAPER_FILLED",
            "price": 70_000,
        }
        first = self._verified_rehearsal_row(
            row_id="first",
            candidate_id="candidate-a",
            created_at="2026-07-16T16:00:00+09:00",
        )
        duplicate = self._verified_rehearsal_row(
            row_id="duplicate",
            candidate_id="candidate-a",
            created_at="2026-07-16T17:00:00+09:00",
        )
        next_day = self._verified_rehearsal_row(
            row_id="next-day",
            candidate_id="candidate-a",
            created_at="2026-07-20T16:00:00+09:00",
        )
        tickets, candidates = self._rehearsal_artifacts([first, duplicate, next_day])

        result = stock_app._promotion_rehearsal_evidence_audit(
            [legacy, first, duplicate, next_day],
            ticket_rows=tickets,
            candidate_rows=candidates,
        )

        self.assertEqual(4, result["raw_count"])
        self.assertEqual(2, result["verified_count"])
        self.assertEqual(2, result["quarantined_count"])
        self.assertEqual(1, result["duplicate_candidate_day_count"])
        self.assertEqual(
            {"first", "next-day"},
            {row["id"] for row in result["verified_rows"]},
        )
        self.assertEqual(1, result["blocker_counts"]["entry_quote_evidence_missing_or_legacy"])
        self.assertEqual(1, result["blocker_counts"]["duplicate_candidate_day"])
        self.assertEqual(2, result["unique_session_day_count"])
        self.assertEqual(1, result["unique_symbol_count"])
        self.assertEqual(1, result["unique_candidate_count"])
        self.assertEqual(1, result["unique_research_forge_experiment_count"])

    def test_promotion_rehearsal_evidence_rejects_duplicate_experiment_same_day(self):
        first = self._verified_rehearsal_row(
            row_id="experiment-first",
            candidate_id="candidate-a",
            created_at="2026-07-16T16:00:00+09:00",
        )
        duplicate_experiment = self._verified_rehearsal_row(
            row_id="experiment-duplicate",
            candidate_id="candidate-b",
            created_at="2026-07-16T17:00:00+09:00",
        )
        rows = [first, duplicate_experiment]
        tickets, _ = self._rehearsal_artifacts(rows)
        candidates = [
            self._verified_promotion_candidate("candidate-a", experiment_id="exp_shared"),
            self._verified_promotion_candidate("candidate-b", experiment_id="exp_shared"),
        ]

        result = stock_app._promotion_rehearsal_evidence_audit(
            rows,
            ticket_rows=tickets,
            candidate_rows=candidates,
        )

        self.assertEqual(1, result["verified_count"])
        self.assertEqual(1, result["quarantined_count"])
        self.assertEqual(1, result["verified_research_experiment_day_count"])
        self.assertEqual(1, result["unique_research_forge_experiment_count"])
        self.assertEqual(
            1,
            result["blocker_counts"]["duplicate_research_forge_experiment_day"],
        )

    def test_promotion_rehearsal_evidence_rejects_unanchored_paper_ticket(self):
        row = self._verified_rehearsal_row(
            row_id="unanchored",
            candidate_id="candidate-a",
            created_at="2026-07-16T16:00:00+09:00",
        )

        result = stock_app._promotion_rehearsal_evidence_audit(
            [row],
            ticket_rows=[],
            candidate_rows=[],
        )

        self.assertEqual(0, result["verified_count"])
        self.assertEqual(1, result["quarantined_count"])
        self.assertEqual(1, result["blocker_counts"]["paper_ticket_artifact_missing"])
        self.assertEqual(1, result["blocker_counts"]["promotion_candidate_artifact_missing"])

    def test_promotion_rehearsal_readiness_requires_count_days_and_symbols(self):
        count_only = stock_app._promotion_rehearsal_readiness(
            {
                "verified_count": 20,
                "unique_session_day_count": 1,
                "unique_symbol_count": 1,
                "unique_candidate_count": 1,
                "unique_research_forge_experiment_count": 1,
            }
        )
        diversified = stock_app._promotion_rehearsal_readiness(
            {
                "verified_count": 20,
                "unique_session_day_count": 5,
                "unique_symbol_count": 3,
                "unique_candidate_count": 3,
                "unique_research_forge_experiment_count": 3,
            }
        )

        self.assertFalse(count_only["ready"])
        self.assertIn("independent_session_days", count_only["blockers"])
        self.assertIn("symbol_diversity", count_only["blockers"])
        self.assertIn("candidate_diversity", count_only["blockers"])
        self.assertIn("research_experiment_diversity", count_only["blockers"])
        self.assertTrue(diversified["ready"])
        self.assertEqual(10.0, diversified["partial_score"])
        self.assertEqual(0, diversified["remaining_verified_count"])

    def test_promotion_rehearsal_entry_quote_uses_official_common_snapshot(self):
        quote_rows = [
            {
                "symbol": "005930",
                "market": "KR",
                "currency": "KRW",
                "price": 70_000,
                "source": "KIS_LIVE",
                "updated_at": "2026-07-16T15:39:58+09:00",
                "unit_status": "ok",
                "temporal_status": "ok",
                "official_mark_eligible": True,
            }
        ]
        snapshot_hash = stock_app._common_quote_snapshot_hash(quote_rows)
        snapshot = {
            "ok": True,
            "generated_at": "2026-07-16T15:40:00+09:00",
            "schema": "codexstock_common_quote_snapshot_v1",
            "snapshot_hash": snapshot_hash,
            "marks": {"005930": 70_000},
            "summary": {"status": "ok"},
            "rows": quote_rows,
        }
        with patch("app.stock_suite_app.build_common_quote_snapshot", return_value=snapshot) as common_quote:
            result = stock_app._promotion_rehearsal_entry_quote_evidence("005930")

        self.assertTrue(result["ok"])
        self.assertEqual(70_000, result["evidence"]["price"])
        self.assertEqual("KRW_per_share", result["evidence"]["quote_unit"])
        self.assertEqual(snapshot_hash, result["evidence"]["snapshot_hash"])
        self.assertEqual(snapshot_hash, result["evidence"]["quote_row_hash"])
        self.assertEqual(
            result["evidence"]["evidence_hash"],
            stock_app._promotion_rehearsal_entry_evidence_hash(result["evidence"]),
        )
        self.assertTrue(common_quote.call_args.kwargs["prefer_live"])
        self.assertTrue(common_quote.call_args.kwargs["record"])

    def test_promotion_rehearsal_rejects_requested_price_far_from_official_quote(self):
        quote_result = {
            "ok": True,
            "evidence": {
                "schema": "codexstock_promotion_rehearsal_entry_quote_v1",
                "price": 70_000,
                "currency": "KRW",
                "quote_unit": "KRW_per_share",
                "snapshot_hash": "snapshot-hash",
                "unit_status": "ok",
                "temporal_status": "ok",
                "official_mark_eligible": True,
                "observed_at": "2026-07-16T15:40:00+09:00",
            },
        }
        candidate = self._verified_promotion_candidate("candidate-a")
        with (
            patch("app.stock_suite_app._promotion_rehearsal_entry_quote_evidence", return_value=quote_result),
            patch.object(stock_app.OPS, "create_order") as create_order,
        ):
            with self.assertRaisesRegex(ValueError, "입력 가격과 공식 시세"):
                stock_app._create_promotion_paper_rehearsal(
                    candidate,
                    quantity=1,
                    requested_price=1_000,
                )

        create_order.assert_not_called()

    def test_native_synthetic_candidate_is_quarantined_before_quote_or_ticket(self):
        result = {
            "symbol": "005930",
            "best": {"fast": 5, "slow": 20, "test_return_pct": 12.0},
            "promotion_review": {"stage": "PAPER_READY", "blockers": []},
            "decision": {"status": "PASS"},
        }
        candidate = stock_app._promotion_candidate_record(
            result,
            scenario="balanced",
            fast_values=[5],
            slow_values=[20],
            source="unit-test",
        )
        status = stock_app._promotion_candidate_validation_evidence_status(candidate)

        self.assertEqual("BLOCKED", candidate["promotion"]["stage"])
        self.assertFalse(status["verified"])
        self.assertIn("synthetic_or_mock_backtest_forbidden", status["blockers"])
        with (
            patch("app.stock_suite_app._promotion_rehearsal_entry_quote_evidence") as quote,
            patch.object(stock_app.OPS, "create_order") as create_order,
        ):
            with self.assertRaisesRegex(ValueError, "historical-provider evidence"):
                stock_app._create_promotion_paper_rehearsal(candidate)
        quote.assert_not_called()
        create_order.assert_not_called()

    def test_promotion_candidate_evidence_hash_tampering_is_quarantined(self):
        candidate = self._verified_promotion_candidate("candidate-tampered")
        candidate["validation_evidence"]["dataset_hash"] = "sha256:" + "b" * 64

        status = stock_app._promotion_candidate_validation_evidence_status(candidate)
        audit = stock_app._promotion_candidate_evidence_audit([candidate])

        self.assertFalse(status["verified"])
        self.assertIn("candidate_validation_evidence_hash_mismatch", status["blockers"])
        self.assertEqual(0, audit["verified_count"])
        self.assertEqual(1, audit["quarantined_count"])

    def test_research_forge_candidate_requires_manual_nomination_and_full_evidence(self):
        payload = {
            "id": "exp_verified_test",
            "status": "PAPER_CANDIDATE",
            "backtest_adapter": "codexstock-analytical-multitimeframe-v1",
            "strategy": {"name": "ma", "version": "1", "rules": {"symbol": "005930", "fast": 5, "slow": 20}},
            "data_snapshot": {
                "dataset_id": "rf-dataset",
                "universe_dataset_id": "rf-universe",
                "adjusted_prices": True,
                "start_date": "2016-01-01",
                "end_date": "2026-07-16",
            },
            "result": {
                "adapter": "codexstock-analytical-multitimeframe-v1",
                "data_mode": "historical_provider",
                "dataset_id": "rf-dataset",
                "dataset_hash": "sha256:" + "c" * 64,
                "symbol": "005930",
                "row_count": 2500,
                "data_quality": {"strict_temporal_order": True, "duplicate_dates": 0, "invalid_ohlc_rows": 0},
                "signal_timing": "close_t",
                "fill_timing": "open_t_plus_delay",
                "total_return_pct": 21.5,
                "max_drawdown_pct": -14.0,
                "trade_count": 80,
            },
            "validation": {
                "passed": True,
                "checks": [
                    {"id": "costs_declared", "ok": True},
                    {"id": "liquidity_model_declared", "ok": True},
                    {"id": "order_delay_declared", "ok": True, "detail": "1"},
                ],
                "universe_evidence": {"passed": True, "dataset_id": "rf-universe"},
                "strict_walk_forward": {
                    "summary": {"passed": True, "temporal_leakage_detected": False},
                    "parameter_selection_uses_oos": False,
                },
                "parameter_robustness": {"summary": {"robust": True}},
            },
        }
        readiness = {
            "eligible_for_manual_paper_nomination": True,
            "automatic_promotion": False,
            "execution_mode": "REALISTIC",
            "blockers": [],
            "checks": [
                {"id": "label_horizon_purge_covered", "ok": True},
                {"id": "report_bundle_verified", "ok": True},
            ],
        }
        experiment = MagicMock()
        experiment.to_dict.return_value = payload
        forge = MagicMock()
        forge.registry.get.return_value = experiment
        forge.lifecycle_readiness.return_value = readiness
        with patch.object(stock_app, "RESEARCH_FORGE", forge):
            ready = stock_app._research_forge_promotion_candidate_record("exp_verified_test")
            payload["status"] = "VALIDATION"
            blocked = stock_app._research_forge_promotion_candidate_record("exp_verified_test")

        self.assertEqual("PAPER_READY", ready["promotion"]["stage"])
        self.assertTrue(ready["validation_evidence_status"]["verified"])
        self.assertFalse(ready["live_order_allowed"])
        self.assertEqual("BLOCKED", blocked["promotion"]["stage"])
        self.assertIn(
            "research_forge_manual_paper_nomination_missing",
            blocked["validation_evidence_status"]["blockers"],
        )

    def test_research_forge_candidate_discovery_imports_once_and_deduplicates(self):
        experiment_id = "exp_discovery_verified"
        experiment = SimpleNamespace(
            id=experiment_id,
            status=SimpleNamespace(value="PAPER_CANDIDATE"),
        )
        forge = MagicMock()
        forge.registry.list.return_value = [experiment]
        candidate = self._verified_promotion_candidate(
            "candidate-discovery",
            experiment_id=experiment_id,
        )
        candidate["research_forge_experiment_id"] = experiment_id
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate_file = Path(temp_dir) / "candidates.jsonl"
            with (
                patch.object(stock_app, "RESEARCH_FORGE", forge),
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", candidate_file),
                patch("app.stock_suite_app._research_forge_promotion_candidate_record", return_value=candidate) as convert,
                patch.object(stock_app.JOURNAL, "add"),
            ):
                first = stock_app._discover_research_forge_promotion_candidates(max_imports=1)
                second = stock_app._discover_research_forge_promotion_candidates(max_imports=1)
                rows = stock_app._read_jsonl(candidate_file, limit=10)

        self.assertEqual("imported", first["status"])
        self.assertEqual(1, first["imported_count"])
        self.assertEqual("already_imported", second["status"])
        self.assertEqual(1, second["already_imported_count"])
        self.assertEqual(1, len(rows))
        self.assertEqual(1, convert.call_count)
        self.assertFalse(first["live_order_allowed"])

    def test_research_forge_candidate_discovery_does_not_store_blocked_evidence(self):
        experiment_id = "exp_discovery_blocked"
        experiment = SimpleNamespace(
            id=experiment_id,
            status=SimpleNamespace(value="PAPER_CANDIDATE"),
        )
        forge = MagicMock()
        forge.registry.list.return_value = [experiment]
        candidate = self._verified_promotion_candidate(
            "candidate-blocked",
            experiment_id=experiment_id,
        )
        candidate["research_forge_experiment_id"] = experiment_id
        candidate["promotion"]["stage"] = "BLOCKED"
        candidate["promotion"]["blockers"] = ["risk_gate_failed"]
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate_file = Path(temp_dir) / "candidates.jsonl"
            with (
                patch.object(stock_app, "RESEARCH_FORGE", forge),
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", candidate_file),
                patch("app.stock_suite_app._research_forge_promotion_candidate_record", return_value=candidate),
            ):
                result = stock_app._discover_research_forge_promotion_candidates(max_imports=1)
                rows = stock_app._read_jsonl(candidate_file, limit=10)

        self.assertEqual("eligible_candidate_blocked", result["status"])
        self.assertEqual(0, result["imported_count"])
        self.assertEqual(1, result["blocked_count"])
        self.assertEqual([], rows)
        self.assertFalse(result["live_order_allowed"])

    def test_promotion_candidate_list_visibly_quarantines_legacy_paper_ready_row(self):
        legacy = {
            "id": "legacy-paper-ready",
            "symbol": "005930",
            "promotion": {"stage": "PAPER_READY", "blockers": []},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_file = root / "candidates.jsonl"
            stock_app._append_jsonl(candidate_file, legacy)
            with (
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", candidate_file),
                patch.object(stock_app, "STRATEGY_PROMOTION_REHEARSAL_FILE", root / "rehearsals.jsonl"),
            ):
                rows = stock_app._promotion_candidates(limit=10)

        self.assertEqual(1, len(rows))
        self.assertEqual("QUARANTINED", rows[0]["promotion"]["stage"])
        self.assertEqual("PAPER_READY", rows[0]["promotion"]["original_stage"])
        self.assertFalse(rows[0]["validation_evidence_status"]["verified"])

    def test_research_forge_candidate_discovery_audit_counts_only_verified_scheduler_candidates(self):
        experiment_id = "exp_discovery_audit"
        experiment = SimpleNamespace(
            id=experiment_id,
            status=SimpleNamespace(value="PAPER_CANDIDATE"),
        )
        forge = MagicMock()
        forge.registry.list.return_value = [experiment]
        candidate = self._verified_promotion_candidate(
            "candidate-discovery-audit",
            experiment_id=experiment_id,
        )
        candidate["research_forge_experiment_id"] = experiment_id
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate_file = Path(temp_dir) / "candidates.jsonl"
            stock_app._append_jsonl(candidate_file, candidate)
            with (
                patch.object(stock_app, "RESEARCH_FORGE", forge),
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", candidate_file),
            ):
                audit = stock_app._research_forge_candidate_discovery_audit()

        self.assertTrue(audit["contract_ready"])
        self.assertEqual(1, audit["manually_nominated_experiment_count"])
        self.assertEqual(1, audit["verified_imported_experiment_count"])
        self.assertEqual(1, audit["scheduler_eligible_candidate_count"])
        self.assertEqual(0, audit["pending_nominated_experiment_count"])
        self.assertTrue(audit["requires_next_krx_session_cooling"])
        self.assertFalse(audit["live_order_allowed"])

    def test_due_promotion_rehearsal_never_creates_forward_sample_on_holiday(self):
        now = datetime(2026, 7, 17, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "mode": "MARKET_CLOSED_LARGE_RESEARCH_FOCUS",
            "market_open": False,
            "market_priority_active": False,
            "market_closed_day": True,
            "market_closed_reason": "제헌절",
        }
        with (
            patch("app.stock_suite_app._create_promotion_paper_rehearsal") as create_rehearsal,
            patch("app.stock_suite_app._discover_research_forge_promotion_candidates") as discover,
        ):
            result = stock_app.run_due_promotion_paper_rehearsal(
                now=now,
                operating_focus=focus,
            )

        self.assertEqual("deferred_no_krx_session", result["status"])
        self.assertEqual(0, result["created_count"])
        self.assertFalse(result["live_order_allowed"])
        self.assertNotIn("forward_observation", result)
        create_rehearsal.assert_not_called()
        discover.assert_not_called()

    def test_due_promotion_rehearsal_records_no_candidate_forward_observation(self):
        now = datetime(2026, 7, 20, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "mode": "DAILY_REVIEW_FOCUS",
            "market_open": False,
            "market_priority_active": False,
            "market_closed_day": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch.object(stock_app, "STRATEGY_PROMOTION_REHEARSAL_FILE", root / "rehearsals.jsonl"),
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", root / "candidates.jsonl"),
                patch.object(stock_app, "PROMOTION_FORWARD_OBSERVATION_FILE", root / "forward.jsonl"),
                patch(
                    "app.stock_suite_app._discover_research_forge_promotion_candidates",
                    return_value={
                        "ok": True,
                        "status": "no_eligible_candidate",
                        "imported_count": 0,
                        "paper_only": True,
                        "live_order_allowed": False,
                    },
                ),
            ):
                result = stock_app.run_due_promotion_paper_rehearsal(
                    now=now,
                    operating_focus=focus,
                )
                rows = stock_app._read_jsonl(root / "forward.jsonl", limit=10)

        self.assertEqual("no_due_candidate", result["status"])
        self.assertTrue(result["forward_observation"]["recorded"])
        self.assertEqual(1, len(rows))
        self.assertEqual("2026-07-20", rows[0]["observed_date"])
        self.assertTrue(rows[0]["market_session_verified"])
        self.assertFalse(rows[0]["live_order_allowed"])
        self.assertEqual(
            "no_eligible_candidate",
            result["research_forge_candidate_discovery"]["status"],
        )

    def test_due_promotion_rehearsal_skips_discovery_when_session_is_already_recorded(self):
        now = datetime(2026, 7, 20, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "mode": "DAILY_REVIEW_FOCUS",
            "market_open": False,
            "market_priority_active": False,
            "market_closed_day": False,
        }
        existing = self._forward_observation_rows(date(2026, 7, 20), date(2026, 7, 20))[0]
        with tempfile.TemporaryDirectory() as temp_dir:
            forward_file = Path(temp_dir) / "forward.jsonl"
            stock_app._append_jsonl(forward_file, existing)
            with (
                patch.object(stock_app, "PROMOTION_FORWARD_OBSERVATION_FILE", forward_file),
                patch("app.stock_suite_app._discover_research_forge_promotion_candidates") as discover,
                patch("app.stock_suite_app._create_promotion_paper_rehearsal") as create_rehearsal,
                patch(
                    "app.stock_suite_app.run_ai_staff_90_session_forward_ab_observer_tick",
                    return_value={
                        "ok": True,
                        "status": "SESSION_CAPTURED",
                        "recorded": True,
                        "paper_only": True,
                        "live_order_allowed": False,
                    },
                ) as forward_ab_observer,
            ):
                result = stock_app.run_due_promotion_paper_rehearsal(
                    now=now,
                    operating_focus=focus,
                    max_candidates=3,
                )

        self.assertEqual("already_recorded_for_session", result["status"])
        self.assertEqual("already_recorded_for_session", result["forward_observation"]["status"])
        self.assertEqual("2026-07-20", result["forward_observation"]["record"]["observed_date"])
        self.assertTrue(result["forward_ab_90_session_observation"]["recorded"])
        self.assertFalse(result["live_order_allowed"])
        discover.assert_not_called()
        create_rehearsal.assert_not_called()
        forward_ab_observer.assert_called_once()

    def test_forward_observer_waits_during_market_without_running_paper_batch(self):
        now = datetime(2026, 7, 20, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "mode": "MARKET_EXECUTION_FOCUS",
            "market_open": True,
            "market_priority_active": True,
            "market_closed_day": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(
                    stock_app,
                    "PROMOTION_FORWARD_OBSERVATION_FILE",
                    Path(temp_dir) / "forward.jsonl",
                ),
                patch("app.stock_suite_app.run_due_promotion_paper_rehearsal") as run_due,
            ):
                result = stock_app.run_promotion_forward_observer_tick(
                    now=now,
                    operating_focus=focus,
                )

        self.assertEqual("WAITING_MARKET_CLOSE", result["status"])
        self.assertFalse(result["executed"])
        self.assertTrue(result["scheduler_independent_of_autopilot"])
        self.assertFalse(result["retroactive_backfill_allowed"])
        self.assertFalse(result["live_order_allowed"])
        run_due.assert_not_called()

    def test_research_daemon_invokes_forward_observer_when_autopilot_is_disabled(self):
        focus = {
            "mode": "DAILY_REVIEW_FOCUS",
            "market_open": False,
            "market_priority_active": False,
            "market_closed_day": False,
        }
        observer_result = {
            "ok": True,
            "status": "RECORDED",
            "scheduler_independent_of_autopilot": True,
            "paper_only": True,
            "live_order_allowed": False,
        }
        daemon = stock_app.AiResearchDaemon()
        with (
            patch.object(stock_app.AUTOPILOT_SCHEDULER, "running", False),
            patch("app.stock_suite_app.build_operating_focus", return_value=focus),
            patch(
                "app.stock_suite_app.run_promotion_forward_observer_tick",
                return_value=observer_result,
            ) as observer,
            patch("app.stock_suite_app.load_universe", side_effect=RuntimeError("stop after observer")),
            patch.object(daemon, "activate_staff_roster"),
            patch.object(daemon, "set_activity"),
            patch.object(daemon, "update_staff_activity"),
        ):
            with self.assertRaisesRegex(RuntimeError, "stop after observer"):
                daemon.run_cycle(source="daemon")

        observer.assert_called_once_with(
            source="daemon-research-daemon-forward-observer",
            max_candidates=3,
            operating_focus=focus,
        )
        self.assertFalse(stock_app.AUTOPILOT_SCHEDULER.running)

    def test_due_promotion_rehearsal_waits_until_session_after_candidate_nomination(self):
        now = datetime(2026, 7, 20, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "mode": "DAILY_REVIEW_FOCUS",
            "market_open": False,
            "market_priority_active": False,
            "market_closed_day": False,
        }
        candidate = self._verified_promotion_candidate("candidate-same-day")
        candidate["first_paper_session_date"] = "2026-07-21"
        evidence = candidate["validation_evidence"]
        evidence["created_at"] = "2026-07-20T15:40:00+09:00"
        evidence["data_end_date"] = "2026-07-20"
        evidence["first_paper_session_date"] = "2026-07-21"
        evidence["evidence_hash"] = stock_app._promotion_candidate_validation_evidence_hash(evidence)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_file = root / "candidates.jsonl"
            stock_app._append_jsonl(candidate_file, candidate)
            with (
                patch.object(stock_app, "STRATEGY_PROMOTION_REHEARSAL_FILE", root / "rehearsals.jsonl"),
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", candidate_file),
                patch.object(stock_app, "PROMOTION_FORWARD_OBSERVATION_FILE", root / "forward.jsonl"),
                patch(
                    "app.stock_suite_app._discover_research_forge_promotion_candidates",
                    return_value={"ok": True, "status": "already_imported", "imported_count": 0},
                ),
                patch("app.stock_suite_app._create_promotion_paper_rehearsal") as create_rehearsal,
            ):
                result = stock_app.run_due_promotion_paper_rehearsal(
                    now=now,
                    operating_focus=focus,
                )

        self.assertEqual("no_due_candidate", result["status"])
        self.assertEqual(0, result["eligible_candidate_count"])
        create_rehearsal.assert_not_called()

    def test_due_promotion_rehearsal_selects_three_diverse_paper_candidates(self):
        now = datetime(2026, 7, 20, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        focus = {
            "mode": "DAILY_REVIEW_FOCUS",
            "market_open": False,
            "market_priority_active": False,
            "market_closed_day": False,
        }
        candidates = [
            self._verified_promotion_candidate("candidate-a", "005930", "exp_a"),
            self._verified_promotion_candidate("candidate-b", "005930", "exp_b"),
            self._verified_promotion_candidate("candidate-c", "000660", "exp_c"),
            self._verified_promotion_candidate("candidate-d", "035420", "exp_d"),
        ]

        def paper_result(candidate, **_kwargs):
            return {
                "ok": True,
                "status": "PAPER_FILLED",
                "candidate": candidate,
                "rehearsal": {"candidate_id": candidate["id"]},
                "paper_only": True,
                "live_order_allowed": False,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidate_file = root / "candidates.jsonl"
            for candidate in candidates:
                stock_app._append_jsonl(candidate_file, candidate)
            with (
                patch.object(stock_app, "STRATEGY_PROMOTION_REHEARSAL_FILE", root / "rehearsals.jsonl"),
                patch.object(stock_app, "STRATEGY_PROMOTION_CANDIDATE_FILE", candidate_file),
                patch.object(stock_app, "PROMOTION_FORWARD_OBSERVATION_FILE", root / "forward.jsonl"),
                patch(
                    "app.stock_suite_app._discover_research_forge_promotion_candidates",
                    return_value={"ok": True, "status": "already_imported", "imported_count": 0},
                ),
                patch.object(stock_app.OPS, "has_today_ticket", return_value=False),
                patch(
                    "app.stock_suite_app._create_promotion_paper_rehearsal",
                    side_effect=paper_result,
                ) as create_rehearsal,
            ):
                result = stock_app.run_due_promotion_paper_rehearsal(
                    now=now,
                    operating_focus=focus,
                    max_candidates=3,
                )

        selected = [call.args[0] for call in create_rehearsal.call_args_list]
        self.assertEqual("completed", result["status"])
        self.assertEqual(3, result["created_count"])
        self.assertEqual(3, result["daily_candidate_limit"])
        self.assertEqual(3, result["selected_unique_symbol_count"])
        self.assertEqual(3, result["selected_unique_experiment_count"])
        self.assertEqual(3, len({row["symbol"] for row in selected}))
        self.assertEqual(3, len({row["validation_evidence"]["experiment_id"] for row in selected}))
        self.assertFalse(result["live_order_allowed"])

    def test_forward_observation_audit_requires_dense_90_day_session_coverage(self):
        rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 3))
        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 4, 3, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertTrue(result["ready"])
        self.assertGreaterEqual(result["verified_forward_days"], 90)
        self.assertGreaterEqual(result["verified_observation_day_count"], 50)
        self.assertEqual(100.0, result["session_coverage_pct"])
        integrity = result["evidence_integrity"]
        self.assertEqual("codexstock_forward_observation_integrity_v1", integrity["schema"])
        self.assertTrue(integrity["hash_chain_complete"])
        self.assertEqual(rows[-1]["observation_hash"], integrity["last_observation_hash"])
        self.assertEqual({"no_due_candidate": len(rows)}, integrity["verified_result_status_counts"])
        self.assertEqual(0, integrity["future_rows_quarantined"])
        self.assertFalse(integrity["live_order_allowed"])
        self.assertFalse(result["live_order_allowed"])

    def test_forward_observation_audit_summarizes_candidate_and_symbol_diversity(self):
        rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 3))
        symbols = ["005930", "000660", "035420"]
        for index, row in enumerate(rows[:9]):
            symbol = symbols[index % len(symbols)]
            candidate_id = f"candidate-{index % len(symbols)}"
            digest = [{"candidate_id": candidate_id, "symbol": symbol, "result": "paper_watch"}]
            row["result_status"] = "completed"
            row["candidate_result_digest"] = digest
            row["candidate_result_hash"] = stock_app._promotion_forward_candidate_digest_hash(digest)
            if index == 0:
                row["previous_observation_hash"] = ""
            else:
                row["previous_observation_hash"] = rows[index - 1]["observation_hash"]
            row["observation_hash"] = stock_app._promotion_forward_observation_hash(row)
            if index + 1 < len(rows):
                rows[index + 1]["previous_observation_hash"] = row["observation_hash"]
                rows[index + 1]["observation_hash"] = stock_app._promotion_forward_observation_hash(rows[index + 1])
        for index in range(9, len(rows)):
            rows[index]["previous_observation_hash"] = rows[index - 1]["observation_hash"]
            rows[index]["observation_hash"] = stock_app._promotion_forward_observation_hash(rows[index])

        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 4, 3, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        integrity = result["evidence_integrity"]

        self.assertTrue(result["ready"])
        self.assertTrue(integrity["hash_chain_complete"])
        self.assertEqual(3, integrity["unique_candidate_count"])
        self.assertEqual(3, integrity["unique_symbol_count"])
        self.assertEqual(9, integrity["verified_result_status_counts"]["completed"])
        self.assertEqual(len(rows) - 9, integrity["verified_result_status_counts"]["no_due_candidate"])

    def test_forward_observation_audit_counts_exact_90_day_window_inclusively(self):
        rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 1))
        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 4, 1, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertEqual(89, result["calendar_span_days"])
        self.assertEqual(90, result["observation_window_calendar_days"])
        self.assertEqual(90, result["verified_forward_days"])
        self.assertEqual(0, result["days_remaining"])
        self.assertTrue(result["ready"])
        self.assertEqual(
            "inclusive_first_and_last_observation_dates",
            result["calendar_day_count_policy"],
        )
        self.assertFalse(result["live_order_allowed"])

    def test_forward_observation_audit_counts_first_verified_day_as_one(self):
        rows = self._forward_observation_rows(date(2026, 7, 20), date(2026, 7, 20))
        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 7, 20, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertEqual(0, result["calendar_span_days"])
        self.assertEqual(1, result["observation_window_calendar_days"])
        self.assertEqual(1, result["verified_forward_days"])
        self.assertEqual(89, result["days_remaining"])
        self.assertFalse(result["ready"])
        self.assertIn("forward_calendar_span_below_90_days", result["blockers"])
        self.assertFalse(result["live_order_allowed"])

    def test_forward_observation_audit_rejects_two_distant_samples(self):
        dense_rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 3))
        sparse_rows = [dense_rows[0], dict(dense_rows[-1])]
        sparse_rows[1]["previous_observation_hash"] = sparse_rows[0]["observation_hash"]
        sparse_rows[1]["observation_hash"] = stock_app._promotion_forward_observation_hash(sparse_rows[1])
        result = stock_app.build_promotion_forward_observation_audit(
            sparse_rows,
            now=datetime(2026, 4, 3, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertFalse(result["ready"])
        self.assertEqual(0, result["verified_forward_days"])
        self.assertLess(result["session_coverage_pct"], 10.0)
        self.assertIn("forward_observation_coverage_below_95_pct", result["blockers"])

    def test_forward_observation_audit_quarantines_hash_tampering(self):
        rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 3))
        rows[10]["created_rehearsal_count"] = 99
        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 4, 3, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertFalse(result["ready"])
        self.assertGreater(result["quarantined_row_count"], 0)
        self.assertIn("observation_hash_mismatch", result["blocker_counts"])
        self.assertIn("forward_observation_integrity_failure", result["blockers"])

    def test_forward_observation_audit_rejects_future_rows_at_audit_cutoff(self):
        rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 3))
        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 2, 2, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertFalse(result["ready"])
        self.assertGreater(result["future_observation_row_count"], 0)
        self.assertIn("observation_after_audit_cutoff", result["blocker_counts"])
        self.assertIn("forward_observation_integrity_failure", result["blockers"])
        self.assertEqual("2026-02-02T16:30:00+09:00", result["audit_cutoff_at"])

    def test_forward_observation_audit_recomputes_candidate_digest_hash(self):
        rows = self._forward_observation_rows(date(2026, 1, 2), date(2026, 4, 3))
        rows[10]["candidate_result_digest"] = [{"symbol": "005930", "status": "forged"}]
        rows[10]["observation_hash"] = stock_app._promotion_forward_observation_hash(rows[10])
        for index in range(11, len(rows)):
            rows[index]["previous_observation_hash"] = rows[index - 1]["observation_hash"]
            rows[index]["observation_hash"] = stock_app._promotion_forward_observation_hash(rows[index])
        result = stock_app.build_promotion_forward_observation_audit(
            rows,
            now=datetime(2026, 4, 3, 16, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )

        self.assertFalse(result["ready"])
        self.assertIn("candidate_result_hash_mismatch", result["blocker_counts"])
        self.assertIn("forward_observation_integrity_failure", result["blockers"])

    def test_counterfactual_scheduler_can_use_its_pre_reserved_heavy_slot(self):
        queue = {
            "ok": True,
            "safe_to_execute_paper": True,
            "job_count": 3,
            "strategy_triplet_count": 1,
            "queue_hash": "queue-hash",
        }
        focus = {
            "large_batch_jobs_allowed": True,
            "market_priority_active": False,
            "market_open": False,
            "market_phase": "closed",
        }
        acquired = stock_app.HEAVY_RESEARCH_JOB_LOCK.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            with (
                patch("app.stock_suite_app.build_operating_focus", return_value=focus),
                patch("app.stock_suite_app.build_ai_staff_learning_counterfactual_queue", return_value=queue),
            ):
                result = stock_app.build_ai_staff_learning_counterfactual_scheduler_status(
                    max_triplets=1,
                    target_start_date="2025-01-06",
                    heavy_slot_reserved=True,
                )
        finally:
            stock_app.HEAVY_RESEARCH_JOB_LOCK.release()

        self.assertTrue(result["ready_to_run"])
        self.assertTrue(result["heavy_slot_available"])
        self.assertTrue(result["heavy_slot_reserved"])

    def test_counterfactual_background_schedule_reserves_two_locked_paper_triplets(self):
        schedule = {
            "ok": True,
            "ready_to_run": True,
            "status": "ready_to_run",
            "queue_hash": "queue-hash",
            "queue_triplet_count": 2,
        }
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = False
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "counterfactual-state.json"
            try:
                with (
                    patch.object(stock_app, "AI_STAFF_LEARNING_COUNTERFACTUAL_SCHEDULER_STATE_FILE", state_path),
                    patch.object(stock_app, "AI_STAFF_LEARNING_COUNTERFACTUAL_THREAD", None),
                    patch(
                        "app.stock_suite_app.build_ai_staff_learning_counterfactual_scheduler_status",
                        return_value=schedule,
                    ),
                    patch("app.stock_suite_app.threading.Thread", return_value=fake_thread),
                ):
                    result = stock_app._maybe_schedule_ai_staff_learning_counterfactual("test-scheduler")
            finally:
                if stock_app.HEAVY_RESEARCH_JOB_LOCK.locked():
                    stock_app.HEAVY_RESEARCH_JOB_LOCK.release()

            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual("QUEUED", result["status"])
        self.assertTrue(result["scheduled"])
        self.assertFalse(result["live_order_allowed"])
        self.assertFalse(result["automatic_promotion"])
        self.assertEqual("QUEUED", state["status"])
        self.assertEqual(2, state["max_triplets"])
        self.assertTrue(state["paper_only"])
        self.assertFalse(state["live_order_allowed"])
        fake_thread.start.assert_called_once_with()

    def test_release_readiness_treats_external_runtime_as_separated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            runtime = root / "runtime"
            dist = repo / "dist" / "CodexStock-Friend"
            repo.mkdir()
            runtime.mkdir()
            dist.mkdir(parents=True)
            (repo / ".env.example").write_text("LIVE_TRADING=false\nKIS_READONLY=true\n", encoding="utf-8")
            private_runtime = runtime / "live_order_submits.jsonl"
            private_runtime.write_text("{}\n", encoding="utf-8")
            settings = SimpleNamespace(live_trading=True, kis_readonly=False, kis_use_mock=False)

            with (
                patch.object(stock_app, "REPO_ROOT", repo),
                patch.object(stock_app, "FRIEND_RELEASE_REQUIRED_FILES", []),
                patch.object(stock_app, "FRIEND_RELEASE_ENV_KEYS", []),
                patch.object(stock_app, "FRIEND_RELEASE_PRIVATE_PATHS", [(private_runtime, "실전 주문 제출 로그")]),
                patch.object(stock_app, "FRIEND_RELEASE_PRIVATE_GLOBS", []),
                patch.object(stock_app, "FRIEND_RELEASE_GITIGNORE_PATTERNS", []),
                patch.object(stock_app.INTEGRATIONS, "settings", return_value=settings),
            ):
                result = stock_app.build_friend_release_readiness()

        self.assertTrue(result["ready"])
        self.assertEqual(100, result["score"])
        self.assertEqual(0, result["summary"]["repo_private_files"])
        self.assertEqual(1, result["summary"]["runtime_private_files"])
        self.assertEqual(0, result["summary"]["dist_private_files"])
        self.assertEqual([], result["private_files"])

    def test_dist_privacy_audit_ignores_source_names_but_blocks_runtime_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir)
            source = dist / "third_party" / "package" / "config_secrets.py"
            source.parent.mkdir(parents=True)
            source.write_text("SECRET_FIELD = 'example'\n", encoding="utf-8")
            (dist / ".env.example").write_text("LIVE_TRADING=false\n", encoding="utf-8")
            (dist / "server.out.log").write_text("runtime output\n", encoding="utf-8")
            (dist / "live_order_submits.jsonl").write_text("{}\n", encoding="utf-8")
            runtime_file = dist / "runtime" / "stock_suite_app.lock"
            runtime_file.parent.mkdir()
            runtime_file.write_text("1", encoding="utf-8")

            findings = stock_app._audit_release_dist_private_files(dist)

        self.assertEqual(
            {"server.out.log", "live_order_submits.jsonl", "runtime/stock_suite_app.lock"},
            {row["path"] for row in findings},
        )


if __name__ == "__main__":
    unittest.main()
