from __future__ import annotations

import os
import re
import secrets
from pathlib import Path


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    source = local_app_data / "CodexStock" / "config" / ".env"
    target = local_app_data / "CodexStock" / "secrets" / "kis_mcp.env"
    if not source.is_file():
        raise SystemExit("CodexStock KIS configuration was not found.")

    values = _read_env(source)
    required = ("KIS_MOCK_APP_KEY", "KIS_MOCK_APP_SECRET", "KIS_MOCK_ACCOUNT_NO")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise SystemExit(f"Missing paper credential fields: {', '.join(missing)}")
    account_digits = re.sub(r"\D", "", values["KIS_MOCK_ACCOUNT_NO"])
    if len(account_digits) < 8:
        raise SystemExit("Paper account number is invalid.")

    existing = _read_env(target) if target.is_file() else {}
    access_token = existing.get("MCP_ACCESS_TOKEN") or secrets.token_urlsafe(48)
    payload = "\n".join(
        [
            "# Generated for CodexStock's loopback-only, paper-read KIS MCP gateway.",
            f"MCP_ACCESS_TOKEN={access_token}",
            f"KIS_PAPER_APP_KEY={values['KIS_MOCK_APP_KEY']}",
            f"KIS_PAPER_APP_SECRET={values['KIS_MOCK_APP_SECRET']}",
            f"KIS_PAPER_STOCK={account_digits[:8]}",
            "KIS_HTS_ID=",
            "MCP_HOST=0.0.0.0",
            "MCP_PORT=3000",
            "",
        ]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, target)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print(f"configured={target} mode=paper secrets_exposed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
