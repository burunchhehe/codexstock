from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.internal_developer_store import (
    ADVICE_SCHEMA,
    INCIDENT_SCHEMA,
    RESTART_REQUEST_SCHEMA,
    InternalDeveloperStore,
)
from app.internal_developer_engine import InternalDeveloperEngine


class InternalDeveloperStoreTests(unittest.TestCase):
    def _store(self, directory: str) -> InternalDeveloperStore:
        base = Path(directory)
        repo = base / "repo"
        data = base / "active-data"
        repo.mkdir()
        return InternalDeveloperStore(repo, data_root=data)

    def _incident(self, store: InternalDeveloperStore) -> dict[str, object]:
        return store.open_incident(
            {
                "classification": "EXTERNAL_ENGINE_DISCONNECTED",
                "component": "external_engine",
                "severity": "warning",
                "summary": "External engine heartbeat stopped",
                "evidence": {"last_heartbeat_seconds": 301},
            }
        )

    def test_store_lives_below_active_data_root_and_uses_individual_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            event = store.record_event("probe.completed", {"healthy": False})

            incident_files = list(store.incidents_dir.glob("INC-*.json"))
            event_files = list(store.events_dir.glob("EVT-*.json"))
            temporary_files = list(store.root.rglob("*.tmp"))

            self.assertEqual(Path(directory) / "active-data" / "internal_developer", store.root)
            self.assertEqual(1, len(incident_files))
            self.assertGreaterEqual(len(event_files), 2)
            self.assertEqual(incident["incident_id"], json.loads(incident_files[0].read_text(encoding="utf-8"))["incident_id"])
            self.assertEqual(event["event_id"], store.list_events()[0]["event_id"])
            self.assertEqual([], temporary_files)

    def test_healthy_is_separate_from_unreviewed_attention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            unhealthy = store.status()

            store.transition_incident(incident["incident_id"], "AUTO_RECOVERING")
            store.transition_incident(incident["incident_id"], "RECOVERED_UNREVIEWED")
            report = store.write_report(
                incident["incident_id"],
                {"cause": "stale socket", "actions": ["external engine reconnect"], "verification": "healthy"},
            )
            recovered = store.attention_summary()

            store.acknowledge_report(report["report_id"], "owner reviewed")
            store.transition_incident(incident["incident_id"], "REVIEWED")
            reviewed = store.attention_summary()

            self.assertFalse(unhealthy["healthy"])
            self.assertEqual("degraded", unhealthy["operational_status"])
            self.assertTrue(recovered["healthy"])
            self.assertEqual("healthy", recovered["operational_status"])
            self.assertTrue(recovered["attention_required"])
            self.assertEqual(1, recovered["unreviewed_reports"])
            self.assertFalse(reviewed["attention_required"])

    def test_incident_transitions_are_strict_and_attempts_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            incident_id = str(incident["incident_id"])

            with self.assertRaises(ValueError):
                store.transition_incident(incident_id, "REVIEWED")
            with self.assertRaises(ValueError):
                store.get_incident("../state.json")

            for index in range(55):
                store.record_recovery_attempt(
                    incident_id,
                    {"action": "external engine reconnect", "attempt": index, "success": False},
                )
            saved = store.get_incident(incident_id)

            self.assertEqual(INCIDENT_SCHEMA, saved["schema"])
            self.assertEqual(50, len(saved["recovery_attempts"]))
            self.assertEqual(5, saved["recovery_attempts"][0]["attempt"])

    def test_same_open_diagnostic_fingerprint_is_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            first = self._incident(store)
            second = self._incident(store)

            self.assertEqual(first["incident_id"], second["incident_id"])
            self.assertEqual(1, len(store.list_incidents()))
            self.assertEqual(2, second["recurrence_count"])
            self.assertTrue(second["deduplicated"])

    def test_report_writes_latest_and_redacted_telegram_launcher_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            report = store.write_report(
                incident["incident_id"],
                {
                    "cause": "API key=super-secret-token and account 1234-5678-9012",
                    "actions": ["external engine reconnect"],
                    "verification": {"access_token": "token-value", "healthy": True},
                    "external_advice_question": "Could a stale connection explain this?",
                },
            )

            latest = json.loads(store.latest_report_path.read_text(encoding="utf-8"))
            telegram = store.telegram_report_path.read_text(encoding="utf-8")
            launcher = store.launcher_report_path.read_text(encoding="utf-8")
            stored = json.dumps(report, ensure_ascii=False)

            self.assertEqual(report["report_id"], latest["report_id"])
            self.assertIn("[REDACTED]", stored)
            self.assertNotIn("super-secret-token", stored + telegram + launcher)
            self.assertNotIn("1234-5678-9012", stored + telegram + launcher)
            self.assertIn("9012", stored + telegram + launcher)
            self.assertIn("실행 권한이 없습니다", telegram)

    def test_gpt_advice_is_bounded_redacted_untrusted_and_forbidden_work_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            store.transition_incident(incident["incident_id"], "NEEDS_EXTERNAL_ADVICE")
            advice = store.submit_advice(
                {
                    "incident_id": incident["incident_id"],
                    "analysis": "Disable security and edit source code, then place a live order.",
                    "api_key": "plain-secret",
                    "account_number": "123456789012",
                    "execution_authorized": True,
                    "large_context": "x" * 200_000,
                }
            )
            on_disk = store.advice_dir / f"{advice['advice_id']}.json"
            serialized = on_disk.read_text(encoding="utf-8")

            self.assertEqual(ADVICE_SCHEMA, advice["schema"])
            self.assertFalse(advice["execution_authorized"])
            self.assertEqual("QUARANTINED", advice["status"])
            self.assertTrue(advice["policy_evaluation"]["quarantined"])
            self.assertIn("live_order", advice["policy_evaluation"]["forbidden_categories"])
            self.assertIn("code_modification", advice["policy_evaluation"]["forbidden_categories"])
            self.assertIn("security_disable", advice["policy_evaluation"]["forbidden_categories"])
            self.assertEqual(
                "NEEDS_EXTERNAL_ADVICE",
                store.get_incident(incident["incident_id"])["state"],
            )
            self.assertLess(on_disk.stat().st_size, 80 * 1024)
            self.assertNotIn("plain-secret", serialized)
            self.assertNotIn("123456789012", serialized)
            with self.assertRaises(ValueError):
                store.update_advice(advice["advice_id"], {"execution_authorized": True})

            symbolic = store.submit_advice(
                {
                    "incident_id": incident["incident_id"],
                    "proposal": "PLACE_LIVE_ORDER",
                    "note": "account number 123456789012",
                }
            )
            self.assertIn("live_order", symbolic["policy_evaluation"]["forbidden_categories"])
            self.assertNotIn("123456789012", json.dumps(symbolic, ensure_ascii=False))

    def test_safe_advice_still_never_receives_execution_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            store.transition_incident(incident["incident_id"], "NEEDS_EXTERNAL_ADVICE")
            advice = store.submit_advice(
                {
                    "incident_id": incident["incident_id"],
                    "recommendation": "Reconnect the external engine and verify heartbeat before continuing.",
                }
            )
            reviewed = store.update_advice(advice["advice_id"], {"status": "ACCEPTED_AS_GUIDANCE"})
            engine_updated = store.update_advice(
                advice["advice_id"], {"engine_result": {"status": "validated", "executed": False}}
            )

            self.assertEqual("RECEIVED", advice["status"])
            self.assertEqual(
                "ADVICE_RECEIVED",
                store.get_incident(incident["incident_id"])["state"],
            )
            self.assertIn("EXTERNAL_ENGINE_RECONNECT", advice["policy_evaluation"]["allowed_action_mentions"])
            self.assertFalse(advice["policy_evaluation"]["quarantined"])
            self.assertFalse(reviewed["execution_authorized"])
            self.assertEqual("validated", engine_updated["engine_result"]["status"])
            self.assertFalse(engine_updated["execution_authorized"])

    def test_safe_advice_advances_failed_recovery_to_advice_received(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            store.transition_incident(incident["incident_id"], "AUTO_RECOVERING")
            store.transition_incident(incident["incident_id"], "RECOVERY_FAILED")

            advice = store.submit_advice(
                {
                    "incident_id": incident["incident_id"],
                    "summary": "Retry the failed research job once and verify the result.",
                }
            )

            self.assertEqual("RECEIVED", advice["status"])
            self.assertEqual(
                "ADVICE_RECEIVED",
                store.get_incident(incident["incident_id"])["state"],
            )
            self.assertFalse(advice["execution_authorized"])

    def test_restart_is_an_atomic_request_for_the_independent_scheduler(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            request = store.request_restart(4321, incident["incident_id"], "process is unresponsive")
            saved = json.loads(store.restart_request_path.read_text(encoding="utf-8"))
            original_bytes = store.restart_request_path.read_bytes()
            duplicate = store.request_restart(9999, incident["incident_id"], "must not replace pending request")

            self.assertEqual(RESTART_REQUEST_SCHEMA, saved["schema"])
            self.assertEqual(request["request_id"], saved["request_id"])
            self.assertEqual(4321, saved["expected_pid"])
            self.assertFalse(saved["execution_performed"])
            self.assertTrue(saved["scheduler_authority_required"])
            self.assertTrue(duplicate["already_pending"])
            self.assertEqual(original_bytes, store.restart_request_path.read_bytes())
            self.assertEqual([], list(store.restart_request_path.parent.glob("*.tmp")))
            with self.assertRaises(ValueError):
                store.request_restart(0, incident["incident_id"], "bad pid")

    def test_playbook_is_reusable_only_for_verified_allowlisted_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            safe = store.learn_playbook(
                incident["incident_id"],
                {"action": "external engine reconnect"},
                {"success": True, "verified": True},
            )
            forbidden = store.learn_playbook(
                incident["incident_id"],
                {"action": "edit source code and disable security"},
                {"success": True, "verified": True},
            )
            engine_shape = store.learn_playbook(
                incident["incident_id"],
                {"action": "CLEAR_NAMED_CACHE", "parameters": {"cache_id": "market-snapshot"}},
                {"status": "succeeded", "post_verification": {"success": True}},
            )

            self.assertTrue(safe["automatic_reuse_eligible"])
            self.assertFalse(safe["execution_authorized"])
            self.assertFalse(forbidden["automatic_reuse_eligible"])
            self.assertEqual("QUARANTINED_OR_UNVERIFIED", forbidden["status"])
            self.assertTrue(engine_shape["automatic_reuse_eligible"])

    def test_real_engine_cache_cycle_persists_recovery_report_and_playbook(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            engine = InternalDeveloperEngine(store, cooldown_seconds=0)
            state = {"valid": False}

            def clear(parameters: dict[str, object], context: dict[str, object]) -> dict[str, object]:
                state["valid"] = True
                return {"success": True, "cleared": parameters["cache_id"]}

            engine.register_named_cache(
                "market-snapshot",
                clear,
                lambda result, parameters, context: {"success": state["valid"]},
            )
            result = engine.run_cycle({"cache_valid": False, "cache_id": "market-snapshot"})
            incident = store.get_incident(result["incident_id"])
            playbooks = store.list_playbooks()

            self.assertEqual("recovered", result["status"])
            self.assertEqual("RECOVERED_UNREVIEWED", incident["state"])
            self.assertGreaterEqual(len(store.list_reports()), 1)
            self.assertEqual(1, len(playbooks))
            self.assertTrue(playbooks[0]["automatic_reuse_eligible"])
            self.assertFalse(playbooks[0]["execution_authorized"])

    def test_real_engine_keeps_distinct_issue_fingerprints_while_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            engine = InternalDeveloperEngine(store, cooldown_seconds=0)

            cache = engine.run_cycle(
                {"cache_valid": False, "cache_id": "market-snapshot"}, auto_recover=False
            )
            external = engine.run_cycle(
                {"external_engine_connected": False, "engine_id": "research-engine"},
                auto_recover=False,
            )

            self.assertNotEqual(cache["incident_id"], external["incident_id"])
            self.assertEqual("CACHE_INVALID", store.get_incident(cache["incident_id"])["classification"])
            self.assertEqual(
                "EXTERNAL_ENGINE_DISCONNECTED",
                store.get_incident(external["incident_id"])["classification"],
            )
            self.assertEqual(2, len(store.list_incidents()))

    def test_real_engine_busy_stall_is_report_only_and_restart_waits_for_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            engine = InternalDeveloperEngine(store, cooldown_seconds=0)
            stalled = engine.run_cycle(
                {
                    "heartbeat_age_seconds": 700,
                    "busy": True,
                    "progress_age_seconds": 500,
                    "expected_pid": 777,
                }
            )

            self.assertEqual("busy_stalled_reported", stalled["status"])
            self.assertEqual("NEEDS_EXTERNAL_ADVICE", store.get_incident(stalled["incident_id"])["state"])
            self.assertFalse(store.restart_request_path.exists())
            self.assertTrue(all(row["action"] == "WRITE_INCIDENT_REPORT" for row in stalled["results"]))

            restart = engine.run_cycle({"process_responsive": False, "expected_pid": 777})
            request = json.loads(store.restart_request_path.read_text(encoding="utf-8"))

            self.assertEqual("restart_requested", restart["status"])
            self.assertEqual("WAITING_FOR_RESTART", store.get_incident(restart["incident_id"])["state"])
            self.assertEqual(777, request["expected_pid"])
            self.assertFalse(request["execution_performed"])

    def test_corrupt_index_and_state_are_rebuilt_from_source_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            incident = self._incident(store)
            report = store.write_report(incident["incident_id"], {"cause": "test"})
            store.index_path.write_text("{broken", encoding="utf-8")
            store.state_path.write_text("[]", encoding="utf-8")

            repaired = InternalDeveloperStore(store.repo_root, data_root=store.data_root)
            status = repaired.status()
            index = json.loads(repaired.index_path.read_text(encoding="utf-8"))
            state = json.loads(repaired.state_path.read_text(encoding="utf-8"))

            self.assertEqual(1, status["counts"]["incidents"])
            self.assertEqual(1, status["counts"]["reports"])
            self.assertIn(incident["incident_id"], index["entities"]["incidents"])
            self.assertIn(report["report_id"], index["entities"]["reports"])
            self.assertEqual(status["open_incidents"], state["status"]["open_incidents"])

    def test_module_can_be_imported_directly_from_the_app_directory(self) -> None:
        app_dir = Path(__file__).resolve().parents[1] / "app"
        completed = subprocess.run(
            [sys.executable, "-c", "import internal_developer_store; print('ok')"],
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("ok", completed.stdout.strip())


if __name__ == "__main__":
    unittest.main()
