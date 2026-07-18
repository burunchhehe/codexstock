import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.kis_mcp_gateway import KisTradingMcpGateway


class KisTradingMcpGatewayTests(unittest.TestCase):
    def _gateway(self, root: Path, endpoint: str = "http://127.0.0.1:3000/sse") -> KisTradingMcpGateway:
        source = root / "885dd4e2f5c3" / "open-trading-api-885dd4e2f5c37e4f7e23dd63c15555a9967bc7bc"
        mcp = source / "MCP" / "Kis Trading MCP"
        (mcp / "module").mkdir(parents=True)
        (mcp / "tools").mkdir(parents=True)
        (mcp / "server.py").write_text("McpAuthMiddleware\n", encoding="utf-8")
        (mcp / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
        (mcp / "module" / "mcp_auth.py").write_text("class McpAuthMiddleware: pass\n", encoding="utf-8")
        (mcp / "tools" / "base.py").write_text(
            "ALLOWED_ENV_DV = {}\nFUNCTION_NAME_PATTERN = ''\nAPI_RUNNER_TEMPLATE = ''\n",
            encoding="utf-8",
        )
        env_file = root / "kis_mcp.env"
        env_file.write_text(
            "MCP_ACCESS_TOKEN=test-token\n"
            "KIS_PAPER_APP_KEY=test-key\n"
            "KIS_PAPER_APP_SECRET=test-secret\n"
            "KIS_PAPER_STOCK=00000000-01\n",
            encoding="utf-8",
        )
        return KisTradingMcpGateway(
            engine_root=root,
            secret_env_file=env_file,
            endpoint=endpoint,
            runtime_root=root / "runtime",
        )

    def test_installed_source_is_reported_but_orders_stay_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway = self._gateway(Path(temp_dir))
            with patch.object(
                gateway,
                "_docker_status",
                return_value={"installed": True, "daemon_ready": False, "container_running": False},
            ):
                status = gateway.status(force=True)

        self.assertTrue(status["ok"])
        self.assertFalse(status["connected"])
        self.assertIn("docker_daemon_not_ready", status["blockers"])
        self.assertEqual(status["order_tool_policy"], "DENY_ALL")
        self.assertFalse(status["live_order_allowed"])
        self.assertIn("cash_order", status["blocked_capabilities"])

    def test_non_loopback_endpoint_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway = self._gateway(Path(temp_dir), endpoint="https://example.com/sse")
            with patch.object(
                gateway,
                "_docker_status",
                return_value={"installed": True, "daemon_ready": True, "container_running": True},
            ):
                status = gateway.status(force=True)

        self.assertFalse(status["connected"])
        self.assertIn("non_loopback_endpoint_blocked", status["blockers"])
        self.assertFalse(status["endpoint"]["reachable"])

    def test_authenticated_loopback_runtime_can_become_read_only_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gateway = self._gateway(Path(temp_dir))
            with (
                patch.object(
                    gateway,
                    "_docker_status",
                    return_value={"installed": True, "daemon_ready": True, "container_running": True},
                ),
                patch.object(
                    gateway,
                    "_endpoint_reachable",
                    return_value={"reachable": True, "checked": True, "http_status": 200},
                ),
                patch.object(
                    gateway,
                    "_mcp_round_trip",
                    return_value={
                        "verified": True,
                        "checked": True,
                        "authenticated": True,
                        "tool_count": 8,
                        "order_tools_invoked": False,
                    },
                ),
            ):
                status = gateway.status(force=True)

        self.assertTrue(status["connected"])
        self.assertEqual(status["status"], "ready")
        self.assertFalse(status["live_order_allowed"])
        self.assertEqual(status["crosscheck_contract"]["mismatch_action"], "BLOCK_SCORE_AND_ORDER")

    def test_native_runtime_replaces_unavailable_docker_without_weakening_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gateway = self._gateway(root)
            mcp_root = Path(str(gateway._latest_source()["mcp_root"]))
            native_python = mcp_root / ".venv" / "Scripts" / "python.exe"
            native_python.parent.mkdir(parents=True)
            native_python.write_bytes(b"placeholder")
            with (
                patch.object(
                    gateway,
                    "_docker_status",
                    return_value={"installed": True, "daemon_ready": False, "container_running": False},
                ),
                patch.object(
                    gateway,
                    "_endpoint_reachable",
                    side_effect=[
                        {"reachable": False, "checked": True},
                        {"reachable": True, "checked": True, "http_status": 200},
                    ],
                ),
                patch.object(
                    gateway,
                    "_start_native_runtime",
                    return_value={
                        **gateway._native_runtime_status(gateway._latest_source()),
                        "start_attempted": True,
                        "started": True,
                    },
                ) as start_native,
                patch.object(
                    gateway,
                    "_mcp_round_trip",
                    return_value={
                        "verified": True,
                        "checked": True,
                        "authenticated": True,
                        "tool_count": 8,
                        "order_tools_invoked": False,
                    },
                ),
            ):
                status = gateway.status(force=True)

        start_native.assert_called_once()
        self.assertTrue(status["connected"])
        self.assertEqual("native_isolated_venv", status["runtime_backend"])
        self.assertEqual([], status["blockers"])
        self.assertEqual("paper", status["configuration"]["credential_mode"])
        self.assertFalse(status["live_order_allowed"])
        self.assertEqual("DENY_ALL", status["order_tool_policy"])


if __name__ == "__main__":
    unittest.main()
