# CodexStock MCP Setup

CodexStock can expose a read-focused MCP interface for GPT, Claude, Codex, or other local MCP clients.

## Local MCP Client Example

Use this shape for clients that can launch a local stdio MCP server.

```json
{
  "mcpServers": {
    "codexstock": {
      "command": "powershell.exe",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "<project-root>\\run_mcp_server.ps1"
      ],
      "env": {
        "CODEXSTOCK_BASE_URL": "http://127.0.0.1:8765"
      }
    }
  }
}
```

## ChatGPT Connection

ChatGPT cannot directly execute a local PowerShell command from the cloud. Use a secure MCP tunnel or a remotely reachable HTTPS MCP endpoint.

Recommended local flow:

```text
CodexStock app at http://127.0.0.1:8765
        -> local stdio MCP server
        -> secure tunnel client
        -> ChatGPT connector
```

## Common Tool Surface

- `codexstock_status`: operational status and safety gates
- `codexstock_scorecard`: architecture and evidence scorecard
- `codexstock_staff_status`: AI staff status
- `codexstock_staff_meetings`: AI meeting records
- `codexstock_live_pilot_plan`: live/paper pilot plan
- `codexstock_live_candidate_decisions`: candidate decision reasons
- `codexstock_today_trades`: same-day trade summary
- `codexstock_radar`: market/news/price radar
- `codexstock_screener`: screener and candidate discovery
- `codexstock_sector_news`: sector and theme news
- `codexstock_learning_insights`: learning and review insights
- `codexstock_ask_agent`: ask the local CodexStock agent

## Security Boundary

The MCP surface is designed for status, research, analysis, candidate review, and redacted reporting.

Do not expose:

- account numbers or account identifiers
- API keys, app secrets, access tokens, refresh tokens, Telegram bot tokens, or chat IDs
- exact cash, holdings, settlement, or total-asset values
- private runtime state, personal trading journals, or raw broker logs

Live broker order submission must remain behind the local CodexStock app's safety gates and local user controls.
