#!/usr/bin/env bash
# deploy.sh — despacha web + API-container-config a la Pi (o cualquier host).
#
#   bash deploy/deploy.sh pi@raspberrypi.local       # completo (build web incl.)
#   SKIP_BUILD=1 bash deploy/deploy.sh pi@host       # sin recompilar la web
#
# Qué hace:
#   1. Compila la SPA con VITE_API_URL del .env raíz → deploy/www/
#   2. rsync de deploy/ (compose, Caddyfile, www/, backend.env) a DEST:~/biblioteca
#   3. docker compose pull + up -d en el host
#
# Requisitos: ssh accesible, rsync, y docker+compose-plugin en el destino.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

DEST="${1:?Uso: bash deploy/deploy.sh usuario@host   (ej. pi@raspberrypi.local)}"
SITE_URL=$(sed -n 's/^VITE_API_URL=//p' .env 2>/dev/null | head -1 | tr -d '[:space:]')

# --- 0. backend.env presente (nadie despacha secretos automáticos) -----------
if [ ! -f deploy/backend.env ]; then
  echo "✗ Falta deploy/backend.env. Copia y rellena el ejemplo primero:" >&2
  echo "    cp deploy/backend.env.example deploy/backend.env" >&2
  exit 1
fi

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  if [ ! -f .env ]; then echo "✗ Falta el .env raíz (VITE_API_URL)." >&2; exit 1; fi
  echo "→ Compilando la SPA (frontend)..."
  (cd frontend && pnpm install --frozen-lockfile --silent && pnpm run build)
  rm -rf deploy/www && mkdir -p deploy/www && cp -R frontend/dist/. deploy/www/
fi
[ -d deploy/www ] || { echo "✗ deploy/www/ no existe (corre sin SKIP_BUILD la primera vez)." >&2; exit 1; }

# --- 1. sincronizar ----------------------------------------------------------
echo "→ Sincronizando a $DEST:~/biblioteca ..."
ssh "$DEST" "mkdir -p ~/biblioteca"
rsync -av --delete deploy/Caddyfile deploy/docker-compose.yml deploy/www \
  "$DEST:~/biblioteca/"
rsync -av deploy/backend.env "$DEST:~/biblioteca/backend.env"

# --- 2. levantar -------------------------------------------------------------
echo "→ docker compose pull + up -d ..."
ssh "$DEST" "cd ~/biblioteca && docker compose pull && docker compose up -d --remove-orphans"

echo ""
echo "✓ Despachado. Verifica:"
echo "    ssh $DEST 'docker compose -f ~/biblioteca/docker-compose.yml ps'"
[ -n "${SITE_URL:-}" ] && echo "    curl $SITE_URL/health"
