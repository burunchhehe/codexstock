# Feature Map

CodexStock is designed as a full investment workflow rather than a single strategy script.

## 1. Market Awareness

- watchlist-centered market view
- intraday candidate radar
- sector/theme notes
- news/disclosure/macro adapter structure
- external signal inbox contract
- trading-session mode switching

## 2. Candidate Discovery

- screener entry points
- liquidity and momentum context
- candidate scoring integrity checks
- live decision context cards
- missed-candidate review hooks
- duplicate-score and sector-concentration guards

## 3. AI Staff Workflow

CodexStock models multiple operating roles:

- research AI
- supply/demand researcher
- fundamentals researcher
- strategy researcher
- trading AI
- risk manager
- Telegram/reporting assistant

The point is not to pretend that each role is a separate human. The point is to force different analytical perspectives to leave structured evidence before a decision is promoted.

## 4. Research Forge

Research Forge is the research-only sub-engine.

It focuses on:

- point-in-time universe handling
- walk-forward validation
- realistic fill assumptions
- replay evidence
- report bundles
- indicator validation
- microstructure collection boundaries
- readiness gates

Research Forge is intentionally not allowed to submit live orders.

## 5. Backtest, Replay, and Review

CodexStock includes structures for:

- historical replay
- daily replay
- post-market review
- missed-name analysis
- chosen-trade reasoning
- replay evidence hashing
- long-horizon performance evidence
- learning-memory trace tests

## 6. Trading Operations

The trading side is built around safety and auditability:

- paper/live separation
- delegated capital policy structure
- order intent and reason logging
- dry-submit style gates
- broker execution checks
- order/fill/account reconciliation
- kill-switch-oriented status

The public repository does not include private account state or live order logs.

## 7. MCP and GPT Access

CodexStock exposes redacted MCP-style access for LLM clients.

Useful GPT-facing tasks:

- ask "what is the system doing?"
- summarize candidate reasons
- inspect staff meeting records
- explain why a trade was chosen or rejected
- review post-market learning
- check system health

Unsafe tasks, such as submitting orders or exposing account identifiers, should remain unavailable from the public MCP surface.

## 8. External Engine Integration

The codebase includes adapters/workers for heavyweight research tools and external engines. These are integration surfaces, not bundled third-party source vaults.

Examples:

- vectorbt worker
- Qlib worker
- OpenBB worker
- Nautilus worker
- Lean worker
- Backtrader worker
- FinRL-style environment worker
- Freqtrade policy worker
- vn.py contract worker

## 9. Public Evaluation Scope

This repository is intended to show:

- system architecture
- safety design
- workflow depth
- code organization
- test coverage direction
- MCP/read-only design
- research-engine integration

It is not intended to show private trading performance, account value, live broker history, or the owner's personal trading journal.

## 10. Internal Developer and Recovery

CodexStock now includes an independent, fail-closed operational sidecar:

- one-minute heartbeat and bounded read-only diagnostics
- busy/progress detection so long-running work is not mistaken for a frozen app
- deterministic incident classification and severity
- atomic JSON incident, report, advice, event, and playbook ledgers
- single-instance scheduling and overlap prevention
- registered cache refresh, external-engine reconnect, research retry, and ledger rebuild handlers
- read-only SQLite lock detection
- verified restart-request handoff to the independent watchdog
- Telegram incident reporting through the existing reporting queue
- launcher health dock with persisted drag position and incident history
- GPT/MCP report reading and external-guidance intake
- quarantine for unknown, malformed, or dangerous actions
- mandatory post-action verification before a recovery is recorded

The automatic-recovery boundary excludes live orders, API key changes, code patches, security changes, risk-limit relaxation, process killing, and database lock-file deletion.

## 11. Local Model Runtime Recovery

The local AI path has a bounded recovery helper for Ollama:

- local loopback endpoints only
- installed executable discovery
- hidden startup with a cooldown to avoid restart storms
- readiness polling before model generation
- optional CPU backend fallback when the detected GPU runtime is incompatible
- deterministic status queries bypass the model entirely when a model response is unnecessary

This improves availability without giving model output authority over operational safety or trading policy.

## 12. Knowledge Curator

The Knowledge Curator keeps accumulated research usable without modifying source ledgers:

- bounded discovery of meetings, reviews, replays, learning, strategy, journal, memory, and evidence sources
- core-versus-archive scheduling so large historical corpora do not block intraday work
- immutable provenance with source path, locator, event time, and content hashes
- JSONL tail indexing and unchanged-source detection
- private SQLite table and column exclusion
- SQLite FTS5/BM25 immediate retrieval
- Qdrant lightweight feature-hash similarity projection
- on-demand LlamaIndex chunk projection
- optional Graphiti and GraphRAG experiments kept outside the always-on path

See [KNOWLEDGE_CURATOR.md](KNOWLEDGE_CURATOR.md) for the exact status and limitations.

## 13. Android Mobile Console

The private mobile console provides paired, revocable access to operational views:

- expiring one-time pairing code
- hashed device tokens and per-device revocation
- private HTTPS transport
- system state, work focus, candidates, staff, sub-engines, and incident views
- read-only assistant commands
- confirmation-gated emergency stop
- explicit blocking of direct orders, automation start, credential access, and risk relaxation

See [MOBILE_CONSOLE.md](MOBILE_CONSOLE.md) for architecture and verification evidence.
