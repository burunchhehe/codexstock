# External Signal Push Contract

The external information scout sends its report to CodexStock through a local, information-only inbox.

CodexStock also polls `C:\external-search-mcp\codexstock_outbox\latest_external_signal_report.json` every 15 seconds. The interval can be changed with `CODEXSTOCK_EXTERNAL_SIGNAL_POLL_SECONDS`, and the outbox can be changed with `CODEXSTOCK_EXTERNAL_SIGNAL_OUTBOX`.

## Endpoint

- Method: `POST`
- URL: `http://127.0.0.1:8765/api/external-signal/report`
- Content-Type: `application/json`
- Maximum body size: 2 MiB

Send either the report directly or wrap it as:

```json
{
  "source": "external-info-scout",
  "report": {
    "schema": "codexstock_external_signal_report_v1"
  }
}
```

If `CODEXSTOCK_CONTROL_PLANE_API_KEY` or `CONTROL_PLANE_API_KEY` is configured for CodexStock, include the same value in `X-Control-Plane-Key` or as a Bearer token. Requests are always limited to loopback clients.

## Mandatory safety contract

```json
{
  "safety": {
    "decision_scope": "information_only",
    "external_engine_decision": "VERIFY_ONLY",
    "live_order_allowed": false,
    "requires_codexstock_validation": true
  }
}
```

Every signal must also contain `external_engine_decision: "VERIFY_ONLY"` and `live_order_allowed: false`. Reports containing secret-like fields are rejected. Accepted signals remain `PENDING_VERIFY_ONLY`; they cannot be promoted or used for live orders until CodexStock performs its own checks.

## Readback

- Compact status: `GET /api/external-signal/status`
- Latest accepted report: `GET /api/external-signal/latest`
- MCP tool: `codexstock_external_signal_inbox`

Repeated reports are identified by a canonical SHA-256 signature and recorded as `DUPLICATE_IGNORED`.

Accepted signals are separately queued in runtime data as `codexstock_external_signal_verification_request_v1` records. Their dedupe key is `generated_at:signal_id`, their action is always `VERIFY_ONLY`, and both live-order and promotion permissions remain false.
