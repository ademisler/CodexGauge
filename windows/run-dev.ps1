$ErrorActionPreference = "Stop"

$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $windowsRoot
$venvPythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$entryPoint = Join-Path $windowsRoot "CodexControlWindows.pyw"

if (Test-Path -LiteralPath $venvPythonw) {
    $runtime = $venvPythonw
} elseif (Test-Path -LiteralPath $venvPython) {
    $runtime = $venvPython
} else {
    throw "Virtual environment not found under $repoRoot\\.venv\\Scripts"
}

Remove-Item Env:TCL_LIBRARY -ErrorAction SilentlyContinue
Remove-Item Env:TK_LIBRARY -ErrorAction SilentlyContinue
$env:PYTHONPATH = $windowsRoot

& $runtime $entryPoint
