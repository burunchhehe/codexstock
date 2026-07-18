# Security Policy

CodexStock is local-first research software. Public releases must be safe to inspect
without exposing the original user's accounts, credentials, private runtime logs, or
live order history.

## Public Release Rules

Never commit:

- `.env`, `.env.local`, or any non-example environment file
- KIS, DART, Naver, Telegram, OpenAI, broker, OAuth, or tunnel tokens
- Account numbers, approval phrases, broker user IDs, or order approval keys
- Live account snapshots, order submissions, fill logs, reconciliation logs, or PnL logs
- Personal watchlists, Telegram chat logs, staff long-memory files, or private journals
- Generated SQLite/JSONL runtime stores, caches, downloaded vaults, or third-party mirrors

Commit only:

- Source code
- Tests
- Documentation
- Safe examples
- `.env.example` with empty values
- Small synthetic sample data when needed

## Live Trading Boundary

The public codebase defaults to research/paper mode. Live trading must require all of
the following in a private local runtime:

- User-owned broker credentials
- Explicit local opt-in
- Position and cash limits
- Order reason logging
- Kill switch availability
- Reconciliation after order/fill/account updates

Public MCP tools must stay read-only and must not expose order submission functions.

## Reporting a Security Issue

If you find a leaked credential, account identifier, unsafe live-trading default, or
private data exposure risk, remove the affected file from public distribution and rotate
the exposed credential before continuing development.
