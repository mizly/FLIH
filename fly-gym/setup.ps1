param(
    [switch]$SkipInstall,
    [switch]$CpuOnly
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

    if ($CpuOnly) {
        $torchIndex = "https://download.pytorch.org/whl/cpu"
    } else {
        $torchIndex = "https://download.pytorch.org/whl/cu128"
    }

    # PyTorch publishes CUDA wheels on its own package index. Installing this
    # pair explicitly avoids the CPU-only wheel selected by ordinary PyPI.
    & $python -m pip install --upgrade --force-reinstall `
        torch==2.9.0 torchvision==0.24.0 --index-url $torchIndex
    if ($LASTEXITCODE -ne 0) { throw "PyTorch installation failed." }

    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}

if (-not $CpuOnly) {
    Write-Host "Verifying CUDA-enabled PyTorch..."
    & $python -c "import torch; assert torch.cuda.is_available(), f'CUDA unavailable (torch={torch.__version__}, build CUDA={torch.version.cuda})'; x=torch.ones(256, device='cuda'); print(f'PyTorch {torch.__version__} | CUDA {torch.version.cuda} | {torch.cuda.get_device_name(0)} | tensor sum={x.sum().item():.0f}')"
    if ($LASTEXITCODE -ne 0) {
        throw "CUDA verification failed. Re-run with -CpuOnly only if GPU training is not required."
    }
}

Write-Host "Running simulator smoke test..."
& $python smoke_test.py
Write-Host "fly-gym setup complete. Activate with: .\.venv\Scripts\Activate.ps1"
