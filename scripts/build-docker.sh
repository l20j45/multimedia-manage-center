#!/usr/bin/env bash
# build-docker.sh — construye la imagen de la API con datos del .env raíz.
#
#   bash scripts/build-docker.sh              → docker build backend -t <SLUG>-api
#
# Variables del .env raíz:
#   PROJECT_SLUG      nombre de la imagen (<SLUG>-api)
#   CONTAINER_ENGINE  docker | podman  (vacío = autodetección; también vale como
#                     variable de entorno al llamar: CONTAINER_ENGINE=podman bash ...)
#   TARGET_PLATFORM   opcional, ej. linux/arm64 para la Raspberry Pi
#                     (vacío = plataforma nativa de esta máquina)
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [ ! -f .env ]; then
  echo "No existe el .env raíz (copia .env.example → .env)." >&2
  exit 1
fi

# .env raíz
get_env() { sed -n "s/^$1=//p" .env | head -1 | tr -d '[:space:]'; }
SLUG=$(get_env PROJECT_SLUG)
ENGINE=$(get_env CONTAINER_ENGINE)
PLATFORM=$(get_env TARGET_PLATFORM)
: "${SLUG:?PROJECT_SLUG no está definido en el .env raíz}"

# Motor: la variable de entorno/CLI gana sobre el .env, luego autodetección
ENGINE="${CONTAINER_ENGINE:-$ENGINE}"
PLATFORM="${TARGET_PLATFORM:-$PLATFORM}"
if [ -z "$ENGINE" ]; then
  if command -v docker >/dev/null 2>&1; then ENGINE="docker"
  elif command -v podman >/dev/null 2>&1; then ENGINE="podman"
  else echo "Ni docker ni podman encontrados en PATH." >&2; exit 1
  fi
fi

echo "Motor: $ENGINE   Plataforma: ${PLATFORM:-nativa}   Imagen: ${SLUG}-api:latest"

EXTRA_ARGS=()
if [ -n "$PLATFORM" ]; then EXTRA_ARGS+=(--platform "$PLATFORM"); fi

# Modo prueba: imprime lo que correría y sale sin construir
if [ "${1:-}" = "--dry-run" ]; then
  echo "dry-run: $ENGINE build ${PLATFORM:+--platform $PLATFORM} backend -t ${SLUG}-api:latest"
  echo "dry-run: transferencia a la RPi: podman save ${SLUG}-api:latest | gzip > ${SLUG}-api.tar.gz"
  exit 0
fi

if [ "$ENGINE" = "podman" ]; then
  # --format docker: imagen portable con docker{,-compose} load/up en la Pi
  podman build --format docker "${EXTRA_ARGS[@]}" backend -t "${SLUG}-api:latest"
  echo ""
  echo "Imagen en el storage de podman: ${SLUG}-api:latest"
  echo "Para la RPi:  podman save ${SLUG}-api:latest | gzip > ${SLUG}-api.tar.gz"
else
  docker build "${EXTRA_ARGS[@]}" backend -t "${SLUG}-api:latest"
fi

echo ""
echo "Prueba local:   $ENGINE run --rm -p 8000:8000 -e SECRET_KEY=dev ${SLUG}-api:latest"
echo "En la RPi:      docker load ... (ver README, sección 'Deploy en Raspberry Pi')"
