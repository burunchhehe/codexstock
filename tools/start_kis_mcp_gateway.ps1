param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$engineRoot = Join-Path $env:LOCALAPPDATA "CodexStock\engines\kis_trading_mcp"
$secretFile = Join-Path $env:LOCALAPPDATA "CodexStock\secrets\kis_mcp.env"
$containerName = "codexstock-kis-trading-mcp"
$docker = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"

if (-not (Test-Path -LiteralPath $docker -PathType Leaf)) {
    throw "Docker Desktop is not installed."
}
& $docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is not ready. Enable WSL2, restart Windows if required, and start Docker Desktop."
}
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    throw "KIS MCP paper credential file is missing. Run tools/configure_kis_mcp_paper.py first."
}

$source = Get-ChildItem -LiteralPath $engineRoot -Directory |
    Sort-Object LastWriteTime -Descending |
    ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Directory -Filter "open-trading-api-*" } |
    Select-Object -First 1
if (-not $source) {
    throw "Official KIS Open Trading API source is not installed."
}
$mcpRoot = Join-Path $source.FullName "MCP\Kis Trading MCP"
if (-not (Test-Path -LiteralPath (Join-Path $mcpRoot "Dockerfile") -PathType Leaf)) {
    throw "Official KIS Trading MCP Dockerfile was not found."
}

$commit = $source.Name -replace '^open-trading-api-', ''
$image = "codexstock/kis-trading-mcp:$($commit.Substring(0, [Math]::Min(12, $commit.Length)))"
$imageExists = & $docker image inspect $image --format "{{.Id}}" 2>$null
if ($Build -or -not $imageExists) {
    & $docker build --pull --tag $image $mcpRoot
    if ($LASTEXITCODE -ne 0) { throw "KIS Trading MCP image build failed." }
}

$existing = & $docker container inspect $containerName --format "{{.State.Running}}" 2>$null
if ($LASTEXITCODE -eq 0 -and $existing -eq "true") {
    Write-Output "container=$containerName status=running endpoint=http://127.0.0.1:3000/sse mode=paper"
    exit 0
}
if ($LASTEXITCODE -eq 0) {
    & $docker container rm $containerName | Out-Null
}

& $docker run --detach `
    --name $containerName `
    --restart unless-stopped `
    --env-file $secretFile `
    --publish "127.0.0.1:3000:3000" `
    --memory "2g" `
    --cpus "2" `
    --security-opt "no-new-privileges:true" `
    --cap-drop ALL `
    $image | Out-Null
if ($LASTEXITCODE -ne 0) { throw "KIS Trading MCP container start failed." }

Write-Output "container=$containerName status=started endpoint=http://127.0.0.1:3000/sse mode=paper"
