#!/usr/bin/env bash
# bootstrap.sh — arranque SOLO con Docker Hub, sin repo ni build en la Pi.
#
# Corre DENTRO de la Pi:
#   bash bootstrap.sh            # en ~/ (crea ~/biblioteca)
#
# Trae:
#   • l20j45/biblioteca-recursos-multimedia-api (Docker Hub)
#   • nginx sirviendo la API (placeholder; la web llega luego con deploy.sh)
#   • docker-compose.yml + nginx.conf generados aquí
#
# Requiere UN solo archivo tuyo al lado: backend.env (SECRET_KEY/CORS/SMTP).
set -euo pipefail

cd "${HOME}/biblioteca" 2>/dev/null || mkdir -p "${HOME}/biblioteca" && cd "${HOME}/biblioteca"

IMAGE_TAG="${IMAGE_TAG:-latest}"
API_PORT="${API_PORT:-8000}"

if [ ! -f backend.env ]; then
  cat >&2 <<EOF
✗ Necesito backend.env en $(pwd) (SECRET_KEY, CORS_ORIGINS, CORS_ORIGIN_REGEX).
  Rellenalo aquí mismo con tu editor, ejemplos en el repo deploy/backend.env.example.
EOF
  exit 1
fi

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
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./www:/usr/share/nginx/html:ro
    depends_on: [api]
    restart: unless-stopped

volumes:
  api-data:
EOF

cat > nginx.conf <<'EOF'
server {
	listen 80;
	server_name _;
	root /usr/share/nginx/html;
	index index.html;
	client_max_body_size 0;
	location /assets/ { expires 1y; add_header Cache-Control "public, immutable"; try_files $uri =404; }
	location ~ ^/(health|health/|auth|users|media|collections|settings) {
		proxy_pass http://api:8000;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto https;
	}
	location / { try_files $uri /index.html; }
}
EOF

mkdir -p www
[ -f www/index.html ] || echo '<!doctype html><meta charset=utf-8><title>Biblioteca</title><p>Web por desplegar: corre deploy.sh desde tu PC (build + rsync de www/).</p>' > www/index.html

docker compose pull
docker compose up -d --remove-orphans
docker compose ps
echo ""
echo "✓ API arriba (API pública :${API_PORT}). Verifica: curl http://localhost:${API_PORT}/health"
echo "  La web en :80 viene cuando corras deploy.sh desde tu PC (rsync de www/)."
echo "  Este script y docker-compose.yml son CHATARRA desechable: puedes borrar"
echo "  ~/biblioteca y no pierdes datos — la BD/uploads viven en el volumen api-data."
