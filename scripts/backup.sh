#!/usr/bin/env bash
# Script de backup de la biblioteca (macOS/Linux).
# Empaqueta backend/uploads + backend/app.db (+ ai-kit opcional con -k flag)
# en backups/ (gitignoreado), o al destino pasado como $1.
#
# Estrategia "staging": copia primero (BD SQLite abierta por el server),
# luego comprime — evita respaldar un fichero a medio escribir.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
stamp="$(date +%Y%m%d-%H%M%S)"
dest="${1:-$root/backups}"
mkdir -p "$dest"

staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT

copied=0
if [ -d "$root/backend/uploads" ]; then
  cp -R "$root/backend/uploads" "$staging/uploads"
  copied=$((copied + 1))
else
  echo "aviso: backend/uploads no existe" >&2
fi
if [ -f "$root/backend/app.db" ]; then
  cp "$root/backend/app.db" "$staging/app.db"
  copied=$((copied + 1))
else
  echo "aviso: backend/app.db no existe" >&2
fi
if [ "$copied" -eq 0 ]; then
  echo "nada que respaldar" >&2
  exit 1
fi

if command -v zip >/dev/null 2>&1; then
  zip_path="$dest/biblioteca-backup-$stamp.zip"
  (cd "$staging" && zip -q -r "$zip_path" .)
else
  zip_path="$dest/biblioteca-backup-$stamp.tar.gz"
  tar -czf "$zip_path" -C "$staging" .
fi

size=$(du -h "$zip_path" | cut -f1 | xargs)
echo "Backup listo: $zip_path ($size)"
echo "Sugerencia cfg cron:  30 23 * * * $root/scripts/backup.sh /ruta/destino"
