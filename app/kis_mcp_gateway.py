from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


KIS_MCP_CONTAINER_NAME = "codexstock-kis-trading-mcp"
KIS_MCP_DEFAULT_ENDPOINT = "http://127.0.0.1:3000/sse"
KIS_MCP_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
KIS_MCP_NATIVE_SECRET_ALLOWLIST = frozenset(
    {
        "MCP_ACCESS_TOKEN",
        "KIS_PAPER_APP_KEY",
        "KIS_PAPER_APP_SECRET",
        "KIS_PAPER_STOCK",
        "KIS_PAPER_FUTURE",
        "KIS_HTS_ID",
        "KIS_PROD_TYPE",
        "KIS_URL_REST_PAPER",
        "KIS_URL_WS_PAPER",
    }
)


def _local_app_data() -> Path:
    configured = os.getenv("LOCALAPPDATA", "").strip()
    return Path(configured) if configured else Path.home() / "AppData" / "Local"


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return values
    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_env_flags(path: Path) -> dict[str, bool]:
    return {key: bool(value) for key, value in _read_env_values(path).items()}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class KisTradingMcpGateway:
    """Read-only boundary around the official KIS Trading MCP runtime."""

    def __init__(
        self,
        engine_root: Path | None = None,
        secret_env_file: Path | None = None,
        endpoint: str | None = None,
        container_name: str = KIS_MCP_CONTAINER_NAME,
        runtime_root: Path | None = None,
    ) -> None:
        self.engine_root = engine_root or (_local_app_data() / "CodexStock" / "engines" / "kis_trading_mcp")
        self.secret_env_file = secret_env_file or (_local_app_data() / "CodexStock" / "secrets" / "kis_mcp.env")
        self.endpoint = endpoint or os.getenv("CODEXSTOCK_KIS_MCP_URL", "").strip() or KIS_MCP_DEFAULT_ENDPOINT
        self.container_name = container_name
        self.runtime_root = runtime_root or (_local_app_data() / "CodexStock" / "runtime")
        self._lock = threading.Lock()
        self._cached_at = 0.0
        self._cached_status: dict[str, object] = {}
        self._round_trip_cached_at = 0.0
        self._round_trip_cache: dict[str, object] = {}

    def _latest_source(self) -> dict[str, object]:
        if not self.engine_root.is_dir():
            return {"installed": False, "engine_root": str(self.engine_root)}
        versions = sorted(
            (path for path in self.engine_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for version in versions:
            for source_root in sorted(version.glob("open-trading-api-*")):
                mcp_root = source_root / "MCP" / "Kis Trading MCP"
                server = mcp_root / "server.py"
                dockerfile = mcp_root / "Dockerfile"
                auth = mcp_root / "module" / "mcp_auth.py"
                base_tool = mcp_root / "tools" / "base.py"
                if not (server.is_file() and dockerfile.is_file()):
                    continue
                commit = source_root.name.removeprefix("open-trading-api-")
                server_text = server.read_text(encoding="utf-8", errors="ignore")
                base_text = base_tool.read_text(encoding="utf-8", errors="ignore") if base_tool.is_file() else ""
                security_markers = {
                    "access_token_middleware": auth.is_file() and "McpAuthMiddleware" in server_text,
                    "input_environment_allowlist": "ALLOWED_ENV_DV" in base_text,
                    "function_name_validation": "FUNCTION_NAME_PATTERN" in base_text,
                    "fixed_runner_template": "API_RUNNER_TEMPLATE" in base_text,
                }
                return {
                    "installed": True,
                    "engine_root": str(self.engine_root),
                    "version_root": str(version),
                    "mcp_root": str(mcp_root),
                    "commit": commit,
                    "commit_short": commit[:12],
                    "server_sha256": _file_sha256(server),
                    "dockerfile_sha256": _file_sha256(dockerfile),
                    "security_markers": security_markers,
                    "security_patch_verified": all(security_markers.values()),
                }
        return {"installed": False, "engine_root": str(self.engine_root)}

    @staticmethod
    def _docker_executable() -> str:
        discovered = shutil.which("docker")
        if discovered:
            return discovered
        candidate = Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"
        return str(candidate) if candidate.is_file() else ""

    @staticmethod
    def _run(
        command: list[str],
        timeout: float = 3.0,
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
            env=env,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

    def _docker_status(self) -> dict[str, object]:
        executable = self._docker_executable()
        if not executable:
            return {"installed": False, "daemon_ready": False, "container_running": False}
        try:
            version = self._run([executable, "--version"], timeout=2.0)
            daemon = self._run([executable, "info", "--format", "{{json .ServerVersion}}"], timeout=3.0)
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "installed": True,
                "executable": executable,
                "daemon_ready": False,
                "container_running": False,
                "error": str(exc)[:300],
            }
        daemon_ready = daemon.returncode == 0 and bool(daemon.stdout.strip().strip('"'))
        payload: dict[str, object] = {
            "installed": version.returncode == 0,
            "executable": executable,
            "client_version": version.stdout.strip(),
            "daemon_ready": daemon_ready,
            "server_version": daemon.stdout.strip().strip('"') if daemon_ready else "",
            "container_running": False,
        }
        if not daemon_ready:
            payload["error"] = (daemon.stderr or daemon.stdout).strip()[:300]
            return payload
        try:
            inspected = self._run(
                [executable, "inspect", "--format", "{{json .State}}", self.container_name],
                timeout=3.0,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            payload["error"] = str(exc)[:300]
            return payload
        if inspected.returncode != 0:
            payload["container_state"] = "not_created"
            return payload
        try:
            state = json.loads(inspected.stdout.strip())
        except json.JSONDecodeError:
            state = {}
        payload["container_state"] = state.get("Status", "unknown")
        payload["container_running"] = bool(state.get("Running"))
        payload["container_started_at"] = state.get("StartedAt", "")
        payload["container_health"] = (state.get("Health") or {}).get("Status", "") if isinstance(state.get("Health"), dict) else ""
        return payload

    def _configuration_status(self) -> dict[str, object]:
        env_flags = _read_env_flags(self.secret_env_file)
        access_token_configured = bool(os.getenv("CODEXSTOCK_KIS_MCP_ACCESS_TOKEN", "").strip()) or env_flags.get("MCP_ACCESS_TOKEN", False)
        paper_configured = all(
            env_flags.get(key, False) or bool(os.getenv(key, "").strip())
            for key in ("KIS_PAPER_APP_KEY", "KIS_PAPER_APP_SECRET", "KIS_PAPER_STOCK")
        )
        live_configured = all(
            env_flags.get(key, False) or bool(os.getenv(key, "").strip())
            for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCT_STOCK")
        )
        parsed = urlparse(self.endpoint)
        loopback_only = parsed.hostname in KIS_MCP_ALLOWED_HOSTS
        return {
            "endpoint": self.endpoint,
            "loopback_only": loopback_only,
            "access_token_configured": access_token_configured,
            "paper_credentials_configured": paper_configured,
            "live_credentials_configured": live_configured,
            "credential_mode": "paper" if paper_configured else "live" if live_configured else "unconfigured",
            "native_runtime_forces_paper_only": True,
            "secret_env_file": str(self.secret_env_file),
            "secret_values_exposed": False,
        }

    @staticmethod
    def _native_python(mcp_root: Path) -> Path:
        windows = mcp_root / ".venv" / "Scripts" / "python.exe"
        posix = mcp_root / ".venv" / "bin" / "python"
        return windows if windows.is_file() else posix

    def _native_runtime_status(self, source: dict[str, object]) -> dict[str, object]:
        mcp_root = Path(str(source.get("mcp_root") or ""))
        python = self._native_python(mcp_root) if mcp_root.is_dir() else Path()
        return {
            "supported": True,
            "available": bool(mcp_root.is_dir() and python.is_file()),
            "runtime_mode": "native_isolated_venv",
            "mcp_root": str(mcp_root) if mcp_root.is_dir() else "",
            "python": str(python) if python.is_file() else "",
            "isolated_venv": python.is_file(),
            "paper_credentials_only": True,
            "order_tools_invoked": False,
        }

    def _native_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        secret_values = _read_env_values(self.secret_env_file)
        for key in KIS_MCP_NATIVE_SECRET_ALLOWLIST:
            value = secret_values.get(key, "").strip()
            if value:
                environment[key] = value
        configured_token = os.getenv("CODEXSTOCK_KIS_MCP_ACCESS_TOKEN", "").strip()
        if configured_token:
            environment["MCP_ACCESS_TOKEN"] = configured_token
        parsed = urlparse(self.endpoint)
        environment.update(
            {
                "ENV": "live",
                "MCP_TYPE": "sse",
                "MCP_HOST": str(parsed.hostname or "127.0.0.1"),
                "MCP_PORT": str(parsed.port or 3000),
                "MCP_PATH": str(parsed.path or "/sse"),
            }
        )
        for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCT_STOCK", "KIS_ACCT_FUTURE"):
            environment.pop(key, None)
        return environment

    def _start_native_runtime(self, source: dict[str, object]) -> dict[str, object]:
        native = self._native_runtime_status(source)
        if not native.get("available"):
            return {**native, "start_attempted": False, "start_error": "native_venv_not_ready"}
        parsed = urlparse(self.endpoint)
        if parsed.hostname not in KIS_MCP_ALLOWED_HOSTS:
            return {**native, "start_attempted": False, "start_error": "non_loopback_endpoint_blocked"}
        mcp_root = Path(str(native.get("mcp_root") or ""))
        python = str(native.get("python") or "")
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        stdout_path = self.runtime_root / "kis-mcp-native.out.log"
        stderr_path = self.runtime_root / "kis-mcp-native.err.log"
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            with stdout_path.open("a", encoding="utf-8") as stdout_handle, stderr_path.open("a", encoding="utf-8") as stderr_handle:
                process = subprocess.Popen(
                    [python, "server.py"],
                    cwd=str(mcp_root),
                    env=self._native_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                    close_fds=True,
                )
        except OSError as exc:
            return {
                **native,
                "start_attempted": True,
                "started": False,
                "start_error": str(exc)[:300],
                "stdout_log": str(stdout_path),
                "stderr_log": str(stderr_path),
            }
        return {
            **native,
            "start_attempted": True,
            "started": True,
            "pid": process.pid,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
        }

    def _access_token(self) -> str:
        configured = os.getenv("CODEXSTOCK_KIS_MCP_ACCESS_TOKEN", "").strip()
        if configured:
            return configured
        return _read_env_values(self.secret_env_file).get("MCP_ACCESS_TOKEN", "").strip()

    def _endpoint_reachable(self, configuration: dict[str, object]) -> dict[str, object]:
        if not configuration.get("access_token_configured"):
            return {"reachable": False, "checked": False}
        parsed = urlparse(self.endpoint)
        if parsed.hostname not in KIS_MCP_ALLOWED_HOSTS:
            return {"reachable": False, "checked": False, "error": "non_loopback_endpoint_blocked"}
        token = self._access_token()
        if not token:
            return {"reachable": False, "checked": False}
        connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        started = time.perf_counter()
        connection = connection_class(parsed.hostname, port, timeout=2.0)
        try:
            connection.request("GET", parsed.path or "/sse", headers={"Authorization": f"Bearer {token}"})
            response = connection.getresponse()
            return {
                "reachable": response.status in {200, 202},
                "checked": True,
                "authenticated_request_sent": True,
                "http_status": response.status,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
            }
        except OSError as exc:
            return {"reachable": False, "checked": True, "error": str(exc)[:200]}
        finally:
            connection.close()

    def _mcp_round_trip(self, source: dict[str, object], *, force: bool = False) -> dict[str, object]:
        age = time.monotonic() - self._round_trip_cached_at
        if self._round_trip_cache and not force and age <= 300:
            return {**self._round_trip_cache, "cached": True, "cache_age_seconds": round(age, 2)}
        native = self._native_runtime_status(source)
        if not native.get("available"):
            return {"verified": False, "checked": False, "error": "native_mcp_client_unavailable"}
        script = """
import asyncio
import json
import os
from fastmcp import Client

async def main():
    async with Client(
        os.environ["CODEXSTOCK_KIS_MCP_URL"],
        auth=os.environ["MCP_ACCESS_TOKEN"],
        timeout=10,
    ) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools]
        print(json.dumps({
            "verified": bool(names),
            "authenticated": True,
            "tool_count": len(names),
            "sample_tools": names[:5],
            "order_tools_invoked": False,
        }, ensure_ascii=False))

asyncio.run(main())
"""
        environment = self._native_environment()
        environment["CODEXSTOCK_KIS_MCP_URL"] = self.endpoint
        started = time.perf_counter()
        try:
            result = self._run(
                [str(native.get("python")), "-c", script],
                timeout=15.0,
                cwd=Path(str(native.get("mcp_root"))),
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            payload = {"verified": False, "checked": True, "error": str(exc)[:300]}
        else:
            payload: dict[str, object] = {}
            for line in reversed(result.stdout.splitlines()):
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    payload = parsed
                    break
            if result.returncode != 0 or not payload:
                payload = {
                    "verified": False,
                    "checked": True,
                    "error": (result.stderr or result.stdout).strip()[-500:],
                }
            else:
                payload["checked"] = True
                payload["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
                payload["proof_type"] = "authenticated_list_tools"
        payload["order_tools_invoked"] = False
        payload["verified_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        self._round_trip_cache = payload
        self._round_trip_cached_at = time.monotonic()
        return {**payload, "cached": False}

    def _build_status(self, *, force: bool = False) -> dict[str, object]:
        source = self._latest_source()
        docker = self._docker_status()
        configuration = self._configuration_status()
        native = self._native_runtime_status(source)
        endpoint = self._endpoint_reachable(configuration)
        can_start_native = bool(
            source.get("installed")
            and source.get("security_patch_verified")
            and native.get("available")
            and configuration.get("loopback_only")
            and configuration.get("access_token_configured")
            and configuration.get("paper_credentials_configured")
        )
        if not endpoint.get("reachable") and can_start_native:
            native = self._start_native_runtime(source)
            for _ in range(24):
                time.sleep(0.25)
                endpoint = self._endpoint_reachable(configuration)
                if endpoint.get("reachable"):
                    break
        runtime_backend = (
            "native_isolated_venv"
            if endpoint.get("reachable") and native.get("available")
            else "docker_container"
            if docker.get("container_running")
            else "unavailable"
        )
        round_trip = self._mcp_round_trip(source, force=force) if endpoint.get("reachable") else {
            "verified": False,
            "checked": False,
        }
        blockers: list[str] = []
        if not source.get("installed"):
            blockers.append("official_source_not_installed")
        elif not source.get("security_patch_verified"):
            blockers.append("security_patch_markers_missing")
        if not configuration.get("loopback_only"):
            blockers.append("non_loopback_endpoint_blocked")
        if not configuration.get("access_token_configured"):
            blockers.append("mcp_access_token_missing")
        if not configuration.get("paper_credentials_configured"):
            blockers.append("paper_credentials_missing")
        if runtime_backend == "unavailable":
            if docker.get("installed") and not docker.get("daemon_ready") and not native.get("available"):
                blockers.append("docker_daemon_not_ready")
            elif not docker.get("installed") and not native.get("available"):
                blockers.append("runtime_not_available")
            elif native.get("start_error"):
                blockers.append("native_runtime_start_failed")
            else:
                blockers.append("mcp_endpoint_unreachable")
        if endpoint.get("reachable") and not round_trip.get("verified"):
            blockers.append("mcp_round_trip_failed")
        connected = not blockers and bool(endpoint.get("reachable") and round_trip.get("verified"))
        if connected:
            status = "ready"
            status_label = "공식 MCP 연결 완료·조회 전용"
        elif not source.get("installed") or not source.get("security_patch_verified"):
            status = "error"
            status_label = "공식 소스·보안 업데이트 점검 필요"
        else:
            status = "preparing"
            status_label = "보안 런타임 연결 준비"
        native.update(
            {
                "running": bool(endpoint.get("reachable") and runtime_backend == "native_isolated_venv"),
                "runtime_backend": runtime_backend,
            }
        )
        return {
            "ok": bool(source.get("installed") and source.get("security_patch_verified")),
            "schema": "codexstock_kis_trading_mcp_gateway_v2",
            "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "engine_id": "kis-trading-mcp",
            "engine_name": "KIS Trading MCP",
            "display_name": "KIS 공식 게이트웨이",
            "role": "broker_data_gateway",
            "status": status,
            "status_label": status_label,
            "connected": connected,
            "runtime_ready": connected,
            "runtime_backend": runtime_backend,
            "source": source,
            "docker": docker,
            "native_runtime": native,
            "configuration": configuration,
            "endpoint": endpoint,
            "round_trip": round_trip,
            "blockers": blockers,
            "allowed_capabilities": [
                "market_data_read",
                "ranking_read",
                "investor_flow_read",
                "account_balance_read",
                "execution_history_read",
                "pnl_read",
            ],
            "blocked_capabilities": [
                "cash_order",
                "credit_order",
                "derivatives_order",
                "order_modify",
                "order_cancel",
            ],
            "crosscheck_contract": {
                "primary": "CodexStock deterministic KIS bridge",
                "secondary": "official KIS Trading MCP",
                "fields": ["symbol", "price", "timestamp", "currency", "unit", "order_id", "filled_qty", "balance_qty", "avg_price", "pnl"],
                "mismatch_action": "BLOCK_SCORE_AND_ORDER",
            },
            "live_order_allowed": False,
            "order_tool_policy": "DENY_ALL",
            "safety": "공식 MCP는 127.0.0.1·접근 토큰·모의계좌 전용으로 실행하며 코덱스스톡은 MCP 주문 도구를 호출하지 않습니다.",
        }

    def status(self, force: bool = False, ttl_seconds: int = 15) -> dict[str, object]:
        with self._lock:
            age = time.monotonic() - self._cached_at
            if self._cached_status and not force and age <= max(1, ttl_seconds):
                return {**self._cached_status, "cached": True, "cache_age_seconds": round(age, 2)}
            payload = self._build_status(force=force)
            self._cached_status = payload
            self._cached_at = time.monotonic()
            return {**payload, "cached": False}
