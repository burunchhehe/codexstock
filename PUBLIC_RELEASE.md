# Public Technical Evaluation Snapshot

This release is intended for public technical review of CodexStock's architecture,
workflow, safety model, and research direction without publishing the owner's private
runtime.

Public visibility is provided only to collect reactions, technical review, and feedback.
It does not grant permission to use, copy, modify, redistribute, deploy, sell, or build
a service from the source. CodexStock is not open-source software. See `LICENSE`.

Project creator and maintainer: **Jinwoo Kim** (`burunchhehe`).

## Included

- Local app and MCP bridge source code
- Research Forge integration source
- External engine worker interfaces
- Public documentation
- Tests and examples
- Empty `.env.example`
- Safety and release notes

## Excluded

- `data/`
- `runtime/`
- `reports/`
- `dist/`
- `build/`
- `third_party/` downloaded source vaults
- Broker/account/order logs
- Private AI staff memory and trading journals

## Recommended Public MCP Surface

Keep the public MCP surface small and read-only. Recommended tool groups:

1. Market brief
2. Candidate analysis
3. External signal summary
4. Strategy validation
5. Paper replay
6. Risk scenario
7. Post-market review
8. Staff meeting summary
9. Learning report
10. System health

Do not expose live order submission, account mutation, or private account details.

See `docs/PUBLIC_MCP_SURFACE.md` for the proposed 18-20 tool facade.

## Next Public Hardening Tasks

- Add synthetic demo data for first-run onboarding
- Add a one-command paper-mode smoke test
- Add screenshots or a short demo GIF after private data is removed
- Split optional heavy engine adapters into separate install extras
- Publish a 18-20 tool read-only PlayMCP facade

## Public Evaluation Framing

CodexStock should be reviewed as an AI-assisted investment research and operations
platform. The public repository demonstrates architecture and workflow depth, not a
verified profit claim.
