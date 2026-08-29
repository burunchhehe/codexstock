$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonCandidates = @(
    @((Join-Path $Root ".venv\Scripts\python.exe"), $env:CODEXSTOCK_PYTHON, (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")) |
        Where-Object { $_ -and (Test-Path -LiteralPath $_) }
)
if ($PythonCandidates.Count -eq 0) { throw "Python을 찾을 수 없습니다. 먼저 scripts\setup_dev.ps1을 실행하세요." }
$Python = $PythonCandidates[0]
& $Python (Join-Path $Root "scripts\paper_mode_smoke.py")
