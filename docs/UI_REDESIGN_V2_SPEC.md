# CodexStock UI v2 Design Specification

## Purpose and boundary

UI v2 is a dashboard-only visual layer. It must not change order submission,
approval, risk checks, AI decisions, research jobs, recovery logic, API
contracts, or data models. The first release is read-only and is enabled only
with `?ui=v2`; the default URL remains the existing UI.

The reference image is a visual direction, not a source of values. Never copy
its example account balance, symbols, prices, dates, percentages, or AI status
into product code. Every visible value must come from an existing CodexStock
binding, or be shown as `조회 대기`.

## Information priority

1. Asset value, daily P/L, invested amount, and risk state.
2. Human approval work that needs attention.
3. What AI staff are doing now and their health.
4. Market, watchlist, and research candidates.
5. Supporting system status and help.

Long instructions, tutorials, and implementation details do not belong on the
dashboard. They remain available through the existing pages and help surfaces.

## Layout

- Desktop-first application shell; minimum usable content width is 1120px.
- Fixed sidebar: 224px. Header: 72px. Main gap: 16px. Card gap: 16px.
- The content area uses the full browser width; it has no artificial maximum.
- At widths below 1180px, the dashboard becomes a single column without clipped
  panels. At phone widths, existing mobile UI remains authoritative.
- Card radius: 14px. Border: 1px solid the border token. Elevation is subtle.
- Tables remain one dense table surface; do not nest a card inside every row.
- A status change may animate briefly. Do not use persistent neon, glowing
  borders, or game-like decoration.

## Token system

All UI v2 CSS must consume these tokens. Components may introduce semantic
aliases, but must not repeat raw colors or arbitrary spacing values.

| Token | Value | Meaning |
| --- | --- | --- |
| `--v2-bg` | `#07111f` | application background |
| `--v2-surface` | `#0c1b2d` | card surface |
| `--v2-surface-raised` | `#10243a` | elevated/selected surface |
| `--v2-border` | `#1e3853` | quiet card/divider border |
| `--v2-text` | `#eaf2fb` | primary text |
| `--v2-muted` | `#8da4bd` | secondary text |
| `--v2-accent` | `#26d8c2` | AI normal/interactive accent |
| `--v2-profit` | `#f16c78` | Korean-market positive return |
| `--v2-loss` | `#5b9dff` | Korean-market negative return |
| `--v2-warning` | `#f6b94a` | caution/action needed |
| `--v2-danger` | `#fa535f` | error/danger |
| `--v2-space-*` | `4px` scale | 4, 8, 12, 16, 24, 32 |
| `--v2-radius-*` | `10px`, `14px`, `18px` | component corners |

## Dashboard components

### Header and navigation

The sidebar has a compact brand, a single search affordance, and the existing
main-page destinations. The selected destination uses an elevated navy surface
with a left accent line. The header shows market/system state without competing
with account information.

### KPI row

The first row always contains Total Asset, Today P/L, Invested Amount, and
Risk. The large number is the primary visual element. Its supporting context is
small and muted. P/L uses semantic profit/loss colors; risk uses normal,
warning, and danger independently from P/L.

### Main data region

- Asset trend: existing account/equity data when it exists; otherwise an honest
  empty state. Do not fabricate a chart.
- Portfolio: existing positions and proportions only.
- AI staff: each item has name, current work, health/status, progress if the
  existing source provides it, and last activity. Card dimensions are uniform.
- Market watchlist and AI candidates: compact table-like regions with current
  values. Each existing item continues to open its existing page; the v2 layer
  never creates an order.
- Approval queue: visually distinct warning surface. Show only type, symbol,
  amount/weight, rationale summary, and requested time. Details are opened in
  the existing supervision page.
- Alerts: concise feed with timestamps. Help/tour content is excluded.

## Data and interaction contract

- Reuse existing read-only API results without changing their contracts. The
  concrete dashboard source map is maintained in `UI_V2_DATA_SOURCE_MAP.md`.
  UI v2 must never issue a data-changing request or modify legacy source
  element values.
- V2 batches its read-only refreshes and applies field/list updates by
  signature. It does not observe legacy DOM mutations or rebuild the complete
  dashboard for every market update.
- The only v2 interactions in phase one are navigation to existing pages and
  opening the existing approval page. No new buy, sell, approval, or automation
  controls are permitted.
- Missing, stale, or unavailable data must say so directly. Never replace it
  with sample numbers or a green status.

## File boundary

```
app/web/ui-v2/
  boot.js          # query flag, mount, safe navigation
  tokens.css       # only design tokens and reset for v2
  dashboard.css    # dashboard layout and components
  dashboard.js     # dashboard renderer; no API writes
```

The existing `index.html` receives only the static asset tags. Existing
`app.js`, `styles.css`, routes, API handlers, and Python trading code are not
rewritten during phase one.

## Acceptance checks

- `/` renders the existing UI exactly as before.
- `/?ui=v2` renders UI v2 without changing an existing data source.
- No UI v2 JavaScript uses `fetch`, `POST`, `PUT`, `PATCH`, `DELETE`, or order
  endpoint strings.
- Every v2 action forwards to an existing page, never a new trade action.
- Test the static contract and existing web module contracts before review.
- Capture baseline and v2 screenshots at the same desktop resolution before
  expanding beyond the dashboard.
