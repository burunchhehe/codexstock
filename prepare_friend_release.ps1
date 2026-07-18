param(
    [string]$OutputDir = "dist\CodexStock-Friend"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
$DistRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "dist"))
$Target = [System.IO.Path]::GetFullPath((Join-Path $Root $OutputDir))

if (-not $Target.StartsWith($DistRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "안전 중단: 배포 대상은 반드시 dist 폴더 안이어야 합니다. 대상=$Target"
}

$excludeDirs = @(
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "artifacts",
    "runtime",
    "data",
    "reports"
)

$excludeFiles = @(
    ".env",
    ".env.local",
    ".env.*.local",
    "*.env.local",
    "*.log",
    "lean-request-debug.json",
    "kis_token_*.json",
    "telegram_offset.json",
    "*credential*.json",
    "*secret*.json",
    "live_order_submits.jsonl",
    "live_position_decisions.jsonl",
    "telegram_outbox.jsonl",
    "telegram_dispatch.jsonl"
)

if (Test-Path -LiteralPath $Target) {
    $ResolvedTarget = (Resolve-Path -LiteralPath $Target).Path
    if (-not $ResolvedTarget.StartsWith($DistRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "안전 중단: 기존 대상 폴더가 dist 밖에 있습니다. 대상=$ResolvedTarget"
    }
    Remove-Item -LiteralPath $ResolvedTarget -Recurse -Force
}

New-Item -ItemType Directory -Path $Target | Out-Null

$robocopyArgs = @(
    $Root,
    $Target,
    "/E",
    "/XD"
) + $excludeDirs + @(
    "/XF"
) + $excludeFiles + @(
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NC",
    "/NS",
    "/NP"
)

robocopy @robocopyArgs | Out-Null
$code = $LASTEXITCODE
if ($code -gt 7) {
    throw "친구용 배포 폴더 생성 실패: robocopy exit code $code"
}

Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination (Join-Path $Target ".env.example") -Force

$safeRuntimeDirs = @("data", "reports")
foreach ($dir in $safeRuntimeDirs) {
    $runtimeDir = Join-Path $Target $dir
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $runtimeDir "README.txt") -Encoding UTF8 -Value @(
        "이 폴더는 친구 PC에서 프로그램 실행 중 새로 생성되는 로컬 데이터 공간입니다.",
        "원본 사용자의 API 키, 계좌 기록, 텔레그램 기록, 학습 기록은 배포본에 포함하지 않습니다."
    )
}

Write-Host "친구용 배포 폴더 생성 완료: $Target"
Write-Host "전달 전 확인: .env, .env.local, KIS 토큰, 실거래 로그, 텔레그램 기록, 원본 data 기록이 포함되면 안 됩니다."
