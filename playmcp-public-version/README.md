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
- What did the replay/review loop learn?
- Which sub-engines produced evidence?

In short:

```text
stock information lookup + CodexStock research / risk / replay workflow
```

## PlayMCP Listing Draft

| Field | Value |
| --- | --- |
| MCP name | `CodexStock Research` |
| MCP identifier | `codexstock` |
| Auth | No auth for the public read-only preview |
| Tool count | 18 |
| Representative image | `assets/playmcp-codexstock-stock-research.png` |

Description:

```text
CodexStock Research는 단순 주식 시세 조회 MCP가 아니라, 시장 요약, 후보 발굴, AI 직원 검토, 리스크 점검, 전략 검증, 장마감 복기, 학습 요약을 연결해 개인 투자 연구 과정을 운영하는 읽기 전용 MCP입니다. 실전 주문, 계좌 조회, 토큰, 개인 매매일지 원문은 제공하지 않습니다.
```

Conversation examples:

```text
코덱스스톡 오늘 시장 요약해줘
후보 종목과 리스크 근거 보여줘
AI 직원들이 지금 뭘 보는지 알려줘
```

## Public Tool Surface

The public server exposes 18 read-only tools:

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

