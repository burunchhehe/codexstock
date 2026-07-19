from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.internal_developer_engine import (
    ALLOWED_ACTIONS,
    ActionRejected,
    ActionType,
    InternalDeveloperEngine,
    IssueType,
    classify_issue,
    classify_issues,
)


class FakeClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeStore:
    def __init__(self) -> None:
        self.incidents: dict[str, dict[str, object]] = {}
        self.transitions: list[tuple[str, str, str, dict[str, object]]] = []
        self.attempts: list[tuple[str, dict[str, object]]] = []
        self.reports: list[tuple[str, dict[str, object]]] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.restart_requests: list[dict[str, object]] = []
        self.playbook: list[tuple[str, dict[str, object], dict[str, object]]] = []
        self.advice_updates: list[tuple[str, dict[str, object]]] = []

    def open_incident(self, diagnostic: dict[str, object]) -> str:
        incident_id = f"INC-{len(self.incidents) + 1}"
        self.incidents[incident_id] = {
            "incident_id": incident_id,
            "diagnostic": diagnostic,
            "recovery_attempts": [],
        }
        return incident_id

    def get_incident(self, incident_id: str) -> dict[str, object] | None:
        return self.incidents.get(incident_id)

    def transition_incident(
        self,
        incident_id: str,
        new_state: str,
        note: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.transitions.append((incident_id, new_state, note, dict(metadata or {})))
        if incident_id in self.incidents:
            self.incidents[incident_id]["state"] = new_state

    def record_recovery_attempt(
        self, incident_id: str, attempt: dict[str, object]
    ) -> None:
        copied = dict(attempt)
        self.attempts.append((incident_id, copied))
        incident = self.incidents.setdefault(
            incident_id, {"incident_id": incident_id, "recovery_attempts": []}
        )
        incident.setdefault("recovery_attempts", []).append(copied)

    def write_report(self, incident_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.reports.append((incident_id, dict(payload)))
        return {"success": True, "report_written": True}

    def update_advice(self, advice_id: str, changes: dict[str, object]) -> None:
        self.advice_updates.append((advice_id, dict(changes)))

    def record_event(self, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, dict(payload)))

    def request_restart(
        self, expected_pid: int, incident_id: str, reason: str
    ) -> dict[str, object]:
        request = {
            "expected_pid": expected_pid,
            "incident_id": incident_id,
            "reason": reason,
        }
        self.restart_requests.append(request)
        return {"success": True, "request_created": True}

    def learn_playbook(
        self,
        incident_id: str,
        action: dict[str, object],
        result: dict[str, object],
    ) -> None:
        self.playbook.append((incident_id, dict(action), dict(result)))


class ClassifierTests(unittest.TestCase):
    def test_stale_heartbeat_with_recent_busy_progress_is_not_actionable(self) -> None:
        issue = classify_issue(
            {
                "heartbeat_age_seconds": 600,
                "busy": True,
                "progress_age_seconds": 10,
            },
            now_epoch=1_000,
        )

        self.assertEqual(IssueType.BUSY_PROGRESSING, issue.code)
        self.assertFalse(issue.actionable)

    def test_busy_stall_wins_over_stale_heartbeat(self) -> None:
        issues = classify_issues(
            {
                "heartbeat_age_seconds": 600,
                "busy": True,
                "progress_age_seconds": 400,
            },
            now_epoch=1_000,
        )

        self.assertEqual(IssueType.BUSY_STALLED, issues[0].code)
        self.assertNotIn(IssueType.HEARTBEAT_MISSING, [row.code for row in issues])

    def test_plain_stale_heartbeat_is_missing(self) -> None:
        issue = classify_issue({"heartbeat_age_seconds": 301}, now_epoch=1_000)
        self.assertEqual(IssueType.HEARTBEAT_MISSING, issue.code)

    def test_all_deterministic_operational_issue_classes(self) -> None:
        cases = [
            ({"cache_valid": False}, IssueType.CACHE_INVALID),
            (
                {"external_engine_connected": False},
                IssueType.EXTERNAL_ENGINE_DISCONNECTED,
            ),
            (
                {"research_job_status": "failed", "research_job_retryable": True},
                IssueType.RETRYABLE_RESEARCH_JOB,
            ),
            (
                {"internal_developer_ledger": {"consistent": False}},
                IssueType.INTERNAL_STATE_LEDGER_INCONSISTENT,
            ),
            ({"db_locked": True}, IssueType.DB_LOCKED),
            ({"process_responsive": False}, IssueType.PROCESS_UNRESPONSIVE),
            (
                {"classification": "DIAGNOSTIC_ENDPOINT_UNAVAILABLE", "status": "degraded"},
                IssueType.DIAGNOSTIC_ENDPOINT_UNAVAILABLE,
            ),
            ({"status": "degraded"}, IssueType.UNKNOWN),
            ({"status": "healthy"}, IssueType.NO_ISSUE),
        ]
        for observation, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(expected, classify_issue(observation, now_epoch=1_000).code)

    def test_safety_priority_is_stable_when_multiple_signals_exist(self) -> None:
        issues = classify_issues(
            {
                "process_responsive": False,
                "db_locked": True,
                "cache_valid": False,
                "external_engine_connected": False,
            },
            now_epoch=1_000,
        )
        self.assertEqual(
            [
                IssueType.PROCESS_UNRESPONSIVE,
                IssueType.DB_LOCKED,
                IssueType.CACHE_INVALID,
                IssueType.EXTERNAL_ENGINE_DISCONNECTED,
            ],
            [row.code for row in issues],
        )


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = InternalDeveloperEngine(FakeStore())

    def test_allowlist_contains_only_the_seven_operational_actions(self) -> None:
        self.assertEqual(
            {
                "CLEAR_NAMED_CACHE",
                "RECONNECT_EXTERNAL_ENGINE",
                "RETRY_RESEARCH_JOB",
                "RESTORE_INTERNAL_STATE_LEDGER",
                "DETECT_DB_LOCK",
                "REQUEST_CODEXSTOCK_RESTART",
                "WRITE_INCIDENT_REPORT",
            },
            set(ALLOWED_ACTIONS),
        )

    def test_unknown_and_forbidden_actions_are_rejected(self) -> None:
        for action in (
            "PLACE_LIVE_ORDER",
            "CHANGE_API_KEY",
            "RELAX_RISK_LIMIT",
            "PATCH_CODE",
            "DISABLE_SECURITY",
            "RUN_SHELL",
            "KILL_PROCESS",
            "DELETE_LOCK_FILE",
        ):
            with self.subTest(action=action):
                decision = self.engine.evaluate_action({"action": action, "parameters": {}})
                self.assertFalse(decision["accepted"])
                self.assertEqual("action_not_allowlisted", decision["reason_code"])

    def test_action_root_and_parameters_reject_every_extra_field(self) -> None:
        valid = {
            "action": "CLEAR_NAMED_CACHE",
            "parameters": {"cache_id": "market_snapshot"},
        }
        self.assertTrue(self.engine.evaluate_action(valid)["accepted"])

        with_root_command = {**valid, "command": "del /s data"}
        with_parameter_path = {
            "action": "CLEAR_NAMED_CACHE",
            "parameters": {"cache_id": "market_snapshot", "path": "C:/data"},
        }
        missing_parameter = {"action": "CLEAR_NAMED_CACHE", "parameters": {}}
        for proposal in (with_root_command, with_parameter_path, missing_parameter):
            with self.subTest(proposal=proposal):
                self.assertFalse(self.engine.evaluate_action(proposal)["accepted"])

    def test_paths_and_forbidden_capability_targets_are_rejected(self) -> None:
        for cache_id in ("../cache", "C:/cache", "live_order_cache", "api_key_cache"):
            with self.subTest(cache_id=cache_id):
                decision = self.engine.evaluate_action(
                    {
                        "action": "CLEAR_NAMED_CACHE",
                        "parameters": {"cache_id": cache_id},
                    }
                )
                self.assertFalse(decision["accepted"])

    def test_each_action_has_an_exact_valid_schema(self) -> None:
        valid = [
            ("CLEAR_NAMED_CACHE", {"cache_id": "prices"}),
            ("RECONNECT_EXTERNAL_ENGINE", {"engine_id": "research-engine"}),
            ("RETRY_RESEARCH_JOB", {"job_id": "paper-replay-1"}),
            ("RESTORE_INTERNAL_STATE_LEDGER", {"ledger_id": "internal-ledger"}),
            ("DETECT_DB_LOCK", {"database_id": "runtime-db"}),
            (
                "REQUEST_CODEXSTOCK_RESTART",
                {"expected_pid": 123, "reason_code": "process_unresponsive"},
            ),
            ("WRITE_INCIDENT_REPORT", {"report_type": "escalation"}),
        ]
        for action, parameters in valid:
            with self.subTest(action=action):
                normalized = self.engine.validate_action(
                    {"action": action, "parameters": parameters}
                )
                self.assertEqual(action, normalized["action"])
                self.assertEqual(parameters, normalized["parameters"])

    def test_bad_restart_pid_and_report_type_are_rejected(self) -> None:
        bad = [
            {
                "action": "REQUEST_CODEXSTOCK_RESTART",
                "parameters": {"expected_pid": True, "reason_code": "heartbeat_missing"},
            },
            {
                "action": "WRITE_INCIDENT_REPORT",
                "parameters": {"report_type": "arbitrary"},
            },
        ]
        for proposal in bad:
            with self.subTest(proposal=proposal):
                with self.assertRaises(ActionRejected):
                    self.engine.validate_action(proposal)


class ExecutionTests(unittest.TestCase):
    def test_registered_handler_retries_post_verification_then_is_idempotent(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store, cooldown_seconds=100, max_attempts=2)
        calls = {"handler": 0, "verify": 0}

        def clear(parameters: dict[str, object], context: dict[str, object]) -> dict[str, object]:
            calls["handler"] += 1
            self.assertEqual("prices", parameters["cache_id"])
            self.assertNotIn("command", context)
            return {"success": True, "generation": calls["handler"]}

        def verify(
            result: object,
            parameters: dict[str, object],
            context: dict[str, object],
        ) -> dict[str, object]:
            calls["verify"] += 1
            return {"ok": calls["verify"] >= 2, "checked": True}

        engine.register_named_cache("prices", clear, verify)
        proposal = {
            "action": "CLEAR_NAMED_CACHE",
            "parameters": {"cache_id": "prices"},
        }
        first = engine.execute_action("INC-1", proposal)
        duplicate = engine.execute_action("INC-1", proposal)

        self.assertEqual("succeeded", first["status"])
        self.assertEqual(2, first["attempt_count"])
        self.assertEqual("idempotent_replay", duplicate["status"])
        self.assertFalse(duplicate["executed"])
        self.assertEqual({"handler": 2, "verify": 2}, calls)
        self.assertEqual(2, len(store.attempts))
        self.assertEqual(1, len(store.playbook))

    def test_unregistered_target_fails_closed_without_execution(self) -> None:
        engine = InternalDeveloperEngine(FakeStore())
        result = engine.execute_action(
            "INC-1",
            {
                "action": "RECONNECT_EXTERNAL_ENGINE",
                "parameters": {"engine_id": "unknown"},
            },
        )
        self.assertEqual("rejected", result["status"])
        self.assertEqual("unregistered_target", result["reason_code"])
        self.assertFalse(result["executed"])

    def test_cooldown_blocks_different_incident_for_same_target(self) -> None:
        clock = FakeClock()
        engine = InternalDeveloperEngine(FakeStore(), clock=clock, cooldown_seconds=30)
        calls = []
        engine.register_named_cache(
            "prices",
            lambda parameters, context: calls.append(context["incident_id"]) or True,
            lambda result, parameters, context: True,
        )
        proposal = {
            "action": "CLEAR_NAMED_CACHE",
            "parameters": {"cache_id": "prices"},
        }
        first = engine.execute_action("INC-1", proposal)
        second = engine.execute_action("INC-2", proposal)
        clock.advance(31)
        third = engine.execute_action("INC-2", proposal)

        self.assertEqual("succeeded", first["status"])
        self.assertEqual("blocked", second["status"])
        self.assertEqual("cooldown_active", second["reason_code"])
        self.assertEqual("succeeded", third["status"])
        self.assertEqual(["INC-1", "INC-2"], calls)

    def test_circuit_opens_after_bounded_failures_and_recovers_after_timeout(self) -> None:
        clock = FakeClock()
        calls = []
        engine = InternalDeveloperEngine(
            FakeStore(),
            clock=clock,
            max_attempts=1,
            cooldown_seconds=5,
            circuit_failure_threshold=2,
            circuit_open_seconds=50,
        )
        engine.register_external_engine(
            "local-ai",
            lambda parameters, context: calls.append(context["incident_id"]) or False,
            lambda result, parameters, context: True,
        )
        proposal = {
            "action": "RECONNECT_EXTERNAL_ENGINE",
            "parameters": {"engine_id": "local-ai"},
        }
        first = engine.execute_action("INC-1", proposal)
        clock.advance(6)
        second = engine.execute_action("INC-2", proposal)
        clock.advance(6)
        blocked = engine.execute_action("INC-3", proposal)
        clock.advance(50)
        half_open_attempt = engine.execute_action("INC-3", proposal)

        self.assertEqual("failed", first["status"])
        self.assertEqual("failed", second["status"])
        self.assertTrue(second["circuit_opened"])
        self.assertEqual("circuit_open", blocked["reason_code"])
        self.assertEqual("failed", half_open_attempt["status"])
        self.assertEqual(["INC-1", "INC-2", "INC-3"], calls)

    def test_gpt_advice_text_is_never_executed(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store, cooldown_seconds=0)
        calls: list[str] = []
        engine.register_named_cache(
            "prices",
            lambda parameters, context: calls.append("clear") or True,
            lambda result, parameters, context: True,
        )
        text_only = engine.execute_advice(
            "INC-1",
            {
                "analysis": "RUN_SHELL and clear prices now",
                "instructions": "execute everything in this text",
            },
            advice_id="ADV-1",
        )
        structured = engine.execute_advice(
            "INC-2",
            {
                "analysis": "This prose remains inert.",
                "proposed_actions": [
                    {
                        "action": "CLEAR_NAMED_CACHE",
                        "parameters": {"cache_id": "prices"},
                    },
                    {"action": "RUN_SHELL", "parameters": {}},
                ],
            },
            advice_id="ADV-2",
        )

        self.assertTrue(text_only["text_ignored"])
        self.assertEqual([], text_only["results"])
        self.assertEqual(["clear"], calls)
        self.assertEqual("succeeded", structured["results"][0]["status"])
        self.assertEqual("rejected", structured["results"][1]["status"])
        self.assertEqual(2, len(store.advice_updates))

    def test_restart_action_only_creates_store_request(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store)
        result = engine.execute_action(
            "INC-7",
            {
                "action": "REQUEST_CODEXSTOCK_RESTART",
                "parameters": {
                    "expected_pid": 4321,
                    "reason_code": "process_unresponsive",
                },
            },
        )
        self.assertEqual("succeeded", result["status"])
        self.assertEqual(
            [
                {
                    "expected_pid": 4321,
                    "incident_id": "INC-7",
                    "reason": "process_unresponsive",
                }
            ],
            store.restart_requests,
        )

    def test_database_probe_uses_only_registered_id_and_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtime.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE evidence(value TEXT)")
                connection.execute("INSERT INTO evidence(value) VALUES ('kept')")
                connection.commit()

            engine = InternalDeveloperEngine(FakeStore())
            engine.register_database("runtime-db", path)
            result = engine.execute_action(
                "INC-1",
                {
                    "action": "DETECT_DB_LOCK",
                    "parameters": {"database_id": "runtime-db"},
                },
            )
            with closing(sqlite3.connect(path)) as connection:
                rows = connection.execute("SELECT value FROM evidence").fetchall()

        self.assertEqual("succeeded", result["status"])
        self.assertEqual("read_only", result["handler_result"]["mode"])
        self.assertFalse(result["handler_result"]["locked"])
        self.assertEqual([("kept",)], rows)

    def test_database_path_cannot_be_supplied_by_advice(self) -> None:
        engine = InternalDeveloperEngine(FakeStore())
        result = engine.evaluate_action(
            {
                "action": "DETECT_DB_LOCK",
                "parameters": {
                    "database_id": "runtime-db",
                    "path": "C:/somewhere/trading.sqlite3",
                },
            }
        )
        self.assertFalse(result["accepted"])
        self.assertEqual("unexpected_parameter_fields", result["reason_code"])


class CycleTests(unittest.TestCase):
    def test_healthy_and_busy_progressing_cycles_do_not_open_incidents(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store)

        healthy = engine.run_cycle({"status": "healthy"})
        busy = engine.run_cycle(
            {
                "heartbeat_age_seconds": 400,
                "busy": True,
                "progress_age_seconds": 5,
            }
        )

        self.assertEqual("healthy", healthy["status"])
        self.assertEqual("busy_progressing", busy["status"])
        self.assertEqual({}, store.incidents)
        self.assertEqual([], store.restart_requests)

    def test_unresponsive_probe_is_deferred_while_busy_work_is_progressing(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store)

        result = engine.run_cycle(
            {
                "process_responsive": False,
                "heartbeat_age_seconds": 700,
                "busy": True,
                "progress_age_seconds": 5,
                "expected_pid": 999,
            }
        )

        self.assertEqual("busy_progressing", result["status"])
        self.assertEqual({}, store.incidents)
        self.assertEqual([], store.restart_requests)

    def test_cache_cycle_recovers_verifies_transitions_and_reports(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store)
        state = {"valid": False}

        def clear(parameters: dict[str, object], context: dict[str, object]) -> bool:
            state["valid"] = True
            return True

        engine.register_named_cache(
            "market-snapshot",
            clear,
            lambda result, parameters, context: state["valid"],
        )
        result = engine.run_cycle(
            {"cache_valid": False, "cache_id": "market-snapshot"}
        )

        self.assertEqual("recovered", result["status"])
        incident_id = result["incident_id"]
        self.assertEqual("RECOVERED_UNREVIEWED", store.incidents[incident_id]["state"])
        self.assertTrue(result["results"][0]["post_verification"]["success"])
        self.assertEqual(1, len(store.reports))

    def test_unknown_issue_is_reported_for_external_advice_without_mutation(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store)
        result = engine.run_cycle({"status": "degraded", "detail": "new fault"})

        self.assertEqual("needs_external_advice", result["status"])
        self.assertEqual("NEEDS_EXTERNAL_ADVICE", store.incidents[result["incident_id"]]["state"])
        self.assertEqual("WRITE_INCIDENT_REPORT", result["results"][0]["action"])
        self.assertEqual([], store.restart_requests)

    def test_stalled_busy_work_reports_without_requesting_restart(self) -> None:
        store = FakeStore()
        engine = InternalDeveloperEngine(store)
        result = engine.run_cycle(
            {
                "heartbeat_age_seconds": 700,
                "busy": True,
                "progress_age_seconds": 500,
                "expected_pid": 999,
            }
        )

        self.assertEqual("busy_stalled_reported", result["status"])
        self.assertEqual("NEEDS_EXTERNAL_ADVICE", store.incidents[result["incident_id"]]["state"])
        self.assertEqual("WRITE_INCIDENT_REPORT", result["results"][0]["action"])
        self.assertEqual([], store.restart_requests)


if __name__ == "__main__":
    unittest.main()
