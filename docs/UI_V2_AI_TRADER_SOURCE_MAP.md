# UI v2 AI Trader Source Map

## Existing screen inventory

The legacy `aiTrader` page contains AI briefing, autopilot status, market
regime, alert/report dispatch, daemon status, staff board, market clock, and
the operational safety gate. It also contains controls that change state.
UI v2 presents only the read-only operational summary and routes every action
back to the legacy page.

| Area | Existing read source | UI v2 fields | Legacy-only state-changing controls |
| --- | --- | --- | --- |
| AI operation / mode | `/api/agent/autopilot` | `summary.autopilot_running`, `mode`, `phase`, `next_check_at`, `actions` | Autopilot tick/start/stop |
| Staff board | `/api/agent/staff/quick?ttl=60` | worker identity, task, status, optional progress, activity | Staff meeting run, persona save |
| Human confirmation | `/api/ops/status/poll` | `approvals.pending`, `approvals.recent` | Approval resolve, policy save, real execution switches |
| AI alerts | `/api/agent/alerts` | priority, title, message, action | Telegram alert digest |
| Market schedule | `/api/agent/market-clock` | sessions, tasks | none in v2 |
| Recent reasoning | `/api/agent/autopilot` | recent runs/actions when supplied | detailed logs stay in legacy |

## Safety boundary

- No UI v2 route issues POST/PUT/PATCH/DELETE.
- No order, approval, scheduler, Telegram, policy, or API-key action is added.
- Any operator action routes to the existing legacy `aiTrader` page.
- The visual fixture is localhost-only and requires `ui=v2`, `page=aiTrader`,
  and `fixture=visual`.
