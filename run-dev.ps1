# run-dev.ps1 — start backend + frontend for local development.
#
# Backend (FastAPI) launches in a new PowerShell window on port 8000.
# Frontend (Streamlit) runs in the current window on port 8501.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$venv = Join-Path $root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venv)) {
    Write-Host "Warning: .venv not found at $venv — using system Python." -ForegroundColor Yellow
}

# Start backend in a separate window so its logs are visible.
$backendCmd = @"
Set-Location '$root'
if (Test-Path '$venv') { & '$venv' }
Write-Host '=== Backend: uvicorn backend.api:app on :8000 ===' -ForegroundColor Cyan
uvicorn backend.api:app --port 8000 --reload
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "Waiting 3s for backend to bind..." -ForegroundColor DarkGray
Start-Sleep -Seconds 3

# Frontend in this window.
Set-Location (Join-Path $root "im-agentic-os")
if (Test-Path $venv) { & $venv }
Write-Host "=== Frontend: streamlit on :8501 ===" -ForegroundColor Cyan
streamlit run app.py
