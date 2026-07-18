# CodexStock PlayMCP Public Version

This folder contains a public, read-only PlayMCP-ready version of CodexStock.

It is intentionally separate from the private CodexStock runtime. It does not expose live trading, account lookup, order submission, tokens, private journals, or personal strategy rules.

> CodexStock Research is an investment research support service. It does not provide investment advisory service, trade recommendation, discretionary trading, or live order execution. All outputs are for research reference only, and investment decisions remain the user's responsibility.

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
- What market risks should be checked first?
- Which sectors and themes are active?
- What catalyst might explain a move?
- Which candidate is stronger after comparison?
- What conditions keep a name on the watchlist?
- What would the research committee observe?
- What did the replay/review loop learn?

In short:

```text
stock information lookup + market risk / theme / catalyst / candidate / risk / replay workflow
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
CodexStock Research is not just a stock quote MCP. It is a read-only investment research MCP that connects market brief, risk events, sector/theme strength, catalysts, candidate discovery, candidate comparison, AI staff review, risk checks, strategy validation, post-market replay, and learning summaries. It does not provide live order submission, account lookup, tokens, or private trading journals.
```

Conversation examples:

```text
What sectors and themes are strong today?
Compare these candidate stocks by evidence and risk
Why did this stock move and should I keep watching it?
```

## Public Tool Surface

The public server exposes 20 read-only tools:

| Tool | Purpose |
| --- | --- |
| `system_health` | Return safe public server status |
| `market_brief` | Summarize market context |
| `market_risk_events` | Summarize macro, flow, calendar, and event risks |
| `sector_theme_brief` | Summarize strong sectors, themes, and evidence categories |
| `market_movers` | Show mover categories without private data |
| `resolve_stock` | Resolve a stock name or code in a lightweight way |
| `stock_snapshot` | Return a redacted quote-style summary |
| `news_signal_summary` | Summarize public news/signal themes |
| `catalyst_check` | Check likely public catalysts behind a stock or theme move |
| `disclosure_financial_summary` | Summarize disclosure/fundamental context |
| `discover_candidates` | Return candidate ideas with reasons |
| `candidate_compare` | Compare candidates by evidence, risk, and next checks |
| `explain_candidate` | Explain one candidate's evidence and risks |
| `risk_check` | Run a public risk explanation |
| `watchlist_plan` | Create keep/drop watchlist conditions |
| `ai_staff_opinions` | Show AI staff viewpoints |
| `investment_committee` | Show a CodexStock-style research committee observation |
| `strategy_validation_summary` | Summarize strategy validation status |
| `post_market_review` | Summarize replay/review output |
| `learning_summary` | Summarize what the system learned |

## Tool Role Boundaries

Some tools may sound similar, so their roles are intentionally separated:

| Tool | Boundary |
| --- | --- |
| `market_brief` | Broad market regime, tone, themes, and risk events |
| `market_risk_events` | Macro, flow, calendar, and event risks to check before research |
| `sector_theme_brief` | Sector/theme strength, not individual stock endorsement |
| `market_movers` | Hot-stock or theme movement categories |
| `discover_candidates` | CodexStock watch candidates after public evidence filtering |
| `candidate_compare` | Relative research comparison between watch candidates |
| `explain_candidate` | Detailed evidence and invalidation checks for one candidate |
| `watchlist_plan` | Keep/drop research conditions for monitoring |
| `investment_committee` | Research-only committee observation, not a buy/sell recommendation |

## Response Metadata

Every tool response includes safety metadata:

```json
{
  "meta": {
    "data_mode": "sample | delayed | live_public",
    "generated_at": "ISO-8601 timestamp",
    "source_scope": "public_redacted",
    "investment_action": "disabled",
    "disclaimer": "Research support only. Not investment advice, not a trade recommendation, and not live order execution."
  }
}
```

When `data_mode` is `sample`, outputs are public examples and must not be interpreted as current market results.

## Local Run

Install dependencies in an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m py_compile server.py
python server.py
```

Run as a local HTTP MCP endpoint:

```powershell
$env:CODEXSTOCK_PUBLIC_MCP_TRANSPORT="streamable-http"
$env:CODEXSTOCK_PUBLIC_MCP_HOST="127.0.0.1"
$env:CODEXSTOCK_PUBLIC_MCP_PORT="8000"
python server.py
```

Local MCP endpoint:

```text
http://127.0.0.1:8000/mcp
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
