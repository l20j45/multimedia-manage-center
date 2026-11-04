# Arranca backend y frontend, cada uno en su terminal
# Uso:  powershell -File run.ps1     (o doble clic)

$root = $PSScriptRoot

Write-Host "Abriendo dos terminales..." -ForegroundColor Cyan

# 1) Backend (FastAPI con uv)
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", "Set-Location '$root\backend'; uv run uvicorn app.main:app --reload"

# 2) Frontend (Tauri)
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", "Set-Location '$root\frontend'; pnpm run tauri dev"

Write-Host ""
Write-Host "API:  http://localhost:8000/docs  (docs interactiva)" -ForegroundColor Green
Write-Host "App:  la ventana de Tauri se abre sola al terminar de compilar" -ForegroundColor Green
Write-Host "Para detener: cierra las dos terminales abiertas."
