# Internal Developer Scheduler

`CodexStock-InternalDeveloper` runs one bounded internal-developer cycle every
minute. It is independent of `CodexStock-Watchdog` and uses both Task
Scheduler's `IgnoreNew` policy and the service's file lock to prevent overlap.

The scheduled action is hidden and runs as the current interactive Windows
user. The launcher first verifies `runtime/codexstock_runtime_root.json` and its
approved Python executable. If no valid contract exists, it only accepts the
repository virtual environment or the known Codex Python runtime for the
current user. Service state, heartbeat, incident data, and
`internal_developer/scheduler.log` stay under the active user-data root.

The scheduler can initiate only the operational recovery actions enforced by
`app/internal_developer_service.py` and the deterministic policy engine. It
does not grant permission to place stock orders, change API keys, relax risk
limits, edit code, or disable security controls.

## Validate without registering

```powershell
powershell.exe -NoProfile -File .\tools\run_internal_developer.ps1 -ValidateOnly
powershell.exe -NoProfile -File .\tools\register_internal_developer.ps1 -WhatIf
```

## Register

```powershell
powershell.exe -NoProfile -File .\tools\register_internal_developer.ps1
```

Registration is idempotent for a task owned by this launcher. A foreign task
using the same name is rejected unless `-ReplaceForeignTask` is supplied after
manual review. Registration does not start a cycle; use `-StartNow` only when
an immediate first run is intended.
