param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) { & py -3.11 -m venv (Join-Path $Root ".venv") }
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e "${Root}[storage,reports,realtime]" pytest
& $VenvPython -m compileall -q (Join-Path $Root "app") (Join-Path $Root "packages") (Join-Path $Root "examples")
if (-not $SkipTests) { & $VenvPython -m pytest -q }
