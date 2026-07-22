param(
    [ValidateRange(1, 30)]
    [int]$PairingMinutes = 10
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$apkPath = Join-Path $repoRoot "dist\CodexStock-Mobile-debug.apk"
$pairingCli = Join-Path $repoRoot "app\mobile_pairing_cli.py"
$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$python = if (Test-Path -LiteralPath $bundledPython) {
    $bundledPython
} else {
    (Get-Command python -ErrorAction Stop).Source
}

Write-Host ""
Write-Host "코덱스스톡 휴대폰 연결 준비" -ForegroundColor Cyan
Write-Host "-----------------------------"

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/mobile/health" -TimeoutSec 5
    if (-not $health.ok) {
        throw "모바일 API가 정상 응답하지 않았습니다."
    }
    Write-Host "[정상] PC 본체와 모바일 API가 실행 중입니다." -ForegroundColor Green
} catch {
    Write-Host "[확인 필요] 코덱스스톡을 먼저 실행해 주세요." -ForegroundColor Yellow
    throw
}

if (Test-Path -LiteralPath $apkPath) {
    Write-Host "[정상] APK: $apkPath" -ForegroundColor Green
} else {
    Write-Host "[확인 필요] APK가 없습니다. .\mobile\build_android.ps1을 먼저 실행하세요." -ForegroundColor Yellow
}

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if ($tailscale) {
    Write-Host "[정상] Tailscale 명령을 찾았습니다: $($tailscale.Source)" -ForegroundColor Green
    Write-Host "        휴대폰과 PC를 같은 개인 Tailscale 네트워크에 연결하세요."
} else {
    Write-Host "[확인 필요] 외부에서 접속하려면 PC와 휴대폰에 Tailscale을 설치하세요." -ForegroundColor Yellow
}

Write-Host ""
Push-Location $repoRoot
try {
    & $python $pairingCli create --minutes $PairingMinutes
    if ($LASTEXITCODE -ne 0) {
        throw "연결 코드 생성에 실패했습니다."
    }
} finally {
    Pop-Location
}

Write-Host "휴대폰 앱 설정에 PC의 Tailscale HTTPS 주소와 위 코드를 입력하세요."
Write-Host "이 코드는 한 번만 사용할 수 있으며 $PairingMinutes분 뒤 만료됩니다."
