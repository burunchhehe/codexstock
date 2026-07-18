param(
    [string]$TunnelId = "",
    [switch]$UpdateProfileOnly,
    [switch]$NoAppStart
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TunnelClient = Join-Path $Root "tools\tunnel-client\tunnel-client.exe"
$ProfileName = "codexstock-local-stdio"
$ProfilePath = Join-Path $env:APPDATA "tunnel-client\$ProfileName.yaml"
$CodexStockHealthUrl = "http://127.0.0.1:8765/api/ops/status/poll"
$SecretDir = "C:\codexstock-mcp\secrets"
$AppStartScript = Join-Path $Root "run_app.ps1"

function Load-SecretValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    $path = Join-Path $SecretDir "$Name.dpapi"
    if (-not (Test-Path -LiteralPath $path)) {
        return $null
    }

    try {
        $cipher = (Get-Content -LiteralPath $path -Raw).Trim()
        $secure = $cipher | ConvertTo-SecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    } catch {
        Write-Host "Saved CodexStock tunnel key could not be read: $path" -ForegroundColor Yellow
        Write-Host "Run codexstock-save to refresh the stored key." -ForegroundColor Yellow
        return $null
    }
}

if (-not (Test-Path $TunnelClient)) {
    throw "tunnel-client.exe not found: $TunnelClient"
}
if (-not (Test-Path $ProfilePath)) {
    throw "tunnel profile not found: $ProfilePath"
}

if ($TunnelId) {
    if ($TunnelId -notmatch '^tunnel_[A-Za-z0-9]+$') {
        throw "Invalid tunnel id. Expected a value like tunnel_abc123..."
    }
    $profileText = Get-Content -LiteralPath $ProfilePath -Raw
    $updatedProfileText = $profileText -replace 'tunnel_id:\s*"tunnel_[^"]+"', "tunnel_id: `"$TunnelId`""
    if ($updatedProfileText -eq $profileText -and $profileText -notmatch [regex]::Escape($TunnelId)) {
        throw "Could not update tunnel_id in profile: $ProfilePath"
    }
    Set-Content -LiteralPath $ProfilePath -Value $updatedProfileText -Encoding UTF8
    Write-Host "Updated tunnel profile to $TunnelId" -ForegroundColor Green
}

$CurrentTunnelId = Select-String -LiteralPath $ProfilePath -Pattern 'tunnel_id:\s*"([^"]+)"' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
Write-Host "Using tunnel id: $CurrentTunnelId" -ForegroundColor Cyan

if ($UpdateProfileOnly) {
    Write-Host "Profile update only. Start again without -UpdateProfileOnly when ready to run the tunnel." -ForegroundColor Yellow
    return
}

Write-Host ""
Write-Host "CodexStock MCP tunnel starter" -ForegroundColor Cyan
Write-Host "Saved keys are read from Windows DPAPI if available. Otherwise the key is kept only in this PowerShell process." -ForegroundColor DarkGray
Write-Host ""

try {
    Invoke-RestMethod -Uri $CodexStockHealthUrl -TimeoutSec 3 | Out-Null
    Write-Host "CodexStock local app is reachable at http://127.0.0.1:8765" -ForegroundColor Green
} catch {
    if (-not $NoAppStart -and (Test-Path -LiteralPath $AppStartScript)) {
        Write-Host "CodexStock local app is not responding. Starting it now..." -ForegroundColor Yellow
        Start-Process powershell.exe -WorkingDirectory $Root -WindowStyle Hidden -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $AppStartScript,
            "-NoOpen"
        )
        Start-Sleep -Seconds 5
        try {
            Invoke-RestMethod -Uri $CodexStockHealthUrl -TimeoutSec 10 | Out-Null
            Write-Host "CodexStock local app is now reachable at http://127.0.0.1:8765" -ForegroundColor Green
        } catch {
            Write-Host "CodexStock app was started, but is still warming up." -ForegroundColor Yellow
            Write-Host "Continuing anyway. If connector creation fails, wait 20 seconds and run codexstock again." -ForegroundColor Yellow
        }
    } else {
        Write-Host "CodexStock local app is not responding yet. Start run_app.ps1 first." -ForegroundColor Yellow
        Write-Host "Continuing anyway, but ChatGPT connector creation may fail until the app is reachable." -ForegroundColor Yellow
    }
}

if (-not $env:CONTROL_PLANE_API_KEY) {
    $env:CONTROL_PLANE_API_KEY = Load-SecretValue -Name "CONTROL_PLANE_API_KEY"
}

if (-not $env:CONTROL_PLANE_API_KEY) {
    Write-Host "No saved tunnel key found. Run codexstock-save once to avoid typing it every time." -ForegroundColor Yellow
    $secureKey = Read-Host "Paste OpenAI Runtime/API key for the tunnel (hidden)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
} else {
    Write-Host "Loaded saved OpenAI tunnel key from Windows DPAPI." -ForegroundColor Green
}

Write-Host ""
Write-Host "Running tunnel doctor..." -ForegroundColor Cyan
& $TunnelClient doctor --profile $ProfileName --explain

Write-Host ""
Write-Host "Starting tunnel. Keep this PowerShell window open while using ChatGPT." -ForegroundColor Cyan
Write-Host "After it says ready/connected, go back to ChatGPT and create the connector." -ForegroundColor Cyan
Write-Host "Log file: C:\codexstock-mcp\tunnel-client.log" -ForegroundColor DarkGray
Write-Host ""
& $TunnelClient run --profile $ProfileName

$exitCode = $LASTEXITCODE
Write-Host ""
Write-Host "Tunnel client stopped. Exit code: $exitCode" -ForegroundColor Red
Write-Host "Do not create the ChatGPT connector while this window has returned to the PowerShell prompt." -ForegroundColor Yellow
Write-Host "If it stopped, send the last lines of C:\codexstock-mcp\tunnel-client.log." -ForegroundColor Yellow
Read-Host "Press Enter to close"
