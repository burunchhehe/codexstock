# Sub-Engine Strategy

CodexStock is the host system. Sub-engines are specialist workers that provide research, validation, market intelligence, or independent evidence.

The core rule is simple:

```text
Sub-engine proposes or verifies -> CodexStock reviews -> risk gate decides -> local app records evidence
```

Sub-engines do not receive broker secrets, account numbers, private journals, or unrestricted live-order authority.

## Engine Roles

| Engine | Role | How CodexStock Uses It | Safety Boundary |
| --- | --- | --- | --- |
| Research Forge | Research-only validation engine | Walk-forward validation, replay evidence, readiness checks, report bundles | Cannot submit live orders |
| External Signal Scout | External information intake | News/blog/cafe/video/theme reports, urgency flags, signal inbox summaries | Sends reports only; no broker access |
| KIS Official Gateway | Official broker/API cross-check layer | Read-only quotation, account-state comparison, KIS MCP readiness and reconciliation support | Isolated and token-gated; order tools blocked in public/MCP surfaces |
| vectorbt Worker | Fast vectorized research | Candidate strategy sweeps and portfolio-style experiments | Receives sanitized research inputs |
| Qlib Worker | Quant research pipeline | Dataset/model experiment bridge for factor-style research | Research-only |
| OpenBB Worker | Market/fundamental research | Additional market, macro, and fundamental context where configured | Read-only |
| Nautilus Worker | Event-driven/backtest research | More realistic event-driven execution and microstructure-style experiments | Research-only |
| Lean Worker | Institutional-style backtest compatibility | Strategy validation through Lean-style project workers | Research-only |
| Backtrader/FinRL/Freqtrade/vn.py Workers | Optional specialist adapters | Tactical backtest, RL-style environment, policy testing, or contract-style gateway experiments | Optional; no live authority by default |
| Knowledge Curator | Host-side knowledge retrieval employee | Incrementally indexes immutable meetings, reviews, research, candidates, and external-signal evidence; routes optional Qdrant, LlamaIndex, Graphiti, and GraphRAG work | Excludes account/order/credential sources and cannot alter source ledgers or submit orders |

## Why Use Sub-Engines?

No single engine is best at everything.

CodexStock uses sub-engines to separate concerns:

- Research Forge: evidence and auditability
- External Signal Scout: outside market information
- KIS Gateway: official Korean broker/API verification
- vectorbt: fast strategy iteration
- Qlib: factor and model research
- OpenBB: broad market research context
- Nautilus/Lean/Backtrader: independent backtest assumptions
- FinRL/Freqtrade/vn.py adapters: optional specialist experimentation
- Knowledge Curator: fast retrieval and provenance across accumulated internal evidence

The Knowledge Curator itself stays lightweight through SQLite FTS and incremental indexing. Qdrant can update in small batches, while LlamaIndex, Graphiti, and GraphRAG are scheduled on demand or outside market hours. Graphiti and GraphRAG remain partial experiments and are not presented as production-complete engines.

## Host Responsibilities

CodexStock remains responsible for:

- deciding which evidence is trusted
- rejecting stale or incomplete outputs
- comparing multiple engines instead of blindly accepting one
- logging why a candidate was promoted, rejected, bought, sold, or reviewed
- keeping private runtime data out of source control
- keeping live trading behind local safety gates

## Public Repository Scope

This repository includes integration workers and contracts, not downloaded third-party source vaults.

That keeps the public release:

- smaller
- legally cleaner
- easier to review
- safer for personal data
- focused on CodexStock's orchestration layer

## Evaluation Notes

When reviewing CodexStock, the important question is not "does it bundle every external engine?"

The better question is:

```text
Can CodexStock route work to specialist engines,
receive evidence,
reject weak outputs,
record the decision,
and improve the next cycle?
```

That orchestration loop is the core value of the sub-engine design.
