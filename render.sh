#!/usr/bin/env bash
# render.sh — convierte ESTA copia del template en un proyecto nuevo.
#
# Sustituye el nombre/slug/identificador del proyecto original por los tuyos,
# genera una SECRET_KEY nueva para el backend y verifica que no queden
# marcadores de plantilla.
#
# Uso:  bash render.sh
#
# Antes de usar: copia este proyecto a la carpeta del proyecto nuevo, entra
# en la carpeta y corre el script. GIT: borra .git e inicializa historial propio.
set -euo pipefail

root="$(cd "$(dirname "$0")" && pwd)"
cd "$root"

verify_cmd() {
  command -v "$1" >/dev/null 2>&1
}
for t in sed python3; do verify_cmd "$t" || { echo "necesitas '$t' instalado"; exit 1; }; done

# sed portable: GNU (Linux / Git-Bash de Windows) usa `sed -i`; BSD (macOS) exige `sedi`.
if sed --version >/dev/null 2>&1; then SEDI_I=(-i); else SEDI_I=(-i ''); fi
sedi() { sed "${SEDI_I[@]}" "$@"; }

# ---------------------------------------------------------------- entrada
default_name=$(sed -n 's/^PROJECT_NAME=//p' .env 2>/dev/null || true)
read -rp "Nombre visible del proyecto [${default_name:-TemplatesIA}]: " NAME
NAME="${NAME:-${default_name:-TemplatesIA}}"

default_slug=$(echo "$NAME" | tr '[:upper:] ' '[:lower:]-' | sed 's/[^a-z0-9-]/-/g; s/-\+/-/g; s/^-//; s/-$//')
read -rp "Slug (paquetes, imagen Docker) [$default_slug]: " SLUG
SLUG="${SLUG:-$default_slug}"

read -rp "Identificador de Tauri [com.$SLUG.app]: " IDENT
IDENT="${IDENT:-com.$SLUG.app}"

if [[ ! "$SLUG" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo "ERROR: el slug debe ser minúsculas alfanuméricas con guiones: '$SLUG'"; exit 1
fi

# ------------------------------------------------------- valores actuales
# Se DERIVAN del .env raíz (no hay literales de proyecto en este script,
# así el script sirve en cualquier copia del template).
OLDIDENT=$(sed -n 's/^PROJECT_IDENTIFIER=//p' .env 2>/dev/null || true)
OLDNAME=$(sed -n 's/^PROJECT_NAME=//p' .env 2>/dev/null || true)
OLDSLUG=$(sed -n 's/^PROJECT_SLUG=//p' .env 2>/dev/null || true)

# Marcadores {{...}} compuestos por concatenación para que este archivo no
# dispare el check de marcadores pendiente más abajo.
PH_NAME='{{PROJ''ECT_NAME}}'
PH_SLUG='{{PROJ''ECT_SLUG}}'
PH_IDENT='{{PROJ''ECT_IDENTIFIER}}'
PH_YEAR='{{YE''AR}}'
if [ -z "$OLDNAME" ] && [ -z "$OLDSLUG" ] && [ -z "$OLDIDENT" ]; then
  echo "ERROR: no encontré PROJECT_NAME/PROJECT_SLUG en .env (raíz)."
  echo "Ponlos y vuelve a intentarlo."
  exit 1
fi
echo "Reemplazando: '$OLDNAME' → '$NAME', '$OLDSLUG' → '$SLUG', '$OLDIDENT' → '$IDENT'"
echo ""

# -------------------------------------------------------------- archivos
if [ -d .git ]; then
  # ai-kit/ va intocado: es el paquete pre-trenzado del grafo (lo renueva /ai-bootstrap)
  FILES=$(git ls-files --cached --others --exclude-standard -- ':(exclude)ai-kit')
else
  FILES=$(find . -type f \( \
    -path './.git/*' -o -path './frontend/node_modules/*' -o -path './backend/.venv/*' \
    -o -path './frontend/src-tauri/target/*' -o -path './frontend/src-tauri/gen/*' \
    -o -path './graphify-out/*' -o -path './ai-kit/*' \
    -o -name '*.db' -o -name '*.keystore' \) -prune -o -type f -print | sed 's|^\./||')
fi

count=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  if [ "$f" = "render.sh" ]; then continue; fi   # el script no reescribe sus propios patrones
  if LC_ALL=C sedi \
      -e "s|$OLDIDENT|$IDENT|g" \
      -e "s|$OLDNAME|$NAME|g" \
      -e "s|$OLDSLUG|$SLUG|g" \
      -e "s|$PH_NAME|$NAME|g" \
      -e "s|$PH_SLUG|$SLUG|g" \
      -e "s|$PH_IDENT|$IDENT|g" \
      -e "s|$PH_YEAR|$(date +%Y)|g" "$f"; then
    count=$((count + 1))
  fi
done <<EOF
$FILES
EOF
echo "$count archivos actualizados."

# -------------------------------------------------------- .env raíz nuevo
sedi -e "s|^PROJECT_NAME=.*|PROJECT_NAME=$NAME|" \
          -e "s|^PROJECT_SLUG=.*|PROJECT_SLUG=$SLUG|" \
          -e "s|^PROJECT_IDENTIFIER=.*|PROJECT_IDENTIFIER=$IDENT|" .env
[ -f .env.example ] && sedi \
  -e "s|^PROJECT_NAME=.*|PROJECT_NAME=$NAME|" \
  -e "s|^PROJECT_SLUG=.*|PROJECT_SLUG=$SLUG|" \
  -e "s|^PROJECT_IDENTIFIER=.*|PROJECT_IDENTIFIER=$IDENT|" .env.example || true

# ------------------------------------------------------ SECRET_KEY backend
if [ ! -f backend/.env ]; then
  [ -f backend/.env.example ] && cp backend/.env.example backend/.env
  echo "backend/.env creado desde backend/.env.example — revisa CORS_ORIGINS/SMTP."
fi
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sedi -e "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET|" backend/.env
echo "SECRET_KEY regenerada para backend/.env (única por proyecto)."

# --------------------------------------------------------------- checks
echo ""
leftover=$(git grep -n "{{[A-Z_]*}}" -- . ':!render.sh' ':!ai-kit' 2>/dev/null || find . -type f \( \
    -path './.git/*' -o -path './frontend/node_modules/*' -o -path './backend/.venv/*' \
    -o -path './frontend/src-tauri/target/*' -o -path './frontend/src-tauri/gen/*' \
    -o -path './graphify-out/*' -o -path './ai-kit/*' \) -prune -o -type f ! -name render.sh -exec grep -l "{{[A-Z_]*}}" {} \; 2>/dev/null || true)
if [ -n "$leftover" ]; then
  echo "ADVERTENCIA: quedaron marcadores de plantilla sin reemplazar:"
  echo "$leftover"
  exit 1
fi

old_leftovers=$(git grep -n "$OLDSLUG" -- . ':!ai-kit' 2>/dev/null | grep -v "render.sh" | grep -v graphify-out || true)
if [ -n "$old_leftovers" ]; then
  echo "ADVERTENCIA: quedaron rastros del slug anterior ($OLDSLUG):"
  echo "$old_leftovers"
  exit 1
fi

echo "OK: proyecto '$NAME' ($SLUG) listo."
echo ""
echo "Siguientes pasos recomendados:"
echo "  1. git reset / nueva historia:   rm -rf .git && git init -b main"
echo "  2. Entorno:                      cd backend && uv sync"
echo "                                   cd frontend && pnpm install"
echo "  3. Probar:                       bash run.sh"
echo "  4. Android (si aplica):          cd frontend && pnpm tauri android init"
echo "                                   bash scripts/setup-android-signing.sh"
echo "  5. IA bootstrap (OpenCode):      /ai-bootstrap"
echo "     Restaura el grafo desde ai-kit/ (~0 tokens), conecta el MCP de"
echo "     graphify y ajusta AGENTS.md al proyecto nuevo."
echo "     Extra recomendado: graphify hook install   (los hooks viven en .git/,"
echo "     no vienen en el clon; con ellos el grafo se reconstruye en cada commit)"
echo "  6. Keystore de Android nuevo (no copies el de este template):"
echo "     \"/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/keytool\" \\"
echo "       -genkeypair -v -keystore android.keystore -storepass TU_PASS -keypass TU_PASS \\"
echo "       -alias $SLUG-key -keyalg RSA -keysize 2048 -validity 10000 \\"
echo "       -dname \"CN=$NAME, OU=Mobile, O=$NAME, C=MX\""
echo "     actualiza TAURI_ANDROID_KEYSTORE_PATH/PASSWORD en .env"
