$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$runtimeContractSelected = $false
$runtimeContractPath = Join-Path $root 'runtime\codexstock_runtime_root.json'
$python = $null
$userData = $null
if (Test-Path -LiteralPath $runtimeContractPath) {
    try {
        $candidate = Get-Content -LiteralPath $runtimeContractPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $candidatePython = [string]$candidate.python_executable
        if (Test-Path -LiteralPath $candidatePython) {
            $env:CODEXSTOCK_CONTRACT_REPO_ROOT = $root
            $validationText = & $candidatePython -c "import json,os,sys; root=os.environ['CODEXSTOCK_CONTRACT_REPO_ROOT']; sys.path.insert(0,root); from app.runtime_paths import read_runtime_root_contract; print(json.dumps(read_runtime_root_contract(root)))"
            Remove-Item Env:CODEXSTOCK_CONTRACT_REPO_ROOT -ErrorAction SilentlyContinue
            $validation = $validationText | ConvertFrom-Json
            if ($validation.valid -eq $true) {
                $python = [string]$validation.python_executable
                $userData = [string]$validation.user_data_root
                $runtimeContractSelected = $true
            }
        }
    }
    catch {
        Remove-Item Env:CODEXSTOCK_CONTRACT_REPO_ROOT -ErrorAction SilentlyContinue
        $runtimeContractSelected = $false
    }
}

if (-not $runtimeContractSelected) {
    $userProfile = Get-ChildItem 'C:\Users' -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Documents\Codex') } |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $userProfile) {
        throw 'Could not locate the CodexStock user profile or a verified runtime-root contract.'
    }
    $python = Join-Path $userProfile '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $userData = Join-Path $userProfile 'AppData\Local\CodexStock\data'
}
$opsHealthUrl = 'http://127.0.0.1:8765/api/ops/status/poll'
$researchHealthUrl = 'http://127.0.0.1:8765/api/external-engines/improvement-loop/status?lesson_limit=1&task_limit=1'
$logFile = Join-Path $root 'runtime\codexstock_watchdog.log'
$restartRequestFile = Join-Path $root 'runtime\codexstock_restart_request.json'
$watchdogStateFile = Join-Path $root 'runtime\codexstock_watchdog_state.json'
$maxConsecutiveFailures = 5

function Write-WatchdogLog([string]$message) {
    $line = '{0} | {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
}

function Read-WatchdogState {
    if (Test-Path -LiteralPath $watchdogStateFile) {
        try {
            return Get-Content -LiteralPath $watchdogStateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        catch {
            Write-WatchdogLog "watchdog state reset after read error: $($_.Exception.Message)"
        }
    }
    return [pscustomobject]@{
        consecutive_failures = 0
        last_research_signature = ''
        last_ok_at = ''
        last_failure_at = ''
    }
}

function Write-WatchdogState([object]$state) {
    $directory = Split-Path -Parent $watchdogStateFile
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $temporary = "$watchdogStateFile.tmp"
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $watchdogStateFile -Force
}

function Reset-WatchdogFailures([string]$reason) {
    $state = Read-WatchdogState
    $previous = [int]($state.consecutive_failures)
    $state.consecutive_failures = 0
    $state.last_ok_at = (Get-Date).ToString('o')
    $state.last_failure_at = ''
    Write-WatchdogState $state
    if ($previous -gt 0) {
        Write-WatchdogLog "watchdog failure counter reset after $reason (previous=$previous)"
    }
}

function Get-ResearchSignature([object]$payload) {
    if (-not $payload) { return '' }
    $state = $payload.state
    if (-not $state) { return '' }
    return @(
        [string]$state.cycle_id,
        [string]$state.status,
        [string]$state.phase,
        [string]$state.phase_index,
        [string]$state.progress_pct,
        [string]$state.active_retraining_task_count,
        [string]$state.claimed_retraining_task_count
    ) -join '|'
}

function Test-ResearchWorkActive([object]$payload) {
    if (-not $payload) { return $false }
    $state = $payload.state
    $terminal = @('COMPLETED', 'FAILED', 'CANCELLED', 'IDLE', 'EXHAUSTED')
    if ($payload.heavy_research_lock_active -eq $true -or $payload.thread_alive -eq $true) {
        return $true
    }
    if ($state) {
        $status = [string]$state.status
        $terminalStatus = [string]$state.terminal_status
        $activeRetraining = [int]($state.active_retraining_task_count)
        $claimedRetraining = [int]($state.claimed_retraining_task_count)
        if ($activeRetraining -gt 0 -or $claimedRetraining -gt 0) { return $true }
        if ($status -and ($terminal -notcontains $status.ToUpperInvariant())) { return $true }
        if ($terminalStatus -and ($terminal -notcontains $terminalStatus.ToUpperInvariant())) { return $true }
    }
    return $false
}

function Register-WatchdogFailure([string]$reason, [object]$researchPayload) {
    $state = Read-WatchdogState
    $signature = Get-ResearchSignature $researchPayload
    $researchActive = Test-ResearchWorkActive $researchPayload
    if ($researchActive) {
        if ($signature -and $signature -ne [string]$state.last_research_signature) {
            $state.consecutive_failures = 0
            $state.last_research_signature = $signature
            $state.last_ok_at = (Get-Date).ToString('o')
            Write-WatchdogState $state
            Write-WatchdogLog "restart deferred: research is active and progressing ($reason)"
            return $false
        }
        Write-WatchdogLog "restart deferred: research is active ($reason)"
        Write-WatchdogState $state
        return $false
    }
    $state.consecutive_failures = [int]($state.consecutive_failures) + 1
    $state.last_research_signature = $signature
    $state.last_failure_at = (Get-Date).ToString('o')
    Write-WatchdogState $state
    Write-WatchdogLog ("watchdog health failure {0}/{1}: {2}" -f $state.consecutive_failures, $maxConsecutiveFailures, $reason)
    return ([int]$state.consecutive_failures -ge $maxConsecutiveFailures)
}

try {
    $restartRequested = $false
    $confirmedRestart = $false
    if (Test-Path -LiteralPath $restartRequestFile) {
        try {
            $request = Get-Content -LiteralPath $restartRequestFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $expectedPid = [int]$request.expected_pid
            $target = Get-CimInstance Win32_Process -Filter "ProcessId=$expectedPid" -ErrorAction SilentlyContinue
            $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
                Select-Object -First 1
            $codexStatus = $null
            try {
                $codexStatus = Invoke-RestMethod -Uri $researchHealthUrl -TimeoutSec 10
            }
            catch {
                $codexStatus = $null
            }
            if (
                $target -and
                $target.Name -eq 'python.exe' -and
                $listener -and
                [int]$listener.OwningProcess -eq $expectedPid -and
                $codexStatus -and
                $codexStatus.contract.schema -eq 'codexstock_external_improvement_contract_v1'
            ) {
                Stop-Process -Id $expectedPid -Force -ErrorAction Stop
                Wait-Process -Id $expectedPid -Timeout 15 -ErrorAction SilentlyContinue
                $restartRequested = $true
                $confirmedRestart = $true
                Write-WatchdogLog "validated restart request stopped PID $expectedPid"
            }
            elseif (-not $target) {
                $restartRequested = $true
                $confirmedRestart = $true
                Write-WatchdogLog "restart request target PID $expectedPid was already absent"
            }
            else {
                Write-WatchdogLog "restart request rejected for PID $expectedPid because the command contract did not match"
            }
        }
        catch {
            Write-WatchdogLog "restart request error: $($_.Exception.Message)"
        }
        finally {
            Remove-Item -LiteralPath $restartRequestFile -Force -ErrorAction SilentlyContinue
        }
    }

    if (-not $restartRequested) {
        try {
            Invoke-RestMethod -Uri $opsHealthUrl -TimeoutSec 10 | Out-Null
            Reset-WatchdogFailures 'ops health success'
            exit 0
        }
        catch {
            $opsError = $_.Exception.Message
            $researchStatus = $null
            try {
                $researchStatus = Invoke-RestMethod -Uri $researchHealthUrl -TimeoutSec 10
            }
            catch {
                $researchStatus = $null
            }
            if ($researchStatus -and (Test-ResearchWorkActive $researchStatus)) {
                Register-WatchdogFailure "ops health failed while research is active: $opsError" $researchStatus | Out-Null
                exit 0
            }
            if ($researchStatus -and $researchStatus.contract.schema -eq 'codexstock_external_improvement_contract_v1') {
                $shouldRestart = Register-WatchdogFailure "ops health failed but secondary research health replied: $opsError" $researchStatus
                if (-not $shouldRestart) { exit 0 }
                $confirmedRestart = $true
            }
            else {
                $shouldRestart = Register-WatchdogFailure "ops health failed and secondary health unavailable: $opsError" $null
                if (-not $shouldRestart) { exit 0 }
                $confirmedRestart = $true
            }
        }
    }

    $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq 'python.exe' -and
            $_.CommandLine -match 'stock_suite_app\.py'
        }

    if ($running -and $confirmedRestart) {
        foreach ($process in $running) {
            Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 3
    }

    if ($confirmedRestart -or -not $running) {
        New-Item -ItemType Directory -Force -Path $userData | Out-Null
        $env:CODEXSTOCK_USER_DATA_DIR = $userData
        Start-Process -FilePath $python `
            -ArgumentList @('app\stock_suite_app.py', '--host', '127.0.0.1', '--port', '8765') `
            -WorkingDirectory $root `
            -WindowStyle Hidden
        Reset-WatchdogFailures 'restart launched'
        Write-WatchdogLog 'CodexStock app restart launched after confirmed watchdog failure'
    }
}
catch {
    Write-WatchdogLog "watchdog error: $($_.Exception.Message)"
    exit 1
}
