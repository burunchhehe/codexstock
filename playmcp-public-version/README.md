# CodexStock PlayMCP Public Version

This folder contains a public, read-only PlayMCP-ready version of CodexStock.

It is intentionally separate from the private CodexStock runtime. It does not expose live trading, account lookup, order submission, tokens, private journals, or personal strategy rules.

## Positioning

Most stock MCP servers answer questions like:

- What is the current price?
- What are the latest news items?
- What does the financial statement show?
- Which names moved today?

CodexStock Research should also answer:

- Why is this stock worth reviewing?
- Which evidence supports or weakens the candidate?
- What does the AI staff think?
- What did the risk gate block or allow?
- What would the investment committee conclude?
- What does the daily operating loop do before, during, and after the market?
- What did the replay/review loop learn?
- Which sub-engines produced evidence?

In short:

```text
stock information lookup + CodexStock research / risk / committee / replay workflow
```

## PlayMCP Listing Draft

| Field | Value |
| --- | --- |
| MCP name | `CodexStock Research` |
| MCP identifier | `codexstock` |
| Auth | No auth for the public read-only preview |
| Tool count | 20 |
| Representative image | `assets/playmcp-codexstock-stock-research.png` |

Description draft:

```text
CodexStock Research is not just a stock quote MCP. It is a read-only investment research MCP that connects market brief, candidate discovery, AI staff review, risk checks, strategy validation, investment committee summaries, post-market replay, learning summaries, and sub-engine status. It does not provide live order submission, account lookup, tokens, or private trading journals.
```

Conversation examples:

```text
Summarize today's market with CodexStock
Show candidate stocks and risk evidence
What are the AI staff watching now?
```

## Public Tool Surface

The public server exposes 20 read-only tools:

| Tool | Purpose |
| --- | --- |
| `explain_codexstock` | Explain what CodexStock Research is |
| `system_health` | Return safe public server status |
| `public_manifest` | List public tools and safety boundaries |
| `market_brief` | Summarize market context |
| `resolve_stock` | Resolve a stock name or code in a lightweight way |
| `stock_snapshot` | Return a redacted quote-style summary |
| `market_movers` | Show mover categories without private data |
| `news_signal_summary` | Summarize public news/signal themes |
| `disclosure_financial_summary` | Summarize disclosure/fundamental context |
| `discover_candidates` | Return candidate ideas with reasons |
| `explain_candidate` | Explain one candidate's evidence and risks |
| `risk_check` | Run a public risk explanation |
| `ai_staff_opinions` | Show AI staff viewpoints |
| `investment_committee` | Show a CodexStock-style committee decision with staff votes |
| `daily_operations_plan` | Show the daily operating loop from pre-market to post-market replay |
| `strategy_validation_summary` | Summarize strategy validation status |
| `post_market_review` | Summarize replay/review output |
| `missed_stock_review` | Explain missed-name review examples |
| `learning_summary` | Summarize what the system learned |
| `sub_engine_status` | Show public sub-engine readiness |

## Local Run

Install dependencies in an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m py_compile server.py
python server.py
```

For a hosted PlayMCP endpoint, deploy this folder as a small read-only MCP server and expose the MCP HTTP endpoint over HTTPS.

## Data Model

By default, the server returns safe demo/public-preview data. To connect it to a private CodexStock runtime safely, export only redacted JSON snapshots into a separate directory and set:

```powershell
$env:CODEXSTOCK_PUBLIC_DATA_DIR="C:\path\to\redacted_public_snapshots"
```

The public server should only read curated files from that directory. Never point it directly at private runtime folders.

## Safety Rules

- No order submission tools
- No account lookup tools
- No token or credential access
- No live order/fill logs
- No private Telegram logs
- No private journal raw text
- No profit guarantee language
- Responses are compact and designed to stay under PlayMCP response limits

