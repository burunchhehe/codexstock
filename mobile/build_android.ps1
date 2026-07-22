param(
    [ValidateSet("debug", "release")]
    [string]$Variant = "debug"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Join-Path $PSScriptRoot "codexstock-android"
$toolchainRoot = Join-Path $env:LOCALAPPDATA "CodexStock\toolchains"
$jdkRoot = Get-ChildItem -LiteralPath (Join-Path $toolchainRoot "jdk-21") -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1
$sdkRoot = Join-Path $toolchainRoot "android-sdk"

if (-not $jdkRoot -or -not (Test-Path -LiteralPath (Join-Path $jdkRoot.FullName "bin\java.exe"))) {
    throw "CodexStock JDK 21 was not found under $toolchainRoot."
}
if (-not (Test-Path -LiteralPath (Join-Path $sdkRoot "platforms\android-36\android.jar"))) {
    throw "Android SDK 36 was not found under $sdkRoot."
}

$env:JAVA_HOME = $jdkRoot.FullName
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:Path"

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath "node_modules")) {
        npm ci
    }
    npx cap sync android

    Push-Location "android"
    try {
        $task = if ($Variant -eq "release") { "assembleRelease" } else { "assembleDebug" }
        & ".\gradlew.bat" --no-daemon $task
        if ($LASTEXITCODE -ne 0) {
            throw "Gradle $task failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    $sourceApk = Join-Path $projectRoot "android\app\build\outputs\apk\$Variant\app-$Variant.apk"
    if (-not (Test-Path -LiteralPath $sourceApk)) {
        throw "APK output was not found: $sourceApk"
    }

    $dist = Join-Path $repoRoot "dist"
    New-Item -ItemType Directory -Path $dist -Force | Out-Null
    $destination = Join-Path $dist "CodexStock-Mobile-$Variant.apk"
    Copy-Item -LiteralPath $sourceApk -Destination $destination -Force
    Write-Host "APK ready: $destination"
}
finally {
    Pop-Location
}
