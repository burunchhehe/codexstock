# Recommended Public MCP Surface

CodexStock has many internal functions, but a public MCP should not expose everything.

For public use and PlayMCP-style review, prefer a compact read-only facade with approximately 18-20 tools.

## Design Rules

1. Keep tools read-only.
2. Keep response size below platform limits.
3. Use names that clearly describe the action.
4. Avoid overlapping tools with vague differences.
5. Redact private account and credential data.
6. Do not expose live order submission.
7. Return structured JSON with concise human summaries.

## Suggested Tool Groups

| Group | Purpose |
| --- | --- |
| System health | Is the local app alive and safe? |
| Market brief | What matters before/during/after market hours? |
| Candidate review | Which names are under review and why? |
| Risk view | What risks block or weaken candidates? |
| Paper replay | What did a paper/historical replay learn? |
| Strategy validation | What evidence supports or rejects a strategy? |
| Staff summary | What are the AI roles doing? |
| External signals | What outside signals arrived and how were they judged? |
| Learning report | What changed after reviews and replays? |

## Example Tool List

1. `codexstock_health`
2. `codexstock_market_brief`
3. `codexstock_intraday_radar`
4. `codexstock_candidate_summary`
5. `codexstock_candidate_explain`
6. `codexstock_risk_snapshot`
7. `codexstock_staff_status`
8. `codexstock_staff_meeting_summary`
9. `codexstock_today_trade_summary`
10. `codexstock_trade_reason_lookup`
11. `codexstock_paper_replay_summary`
12. `codexstock_post_market_review`
13. `codexstock_missed_candidate_review`
14. `codexstock_strategy_validation_summary`
15. `codexstock_research_forge_status`
16. `codexstock_external_signal_summary`
17. `codexstock_learning_report`
18. `codexstock_public_scorecard`
19. `codexstock_runtime_safety_audit`
20. `codexstock_help`

## Tools That Should Stay Private

- live order submit
- account mutation
- exact balance lookup
- raw broker token inspection
- raw Telegram chat access
- full private journal dump
- secret/config writing
- local filesystem export of private runtime data

## Response Shape

Prefer this pattern:

```json
{
  "ok": true,
  "generated_at": "2026-07-18T00:00:00+09:00",
  "summary": "Short human-readable answer.",
  "items": [],
  "warnings": [],
  "redactions": ["account_number", "exact_cash"]
}
```

## Public Review Positioning

The public MCP should make CodexStock easy to inspect, not easy to misuse.

The best public value is:

- explainability
- auditability
- research evidence
- safety state
- post-market learning

The live broker execution layer should remain local and private.
