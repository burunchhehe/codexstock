$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "CodexStock MCP tunnel status" -ForegroundColor Cyan

$processes = Get-Process | Where-Object { $_.ProcessName -like "*tunnel-client*" }
if ($processes) {
    Write-Host "1. tunnel-client process: RUNNING" -ForegroundColor Green
    $processes | Select-Object Id, ProcessName, StartTime, Path | Format-Table -AutoSize
} else {
    Write-Host "1. tunnel-client process: NOT RUNNING" -ForegroundColor Red
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8080/healthz" -TimeoutSec 2
    Write-Host "2. tunnel healthz: OK" -ForegroundColor Green
    $health | ConvertTo-Json -Depth 8
} catch {
    Write-Host "2. tunnel healthz: NOT READY - $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $ready = Invoke-RestMethod -Uri "http://127.0.0.1:8080/readyz" -TimeoutSec 2
    Write-Host "3. tunnel readyz: OK" -ForegroundColor Green
    $ready | ConvertTo-Json -Depth 8
} catch {
    Write-Host "3. tunnel readyz: NOT READY - $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $app = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/ops/status/poll" -TimeoutSec 3
    Write-Host "4. CodexStock app: OK" -ForegroundColor Green
    $app | Select-Object ok, mode, generated_at | ConvertTo-Json -Compress
} catch {
    Write-Host "4. CodexStock app: NOT READY - $($_.Exception.Message)" -ForegroundColor Red
}

$logPath = "C:\codexstock-mcp\tunnel-client.log"
if (Test-Path $logPath) {
    Write-Host ""
    Write-Host "Recent tunnel log:" -ForegroundColor Cyan
    Get-Content $logPath -Tail 30
} else {
    Write-Host ""
    Write-Host "No tunnel log file yet: $logPath" -ForegroundColor Yellow
}
