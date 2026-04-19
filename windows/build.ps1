param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $windowsRoot
Set-Location $repoRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$pythonLauncherArgs = @()
if ($pythonCommand) {
    $pythonExecutable = $pythonCommand.Source
} else {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pyCommand) {
        throw "Python was not found on PATH."
    }
    $pythonExecutable = $pyCommand.Source
    $pythonLauncherArgs = @("-3")
}

if ($Clean) {
    Remove-Item -LiteralPath (Join-Path $windowsRoot "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $windowsRoot "dist") -Recurse -Force -ErrorAction SilentlyContinue
}

& $pythonExecutable @pythonLauncherArgs -m pip install -r (Join-Path $windowsRoot "requirements-build.txt")
& $pythonExecutable @pythonLauncherArgs (Join-Path $windowsRoot "tools\generate_app_icon.py")

$distDir = Join-Path $windowsRoot "dist"
$workDir = Join-Path $windowsRoot "build"
$specDir = $windowsRoot
$iconPath = Join-Path $windowsRoot "build-assets\CodexControl.ico"
$entryPath = Join-Path $windowsRoot "CodexControlWindows.pyw"

& $pythonExecutable @pythonLauncherArgs -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name CodexControl `
  --distpath $distDir `
  --workpath $workDir `
  --specpath $specDir `
  --paths $windowsRoot `
  --icon $iconPath `
  --hidden-import pystray._win32 `
  --hidden-import PIL._tkinter_finder `
  $entryPath

Write-Output "Built: $(Join-Path $distDir 'CodexControl.exe')"
