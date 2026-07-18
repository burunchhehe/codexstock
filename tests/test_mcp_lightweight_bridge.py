from __future__ import annotations

import json
import urllib.error
import unittest
from unittest.mock import patch

from app import codexstock_mcp_server as mcp_server
from app import stock_suite_app as stock_app


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b'{"ok":true,"source":"test"}'


class McpLightweightBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        mcp_server._HTTP_JSON_CACHE.clear()

    def test_instant_overview_does_not_scan_heavy_ledgers(self) -> None:
        staff_activity = {
            "researcher": {
                "state": "상시근무",
                "task": "연구 통합",
                "target": "전체 시장",
                "progress_pct": 40,
                "updated_at": "2026-07-18T09:00:00+09:00",
            }
        }
        policy = {
            "emergency_halt": False,
            "day_halted": False,
            "live_candidate_enabled": True,
            "live_execution_enabled": False,
            "delegated_live_autonomy_enabled": False,
            "require_approval": True,
        }
        with (
            patch.object(stock_app.OPS, "autotrade_policy", return_value=policy),
            patch.object(stock_app.AI_DAEMON, "running", True),
            patch.object(stock_app.AI_DAEMON, "staff_activity", staff_activity),
            patch.object(
                stock_app.AI_DAEMON,
                "current_activity",
                {"phase": "working", "label": "후보 감시", "progress_pct": 40},
            ),
            patch.object(stock_app, "_iso_age_seconds", return_value=10.0),
            patch.object(stock_app, "build_today_trade_quick_summary") as trade_summary,
            patch.object(stock_app.MEMORY, "summary") as memory_summary,
        ):
            payload = stock_app.build_mcp_instant_overview()

        self.assertEqual("instant_memory_only", payload["response_profile"])
        self.assertEqual(1, payload["staff"]["count"])
        self.assertFalse(payload["live_order_allowed"])
        self.assertLess(len(json.dumps(payload, ensure_ascii=False)), 20_000)
        trade_summary.assert_not_called()
        memory_summary.assert_not_called()

    def test_default_status_and_staff_tools_use_instant_endpoints(self) -> None:
        with patch.object(mcp_server, "_http_json", return_value={"ok": True}) as http_json:
            mcp_server._call_tool("codexstock_status", {})
            self.assertEqual("/api/mcp/overview", http_json.call_args.args[1])
            self.assertEqual(3.0, http_json.call_args.kwargs["timeout_seconds"])

        with patch.object(mcp_server, "_http_json", return_value={"ok": True}) as http_json:
            mcp_server._call_tool("codexstock_staff_status", {})
            self.assertEqual("/api/mcp/staff", http_json.call_args.args[1])
            self.assertEqual(3.0, http_json.call_args.kwargs["timeout_seconds"])

    def test_meeting_tool_defaults_to_compact_pagination(self) -> None:
        with patch.object(mcp_server, "_http_json", return_value={"ok": True}) as http_json:
            mcp_server._call_tool("codexstock_staff_meetings", {"limit": 5, "offset": 10})

        params = http_json.call_args.args[2]
        self.assertEqual(5, params["limit"])
        self.assertEqual(10, params["offset"])
        self.assertEqual(1, params["compact"])

    def test_cached_get_returns_recent_value_when_app_is_temporarily_unavailable(self) -> None:
        with patch.object(mcp_server.urllib.request, "urlopen", return_value=_FakeResponse()):
            first = mcp_server._http_json(
                "GET",
                "/api/mcp/overview",
                cache_ttl_seconds=0.01,
                stale_if_error_seconds=60,
            )
        self.assertTrue(first["ok"])

        with patch.object(
            mcp_server.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("temporary outage"),
        ):
            second = mcp_server._http_json(
                "GET",
                "/api/mcp/overview",
                cache_ttl_seconds=0,
                stale_if_error_seconds=60,
            )

        self.assertTrue(second["ok"])
        self.assertEqual("stale_fallback", second["mcp_transport"]["cache"])
        self.assertIn("upstream_error", second["mcp_transport"])


if __name__ == "__main__":
    unittest.main()
