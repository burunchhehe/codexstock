"""Print the current CodexStock Shadow execution evidence audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
for path in (APP_ROOT, REPO_ROOT / "packages"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ops_core import HepiOpsCore  # noqa: E402
from stock_suite.sidecar_audit import audit_shadow_runtime  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--min-results", type=int, default=10)
    parser.add_argument("--min-symbols", type=int, default=2)
    args = parser.parse_args()
    ops = HepiOpsCore(REPO_ROOT)
    audit = audit_shadow_runtime(
        ops.data_dir / "execution_sidecar",
        args.hours,
        min_result_count=max(1, args.min_results),
        min_symbol_count=max(1, args.min_symbols),
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit["operational_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
