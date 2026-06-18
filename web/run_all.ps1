<#
.SYNOPSIS
   Starts the Somali NLP FastAPI backend and Vite frontend for local development.
#>

$ErrorActionPreference = "Stop"

$WebRoot = Resolve-Path $PSScriptRoot
$BackendDir = Join-Path $WebRoot "backend"
$FrontendDir = Join-Path $WebRoot "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$NpmExe = "npm.cmd"

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Cyan
    python -m venv $VenvDir
}

Write-Host "Installing backend requirements..." -ForegroundColor Cyan
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")

Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
Push-Location $FrontendDir
& $NpmExe install
Pop-Location

Write-Host "Starting FastAPI backend on http://127.0.0.1:8001" -ForegroundColor Cyan
$backendCommand = "& '$PythonExe' -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload"
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo", "-NoExit", "-Command", $backendCommand) -WorkingDirectory $WebRoot

Write-Host "Starting Vite frontend on http://localhost:5173" -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo", "-NoExit", "-Command", "$NpmExe run dev") -WorkingDirectory $FrontendDir

Write-Host ""
Write-Host "Backend docs: http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "Frontend UI : http://localhost:5173" -ForegroundColor Green
