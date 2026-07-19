[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [switch]$StartNow,
    [switch]$ReplaceForeignTask
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$taskName = 'CodexStock-InternalDeveloper'
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$hiddenLauncher = Join-Path $repoRoot 'tools\run_internal_developer_hidden.vbs'
$runner = Join-Path $repoRoot 'tools\run_internal_developer.ps1'
$wscript = Join-Path $env:WINDIR 'System32\wscript.exe'
$powershell = Join-Path $PSHOME 'powershell.exe'

foreach ($requiredPath in @($hiddenLauncher, $runner, $wscript, $powershell)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required scheduler file is missing: $requiredPath"
    }
}

# Validate repository/Python/data resolution without running a diagnostic cycle.
$validationText = & $powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $runner -ValidateOnly
if ($LASTEXITCODE -ne 0) {
    throw "Internal-developer launcher validation failed (exit=$LASTEXITCODE)."
}
$validation = $validationText | Select-Object -Last 1 | ConvertFrom-Json
if ($validation.ok -ne $true -or $validation.execution_performed -ne $false) {
    throw 'Internal-developer launcher validation returned an invalid contract.'
}

$quotedLauncher = '"{0}"' -f $hiddenLauncher
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    $owned = $false
    foreach ($existingAction in @($existing.Actions)) {
        if (
            [string]$existingAction.Execute -ieq $wscript -and
            ([string]$existingAction.Arguments).Trim() -eq $quotedLauncher
        ) {
            $owned = $true
            break
        }
    }
    if (-not $owned -and -not $ReplaceForeignTask) {
        throw "Task '$taskName' already exists with a foreign action. Use -ReplaceForeignTask only after reviewing it."
    }
}

$action = New-ScheduledTaskAction `
    -Execute $wscript `
    -Argument $quotedLauncher `
    -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -Hidden `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal `
    -UserId $identity `
    -LogonType Interactive `
    -RunLevel Limited
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'CodexStock safe internal-developer diagnostics and operational recovery only; no orders, credentials, risk changes, code edits, or security changes.'

if ($PSCmdlet.ShouldProcess($taskName, 'Register idempotent one-minute internal-developer task')) {
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
    if ($StartNow) {
        Start-ScheduledTask -TaskName $taskName
    }
}

[pscustomobject]@{
    task_name = $taskName
    registered = -not $WhatIfPreference
    started = [bool]($StartNow -and -not $WhatIfPreference)
    interval_seconds = 60
    multiple_instances = 'IgnoreNew'
    hidden = $true
    principal = $identity
    launcher = $hiddenLauncher
    log_path = [string]$validation.log_path
} | ConvertTo-Json -Compress
