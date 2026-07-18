from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def replay_child_creationflags() -> int:
    """Keep CPU-heavy replay children behind the interactive web server."""
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
        getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    )


def run_replay_subprocess(
    replay_id: str,
    *,
    python_executable: str,
    repo_root: Path,
    result_dir: Path,
    timeout_seconds: int = 1_800,
    force: bool = False,
) -> dict[str, object]:
    """Run one CPU-heavy Paper replay outside the web server process."""
    normalized_id = str(replay_id or "").strip().upper()
    if not normalized_id.startswith("HREPLAY-"):
        return {
            "ok": False,
            "status": "invalid_replay_id",
            "source_replay_id": normalized_id,
            "paper_only": True,
            "live_order_allowed": False,
        }
    result_dir = Path(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_dir / f"{normalized_id}.{uuid4().hex}.json"
    command = [
        str(python_executable),
        "-m",
        "app.replay_regeneration_subprocess",
        "--child",
        "--replay-id",
        normalized_id,
        "--output",
        str(output_path),
    ]
    if force:
        command.append("--force")
    try:
        completed = subprocess.run(
            command,
            cwd=str(Path(repo_root)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(60, int(timeout_seconds)),
            check=False,
            env={**os.environ, "CODEXSTOCK_REPLAY_CHILD": "1"},
            creationflags=replay_child_creationflags(),
        )
        if completed.returncode != 0:
            return {
                "ok": False,
                "status": "regeneration_subprocess_failed",
                "source_replay_id": normalized_id,
                "returncode": completed.returncode,
                "error": (completed.stderr or completed.stdout or "child process failed")[-2_000:],
                "paper_only": True,
                "live_order_allowed": False,
            }
        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            diagnostic = (completed.stderr or completed.stdout or "").strip()[-2_000:]
            return {
                "ok": False,
                "status": "regeneration_subprocess_result_missing",
                "source_replay_id": normalized_id,
                "error": "child exited successfully without writing the required result file",
                "diagnostic": diagnostic,
                "paper_only": True,
                "live_order_allowed": False,
            }
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "status": "regeneration_subprocess_result_invalid",
                "source_replay_id": normalized_id,
                "error": str(exc),
                "paper_only": True,
                "live_order_allowed": False,
            }
        if (
            not isinstance(result, dict)
            or result.get("paper_only") is not True
            or result.get("live_order_allowed") is not False
        ):
            return {
                "ok": False,
                "status": "unsafe_regeneration_subprocess_result",
                "source_replay_id": normalized_id,
                "paper_only": True,
                "live_order_allowed": False,
            }
        result["execution_isolation"] = "subprocess"
        return result
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "status": "regeneration_subprocess_timeout",
            "source_replay_id": normalized_id,
            "error": str(exc),
            "paper_only": True,
            "live_order_allowed": False,
        }
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass


def _child_main(replay_id: str, output_path: Path, *, force: bool = False) -> int:
    from app import stock_suite_app as suite

    result = suite._regenerate_historical_paper_replay_locked(replay_id, force=force)
    if result.get("paper_only") is not True or result.get("live_order_allowed") is not False:
        result = {
            "ok": False,
            "status": "unsafe_child_result_blocked",
            "source_replay_id": replay_id,
            "paper_only": True,
            "live_order_allowed": False,
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, output_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--replay-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.child:
        parser.error("--child is required")
    return _child_main(
        str(args.replay_id).strip().upper(),
        Path(args.output),
        force=bool(args.force),
    )


if __name__ == "__main__":
    raise SystemExit(main())
