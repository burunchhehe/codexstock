[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [ValidateRange(1, 3600)]
    [int]$IntervalSeconds = 60,
    [ValidatePattern('^http://127\.0\.0\.1(?::\d+)?$')]
    [string]$BaseUrl = 'http://127.0.0.1:8765'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$servicePath = Join-Path $repoRoot 'app\internal_developer_service.py'
$contractPath = Join-Path $repoRoot 'runtime\codexstock_runtime_root.json'
$profileRoot = [Environment]::GetFolderPath('UserProfile')

if (-not (Test-Path -LiteralPath $servicePath -PathType Leaf)) {
    throw "Internal-developer service is missing: $servicePath"
}

function Get-ApprovedPythonCandidates {
    return @(
        (Join-Path $repoRoot '.venv\Scripts\python.exe'),
        (Join-Path $profileRoot '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    )
}

function Test-ApprovedPython([string]$CandidatePath) {
    if ([string]::IsNullOrWhiteSpace($CandidatePath)) { return $false }
    if (-not (Test-Path -LiteralPath $CandidatePath -PathType Leaf)) { return $false }
    $leaf = [System.IO.Path]::GetFileName($CandidatePath).ToLowerInvariant()
    if (@('python.exe', 'python', 'python3') -notcontains $leaf) { return $false }
    $candidateFullPath = [System.IO.Path]::GetFullPath($CandidatePath)
    $approved = Get-ApprovedPythonCandidates | Where-Object {
        [System.IO.Path]::GetFullPath([string]$_) -ieq $candidateFullPath
    }
    if ($null -eq $approved) { return $false }
    try {
        $env:CODEXSTOCK_LAUNCHER_REPO_ROOT = $repoRoot
        $probe = & $CandidatePath -c "import json,os,sys; root=os.environ['CODEXSTOCK_LAUNCHER_REPO_ROOT']; sys.path.insert(0,root); import app.internal_developer_service; print(json.dumps({'ok': True, 'major': sys.version_info.major, 'minor': sys.version_info.minor}))" 2>$null
        $exitCode = $LASTEXITCODE
        Remove-Item Env:CODEXSTOCK_LAUNCHER_REPO_ROOT -ErrorAction SilentlyContinue
        if ($exitCode -ne 0) { return $false }
        $result = $probe | Select-Object -Last 1 | ConvertFrom-Json
        return ($result.ok -eq $true -and [int]$result.major -eq 3 -and [int]$result.minor -ge 10)
    }
    catch {
        Remove-Item Env:CODEXSTOCK_LAUNCHER_REPO_ROOT -ErrorAction SilentlyContinue
        return $false
    }
}

function Get-VerifiedRuntimeContract {
    if (-not (Test-Path -LiteralPath $contractPath -PathType Leaf)) { return $null }
    try {
        $raw = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $candidatePython = [string]$raw.python_executable
        if (-not (Test-ApprovedPython $candidatePython)) { return $null }
        $env:CODEXSTOCK_LAUNCHER_REPO_ROOT = $repoRoot
        $verifiedText = & $candidatePython -c "import json,os,sys; root=os.environ['CODEXSTOCK_LAUNCHER_REPO_ROOT']; sys.path.insert(0,root); from app.runtime_paths import read_runtime_root_contract; print(json.dumps(read_runtime_root_contract(root)))" 2>$null
        $exitCode = $LASTEXITCODE
        Remove-Item Env:CODEXSTOCK_LAUNCHER_REPO_ROOT -ErrorAction SilentlyContinue
        if ($exitCode -ne 0) { return $null }
        $verified = $verifiedText | Select-Object -Last 1 | ConvertFrom-Json
        if ($verified.valid -ne $true) { return $null }
        if ([string]$verified.python_executable -ne $candidatePython) { return $null }
        return $verified
    }
    catch {
        Remove-Item Env:CODEXSTOCK_LAUNCHER_REPO_ROOT -ErrorAction SilentlyContinue
        return $null
    }
}

$contract = Get-VerifiedRuntimeContract
$python = $null
$userDataRoot = $null
$resolutionSource = $null

if ($null -ne $contract) {
    $python = [string]$contract.python_executable
    $userDataRoot = [string]$contract.user_data_root
    $resolutionSource = 'verified_runtime_root_contract'
}
else {
    $candidatePaths = Get-ApprovedPythonCandidates
    foreach ($candidatePath in $candidatePaths) {
        if (Test-ApprovedPython $candidatePath) {
            $python = $candidatePath
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($python)) {
        throw 'No approved Python runtime could import the internal-developer service.'
    }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'LOCALAPPDATA is unavailable and no verified runtime-root contract exists.'
    }
    $userDataRoot = Join-Path $env:LOCALAPPDATA 'CodexStock\data'
    $resolutionSource = 'current_user_approved_runtime'
}

$internalDeveloperRoot = Join-Path $userDataRoot 'internal_developer'
$logPath = Join-Path $internalDeveloperRoot 'scheduler.log'

function Rotate-SchedulerLogIfNeeded {
    if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) { return }
    $file = Get-Item -LiteralPath $logPath
    if ($file.Length -lt 5MB) { return }
    $archivePath = Join-Path $internalDeveloperRoot 'scheduler.previous.log'
    if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
        [System.IO.File]::Delete($archivePath)
    }
    [System.IO.File]::Move($logPath, $archivePath)
}

function Write-SchedulerLog([string]$Message) {
    $safe = ([string]$Message).Replace("`r", ' ').Replace("`n", ' ')
    if ($safe.Length -gt 2000) { $safe = $safe.Substring(0, 2000) + '...[truncated]' }
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value ('{0:o} | {1}' -f (Get-Date), $safe)
}

if ($ValidateOnly) {
    [pscustomobject]@{
        ok = $true
        repo_root = $repoRoot
        python_executable = $python
        user_data_root = $userDataRoot
        log_path = $logPath
        resolution_source = $resolutionSource
        execution_performed = $false
    } | ConvertTo-Json -Compress
    exit 0
}

New-Item -ItemType Directory -Path $internalDeveloperRoot -Force | Out-Null
Rotate-SchedulerLogIfNeeded
$env:CODEXSTOCK_USER_DATA_DIR = $userDataRoot
$startedAt = Get-Date
Write-SchedulerLog ('scheduler cycle started | source={0}' -f $resolutionSource)

Push-Location -LiteralPath $repoRoot
try {
    $output = & $python '-m' 'app.internal_developer_service' 'once' '--base-url' $BaseUrl '--interval' ([string]$IntervalSeconds) 2>&1
    $serviceExitCode = $LASTEXITCODE
    foreach ($line in @($output)) {
        try {
            $payload = ([string]$line) | ConvertFrom-Json
            Write-SchedulerLog (
                'service | status={0} classification={1} incident={2} restart={3} cycle={4}' -f
                [string]$payload.status,
                [string]$payload.classification,
                [string]$payload.incident_id,
                [bool]$payload.restart_requested,
                [string]$payload.heartbeat.cycle_count
            )
        }
        catch {
            Write-SchedulerLog ('service | {0}' -f [string]$line)
        }
    }
    Write-SchedulerLog ('scheduler cycle finished | exit={0}' -f $serviceExitCode)
    exit $serviceExitCode
}
catch {
    $safeError = $_.Exception.Message.Replace("`r", ' ').Replace("`n", ' ')
    Write-SchedulerLog ('launcher error | {0}' -f $safeError)
    exit 1
}
finally {
    Pop-Location
}
