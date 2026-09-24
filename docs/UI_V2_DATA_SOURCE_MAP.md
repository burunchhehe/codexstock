# UI v2 Dashboard Data Source Map

UI v2 only uses existing read-only GET routes. It does not call a write route,
submit an order, approve a ticket, alter risk settings, or trigger a strategy
run. The first dashboard refresh batches these reads; subsequent refreshes run
every 30 seconds, while the KIS account read is limited to once per 60 seconds.

| UI area | Existing source | Fields used | Display rule |
| --- | --- | --- | --- |
| Mode badge | `/api/kis/account`, `/api/ops/status/poll` | `ok`, `summary`, `paper` | Use `실전 계좌 · KIS` only when KIS account is successful; use `Paper 모의 계좌` only when the Paper ledger is actually returned; otherwise show an account retrieval failure. |
| Market header | `/api/agent/market-clock` | `sessions[].name`, `phase`, `phase_label` | Korean market phase only; no inferred OPEN state. |
| Market summary | `/api/market?bars=1` | `quotes[]` | Shows number of watchlist quotes received. KOSPI/KOSDAQ summary remains `미제공` because this route has no index contract. |
| AI header/status | `/api/agent/staff/quick?ttl=60` | `worker_board.summary`, `worker_board.workers[]` | Use only reported active/working/attention counts and worker state fields. |
| Alert badge and feed | `/api/agent/alerts` | `summary.total`, `alerts[]` | Uses reported priority/title/message/action; an empty list is a real empty state. |
| Total asset | `/api/kis/account` then `/api/ops/status/poll` | KIS `summary.net_liquidation_value` or `total_value`; Paper `paper.equity` | KIS value wins only if account `ok`; Paper fallback is labeled. |
| Today realized P/L | `/api/ops/live-performance` | `today_realized_gross_pnl`, `today_realized_count` | This is realized P/L from matched execution records, not account-wide unrealized daily P/L. |
| Invested amount | `/api/kis/account` then `/api/ops/status/poll` | KIS `summary.stock_value`; Paper `paper.market_value` | Uses same explicit live/Paper mode as total asset. |
| Risk KPI | `/api/ops/status/poll` | `safety`, `safety_state.real_order`, `approvals.pending` | Uses reported gate state, not a fabricated normal/healthy state. |
| Asset trend | No suitable current contract | none | Deliberate empty state. `app.js` `state.equity` is a backtest curve and is never presented as account history. |
| Portfolio allocation | `/api/kis/account` then `/api/ops/status/poll` | positions, value/evaluation amount, profit/loss rate | Computes weight only from current source equity. Donut appears only from real positions/cash. |
| AI staff board | `/api/agent/staff/quick?ttl=60` | `workers[].name/id`, state/status, task, activity timestamp, optional progress | Progress bar exists only when a numeric progress field is actually returned. |
| Main watchlist | `/api/market?bars=1` | `quotes[].name/symbol`, `price`, `change_pct` | Shows server-returned quotes; no sample symbols or prices. |
| AI candidates | `/api/agent/screener` | `candidates[].name/symbol`, `score`, `risk_gate_status/gate` | Reads cache/default response without `force=1`. Missing candidates remain empty. |
| Approval queue | `/api/ops/status/poll` | `approvals.pending`, `approvals.recent[]` | Shows only records whose existing status is `pending`. No approval action is added. |

## Deliberate omissions

- A period-switchable account chart is not implemented until a true account
  valuation history API exists.
- KOSPI/KOSDAQ index percentages are not synthesized from watchlist quotes.
- No AI activity percentage, healthy state, P/L, asset figure, stock, or alert
  is fabricated if the API does not provide it.
- The side navigation maps to existing legacy page IDs. It never creates a new
  operational endpoint or duplicates an action surface.
