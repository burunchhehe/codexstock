# CodexStock Technical Brief

CodexStock is a local AI-assisted investment research, validation, monitoring, and trading-operations platform.

This private repository snapshot is intended to preserve the source code and non-confidential technical materials. It does not include private runtime data, account logs, API keys, broker tokens, personal trading journals, large generated datasets, or executable builds.

## High-Level Architecture

- Local Python application server
- Browser-based HTS-style dashboard
- MCP server surface for redacted GPT/Codex access
- AI staff workflow for research, risk, strategy review, and trade journaling
- KIS/OpenDART/KRX/macro-ready adapters
- Paper/live separation with safety gates
- External research-engine integration points
- Replay, backtest, reconciliation, and review evidence stores

## Core Modules

- `app/stock_suite_app.py`: primary local application server and workflow coordinator
- `app/codexstock_mcp_server.py`: MCP tool manifest and redacted tool routing
- `app/integrations.py`: market, broker, disclosure, macro, and notification adapters
- `app/kis_mcp_gateway.py`: isolated KIS MCP gateway status and safety bridge
- `app/ops_core.py`: operational logs, Telegram policy, and audit helpers
- `app/web/`: dashboard UI
- `packages/stock_suite/`: reusable package-level stock-suite utilities
- `packages/codexstock_research_forge/`: research-only validation engine package
- `tools/`: local helper scripts and verification utilities
- `tests/`: regression and safety tests

## Safety Boundaries

CodexStock separates analysis from execution.

- GPT-facing tools are intended for status, research, candidates, and redacted reports.
- Live broker order authority must remain behind local safety gates.
- External engines may propose or validate research outputs, but must not receive broker secrets or live-order authority.
- `.env.local`, real keys, tokens, account numbers, personal runtime folders, broker logs, and exact asset snapshots must never be committed.

## Repository Exclusions

The upload intentionally excludes:

- `data/`
- `runtime/`
- `reports/`
- `build/`
- `dist/`
- `third_party/`
- logs, SQLite databases, archives, executable builds, backups, and damaged runtime files

## Validation Commands

Run from the repository root after installing dependencies:

```powershell
python -m py_compile app\stock_suite_app.py
python -m py_compile app\codexstock_mcp_server.py
node --check app\web\app.js
python -m pytest tests
```

If local dependencies are incomplete, start with targeted syntax checks and then expand to the full test suite.

## Current Maturity View

Technically, CodexStock is beyond a simple auto-trading script. It is closer to a personal AI investment operations platform with:

- multi-source data adapters
- candidate discovery and market radar
- AI staff review loops
- backtest and replay evidence
- paper/live trade separation
- reconciliation-oriented order logs
- MCP-based redacted status access
- external research-engine integration

However, production investment-performance claims still require long forward observation, strict point-in-time data, blind/OOS evidence, Monte Carlo stress testing, and real-world execution stability over time.

## Next Engineering Priorities

1. Keep public/private release hygiene strict.
2. Strengthen point-in-time universe and corporate-action evidence.
3. Keep heavy research jobs separated from market-hours trading operations.
4. Improve GPT-facing MCP schemas so tool discovery stays compact and current.
5. Continue tightening live order, fill, balance, and PnL reconciliation.
6. Preserve daily review and learning evidence in private runtime storage, not source control.
