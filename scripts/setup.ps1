# One-time setup: Python virtual environment + backend packages, frontend packages.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Write-Host '== Backend (Python)' -ForegroundColor Cyan
Push-Location "$root\backend"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location

Write-Host '== Frontend (Node)' -ForegroundColor Cyan
Push-Location "$root\frontend"
npm install
Pop-Location

Write-Host ''
Write-Host 'Done. Start the app with:  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1' -ForegroundColor Green
