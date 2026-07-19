from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import codexstock_mcp_server as mcp_server
from app.internal_developer_engine import InternalDeveloperEngine
from app.internal_developer_service import (
    EXTERNAL_ENGINE_STATUS_PATH,
    FEATURE_HEALTH_FORCE_PATH,
    FEATURE_HEALTH_PATH,
    IMPROVEMENT_STATUS_PATH,
    OVERVIEW_PATH,
    SYSTEM_RESOURCES_PATH,
    InternalDeveloperService,
    ServiceConfig,
)
from app.internal_developer_store import InternalDeveloperStore


class LocalHttp:
    def __init__(self) -> None:
        self.get_calls: list[str] = []

    def get(self, path: str, *, timeout: float) -> dict[str, object]:
        self.get_calls.append(path)
        routes: dict[str, dict[str, object]] = {
            OVERVIEW_PATH: {"ok": True, "runtime": {"app": "running"}},
            SYSTEM_RESOURCES_PATH: {"ok": True, "app": {"pid": 4321}},
            IMPROVEMENT_STATUS_PATH: {
                "ok": True,
                "state": {
                    "cycle_id": "idle-cycle",
                    "status": "COMPLETED",
                    "phase": "completed",
                    "phase_index": 1,
                    "progress_pct": 100,
                },
                "thread_alive": False,
                "heavy_research_lock_active": False,
            },
            FEATURE_HEALTH_PATH: {
                "ok": True,
                "operational_broken_count": 0,
                "delayed_count": 0,
                "verification_pending_count": 0,
            },
            FEATURE_HEALTH_FORCE_PATH: {
                "ok": True,
                "operational_broken_count": 0,
            },
            EXTERNAL_ENGINE_STATUS_PATH: {
                "ok": True,
                "engines": [
                    {
                        "engine_id": "kis-trading-mcp",
                        "connected": True,
                        "execution_policy": "resident_read_only_gateway_auto_recover",
                        "live_order_allowed": False,
                    }
                ],
            },
        }
        return routes[path]

    def post(
        self, path: str, payload: dict[str, object], *, timeout: float
    ) -> dict[str, object]:
        raise AssertionError(f"unexpected POST: {path}")


class InternalDeveloperEndToEndTests(unittest.TestCase):
    @staticmethod
    def _mcp_payload(result: dict[str, object]) -> dict[str, object]:
        content = result["content"]
        assert isinstance(content, list) and content
        row = content[0]
        assert isinstance(row, dict)
        return json.loads(str(row["text"]))

    def test_gpt_reads_report_submits_guidance_and_sidecar_reverifies_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_root = root / "active-data"
            store = InternalDeveloperStore(root, data_root=data_root)
            engine = InternalDeveloperEngine(store, max_attempts=1, cooldown_seconds=0)
            opened = engine.run_cycle(
                {"status": "degraded", "abnormal": True},
                auto_recover=True,
            )
            incident_id = str(opened["incident_id"])
            self.assertEqual("NEEDS_EXTERNAL_ADVICE", store.get_incident(incident_id)["state"])
            attempt_count_before_advice = len(
                store.get_incident(incident_id)["recovery_attempts"]
            )

            with patch.object(mcp_server, "_internal_developer_store", return_value=store):
                before = self._mcp_payload(
                    mcp_server._call_tool("codexstock_internal_developer_brief", {})
                )
                submitted = self._mcp_payload(
                    mcp_server._call_tool(
                        "codexstock_submit_developer_advice",
                        {
                            "incident_id": incident_id,
                            "summary": "Refresh the bounded feature-health cache and verify it.",
                            "proposed_actions": [
                                {
                                    "action": "CLEAR_NAMED_CACHE",
                                    "parameters": {"cache_id": "feature-health"},
                                }
                            ],
                        },
                    )
                )

            self.assertIn("latest_report", before, before)
            self.assertEqual(incident_id, before["latest_report"]["incident_id"])
            self.assertFalse(submitted["execution_authorized"])
            self.assertFalse(submitted["execution_performed"])
            self.assertEqual("ADVICE_RECEIVED", store.get_incident(incident_id)["state"])
            self.assertEqual(
                attempt_count_before_advice,
                len(store.get_incident(incident_id)["recovery_attempts"]),
            )

            http = LocalHttp()
            service = InternalDeveloperService(
                repo_root=root,
                data_root=data_root,
                store=store,
                engine=engine,
                http_client=http,
                config=ServiceConfig(expected_pid=4321),
            )
            recovered = service.run_once()

            with patch.object(mcp_server, "_internal_developer_store", return_value=store):
                after = self._mcp_payload(
                    mcp_server._call_tool("codexstock_internal_developer_brief", {})
                )

            self.assertEqual("recovered_from_external_guidance", recovered["status"])
            self.assertIn(FEATURE_HEALTH_FORCE_PATH, http.get_calls)
            self.assertEqual("RECOVERED_UNREVIEWED", store.get_incident(incident_id)["state"])
            self.assertEqual(
                "ACCEPTED_AS_GUIDANCE", after["recent_advice"][0]["status"]
            )
            self.assertFalse(after["recent_advice"][0]["execution_authorized"])
            self.assertFalse(store.restart_request_path.exists())


if __name__ == "__main__":
    unittest.main()
