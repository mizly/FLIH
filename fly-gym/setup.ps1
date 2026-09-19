param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating local Python environment..."
    python -m venv .venv
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not $SkipInstall) {
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
}

Write-Host "Running simulator smoke test..."
& $python smoke_test.py
Write-Host "fly-gym setup complete. Activate with: .\.venv\Scripts\Activate.ps1"
