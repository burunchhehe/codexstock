from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import StrategyDefinition
from .service import ResearchForge


def _runtime_root() -> Path:
    configured = os.getenv("CODEXSTOCK_RESEARCH_FORGE_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.cwd() / "data" / "research_forge"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codexstock-research-forge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("doctor")
    mcp = sub.add_parser("mcp")
    mcp.add_argument("action", choices=["manifest"])
    sub.add_parser("demo")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true", help="Run one orphan recovery/resume cycle and exit")
    worker.add_argument("--poll-seconds", type=float, default=5.0)
    worker.add_argument("--orphan-grace-seconds", type=float, default=30.0)
    realtime = sub.add_parser("realtime-soak")
    realtime.add_argument("--symbols", nargs="+", required=True)
    realtime.add_argument("--duration-seconds", type=float, required=True)
    realtime.add_argument("--heartbeat-timeout", type=float, default=30.0)
    realtime.add_argument("--max-reconnects", type=int, default=1000)
    return parser


def _demo(forge: ResearchForge) -> dict[str, object]:
    strategy = StrategyDefinition(
        name="demo_sma_cross",
        version="1.0.0",
        description="Offline deterministic smoke test",
        rules={"timeframe": "1d", "entry": "SMA(5) > SMA(20)", "exit": "SMA(5) <= SMA(20)"},
    )
    record = forge.create_experiment(
        strategy,
        {"dataset_id": "mock-ohlcv-v1", "data_mode": "mock"},
        {"fill_model": "next_bar_open", "commission_bps": 0, "slippage_bps": 0},
    )
    return forge.run_backtest(record.id).to_dict()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    forge = ResearchForge.local(_runtime_root())
    if args.command == "status":
        payload = forge.status()
    elif args.command == "doctor":
        payload = forge.doctor()
    elif args.command == "mcp":
        payload = forge.manifest()
    elif args.command == "demo":
        payload = _demo(forge)
    elif args.command == "worker":
        payload = _worker(forge, args.once, args.poll_seconds, args.orphan_grace_seconds)
    else:
        payload = _realtime_soak(forge, args.symbols, args.duration_seconds, args.heartbeat_timeout, args.max_reconnects)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok", True) else 1


def _worker(forge: ResearchForge, once: bool, poll_seconds: float, orphan_grace_seconds: float) -> dict[str, object]:
    from .gateway import _async_handler
    manager = forge.jobs()
    repo_root = Path(os.getenv("CODEXSTOCK_REPO_ROOT", str(Path.cwd()))).resolve()
    runtime_root = forge.registry.root.parent
    cycles = 0; recovered_total = 0; resumed_total = 0
    heartbeat = manager.root / "worker_status.json"
    try:
        while True:
            recovery = manager.recover_orphaned_running(max(0.0, orphan_grace_seconds))
            resumed = manager.resume_interrupted(lambda kind: _async_handler(kind, runtime_root, repo_root))
            cycles += 1; recovered_total += int(recovery["recovered_count"]); resumed_total += int(resumed["resumed_count"])
            state = {"ok": True, "mode": "once" if once else "continuous", "pid": os.getpid(), "cycles": cycles, "last_recovery": recovery, "last_resume": resumed, "updated_at": datetime.now(timezone.utc).isoformat()}
            temporary = heartbeat.with_suffix(".json.tmp"); temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"); temporary.replace(heartbeat)
            if once: break
            time.sleep(max(0.2, min(300.0, float(poll_seconds))))
    except KeyboardInterrupt:
        pass
    return {"ok": True, "cycles": cycles, "recovered_total": recovered_total, "resumed_total": resumed_total, "heartbeat_path": str(heartbeat)}


def _realtime_soak(forge: ResearchForge, symbols: list[str], duration_seconds: float, heartbeat_timeout: float, max_reconnects: int) -> dict[str, object]:
    from .gateway import call_research_tool
    repo_root = Path(os.getenv("CODEXSTOCK_REPO_ROOT", str(Path.cwd()))).resolve()
    return call_research_tool("research_realtime_start", {"symbols": symbols, "max_messages": 0, "duration_seconds": duration_seconds, "heartbeat_timeout": heartbeat_timeout, "max_reconnects": max_reconnects}, runtime_root=forge.registry.root.parent, repo_root=repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
