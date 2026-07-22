#!/usr/bin/env python3
"""Read-only completion verifier for the CodexStock execution sidecar."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def evaluate(payload: dict[str, object], require_complete: bool = False) -> dict[str, object]:
    runtime = payload.get("runtime_process") if isinstance(payload.get("runtime_process"), dict) else {}
    supervisor = payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}
    proof = payload.get("validation_proof") if isinstance(payload.get("validation_proof"), dict) else {}
    checks = proof.get("checks") if isinstance(proof.get("checks"), dict) else {}
    failed_checks = sorted(str(name) for name, passed in checks.items() if passed is not True)
    required = {
        "api_ok": payload.get("ok") is True,
        "shadow_mode": payload.get("mode") == "shadow",
        "process_alive": runtime.get("process_alive") is True,
        "status_fresh": runtime.get("status_fresh") is True,
        "supervisor_monitoring": supervisor.get("state") == "MONITORING",
        "operational_audit": proof.get("operational_ok") is True,
        "all_embedded_checks": bool(checks) and not failed_checks,
        "real_order_disabled": payload.get("real_order_supported") is False,
    }
    if require_complete:
        required["long_run_and_coverage_complete"] = proof.get("proof_complete") is True
    failures = sorted(name for name, passed in required.items() if not passed)
    return {
        "ok": not failures,
        "mode": "completion" if require_complete else "operational",
        "requirements": required,
        "failures": failures,
        "failed_embedded_checks": failed_checks,
        "runtime_session_id": payload.get("runtime_session_id"),
        "process_id": runtime.get("process_id"),
        "observation_hours": proof.get("observation_hours"),
        "required_observation_hours": proof.get("required_observation_hours"),
        "qualifying_result_count": proof.get("qualifying_result_count"),
        "required_result_count": proof.get("required_result_count"),
        "observed_symbol_count": proof.get("observed_symbol_count"),
        "required_symbol_count": proof.get("required_symbol_count"),
        "real_order_supported": payload.get("real_order_supported"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8765/api/execution-sidecar/status",
        help="CodexStock lightweight sidecar status endpoint",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="also require 24-hour runtime and real candidate coverage proof",
    )
    args = parser.parse_args()
    try:
        with urlopen(args.url, timeout=10) as response:
            payload = json.load(response)
    except (OSError, URLError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(payload, dict):
        print(json.dumps({"ok": False, "error": "status response must be a JSON object"}))
        return 3
    report = evaluate(payload, require_complete=args.require_complete)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
