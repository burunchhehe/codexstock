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
$healthUrl = 'http://127.0.0.1:8765/api/external-engines/improvement-loop/status?lesson_limit=1&task_limit=1'
$logFile = Join-Path $root 'runtime\codexstock_watchdog.log'
$restartRequestFile = Join-Path $root 'runtime\codexstock_restart_request.json'

function Write-WatchdogLog([string]$message) {
    $line = '{0} | {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
}

try {
    $restartRequested = $false
    if (Test-Path -LiteralPath $restartRequestFile) {
        try {
            $request = Get-Content -LiteralPath $restartRequestFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $expectedPid = [int]$request.expected_pid
            $target = Get-CimInstance Win32_Process -Filter "ProcessId=$expectedPid" -ErrorAction SilentlyContinue
            $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
                Select-Object -First 1
            $codexStatus = $null
            try {
                $codexStatus = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10
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
                Write-WatchdogLog "validated restart request stopped PID $expectedPid"
            }
            elseif (-not $target) {
                $restartRequested = $true
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
        Invoke-RestMethod -Uri $healthUrl -TimeoutSec 10 | Out-Null
            exit 0
        }
        catch {
            # Continue to process inspection and restart.
        }
    }

    $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq 'python.exe' -and
            $_.CommandLine -match 'stock_suite_app\.py'
        }

    if (-not $running) {
        New-Item -ItemType Directory -Force -Path $userData | Out-Null
        $env:CODEXSTOCK_USER_DATA_DIR = $userData
        Start-Process -FilePath $python `
            -ArgumentList @('app\stock_suite_app.py', '--host', '127.0.0.1', '--port', '8765') `
            -WorkingDirectory $root `
            -WindowStyle Hidden
        Write-WatchdogLog 'CodexStock app was not running; restart requested'
    }
}
catch {
    Write-WatchdogLog "watchdog error: $($_.Exception.Message)"
    exit 1
}
