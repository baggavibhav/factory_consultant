<#
.SYNOPSIS
  One-time setup for the Factory Consultant Agent on Windows.
.DESCRIPTION
  Creates .venv with Python 3.12, installs the project and dev tools,
  downloads the LibreDWG converter into tools\libredwg, and runs the tests.
  Run from the project root:
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$LibreDwgVersion = "0.13.3"
$LibreDwgUrl = "https://github.com/LibreDWG/libredwg/releases/download/$LibreDwgVersion/libredwg-$LibreDwgVersion-win64.zip"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step "Checking Python 3.12"
try { $pyVersion = & py -3.12 --version } catch { $pyVersion = $null }
if (-not $pyVersion) {
    throw "Python 3.12 not found. Install it with: winget install -e --id Python.Python.3.12  (then reopen the terminal)"
}
Write-Host $pyVersion

Step "Creating virtual environment (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & py -3.12 -m venv .venv }
$Py = Join-Path $Root ".venv\Scripts\python.exe"

Step "Installing project and dev tools"
& $Py -m pip install --upgrade pip --quiet
& $Py -m pip install -e ".[dev]" --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Step "Installing LibreDWG $LibreDwgVersion (DWG to DXF converter)"
$ToolDir = Join-Path $Root "tools\libredwg"
if (-not (Test-Path (Join-Path $ToolDir "dwg2dxf.exe"))) {
    New-Item -ItemType Directory -Force -Path $ToolDir | Out-Null
    $Zip = Join-Path $env:TEMP "libredwg-$LibreDwgVersion-win64.zip"
    Invoke-WebRequest -Uri $LibreDwgUrl -OutFile $Zip
    Expand-Archive -Path $Zip -DestinationPath $ToolDir -Force
    Remove-Item $Zip
    # Some archives nest files in a subfolder; move dwg2dxf.exe and its DLLs up if so.
    $exe = Get-ChildItem -Path $ToolDir -Recurse -Filter "dwg2dxf.exe" | Select-Object -First 1
    if ($exe -and $exe.DirectoryName -ne $ToolDir) {
        Get-ChildItem -Path $exe.DirectoryName -File | Move-Item -Destination $ToolDir -Force
    }
}
if (-not (Test-Path (Join-Path $ToolDir "dwg2dxf.exe"))) { throw "dwg2dxf.exe not found after download" }
Write-Host "dwg2dxf.exe ready in tools\libredwg"

Step "Creating .env from template (if missing)"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Step "Creating data folders"
New-Item -ItemType Directory -Force -Path "data\reference", "data\work", "outputs" | Out-Null

Step "Running tests"
& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed. Send the output above to continue." }

Write-Host "`nSetup complete. In VS Code: Ctrl+Shift+P > Python: Select Interpreter > .venv\Scripts\python.exe" -ForegroundColor Green
