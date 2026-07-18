# ChatGPT MCP Tunnel Handoff

This document explains how to expose a local CodexStock MCP server to ChatGPT through a secure tunnel.

## Local Service

- CodexStock app URL: `http://127.0.0.1:8765`
- Local MCP command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <project-root>\run_mcp_server.ps1`
- MCP transport: `stdio`
- Live broker order submission tools are not exposed through the MCP surface.

## Safety Defaults

- Account numbers, API keys, tokens, cash balances, and exact asset values must be redacted before leaving the local machine.
- GPT-facing responses should use masked account labels and coarse value ranges where financial context is needed.
- Live order authority stays inside the local CodexStock app and its explicit local safety gates.

## Example Tunnel Command

Replace placeholders with values from your own secure tunnel setup.

```powershell
$env:CONTROL_PLANE_API_KEY = "<control-plane-api-key>"

tunnel-client init `
  --sample sample_mcp_stdio_local `
  --profile codexstock-local-stdio `
  --tunnel-id <tunnel-id> `
  --mcp-command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"<project-root>\run_mcp_server.ps1`""

tunnel-client doctor --profile codexstock-local-stdio --explain
tunnel-client run --profile codexstock-local-stdio
```

## ChatGPT Setup

1. Start the local CodexStock app.
2. Start the tunnel client.
3. Add the tunnel connection in ChatGPT's connector/MCP configuration.
4. Verify that CodexStock tools appear and that status calls return redacted output.

Never paste real API keys, account numbers, or private runtime files into a public repository or a shared chat.
