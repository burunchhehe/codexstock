$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Python = if (Test-Path $BundledPython) { $BundledPython } else { "python" }

if (-not $env:CODEXSTOCK_BASE_URL) {
    $env:CODEXSTOCK_BASE_URL = "http://127.0.0.1:8765"
}

& $Python (Join-Path $Root "app\codexstock_mcp_server.py")
