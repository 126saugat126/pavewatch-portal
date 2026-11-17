# Start the backend (port 8000) and the frontend dev server (port 5173) in two windows.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
# Add -Seed to also (re)load the synthetic demo data once the backend is up.
param([switch]$Seed)
$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\backend'; `$host.UI.RawUI.WindowTitle='PaveWatch backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\frontend'; `$host.UI.RawUI.WindowTitle='PaveWatch frontend'; npm run dev"

if ($Seed) {
  Write-Host 'Waiting for the backend...'
  for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-RestMethod http://127.0.0.1:8000/api/health | Out-Null; break } catch { Start-Sleep -Milliseconds 500 }
  }
  & "$root\backend\.venv\Scripts\python.exe" "$root\tools\synthetic\generate.py"
}

Write-Host 'Portal:   http://localhost:5173' -ForegroundColor Green
Write-Host 'API docs: http://localhost:8000/docs' -ForegroundColor Green
