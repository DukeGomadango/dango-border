$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing/updating dependencies..."
& $venvPython -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org

Write-Host "Starting API at http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
& $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
