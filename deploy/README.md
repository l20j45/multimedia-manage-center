# deploy/ — despliegue self-hosted con Cloudflare (TLS fuera de la Pi)

```
                 Cloudflare (TLS, CDN, tu dominio)
                          │ HTTPS
                          ▼ 80 (proxy naranja)
┌───────────── Pi ────────────────────────────────┐
│ web   nginx:  página (www/) + proxea la API     │
│ api   FastAPI (imagen de Docker Hub)  + volumen │
└─────────────────────────────────────────────────┘
```

Nada de certificados en la Pi: **Cloudflare termina TLS** y al origen le llega
HTTP por el 80 (modo SSL *Full* en el panel de Cloudflare).

## Puesta en marcha (una vez)

```bash
# 1. DNS en Cloudflare: registro A/AAAA de tu dominio → IP de la Pi (proxy ON).

# 2. Secretos:
cp deploy/backend.env.example deploy/backend.env
$EDITOR deploy/backend.env          # SECRET_KEY (openssl rand -base64 48) + CORS

# 3. Dominio (si no es assetsmanager.l20j45.us):
#    - deploy/backend.env → CORS_ORIGINS
#    - el .env RAÍZ → VITE_API_URL (con el que se compila la web)

# 4. Despacha (compila la web, sincroniza y levanta):
bash deploy/deploy.sh pi@raspberrypi.local
```

## Qué queda corriendo en la Pi

| Contenedor | Qué hace |
|---|---|
| `web` (nginx) | sirve `deploy/www/` (la SPA) y proxea `/auth /media /users /collections /settings /health` → `api:8000` |
| `api` (Docker Hub) | FastAPI + SQLite + ffmpeg/Pillow; migraciones al arrancar; **puerto público `API_PORT`** (default 8000) |

Los datos (BD `app.db` + `uploads/`) viven en el volumen **`api-data`**:
sobreviven recreaciones de contenedores.

## API pública para la sincronización multi-dispositivo

La API escucha directo en `${API_PORT}` (default **8000**) — para las
instancias locales del proyecto y otras páginas que quieran los endpoints
sin pasar por nginx:

- **Local/LAN**: `http://<ip-de-la-pi>:8000` (basta con abrir ese puerto en
  la LAN; sin internet).
- **Internet**: recomendado **Cloudflare Tunnel** (`cloudflared`) — versión
  cero-abrir-puertos de tu router; o abre 8000 y, si va a andar público,
  mantén TLS adelante (via Cloudflare, proxy A/AAAA del subdominio, etc).
- **CORS**: cada página/dispositivo extra debe estar listado en
  `CORS_ORIGINS` de `backend.env`; el token JWT hace la parte de seguridad
  de identidad y los rate limits del template frenan el brute force.

## Dos formas de publicar la página

**A) La Pi sirve la web (por defecto aquí).** `deploy.sh` compila `dist/`,
lo deja en `deploy/www/` y nginx lo sirve en tu dominio. Cambios de web =
re-correr `deploy.sh`.

**B) "Compilado para subirlo" a otro lado.** La web es estática: cualquier
hosting de ficheros sirve:

```bash
cd frontend && pnpm run build        # → frontend/dist/  (usa VITE_API_URL del .env raíz)
# sube frontend/dist/ a Cloudflare Pages, S3, FTP, lo que sea…
```

Con B, apunta `VITE_API_URL` (o el selector "cambiar servidor" del login) a tu
API y agrega ese dominio a `CORS_ORIGINS` en `backend.env`.

## Cloudflare: 3 ajustes recomendados

1. **SSL/TLS mode → Full** (el origen es HTTP; *Full (strict)* fallaría).
2. **Uploads grandes**: el plan free corta el body en 100 MB — para videos
   grandes sube por LAN (o *bypass* del proxy para `/media` con una regla).
3. **CORS**: todo sale del mismo dominio (`/` web y API), así que no hay
   problema de CORS del navegador; solo importa para la app de escritorio/APK
   (por eso `tauri.localhost` en `CORS_ORIGINS`).

## Día a día

```bash
bash deploy/deploy.sh pi@raspberrypi.local       # cambios de la web
SKIP_BUILD=1 bash deploy/deploy.sh pi@host       # solo configs (nginx.conf, backend.env)
ssh pi@raspberrypi 'docker logs -f deploy-web-1' # logs
```

⚠️ `latest` en Docker Hub la publica el CI con cada tag `v*`; fija `IMAGE_TAG`
en el `.env` de deploy si no quieres que la versión cambie sola bajo ti.
