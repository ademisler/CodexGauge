param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $windowsRoot
Set-Location $repoRoot

$releaseRoot = Join-Path $repoRoot "ReleaseArtifacts"
$packageRoot = Join-Path $releaseRoot "windows-package"
$zipPath = Join-Path $releaseRoot "CodexControl-windows.zip"
$hashPath = "$zipPath.sha256"
$buildArgs = @()

if ($Clean) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $hashPath -Force -ErrorAction SilentlyContinue
    $buildArgs += "-Clean"
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $windowsRoot "build.ps1") @buildArgs

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
Remove-Item -LiteralPath $packageRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

Copy-Item (Join-Path $windowsRoot "dist\CodexControl.exe") (Join-Path $packageRoot "CodexControl.exe")
Copy-Item (Join-Path $windowsRoot "install.ps1") (Join-Path $packageRoot "install.ps1")
Copy-Item (Join-Path $windowsRoot "README.md") (Join-Path $packageRoot "README.md")

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 $zipPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath $hashPath -Value "$hash  CodexControl-windows.zip"

Write-Output $zipPath
Write-Output $hashPath
