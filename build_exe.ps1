$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Root "launcher\StockSuiteHTS.cs"
$Output = Join-Path $Root "StockSuiteHTS.exe"
$Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not (Test-Path -LiteralPath $Csc)) {
    throw "C# 컴파일러를 찾을 수 없습니다: $Csc"
}

& $Csc /nologo /target:winexe /platform:anycpu /out:$Output /reference:System.Windows.Forms.dll /reference:System.Drawing.dll $Source

Write-Host "완료: $Output"
