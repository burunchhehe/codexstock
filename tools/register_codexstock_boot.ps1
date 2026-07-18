$ErrorActionPreference = 'Stop'

$watchdog = Join-Path $PSScriptRoot 'codexstock_watchdog.ps1'
$taskAction = 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $watchdog

& schtasks.exe /Create /TN 'CodexStock-Boot' /SC ONSTART /DELAY 0001:00 /RU SYSTEM /RL HIGHEST /TR $taskAction /F
if ($LASTEXITCODE -ne 0) { throw "Failed to register CodexStock-Boot (exit=$LASTEXITCODE)" }

& schtasks.exe /Run /TN 'CodexStock-Boot'
if ($LASTEXITCODE -ne 0) { throw "Registered CodexStock-Boot, but test run failed (exit=$LASTEXITCODE)" }
