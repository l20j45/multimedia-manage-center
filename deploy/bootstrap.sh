#!/usr/bin/env bash
# bootstrap.sh — TODO en la Raspberry, sin PC: imagen de Docker Hub + web del release.
#
#   bash bootstrap.sh                      # en ~/ (crea/usa ~/biblioteca)
#
# Opciones (variables de entorno):
#   DOMAIN=com.tudominio.us   el dominio que apunta a esta Pi (para CORS)
#   IMAGE_TAG=v1.0            versión de la API (default latest)
#   API_PORT=8000             puerto público de la API
#   WEB_TAG=v1.0              release de GitHub del que bajar la web (default el último)
#   SKIP_WEB=1                no bajar la web (dejamos placeholder)
#
# Genera backend.env automáticamente si no existe (SECRET_KEY nueva + CORS del DOMAIN);
# si quieres SMTP u otros, edita backend.env y re-corre `docker compose up -d`.
set -euo pipefail

REPO=l20j45/multimedia-manage-center
DOMAIN="${DOMAIN:-https://assetsmanager.l20j45.us}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
API_PORT="${API_PORT:-4010}"   # API pública (apps/devices)
WEB_PORT="${WEB_PORT:-4011}"   # web (nginx)

cd "$HOME/biblioteca" 2>/dev/null || { mkdir -p "$HOME/biblioteca"; cd "$HOME/biblioteca"; }

# --- backend.env: se auto-genera con SECRET_KEY nueva si no existe ------------
if [ ! -f backend.env ]; then
  SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
  cat > backend.env <<EOF
# Auto-generado por bootstrap.sh — editable en cualquier momento
# (cada cambio requiere:  docker compose up -d  para reiniciar la API).
SECRET_KEY=${SECRET_KEY}

# Origen de tu web + regex para subdominios nuevos del proyecto:
CORS_ORIGINS=${DOMAIN},http://localhost:5173,http://tauri.localhost,https://tauri.localhost
CORS_ORIGIN_REGEX=https://.*\\.$(echo "$DOMAIN" | sed 's|^https://||; s|/.*||' | awk -F. '{print $(NF-1)"."$NF}')

# SMTP opcional (recuperación por correo); sin esto los códigos van al log:
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=465
# SMTP_USER=
# SMTP_PASSWORD=
EOF
  chmod 600 backend.env
  echo "→ backend.env GENERADO (SECRET_KEY nueva incluida). Dónde editarlo: $PWD/backend.env"
fi

# --- docker-compose.yml + nginx.conf regenerables ------------------------------
cat > docker-compose.yml <<EOF
services:
  api:
    image: l20j45/biblioteca-recursos-multimedia-api:${IMAGE_TAG}
    ports:
      - "${API_PORT}:8000"       # API pública para apps/dispositivos
    env_file: [backend.env]
    environment:
      DATABASE_URL: sqlite:////app/data/app.db
      MEDIA_DIR: /app/data/uploads
    volumes:
      - api-data:/app/data
    restart: unless-stopped

  web:
    image: nginx:1.27-alpine
    ports:
      - "${WEB_PORT}:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./www:/usr/share/nginx/html:ro
    depends_on: [api]
    restart: unless-stopped

volumes:
  api-data:
EOF

cat > nginx.conf <<EOF
# TLS lo termina Cloudflare (o el proxy que uses): aquí llega HTTP (el 80 se
# mapea a ${WEB_PORT} en el host). El proxy interno hacia la API NO cambia.
server {
	listen 80;
	server_name _;
	root /usr/share/nginx/html;
	index index.html;
	client_max_body_size 0;
	location /assets/ { expires 1y; add_header Cache-Control "public, immutable"; try_files \$uri =404; }
	location ~ ^/(health|health/|auth|users|media|collections|settings) {
		proxy_pass http://api:8000;
		proxy_set_header Host \$host;
		proxy_set_header X-Real-IP \$remote_addr;
		proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto https;
	}
	location / { try_files \$uri /index.html; }
}
EOF

# --- web: baja la SPA precompilada del release de GitHub -------------------------
if [ "${SKIP_WEB:-0}" != "1" ] && command -v curl >/dev/null; then
  TAG="${WEB_TAG:-}"
  [ -z "$TAG" ] && TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
      | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)
  DESCARGADA=0
  if [ -n "$TAG" ]; then
    echo "→ Bajando web precompilada del release ${TAG} ..."
    # 1) intento directo del browser_download_url…
    # 2) fallback por asset-id vía API (GitHub suele tardar en propagar la URL)
    curl -fL -o web-dist.tar.gz \
      "https://github.com/${REPO}/releases/download/${TAG}/web-dist.tar.gz" 2>/dev/null && DESCARGADA=1
    if [ "$DESCARGADA" != 1 ] && command -v awk >/dev/null; then
      ASSET_ID=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/tags/${TAG}" \
        | awk 'BEGIN{q=0; id=""} /"assets":/{q=1} q&&/"id":/{gsub(/[^0-9]/,"",$2); id=$2} /"name": *"web-dist.tar.gz"/{print id; exit}')
      [ -n "$ASSET_ID" ] && curl -fL -o web-dist.tar.gz \
        -H "Accept: application/octet-stream" \
        "https://api.github.com/repos/${REPO}/releases/assets/${ASSET_ID}" && DESCARGADA=1
    fi
  fi
  if [ "$DESCARGADA" = 1 ]; then
    rm -rf www && mkdir -p www && tar xzf web-dist.tar.gz -C www && rm web-dist.tar.gz
  else
    echo "⚠️  No pude bajar web-dist.tar.gz (¿release sin él?). Pongo placeholder por ahora."
  fi
fi
mkdir -p www
[ -f www/index.html ] || echo '<!doctype html><meta charset=utf-8><title>Biblioteca</title><p>Web por desplegar (corre de nuevo bootstrap.sh cuando exista un release).</p>' > www/index.html

# --- subir -----------------------------------------------------------------------
docker compose pull
docker compose up -d --remove-orphans
docker compose ps
echo ""
echo "✓ API arriba en :${API_PORT}  |  web en :${WEB_PORT}  |  datos en el volumen api-data"
echo "  Verifica:  curl http://localhost:${API_PORT}/health"
echo "  Todo editable en $PWD (backend.env / docker-compose.yml / nginx.conf)."
echo "  Puedes BORRAR este script: nada de lo que corre depende de él."
