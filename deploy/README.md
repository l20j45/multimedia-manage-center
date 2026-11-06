# deploy/ — despliegue completo self-hosted (Pi o cualquier Linux arm64/amd64)

API + **página web en el mismo dominio**, con HTTPS automático de Caddy:

```
                    ┌───────────── Pi ─────────────┐
browser/app ──443──▶│ Caddy                        │
                    │  ├─ www/        (la SPA)     │
                    │  └─ /auth /media … ──▶ api   │
                    │                 Docker Hub   │
                    └──────────────────────────────┘
```

## Puesta en marcha (una vez)

```bash
# 1. DNS: apunta el A/AAAA registro de tu dominio a la IP de la Pi.

# 2. Configura los secretos:
cp deploy/backend.env.example deploy/backend.env
$EDITOR deploy/backend.env          # SECRET_KEY (openssl rand -base64 48) + CORS

# 3. Edita deploy/Caddyfile si tu dominio no es assetsmanager.l20j45.us.

# 4. Despacha (compila la web, sincroniza y levanta):
bash deploy/deploy.sh pi@raspberrypi.local
```

## Qué despliega

| Pieza                       | Cómo                                |
|-----------------------------|-------------------------------------|
| API (FastAPI + SQLite)      | imagen `l20j45/biblioteca-recursos-multimedia-api` (tag configurable via `IMAGE_TAG`) |
| Página web                  | `deploy/www/` compilado con Vite (`VITE_API_URL` del .env raíz) |
| HTTPS                       | Caddy, certificados de Let's Encrypt automáticos |
| Datos (BD + uploads)        | volumen `api-data` (sobrevive recreaciones) |

## Día a día

```bash
bash deploy/deploy.sh pi@raspberrypi.local      # cambios de la web
SKIP_BUILD=1 bash deploy/deploy.sh pi@host      # solo tocar configs/Caddyfile
docker image pull … && IMAGE_TAG=nuevo bash …   # actualizar API (ver docs, menos scripts)
```

Los logs: `ssh pi@raspberrypi 'docker logs -f biblioteca-caddy-1'`.

⚠️ La imagen `latest` la publica el CI con cada tag `v*`; fija `IMAGE_TAG=v0.10`
en tu `.env` de deploy si no quieres que `latest` cambie por debajo de ti.
