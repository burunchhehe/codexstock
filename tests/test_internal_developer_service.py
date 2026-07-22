from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Mapping
from unittest import mock

from app.internal_developer_service import (
    EXTERNAL_ENGINE_STATUS_PATH,
    FEATURE_HEALTH_FORCE_PATH,
    FEATURE_HEALTH_PATH,
    FORBIDDEN_AUTOMATION,
    IMPROVEMENT_RETRY_PATH,
    IMPROVEMENT_STATUS_PATH,
    KIS_RECONNECT_PATH,
    OVERVIEW_PATH,
    SYSTEM_RESOURCES_PATH,
    TELEGRAM_QUEUE_PATH,
    InternalDeveloperService,
    ServiceConfig,
    SingleInstanceLock,
    _atomic_write_json,
)


class FakeClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeHttp:
    def __init__(self, routes: Mapping[str, object] | None = None) -> None:
        self.routes = dict(routes or {})
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, dict[str, object]]] = []

    def _next(self, path: str) -> object:
        value = self.routes.get(path, {})
        if isinstance(value, list):
            if not value:
                return {}
            value = value.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def get(self, path: str, *, timeout: float) -> object:
        self.get_calls.append(path)
        return self._next(path)

    def post(
        self, path: str, payload: Mapping[str, object], *, timeout: float
    ) -> object:
        self.post_calls.append((path, dict(payload)))
        return self._next(path)


class FakeStore:
    def __init__(self) -> None:
        self.ledger_consistent = True
        self.rebuild_count = 0
        self.events: list[tuple[str, dict[str, object]]] = []
        self.incidents: dict[str, dict[str, object]] = {}
        self.reports: list[tuple[str, dict[str, object]]] = []
        self.restart_requests: list[dict[str, object]] = []

    def status(self) -> dict[str, object]:
        return {"ledger_consistent": self.ledger_consistent}

    def rebuild_ledgers(self) -> dict[str, object]:
        self.rebuild_count += 1
        self.ledger_consistent = True
        return {"ok": True}

    def record_event(self, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, dict(payload)))

    def open_incident(self, diagnostic: dict[str, object]) -> dict[str, object]:
        incident_id = f"INC-{len(self.incidents) + 1}"
        self.incidents[incident_id] = {
            "incident_id": incident_id,
            "state": "NEW",
            "classification": diagnostic.get("classification"),
            "diagnostic": dict(diagnostic),
        }
        return self.incidents[incident_id]

    def list_incidents(self, limit: int = 100) -> list[dict[str, object]]:
        return list(reversed(list(self.incidents.values())[-limit:]))

    def transition_incident(
        self,
        incident_id: str,
        state: str,
        *,
        note: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.incidents[incident_id]["state"] = state

    def write_report(
        self, incident_id: str, payload: dict[str, object]
    ) -> dict[str, object]:
        self.reports.append((incident_id, dict(payload)))
        return {"success": True, "report_id": f"REP-{len(self.reports)}"}

    def list_reports(self, limit: int = 100) -> list[dict[str, object]]:
        rows = [
            {
                "report_id": f"REP-{index}",
                "incident_id": incident_id,
                "payload": dict(payload),
            }
            for index, (incident_id, payload) in enumerate(self.reports, start=1)
        ]
        return list(reversed(rows[-limit:]))

    def get_incident(self, incident_id: str) -> dict[str, object] | None:
        return self.incidents.get(incident_id)

    def request_restart(
        self, expected_pid: int, incident_id: str, reason: str
    ) -> dict[str, object]:
        row = {
            "success": True,
            "expected_pid": expected_pid,
            "incident_id": incident_id,
            "reason": reason,
        }
        self.restart_requests.append(row)
        return row


class FakeEngine:
    """Minimal policy-engine double that invokes only registered callbacks."""

    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.caches: dict[str, tuple[object, object]] = {}
        self.external: dict[str, tuple[object, object]] = {}
        self.jobs: dict[str, tuple[object, object]] = {}
        self.ledgers: dict[str, tuple[object, object]] = {}
        self.databases: dict[str, Path] = {}
        self.cycles: list[tuple[dict[str, object], bool]] = []
        self.executed_actions: list[str] = []

    def register_named_cache(self, name: str, handler: object, verifier: object) -> None:
        self.caches[name] = (handler, verifier)

    def register_external_engine(self, name: str, handler: object, verifier: object) -> None:
        self.external[name] = (handler, verifier)

    def register_research_job(self, name: str, handler: object, verifier: object) -> None:
        self.jobs[name] = (handler, verifier)

    def register_internal_state_ledger(
        self, name: str, handler: object, verifier: object
    ) -> None:
        self.ledgers[name] = (handler, verifier)

    def register_database(self, name: str, path: Path) -> None:
        self.databases[name] = Path(path)

    def _report(self, issue: str, observation: dict[str, object]) -> str:
        opened = self.store.open_incident(
            {"classification": issue, "summary": issue, "observation": observation}
        )
        incident_id = str(opened["incident_id"])
        self.store.write_report(
            incident_id,
            {"classification": issue, "execution_authorized": False},
        )
        return incident_id

    @staticmethod
    def _invoke(
        binding: tuple[object, object], target_key: str, target: str
    ) -> tuple[object, object]:
        handler, verifier = binding
        parameters = {target_key: target}
        context = {"incident_id": "INC-FAKE"}
        result = handler(parameters, context)  # type: ignore[operator]
        verified = verifier(result, parameters, context)  # type: ignore[operator]
        return result, verified

    def run_cycle(
        self, observation: dict[str, object], *, auto_recover: bool = True
    ) -> dict[str, object]:
        copied = dict(observation)
        self.cycles.append((copied, auto_recover))
        issue = "NO_ISSUE"
        results: list[dict[str, object]] = []

        if observation.get("internal_ledger_consistent") is False:
            issue = "INTERNAL_STATE_LEDGER_INCONSISTENT"
            if auto_recover:
                target = str(observation["ledger_id"])
                result, verified = self._invoke(self.ledgers[target], "ledger_id", target)
                self.executed_actions.append("RESTORE_INTERNAL_STATE_LEDGER")
                results.append({"result": result, "verified": verified})
        elif observation.get("busy_stalled") is True:
            issue = "BUSY_STALLED"
        elif observation.get("heartbeat_missing") is True:
            issue = "HEARTBEAT_MISSING"
            if auto_recover and isinstance(observation.get("expected_pid"), int):
                incident_id = self._report(issue, copied)
                self.store.request_restart(
                    int(observation["expected_pid"]), incident_id, "heartbeat_missing"
                )
                self.executed_actions.append("REQUEST_CODEXSTOCK_RESTART")
                return {
                    "status": "restart_requested",
                    "incident_id": incident_id,
                    "diagnostic": {"primary_issue": issue},
                    "results": [],
                }
        else:
            if observation.get("cache_valid") is False:
                issue = "CACHE_INVALID"
                if auto_recover:
                    target = str(observation["cache_id"])
                    result, verified = self._invoke(self.caches[target], "cache_id", target)
                    self.executed_actions.append("CLEAR_NAMED_CACHE")
                    results.append({"result": result, "verified": verified})
            if observation.get("external_engine_connected") is False:
                issue = "EXTERNAL_ENGINE_DISCONNECTED"
                if auto_recover:
                    target = str(observation["engine_id"])
                    result, verified = self._invoke(self.external[target], "engine_id", target)
                    self.executed_actions.append("RECONNECT_EXTERNAL_ENGINE")
                    results.append({"result": result, "verified": verified})
            if observation.get("research_job_retryable") is True:
                issue = "RETRYABLE_RESEARCH_JOB"
                if auto_recover:
                    target = str(observation["job_id"])
                    result, verified = self._invoke(self.jobs[target], "job_id", target)
                    self.executed_actions.append("RETRY_RESEARCH_JOB")
                    results.append({"result": result, "verified": verified})
            if observation.get("abnormal") is True:
                issue = "UNKNOWN"

        if issue == "NO_ISSUE":
            return {
                "status": "healthy",
                "incident_id": None,
                "diagnostic": {"primary_issue": issue},
                "results": [],
            }
        if not auto_recover or not results:
            incident_id = self._report(issue, copied)
            return {
                "status": "diagnosed",
                "incident_id": incident_id,
                "diagnostic": {"primary_issue": issue},
                "results": [],
            }
        return {
            "status": "recovered",
            "incident_id": "INC-FAKE",
            "diagnostic": {"primary_issue": issue},
            "results": results,
        }


def idle_improvement(status: str = "IDLE") -> dict[str, object]:
    return {
        "ok": True,
        "state": {
            "cycle_id": "cycle-1",
            "status": status,
            "phase": "idle",
            "phase_index": 0,
            "progress_pct": 0,
            "updated_at": "2026-07-19T00:00:00+00:00",
        },
        "thread_alive": False,
        "heavy_research_lock_active": False,
    }


def healthy_routes() -> dict[str, object]:
    return {
        OVERVIEW_PATH: {"ok": True, "runtime": {"app": "running"}},
        SYSTEM_RESOURCES_PATH: {"ok": True, "app": {"pid": 4321}},
        IMPROVEMENT_STATUS_PATH: idle_improvement(),
        FEATURE_HEALTH_PATH: {
            "ok": True,
            "operational_broken_count": 0,
            "delayed_count": 0,
            "verification_pending_count": 0,
        },
        EXTERNAL_ENGINE_STATUS_PATH: {
            "engines": [
                {
                    "engine_id": "kis-trading-mcp",
                    "connected": True,
                    "execution_policy": "resident_read_only_gateway_auto_recover",
                    "resident_component": True,
                    "live_order_allowed": False,
                }
            ]
        },
    }


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data_root = self.root / "data"
        self.clock = FakeClock()
        self.store = FakeStore()
        self.engine = FakeEngine(self.store)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def service(
        self,
        http: FakeHttp,
        *,
        expected_pid: int | None = 4321,
        busy_stall_seconds: float = 300.0,
    ) -> InternalDeveloperService:
        return InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=self.store,
            engine=self.engine,
            http_client=http,
            config=ServiceConfig(
                interval_seconds=60,
                expected_pid=expected_pid,
                busy_stall_seconds=busy_stall_seconds,
            ),
            clock=self.clock,
        )

    def test_healthy_cycle_is_noop_and_writes_heartbeat(self) -> None:
        http = FakeHttp(healthy_routes())
        service = self.service(http)

        result = service.run_once()

        self.assertEqual("healthy", result["status"])
        self.assertEqual([], self.engine.executed_actions)
        self.assertEqual([], http.post_calls)
        self.assertTrue(service.heartbeat_path.is_file())
        heartbeat = json.loads(service.heartbeat_path.read_text(encoding="utf-8"))
        self.assertEqual("healthy", heartbeat["status"])

    def test_atomic_heartbeat_write_retries_transient_windows_share_denial(self) -> None:
        target = self.data_root / "internal_developer" / "service_heartbeat.json"
        real_replace = os.replace
        attempts = 0

        def flaky_replace(source: object, destination: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise PermissionError(5, "transient sharing violation")
            real_replace(source, destination)

        with mock.patch(
            "app.internal_developer_service.os.replace", side_effect=flaky_replace
        ):
            _atomic_write_json(target, {"schema": "test", "healthy": True})

        self.assertEqual(3, attempts)
        self.assertEqual(
            {"schema": "test", "healthy": True},
            json.loads(target.read_text(encoding="utf-8")),
        )

    def test_sidecar_internal_error_closes_after_three_healthy_cycles(self) -> None:
        opened = self.store.open_incident(
            {
                "classification": "SIDECAR_INTERNAL_ERROR",
                "summary": "transient heartbeat write collision",
            }
        )
        incident_id = str(opened["incident_id"])
        self.store.transition_incident(incident_id, "NEEDS_EXTERNAL_ADVICE")
        service = self.service(FakeHttp(healthy_routes()))

        first = service.run_once()
        second = service.run_once()
        third = service.run_once()

        self.assertEqual("healthy", first["status"])
        self.assertEqual("healthy", second["status"])
        self.assertEqual("healthy", third["status"])
        self.assertEqual("RECOVERED_UNREVIEWED", self.store.incidents[incident_id]["state"])
        self.assertIn(incident_id, third["reverified_transient_incidents"])

    def test_urgent_report_uses_existing_telegram_outbox_once_per_incident(self) -> None:
        opened = self.store.open_incident(
            {
                "classification": "UNSAFE_AUTOMATIC_REPAIR",
                "component": "strategy-runtime",
                "severity": "critical",
                "summary": "Automatic repair is outside the safe boundary.",
            }
        )
        incident_id = str(opened["incident_id"])
        self.store.transition_incident(incident_id, "NEEDS_EXTERNAL_ADVICE")
        self.store.write_report(
            incident_id,
            {
                "cause": "code change required",
                "next_step": "Ask GPT or Codex for a reviewed patch.",
                "needs_external_advice": True,
            },
        )
        http = FakeHttp(
            {
                TELEGRAM_QUEUE_PATH: {
                    "ok": True,
                    "record": {"id": "TG-URGENT-1", "status": "queued"},
                }
            }
        )
        service = self.service(http)

        first = service._finish(
            {"status": "needs_external_advice", "incident_id": incident_id},
            phase="reporting",
        )
        second = service._finish(
            {"status": "needs_external_advice", "incident_id": incident_id},
            phase="reporting",
        )

        self.assertTrue(first["telegram_alert"]["queued"])
        self.assertNotIn("telegram_alert", second)
        self.assertEqual(1, len(http.post_calls))
        path, payload = http.post_calls[0]
        self.assertEqual(TELEGRAM_QUEUE_PATH, path)
        self.assertEqual("internal_developer_urgent", payload["message_type"])
        self.assertTrue(payload["metadata"]["single_delivery"])
        self.assertEqual(incident_id, payload["metadata"]["single_delivery_id"])

    def test_closed_incident_never_requeues_an_old_urgent_report(self) -> None:
        opened = self.store.open_incident(
            {
                "classification": "UNKNOWN",
                "component": "drill-simulator",
                "severity": "high",
                "summary": "Synthetic communication drill.",
            }
        )
        incident_id = str(opened["incident_id"])
        self.store.transition_incident(incident_id, "NEEDS_EXTERNAL_ADVICE")
        self.store.write_report(
            incident_id,
            {
                "status": "waiting_for_advice",
                "needs_external_advice": True,
            },
        )
        self.store.transition_incident(incident_id, "CLOSED")
        http = FakeHttp({})
        service = self.service(http)

        result = service._finish(
            {"status": "healthy", "incident_id": incident_id},
            phase="reporting",
        )

        self.assertNotIn("telegram_alert", result)
        self.assertEqual([], http.post_calls)

    def test_improvement_progress_is_busy_without_recovery_or_restart(self) -> None:
        routes = healthy_routes()
        routes[IMPROVEMENT_STATUS_PATH] = {
            "state": {
                "cycle_id": "running-1",
                "status": "RUNNING",
                "phase": "vectorbt",
                "phase_index": 3,
                "progress_pct": 50,
                "updated_at": "2026-07-19T00:01:00+00:00",
            },
            "thread_alive": True,
        }
        http = FakeHttp(routes)
        service = self.service(http)

        first = service.run_once()
        self.clock.advance(120)
        second = service.run_once()

        self.assertEqual("BUSY_PROGRESSING", first["classification"])
        self.assertEqual("BUSY_PROGRESSING", second["classification"])
        self.assertEqual([], self.engine.cycles)
        self.assertEqual([], self.store.restart_requests)
        self.assertNotIn(FEATURE_HEALTH_PATH, http.get_calls)

    def test_busy_stall_is_report_only(self) -> None:
        routes = healthy_routes()
        routes[IMPROVEMENT_STATUS_PATH] = {
            "state": {
                "cycle_id": "running-1",
                "status": "RUNNING",
                "phase": "qlib",
                "phase_index": 4,
                "progress_pct": 70,
                "updated_at": "2026-07-19T00:01:00+00:00",
            },
            "thread_alive": True,
        }
        service = self.service(FakeHttp(routes), busy_stall_seconds=300)
        service.run_once()
        self.clock.advance(301)

        stalled = service.run_once()

        self.assertEqual("busy_stalled_reported", stalled["status"])
        self.assertEqual("BUSY_STALLED", stalled["classification"])
        self.assertFalse(self.engine.cycles[-1][1])
        self.assertEqual([], self.engine.executed_actions)
        self.assertEqual([], self.store.restart_requests)
        self.assertGreaterEqual(len(self.store.reports), 1)

    def test_restart_requires_five_consecutive_nonbusy_liveness_failures(self) -> None:
        http = FakeHttp({OVERVIEW_PATH: ConnectionError("app offline")})
        service = self.service(http, expected_pid=9876)

        results = [service.run_once() for _ in range(5)]

        self.assertTrue(all(not row["restart_requested"] for row in results[:4]))
        self.assertTrue(all(row["status"] == "app_unreachable_observing" for row in results[:4]))
        self.assertEqual("restart_requested", results[4]["status"])
        self.assertEqual([True], [row[1] for row in self.engine.cycles])
        self.assertEqual(1, len(self.store.restart_requests))
        self.assertEqual(9876, self.store.restart_requests[0]["expected_pid"])

    def test_delayed_and_verification_pending_are_not_operational_faults(self) -> None:
        routes = healthy_routes()
        routes[FEATURE_HEALTH_PATH] = {
            "ok": False,
            "overall": "fail",
            "broken_count": 99,
            "operational_broken_count": 0,
            "delayed_count": 7,
            "verification_pending_count": 11,
            "checks": [
                {"status": "fail", "operational_state": "delayed"},
                {"status": "fail", "operational_state": "verification_pending"},
            ],
        }
        http = FakeHttp(routes)
        service = self.service(http)

        result = service.run_once()

        self.assertEqual("healthy", result["status"])
        self.assertNotIn("CLEAR_NAMED_CACHE", self.engine.executed_actions)
        self.assertNotIn(FEATURE_HEALTH_FORCE_PATH, http.get_calls)

    def test_operational_broken_uses_only_allowlisted_force_refresh(self) -> None:
        routes = healthy_routes()
        routes[FEATURE_HEALTH_PATH] = {"operational_broken_count": 2}
        routes[FEATURE_HEALTH_FORCE_PATH] = {"operational_broken_count": 0}
        http = FakeHttp(routes)
        service = self.service(http)

        result = service.run_once()

        self.assertEqual("recovered", result["status"])
        self.assertEqual(["CLEAR_NAMED_CACHE"], self.engine.executed_actions)
        self.assertIn(FEATURE_HEALTH_FORCE_PATH, http.get_calls)

    def test_only_resident_read_only_kis_is_reconnected(self) -> None:
        routes = healthy_routes()
        routes[EXTERNAL_ENGINE_STATUS_PATH] = {
            "engines": [
                {
                    "engine_id": "vectorbt",
                    "connected": False,
                    "execution_policy": "spawn_on_demand_only",
                    "live_order_allowed": False,
                },
                {
                    "engine_id": "kis-trading-mcp",
                    "connected": False,
                    "execution_policy": "resident_read_only_gateway_auto_recover",
                    "resident_component": True,
                    "live_order_allowed": False,
                },
                {
                    "engine_id": "order-router",
                    "connected": False,
                    "execution_policy": "resident_read_only_gateway_auto_recover",
                    "live_order_allowed": True,
                },
            ]
        }
        routes[KIS_RECONNECT_PATH] = {
            "ok": True,
            "connected": True,
            "live_order_allowed": False,
        }
        http = FakeHttp(routes)
        service = self.service(http)

        result = service.run_once()

        self.assertEqual("recovered", result["status"])
        self.assertEqual(["RECONNECT_EXTERNAL_ENGINE"], self.engine.executed_actions)
        self.assertEqual(1, http.get_calls.count(KIS_RECONNECT_PATH))

    def test_failed_or_interrupted_research_job_is_retried_only_once(self) -> None:
        routes = healthy_routes()
        routes[IMPROVEMENT_STATUS_PATH] = idle_improvement("INTERRUPTED")
        routes[IMPROVEMENT_RETRY_PATH] = {
            "__status_code__": 202,
            "ok": True,
            "status": "QUEUED",
            "live_order_allowed": False,
        }
        http = FakeHttp(routes)
        service = self.service(http)

        first = service.run_once()
        second = service.run_once()

        self.assertEqual("recovered", first["status"])
        self.assertEqual(1, len(http.post_calls))
        path, payload = http.post_calls[0]
        self.assertEqual(IMPROVEMENT_RETRY_PATH, path)
        self.assertTrue(payload["research_only"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertNotEqual("restart_requested", second["status"])

    def test_cancelled_and_forbidden_capabilities_never_execute(self) -> None:
        routes = healthy_routes()
        routes[IMPROVEMENT_STATUS_PATH] = idle_improvement("CANCELLED")
        http = FakeHttp(routes)
        service = self.service(http)

        result = service.run_once()

        self.assertEqual("healthy", result["status"])
        self.assertEqual([], http.post_calls)
        self.assertEqual([], self.engine.executed_actions)
        self.assertEqual(
            {
                "cancelled_job_retry",
                "live_order",
                "api_key_change",
                "risk_limit_relaxation",
                "code_edit",
                "security_disable",
                "process_kill",
                "lock_delete",
            },
            set(FORBIDDEN_AUTOMATION),
        )
        with self.assertRaises(PermissionError):
            service._recovery_post("/api/orders/live", {})
        with self.assertRaises(PermissionError):
            service._recovery_get("/api/security/disable")

    def test_corrupt_own_state_rebuilds_only_internal_ledger(self) -> None:
        target = self.data_root / "internal_developer" / "service_state.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{not-json", encoding="utf-8")
        service = self.service(FakeHttp(healthy_routes()))

        result = service.run_once()

        self.assertEqual("INTERNAL_STATE_LEDGER_INCONSISTENT", result["classification"])
        self.assertEqual(["RESTORE_INTERNAL_STATE_LEDGER"], self.engine.executed_actions)
        self.assertEqual(1, self.store.rebuild_count)
        rebuilt = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual("codexstock.internal-developer-service-state.v1", rebuilt["schema"])

    def test_single_instance_lock_never_deletes_lock_file(self) -> None:
        path = self.root / "runtime" / "service.lock"
        first = SingleInstanceLock(path)
        second = SingleInstanceLock(path)
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        first.release()
        self.assertTrue(path.is_file())
        self.assertTrue(second.acquire())
        second.release()
        self.assertTrue(path.is_file())

    def test_direct_script_once_entrypoint_works_without_app_package_import(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["CODEXSTOCK_USER_DATA_DIR"] = str(self.data_root / "direct-entry")
        completed = subprocess.run(
            [
                sys.executable,
                str(repository / "app" / "internal_developer_service.py"),
                "once",
                "--repo-root",
                str(self.root),
                "--base-url",
                "http://127.0.0.1:1",
            ],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("app_unreachable_observing", payload["status"])
        self.assertFalse(payload["incident_opened"])
        self.assertTrue((self.root / "runtime" / "internal_developer" / "service.lock").is_file())
        self.assertFalse((self.root / "runtime" / "codexstock_restart_request.json").exists())

    def test_real_store_and_engine_healthy_once_has_no_incident_or_restart(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(
            real_store,
            max_attempts=1,
            cooldown_seconds=0,
        )
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        result = service.run_once()

        self.assertEqual("healthy", result["status"])
        self.assertEqual([], real_store.list_incidents())
        self.assertEqual([], real_store.list_reports())
        self.assertEqual(service.restart_request_path, real_store.restart_request_path)
        self.assertEqual(
            self.root / "runtime" / "codexstock_restart_request.json",
            service.restart_request_path,
        )
        self.assertFalse(real_store.restart_request_path.exists())

    def test_single_transient_liveness_failure_does_not_open_incident(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        routes = healthy_routes()
        routes[OVERVIEW_PATH] = [
            ConnectionError("brief app transition"),
            {"ok": True, "runtime": {"app": "running"}},
        ]
        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(routes),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        first = service.run_once()
        second = service.run_once()
        status = real_store.status()
        report_count = len(real_store.list_reports())
        third = service.run_once()

        self.assertEqual("app_unreachable_observing", first["status"])
        self.assertFalse(first["incident_opened"])
        self.assertEqual("healthy", second["status"])
        self.assertEqual([], second["reverified_transient_incidents"])
        self.assertTrue(status["healthy"])
        self.assertEqual("healthy", status["operational_status"])
        self.assertEqual(0, status["open_incidents"])
        self.assertFalse(status["attention_required"])
        self.assertEqual(0, report_count)
        self.assertEqual([], third["reverified_transient_incidents"])
        self.assertEqual(report_count, len(real_store.list_reports()))
        self.assertFalse(real_store.restart_request_path.exists())

    def test_single_transient_diagnostic_failure_does_not_open_incident(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        routes = healthy_routes()
        routes[IMPROVEMENT_STATUS_PATH] = [
            TimeoutError("bounded diagnostic timeout"),
            idle_improvement(),
        ]
        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(routes),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        first = service.run_once()
        second = service.run_once()

        self.assertEqual("diagnostic_endpoint_observing", first["status"])
        self.assertFalse(first["incident_opened"])
        self.assertEqual([], second["reverified_transient_incidents"])
        self.assertEqual([], real_store.list_incidents())
        self.assertEqual(0, real_store.status()["open_incidents"])
        self.assertFalse(real_store.restart_request_path.exists())

    def test_restart_liveness_incident_requires_three_healthy_reverification_cycles(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        opened = real_store.open_incident(
            {
                "primary_issue": "HEARTBEAT_MISSING",
                "classification": "HEARTBEAT_MISSING",
                "summary": "The app stopped answering bounded liveness probes.",
            }
        )
        incident_id = str(opened["incident_id"])
        real_store.transition_incident(incident_id, "DIAGNOSING")
        real_store.transition_incident(incident_id, "WAITING_FOR_RESTART")
        real_store.record_recovery_attempt(
            incident_id,
            {
                "action": "REQUEST_CODEXSTOCK_RESTART",
                "parameters": {"expected_pid": 9876, "reason_code": "heartbeat_missing"},
                "status": "succeeded",
                "handler_result": {"restart_request_created": True},
                "post_verification": {"success": True},
            },
        )
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        first = service.run_once()
        second = service.run_once()
        state_after_two = real_store.get_incident(incident_id)["state"]
        third = service.run_once()
        incident = real_store.get_incident(incident_id)

        self.assertEqual([], first["reverified_transient_incidents"])
        self.assertEqual([], second["reverified_transient_incidents"])
        self.assertEqual("WAITING_FOR_RESTART", state_after_two)
        self.assertEqual([incident_id], third["reverified_transient_incidents"])
        self.assertEqual("RECOVERED_UNREVIEWED", incident["state"])
        recovery_report = real_store.list_reports(limit=1)[0]
        verification = recovery_report["payload"]["verification"]
        self.assertEqual(3, verification["consecutive_healthy_cycles"])
        self.assertTrue(verification["pid_changed"])
        self.assertFalse(real_store.restart_request_path.exists())

    def test_pending_restart_request_blocks_liveness_reconciliation_and_is_untouched(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        opened = real_store.open_incident(
            {
                "primary_issue": "HEARTBEAT_MISSING",
                "classification": "HEARTBEAT_MISSING",
                "summary": "The app stopped answering bounded liveness probes.",
            }
        )
        incident_id = str(opened["incident_id"])
        real_store.transition_incident(incident_id, "DIAGNOSING")
        real_store.transition_incident(incident_id, "WAITING_FOR_RESTART")
        real_store.record_recovery_attempt(
            incident_id,
            {
                "action": "REQUEST_CODEXSTOCK_RESTART",
                "parameters": {"expected_pid": 9876, "reason_code": "heartbeat_missing"},
                "status": "succeeded",
            },
        )
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )
        service.restart_request_path.parent.mkdir(parents=True, exist_ok=True)
        original = b'{not-json-but-owned-by-launcher\n'
        service.restart_request_path.write_bytes(original)

        results = [service.run_once() for _ in range(4)]

        self.assertTrue(all(row["reverified_transient_incidents"] == [] for row in results))
        self.assertEqual("WAITING_FOR_RESTART", real_store.get_incident(incident_id)["state"])
        self.assertEqual(original, service.restart_request_path.read_bytes())

    def test_consumed_restart_request_with_same_pid_records_responsiveness_recovery(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        opened = real_store.open_incident(
            {
                "primary_issue": "HEARTBEAT_MISSING",
                "classification": "HEARTBEAT_MISSING",
                "summary": "The app stopped answering bounded liveness probes.",
            }
        )
        incident_id = str(opened["incident_id"])
        real_store.transition_incident(incident_id, "DIAGNOSING")
        real_store.transition_incident(incident_id, "WAITING_FOR_RESTART")
        real_store.record_recovery_attempt(
            incident_id,
            {
                "action": "REQUEST_CODEXSTOCK_RESTART",
                "parameters": {"expected_pid": 4321, "reason_code": "heartbeat_missing"},
                "status": "succeeded",
            },
        )
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        results = [service.run_once() for _ in range(3)]
        report = real_store.list_reports(limit=1)[0]
        verification = report["payload"]["verification"]

        self.assertEqual([incident_id], results[-1]["reverified_transient_incidents"])
        self.assertEqual("RECOVERED_UNREVIEWED", real_store.get_incident(incident_id)["state"])
        self.assertFalse(verification["restart_verified"])
        self.assertEqual(
            "service_restored_without_verified_restart", verification["recovery_basis"]
        )

    def test_real_store_and_engine_busy_stall_remains_report_only(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        routes = healthy_routes()
        routes[IMPROVEMENT_STATUS_PATH] = {
            "state": {
                "cycle_id": "real-running-1",
                "status": "RUNNING",
                "phase": "nautilus",
                "phase_index": 5,
                "progress_pct": 88,
                "updated_at": "2026-07-19T00:02:00+00:00",
            },
            "thread_alive": True,
        }
        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(routes),
            config=ServiceConfig(expected_pid=4321, busy_stall_seconds=300),
            clock=self.clock,
        )
        service.run_once()
        self.clock.advance(301)

        result = service.run_once()

        self.assertEqual("busy_stalled_reported", result["status"])
        self.assertEqual("BUSY_STALLED", result["classification"])
        self.assertGreaterEqual(len(real_store.list_reports()), 1)
        self.assertFalse(real_store.restart_request_path.exists())

    def test_registered_sqlite_lock_signal_runs_only_read_only_probe(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        database = self.root / "runtime.sqlite3"
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE evidence(value TEXT)")
            connection.execute("INSERT INTO evidence(value) VALUES ('kept')")
            connection.commit()
        routes = healthy_routes()
        routes[FEATURE_HEALTH_PATH] = {
            "operational_broken_count": 1,
            "checks": [
                {
                    "id": "runtime_database",
                    "operational_state": "broken",
                    "detail": "SQLite database locked",
                    "database_id": "runtime-db",
                }
            ],
        }
        routes[FEATURE_HEALTH_FORCE_PATH] = {"operational_broken_count": 0}
        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(routes),
            config=ServiceConfig(expected_pid=4321),
            registered_databases={"runtime-db": database},
            clock=self.clock,
        )

        result = service.run_once()
        database_probe = next(
            row for row in result["results"] if row.get("action") == "DETECT_DB_LOCK"
        )
        with closing(sqlite3.connect(database)) as connection:
            values = connection.execute("SELECT value FROM evidence").fetchall()

        self.assertEqual("read_only", database_probe["handler_result"]["mode"])
        self.assertEqual([("kept",)], values)
        self.assertFalse(real_store.restart_request_path.exists())

    def test_registered_sqlite_exclusive_lock_is_detected_without_http_hint(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        database = self.root / "actively-locked.sqlite3"
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("CREATE TABLE evidence(value TEXT)")
            connection.execute("INSERT INTO evidence(value) VALUES ('kept')")
            connection.commit()
        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            registered_databases={"runtime-db": database},
            clock=self.clock,
        )

        locker = sqlite3.connect(database, timeout=0.1, isolation_level=None)
        try:
            locker.execute("BEGIN EXCLUSIVE")
            result = service.run_once()
        finally:
            locker.rollback()
            locker.close()

        database_probe = next(
            row for row in result["results"] if row.get("action") == "DETECT_DB_LOCK"
        )
        with closing(sqlite3.connect(database)) as connection:
            values = connection.execute("SELECT value FROM evidence").fetchall()

        self.assertEqual("DB_LOCKED", result["classification"])
        self.assertTrue(database_probe["handler_result"]["locked"])
        self.assertEqual("read_only", database_probe["handler_result"]["mode"])
        self.assertEqual([("kept",)], values)
        self.assertFalse(real_store.restart_request_path.exists())

    def test_structured_gpt_guidance_runs_only_through_local_policy_and_reverification(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        routes = healthy_routes()
        routes[FEATURE_HEALTH_FORCE_PATH] = {
            "ok": True,
            "operational_broken_count": 0,
        }
        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        opened = real_engine.run_cycle(
            {"status": "degraded", "abnormal": True},
            auto_recover=True,
        )
        incident_id = str(opened["incident_id"])
        advice = real_store.submit_advice(
            {
                "incident_id": incident_id,
                "summary": "Use the bounded cache refresh and verify health.",
                "proposed_actions": [
                    {
                        "action": "CLEAR_NAMED_CACHE",
                        "parameters": {"cache_id": "feature-health"},
                    }
                ],
            }
        )
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(routes),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        result = service.run_once()
        stored_advice = real_store.get_advice(str(advice["advice_id"]))
        incident = real_store.get_incident(incident_id)

        self.assertEqual("recovered_from_external_guidance", result["status"])
        self.assertEqual("RECOVERED_UNREVIEWED", incident["state"])
        self.assertEqual("ACCEPTED_AS_GUIDANCE", stored_advice["status"])
        self.assertFalse(stored_advice["execution_authorized"])
        self.assertTrue(stored_advice["application_result"]["success"])
        self.assertTrue(stored_advice["application_result"]["text_ignored"])
        self.assertFalse(real_store.restart_request_path.exists())

    def test_gpt_restart_proposal_is_rejected_even_when_structurally_valid(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        opened = real_engine.run_cycle(
            {"status": "degraded", "abnormal": True},
            auto_recover=True,
        )
        incident_id = str(opened["incident_id"])
        advice = real_store.submit_advice(
            {
                "incident_id": incident_id,
                "summary": "Restart proposal must remain locally forbidden.",
                "proposed_actions": [
                    {
                        "action": "REQUEST_CODEXSTOCK_RESTART",
                        "parameters": {
                            "expected_pid": 4321,
                            "reason_code": "external_advice",
                        },
                    }
                ],
            }
        )
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        result = service.run_once()
        stored_advice = real_store.get_advice(str(advice["advice_id"]))
        incident = real_store.get_incident(incident_id)

        self.assertEqual("external_advice_rejected", result["status"])
        self.assertEqual("NEEDS_CODE_FIX", incident["state"])
        self.assertEqual("REJECTED", stored_advice["status"])
        self.assertFalse(stored_advice["execution_authorized"])
        self.assertEqual(
            "external_advice_restart_forbidden",
            stored_advice["application_result"]["results"][0]["reason_code"],
        )
        self.assertFalse(real_store.restart_request_path.exists())

    def test_gpt_report_only_guidance_does_not_claim_the_incident_was_repaired(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        opened = real_engine.run_cycle(
            {"status": "degraded", "abnormal": True},
            auto_recover=True,
        )
        incident_id = str(opened["incident_id"])
        advice = real_store.submit_advice(
            {
                "incident_id": incident_id,
                "summary": "Write another bounded escalation report.",
                "proposed_actions": [
                    {
                        "action": "WRITE_INCIDENT_REPORT",
                        "parameters": {"report_type": "escalation"},
                    }
                ],
            }
        )
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        result = service.run_once()
        stored_advice = real_store.get_advice(str(advice["advice_id"]))
        incident = real_store.get_incident(incident_id)

        self.assertEqual("external_advice_recorded", result["status"])
        self.assertEqual("NEEDS_CODE_FIX", incident["state"])
        self.assertEqual("ACCEPTED_AS_GUIDANCE", stored_advice["status"])
        self.assertTrue(stored_advice["application_result"]["success"])
        self.assertFalse(stored_advice["application_result"]["recovered"])
        self.assertFalse(real_store.restart_request_path.exists())

    def test_gpt_report_only_guidance_closes_verified_informational_drill(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        incident = real_store.open_incident(
            {
                "classification": "UNKNOWN",
                "component": "drill-simulator",
                "summary": "Synthetic GPT round-trip drill.",
                "drill": True,
                "actual_failure": False,
            }
        )
        incident_id = str(incident["incident_id"])
        real_store.transition_incident(incident_id, "NEEDS_EXTERNAL_ADVICE")
        advice = real_store.submit_advice(
            {
                "incident_id": incident_id,
                "summary": "Record the completed communication drill.",
                "proposed_actions": [
                    {
                        "action": "WRITE_INCIDENT_REPORT",
                        "parameters": {"report_type": "diagnostic"},
                    }
                ],
            }
        )
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        result = service.run_once()
        stored_advice = real_store.get_advice(str(advice["advice_id"]))
        stored_incident = real_store.get_incident(incident_id)

        self.assertEqual("recovered_from_external_guidance", result["status"])
        self.assertEqual("CLOSED", stored_incident["state"])
        self.assertEqual("ACCEPTED_AS_GUIDANCE", stored_advice["status"])
        self.assertTrue(
            stored_advice["application_result"]["informational_drill_completed"]
        )
        self.assertEqual(0, real_store.status()["drill_open_incidents"])

    def test_service_reconciles_legacy_verified_report_only_drill(self) -> None:
        from app.internal_developer_engine import InternalDeveloperEngine
        from app.internal_developer_store import InternalDeveloperStore

        real_store = InternalDeveloperStore(self.root, data_root=self.data_root)
        real_engine = InternalDeveloperEngine(real_store, max_attempts=1, cooldown_seconds=0)
        incident = real_store.open_incident(
            {
                "classification": "UNKNOWN",
                "component": "drill-simulator-v2",
                "summary": "Legacy completed drill.",
                "drill": True,
                "actual_failure": False,
            }
        )
        incident_id = str(incident["incident_id"])
        real_store.transition_incident(incident_id, "NEEDS_EXTERNAL_ADVICE")
        advice = real_store.submit_advice(
            {
                "incident_id": incident_id,
                "summary": "Verified report-only guidance.",
                "proposed_actions": [
                    {
                        "action": "WRITE_INCIDENT_REPORT",
                        "parameters": {"report_type": "diagnostic"},
                    }
                ],
            }
        )
        real_store.transition_incident(incident_id, "AUTO_RECOVERING")
        real_store.record_recovery_attempt(
            incident_id,
            {
                "action": "WRITE_INCIDENT_REPORT",
                "status": "succeeded",
                "post_verification": {"ok": True, "store_acknowledged": True},
            },
        )
        real_store.transition_incident(incident_id, "NEEDS_CODE_FIX")
        real_store.update_advice(
            str(advice["advice_id"]),
            {"status": "ACCEPTED_AS_GUIDANCE"},
        )
        service = InternalDeveloperService(
            repo_root=self.root,
            data_root=self.data_root,
            store=real_store,
            engine=real_engine,
            http_client=FakeHttp(healthy_routes()),
            config=ServiceConfig(expected_pid=4321),
            clock=self.clock,
        )

        closed = service._reconcile_completed_informational_drills()

        self.assertEqual([incident_id], closed)
        self.assertEqual("CLOSED", real_store.get_incident(incident_id)["state"])
        self.assertEqual(0, real_store.status()["drill_open_incidents"])

    def test_pipeline_incident_auto_closes_only_after_three_healthy_proofs(self) -> None:
        incident = self.store.open_incident(
            {"classification": "LEGACY_APPROVAL_GATE_ACTIVE"}
        )
        self.store.transition_incident(str(incident["incident_id"]), "NEEDS_CODE_FIX")
        service = self.service(FakeHttp(healthy_routes()))
        pipeline = {
            "trading_pipeline_healthy": True,
            "state": "connected",
            "execution_mode_contract": {"mode_consistent": True},
            "stage_counts": {
                "candidate_tickets": 4,
                "signed_signal_published": 4,
                "executor_processed": 4,
                "executor_results": 4,
            },
            "pending_handoff_count": 0,
            "incidents": [],
        }

        self.assertEqual([], service._reconcile_recovered_pipeline_incidents(pipeline))
        self.assertEqual([], service._reconcile_recovered_pipeline_incidents(pipeline))
        closed = service._reconcile_recovered_pipeline_incidents(pipeline)

        self.assertEqual([incident["incident_id"]], closed)
        self.assertEqual("CLOSED", self.store.get_incident(str(incident["incident_id"]))["state"])


if __name__ == "__main__":
    unittest.main()
