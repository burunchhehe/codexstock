param(
    [switch]$NoOpen
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
function Resolve-CodexStockPython {
    $candidates = @(
        @(
            (Join-Path $Root ".venv\Scripts\python.exe"),
            $env:CODEXSTOCK_PYTHON,
            (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    )
    if ($candidates.Count -eq 0) { throw "Python을 찾을 수 없습니다. .venv를 만들거나 CODEXSTOCK_PYTHON을 지정하세요." }
    return $candidates[0]
}
$Python = Resolve-CodexStockPython
$DefaultUserDataDir = Join-Path $env:LOCALAPPDATA "CodexStock\data"
if ([string]::IsNullOrWhiteSpace($env:CODEXSTOCK_USER_DATA_DIR)) {
    $env:CODEXSTOCK_USER_DATA_DIR = $DefaultUserDataDir
}
New-Item -ItemType Directory -Force -Path $env:CODEXSTOCK_USER_DATA_DIR | Out-Null
Set-Location -LiteralPath $Root
$ArgsList = @("app\stock_suite_app.py", "--host", "127.0.0.1", "--port", "8765")
if (-not $NoOpen) {
    $ArgsList += "--open"
}
& $Python @ArgsList
