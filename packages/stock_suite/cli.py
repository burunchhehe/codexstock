from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Sequence

from .registry import available_projects


PYTHON_IMPORTS = {
    "yfinance": "yfinance",
    "vectorbt": "vectorbt",
    "backtrader": "backtrader",
    "zipline": "zipline",
    "finrl": "finrl",
    "freqtrade": "freqtrade",
}


def _module_status(project_name: str) -> str:
    module_name = PYTHON_IMPORTS.get(project_name)
    if not module_name:
        return "source"
    return "importable" if importlib.util.find_spec(module_name) else "source-only"


def print_status() -> None:
    print("Stock Open Source Suite")
    print()
    for project in available_projects():
        state = "present" if project.exists else "missing"
        module_state = _module_status(project.name)
        print(f"- {project.name:10} {state:7} {module_state:11} {project.role}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stock-suite")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Show bundled project status")
    args = parser.parse_args(argv)

    if args.command in (None, "status"):
        print_status()
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2
