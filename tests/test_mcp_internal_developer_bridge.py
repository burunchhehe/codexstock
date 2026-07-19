from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import codexstock_mcp_server as mcp_server
from app.internal_developer_store import InternalDeveloperStore


class McpInternalDeveloperBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data_root = Path(self.temporary.name) / "data"
        self.repo_root = Path(self.temporary.name) / "repo"
        self.repo_root.mkdir(parents=True)
        self.store = InternalDeveloperStore(self.repo_root, data_root=self.data_root)
        self.root_patch = patch.object(
            mcp_server, "active_data_root", return_value=self.data_root
        )
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    @staticmethod
    def _payload(result: dict[str, object]) -> dict[str, object]:
        content = result.get("content")
        assert isinstance(content, list) and content
        row = content[0]
        assert isinstance(row, dict)
        return json.loads(str(row["text"]))

    def _incident(self) -> dict[str, object]:
        return self.store.open_incident(
            {
                "classification": "EXTERNAL_ENGINE_DISCONNECTED",
                "component": "kis-trading-mcp",
                "severity": "high",
                "summary": "Read-only gateway did not answer its health probe.",
            }
        )

    def test_regular_status_includes_direct_attention_when_app_http_is_down(self) -> None:
        incident = self._incident()
        incident_id = str(incident["incident_id"])
        self.store.transition_incident(incident_id, "DIAGNOSING")
        self.store.transition_incident(incident_id, "NEEDS_EXTERNAL_ADVICE")
        self.store.write_report(incident_id, {"cause": "gateway unavailable"})

        with patch.object(
            mcp_server,
            "_http_json",
            return_value={"ok": False, "error": "app unavailable"},
        ):
            payload = self._payload(mcp_server._call_tool("codexstock_status", {}))

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["developer_attention_required"])
        attention = payload["internal_developer"]
        self.assertEqual("degraded", attention["operational_status"])
        self.assertEqual(1, attention["open_incidents"])
        self.assertEqual(1, attention["unreviewed_reports"])
        self.assertEqual("mcp-direct-store", attention["served_by"])

    def test_direct_incident_report_brief_and_activity_tools_work_without_http(self) -> None:
        incident = self._incident()
        incident_id = str(incident["incident_id"])
        report = self.store.write_report(incident_id, {"next_step": "Ask GPT for advice."})

        listed = self._payload(
            mcp_server._call_tool(
                "codexstock_internal_developer_list_incidents", {"limit": 10}
            )
        )
        fetched = self._payload(
            mcp_server._call_tool(
                "codexstock_internal_developer_get_incident",
                {"incident_id": incident_id},
            )
        )
        latest = self._payload(
            mcp_server._call_tool("codexstock_internal_developer_latest_report", {})
        )
        brief = self._payload(
            mcp_server._call_tool("codexstock_internal_developer_brief", {})
        )
        activity = self._payload(
            mcp_server._call_tool(
                "codexstock_internal_developer_activity", {"limit": 20}
            )
        )

        self.assertEqual(1, listed["count"])
        self.assertEqual(incident_id, fetched["incident"]["incident_id"])
        self.assertEqual(report["report_id"], latest["report"]["report_id"])
        self.assertEqual(report["report_id"], brief["latest_report"]["report_id"])
        self.assertGreaterEqual(len(activity["items"]), 2)

    def test_submitted_advice_is_saved_but_never_executed(self) -> None:
        incident = self._incident()
        incident_id = str(incident["incident_id"])
        result = self._payload(
            mcp_server._call_tool(
                "codexstock_submit_developer_advice",
                {
                    "incident_id": incident_id,
                    "summary": "Reconnect the registered read-only KIS gateway.",
                    "analysis": "Use only the deterministic reconnect adapter.",
                    "proposed_actions": [
                        {
                            "action": "RECONNECT_EXTERNAL_ENGINE",
                            "parameters": {"engine_id": "kis-trading-mcp"},
                        }
                    ],
                },
            )
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["execution_performed"])
        saved = result["saved"]
        self.assertFalse(saved["execution_authorized"])
        self.assertEqual("RECEIVED", saved["status"])
        stored_incident = self.store.get_incident(incident_id)
        assert stored_incident is not None
        self.assertEqual([], stored_incident["recovery_attempts"])
        brief = self._payload(
            mcp_server._call_tool("codexstock_internal_developer_brief", {})
        )
        self.assertEqual(saved["advice_id"], brief["recent_advice"][0]["advice_id"])
        self.assertFalse(brief["recent_advice"][0]["execution_authorized"])

    def test_reading_latest_report_does_not_acknowledge_it(self) -> None:
        incident = self._incident()
        report = self.store.write_report(str(incident["incident_id"]), {"cause": "test"})

        mcp_server._call_tool("codexstock_internal_developer_latest_report", {})

        persisted = self.store.get_report(str(report["report_id"]))
        assert persisted is not None
        self.assertEqual("UNREVIEWED", persisted["review_status"])

    def test_manifest_declares_and_handles_every_internal_developer_tool(self) -> None:
        names = {
            str(tool.get("name") or "")
            for tool in mcp_server.TOOLS
            if "internal_developer" in str(tool.get("name") or "")
            or tool.get("name") == "codexstock_submit_developer_advice"
        }
        self.assertEqual(9, len(names))
        source = Path(mcp_server.__file__).read_text(encoding="utf-8")
        for name in names:
            self.assertIn(f'if name == "{name}"', source)

    def test_ask_agent_structured_router_reaches_internal_developer_tools(self) -> None:
        with patch.object(
            mcp_server, "_internal_developer_store", return_value=self.store
        ):
            result = mcp_server._agent_local_fallback(
                json.dumps(
                    {
                        "mcp_tool": "codexstock_internal_developer_status",
                        "arguments": {},
                    }
                ),
                max_chars=12000,
            )

        assert result is not None
        payload = self._payload(result)
        self.assertTrue(payload["healthy"])
        self.assertEqual("codexstock_ask_agent", result["routed_via"])
        self.assertEqual(
            "codexstock_internal_developer_status", result["routed_tool"]
        )

    def test_ask_agent_natural_language_router_survives_schema_cache_lag(self) -> None:
        incident = self._incident()
        self.store.write_report(
            str(incident["incident_id"]), {"cause": "read-only gateway unavailable"}
        )

        with patch.object(
            mcp_server, "_internal_developer_store", return_value=self.store
        ):
            result = mcp_server._agent_local_fallback(
                "internal developer latest report", max_chars=12000
            )

        assert result is not None
        payload = self._payload(result)
        self.assertTrue(payload["report_available"])
        self.assertTrue(result["schema_cache_fallback"])
        self.assertEqual(
            "codexstock_internal_developer_latest_report", result["routed_tool"]
        )


if __name__ == "__main__":
    unittest.main()
