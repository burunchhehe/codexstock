from __future__ import annotations

import ast
from pathlib import Path


SERVER = Path(__file__).with_name("server.py")


def _literal_public_tools() -> list[str]:
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PUBLIC_TOOLS":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, list):
                        return value
    raise AssertionError("PUBLIC_TOOLS not found")


def main() -> None:
    tools = _literal_public_tools()
    assert len(tools) == 20, f"expected 20 tools, got {len(tools)}"
    assert "investment_committee" in tools
    assert "daily_operations_plan" in tools
    source = SERVER.read_text(encoding="utf-8")
    assert "investment_action" in source
    assert "disabled" in source
    assert "Not investment advice" in source
    assert "live order submission" in source
    print("public contract smoke test passed")


if __name__ == "__main__":
    main()

