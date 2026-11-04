#!/usr/bin/env bash
# run.sh — Arranca backend y frontend juntos (macOS / Linux)
# Uso: bash run.sh     (Ctrl+C detiene ambos)

set -e
root="$(cd "$(dirname "$0")" && pwd)"

# Bootstrap: dependencias e íconos si faltan (evita fallos tardíos de compilación)
if [ ! -d "$root/frontend/node_modules" ]; then
  echo "Instalando dependencias del frontend (pnpm)..."
  (cd "$root/frontend" && pnpm install)
fi
if [ ! -f "$root/frontend/src-tauri/icons/32x32.png" ]; then
  echo "Generando íconos de Tauri (placeholder app-icon.png)..."
  (cd "$root/frontend" && pnpm tauri icon src-tauri/app-icon.png)
fi

# Backend en segundo plano
pushd "$root/backend" >/dev/null
uv run uvicorn app.main:app --reload &
BACK_PID=$!
popd >/dev/null
trap 'kill $BACK_PID 2>/dev/null' EXIT

echo ""
echo "API:  http://localhost:8000/docs"
echo "App:  la ventana de Tauri se abre sola al compilar"
echo "Ctrl+C para detener ambos."
echo ""

# Frontend en primer plano (compila Rust la primera vez)
cd "$root/frontend"
pnpm run tauri dev
