param(
    [switch]$NoOpen
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$DefaultUserDataDir = Join-Path $env:LOCALAPPDATA "CodexStock\data"
if ([string]::IsNullOrWhiteSpace($env:CODEXSTOCK_USER_DATA_DIR)) {
    $env:CODEXSTOCK_USER_DATA_DIR = $DefaultUserDataDir
}
New-Item -ItemType Directory -Force -Path $env:CODEXSTOCK_USER_DATA_DIR | Out-Null
Set-Location -LiteralPath $Root
$ArgsList = @("app\stock_suite_app.py", "--host", "127.0.0.1", "--port", "8765")
$SidecarArgs = @("app\execution_sidecar_service.py", "--mode", "shadow", "--interval", "1")
Start-Process -FilePath $Python -ArgumentList $SidecarArgs -WorkingDirectory $Root -WindowStyle Hidden
if (-not $NoOpen) {
    $ArgsList += "--open"
}
& $Python @ArgsList
