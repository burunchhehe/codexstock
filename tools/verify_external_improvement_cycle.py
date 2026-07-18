from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


os.environ.setdefault("CODEXSTOCK_ALLOW_TEST_IMPORT", "1")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import stock_suite_app as stock_app  # noqa: E402


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        status = int(exc.code)
        value = json.loads(exc.read().decode("utf-8"))
    return status, value if isinstance(value, dict) else {"value": value}


def _blackbox_counts(base_url: str) -> dict[str, int]:
    _, payload = _request_json(
        "GET",
        f"{base_url}/api/ops/live-order-blackbox?limit=1000&persist=0",
        timeout=60,
    )
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    return {
        "total": int(counts.get("total") or 0),
        "submitted": int(counts.get("submitted") or 0),
        "blocked": int(counts.get("blocked") or 0),
        "failed": int(counts.get("failed") or 0),
    }


def _task_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [
        {
            "task_id": row.get("task_id"),
            "engine_id": row.get("engine_id"),
            "status": row.get("status"),
            "attempt_count": row.get("attempt_count"),
            "max_attempts": row.get("max_attempts"),
            "resolution_blockers": row.get("resolution_blockers") or [],
        }
        for row in rows
        if isinstance(row, dict)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one API-level research-only improvement cycle.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--wait-seconds", type=int, default=900)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), stock_app.StockSuiteHandler)
    thread = threading.Thread(target=server.serve_forever, name="improvement-verifier-http", daemon=True)
    thread.start()
    base_url = f"http://{args.host}:{args.port}"
    result: dict[str, Any] = {
        "schema": "codexstock_external_improvement_api_verification_v1",
        "base_url": base_url,
        "live_order_allowed": False,
        "promotion_allowed": False,
    }
    try:
        before_blackbox = _blackbox_counts(base_url)
        status_code, queued = _request_json(
            "POST",
            f"{base_url}/api/external-engines/improvement-loop/run",
            {
                "symbols": ["005930", "000660", "329180", "086790", "042660"],
                "max_symbols": 5,
                "rows": 260,
                "fast_window": 10,
                "slow_window": 40,
                "fold_count": 4,
                "timeout_seconds": 300,
                "requested_by": "api-verification-research-only",
            },
            timeout=60,
        )
        result["start_http_status"] = status_code
        result["queued"] = queued
        if status_code != 202 or queued.get("ok") is not True:
            result["ok"] = False
            result["error"] = "improvement_cycle_not_queued"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        deadline = time.monotonic() + max(60, min(args.wait_seconds, 1800))
        final_status: dict[str, Any] = {}
        while time.monotonic() < deadline:
            _, final_status = _request_json(
                "GET",
                f"{base_url}/api/external-engines/improvement-loop/status?lesson_limit=2&task_limit=20",
                timeout=60,
            )
            state = final_status.get("state") if isinstance(final_status.get("state"), dict) else {}
            if state.get("status") in {"COMPLETED", "COMPLETED_WITH_BLOCKERS", "FAILED"}:
                break
            time.sleep(2)

        after_blackbox = _blackbox_counts(base_url)
        state = final_status.get("state") if isinstance(final_status.get("state"), dict) else {}
        result.update(
            {
                "cycle_id": state.get("cycle_id"),
                "status": state.get("status"),
                "progress_pct": state.get("progress_pct"),
                "contract_pass_count": state.get("contract_pass_count"),
                "quality_pass_count": state.get("quality_pass_count"),
                "claimed_retraining_tasks": _task_rows(state.get("claimed_retraining_tasks")),
                "retraining_usage": state.get("retraining_usage") or {},
                "vectorbt_retraining_attempts": state.get("vectorbt_retraining_attempts") or [],
                "qlib_retraining_attempts": state.get("qlib_retraining_attempts") or [],
                "retraining_resolution": state.get("retraining_resolution") or {},
                "active_retraining_tasks": _task_rows(final_status.get("active_retraining_tasks")),
                "engine_results": state.get("engine_results") or [],
                "strategy_corroborated": state.get("strategy_corroborated"),
                "candidate_score_delta": state.get("candidate_score_delta"),
                "strategy_version_recorded": state.get("strategy_version_recorded"),
                "learning_memory_refreshed": state.get("learning_memory_refreshed"),
                "before_live_order_blackbox": before_blackbox,
                "after_live_order_blackbox": after_blackbox,
                "live_order_blackbox_unchanged": before_blackbox == after_blackbox,
                "live_order_allowed": state.get("live_order_allowed") is True,
                "promotion_allowed": state.get("promotion_allowed") is True,
            }
        )
        result["ok"] = bool(
            state.get("status") in {"COMPLETED", "COMPLETED_WITH_BLOCKERS"}
            and int(state.get("contract_pass_count") or 0) == 5
            and before_blackbox == after_blackbox
            and state.get("learning_memory_refreshed") is True
            and state.get("live_order_allowed") is False
            and state.get("promotion_allowed") is False
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
