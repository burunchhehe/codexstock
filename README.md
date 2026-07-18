# CodexStock

CodexStock is a local-first AI investment research and trading-operations workbench.

It is designed to help an individual investor organize market data, candidate discovery,
strategy validation, paper trading, trading journals, staff-style AI reviews, and
post-market retrospectives in one place.

> Status: public preview. The default mode is research and paper trading. Live trading
> is disabled unless a user configures their own local broker keys and explicitly
> enables live-trading safeguards.

## What Makes It Different

- AI staff workflow for research, risk review, trading notes, and post-market learning
- MCP-friendly read-only status surfaces for ChatGPT and other clients
- Research Forge integration for reproducible strategy experiments and report bundles
- Korean-market oriented workflows with KIS/OpenDART-ready adapters
- External signal inbox design for news, blog, cafe, video, and theme scanners
- Post-market review loops for missed names, chosen trades, reasons, outcomes, and next actions
- Safety-first separation between research/paper mode and live order submission

## Safety Boundaries

This repository must not contain personal credentials or private runtime data.

Do not commit:

- KIS, DART, Naver, Telegram, OpenAI, or other API keys
- Account numbers, broker tokens, approval keys, or OAuth tokens
- Private trading journals, live account snapshots, order logs, or Telegram logs
- Local user data folders, generated runtime databases, or downloaded third-party source vaults

See [SECURITY.md](SECURITY.md) for the public-release policy.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m stock_suite status
```

For local app usage, copy `.env.example` to `.env.local` and fill in only your own
API credentials. Keep `.env.local` private.

```powershell
Copy-Item .env.example .env.local
.\run_app.ps1
```

## Public vs Private Runtime

The public repository is intended to include code, examples, tests, and documentation.
The live user's personal runtime is intentionally separate.

| Area | Public repo | Private local runtime |
| --- | --- | --- |
| Source code | Yes | Yes |
| Sample data | Yes | Optional |
| API keys | No | User-provided |
| Account/order logs | No | Local only |
| Live trading | Disabled by default | Explicit local opt-in only |
| Research/paper mode | Yes | Yes |

## Project Shape

- `app/`: local API server, UI routes, MCP bridge, integrations, and operating logic
- `packages/`: reusable research and facade packages
- `tests/`: focused regression tests for safety, MCP surfaces, and research integration
- `docs/`: public documentation and operating notes
- `examples/`: sample workflows and non-private examples
- `tools/`: local maintenance and validation helpers

Large upstream trading engines are referenced as optional integrations. They should be
installed or downloaded separately for full heavyweight research runs instead of being
committed with private runtime data.

## MCP/Public Tooling Strategy

CodexStock has a broad internal tool surface, but public MCP surfaces should be small,
read-only, and easy for an LLM to choose correctly. The recommended public surface is
about 18-20 tools focused on:

- market brief
- candidate analysis
- strategy validation
- paper replay
- risk scenarios
- post-market review
- staff meeting summary
- external signal summary
- system health

Live order submission tools are not part of the public MCP surface.

## Disclaimer

CodexStock is research software. It is not investment advice and does not guarantee
profit. Backtests, paper simulations, and AI-generated explanations can be wrong or
overfit. Use real capital only after independent review, conservative limits, and
your own responsibility.
