# Script de backup de la biblioteca (Windows).
# Empaqueta: backend/uploads (ficheros de usuarios), backend/app.db (BD) y
# opcionalmente ai-kit/ (grafo). Suelta el zip en backups/ (gitignoreado).
#
# Estrategia "staging": primero COPIA los ficheros (la BD de SQLite está
# abierta por el server y no se puede comprimir en vivo), luego comprime.
#
# Usar:            powershell -File scripts/backup.ps1
# Destino propio:  powershell -File scripts/backup.ps1 -Dest D:\Backups
param(
    [string]$Dest = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $Dest) { $Dest = Join-Path $root "backups" }
$staging = Join-Path ([IO.Path]::GetTempPath()) "biblioteca-backup-$stamp"
New-Item -ItemType Directory -Force -Path $Dest, $staging | Out-Null

$copied = 0
$uploads = Join-Path $root "backend\uploads"
if (Test-Path $uploads) {
    Copy-Item $uploads -Destination (Join-Path $staging "uploads") -Recurse -Force
    $copied += (Get-ChildItem (Join-Path $staging "uploads") -Recurse -File | Measure-Object).Count
} else {
    Write-Warning "backend/uploads no existe (sin ficheros de usuarios)"
}
$db = Join-Path $root "backend\app.db"
if (Test-Path $db) {
    Copy-Item $db -Destination (Join-Path $staging "app.db") -Force
    $copied += 1
} else {
    Write-Warning "backend/app.db no existe (¿aún no arrancó el backend?)"
}
if ($copied -eq 0) { Write-Error "Nada que respaldar."; exit 1 }

$zip = Join-Path $Dest "biblioteca-backup-$stamp.zip"
Compress-Archive -Path "$staging\*" -DestinationPath $zip -Force
Remove-Item $staging -Recurse -Force

$size = "{0:N1} MB" -f ((Get-Item $zip).Length / 1MB)
Write-Output ""
Write-Output "Backup listo: $zip ($size) · $copied elemento(s)"
Write-Output ""
Write-Output "Sugerencia: programa una tarea diaria:"
Write-Output '  schtasks /Create /SC DAILY /TN "BibliotecaBackup" /TR "powershell -File C:\ruta\a\scripts\backup.ps1 -Dest D:\Backups" /ST 23:30'
