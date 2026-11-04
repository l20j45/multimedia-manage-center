# AGENTS.md — Biblioteca de Recursos Multimedia

Instrucciones para agentes IA (OpenCode u otros) que trabajen en este repo.
Deriva del scaffold **FastAPI + Tauri**; si algo de abajo no matchea el código
real, el código manda.

## Qué es

- **Backend** (`backend/`): FastAPI + SQLite, Python 3.14+, gestionado con **uv**.
  Auth JWT + bcrypt, recuperación de contraseña por código de 6 dígitos,
  correos SMTP opcional, rate limiting por IP, migraciones **Alembic** (se
  aplican solas al arrancar).
- **Frontend** (`frontend/`): Tauri 2 + React + Vite (escritorio Windows/macOS/
  Linux + APK Android). UI de login/registro/recuperación; íconos multiplataforma.
- **Deploy**: `docker-compose.yml` (API + BD persistente), imagen
  `biblioteca-recursos-multimedia-api`, puerto `${API_PORT}`.
- **IA/KM**: grafo de conocimiento del código en `graphify-out/` (gitignoreado),
  servido vía MCP de **graphify** (ver sección Graphify).

## Estructura (canonical del template)

```
backend/
  app/
    main.py        # entrypoint: aplica migraciones + monta routers
    config.py      # settings desde backend/.env
    database.py    # conexión SQLite
    models.py      # modelos (User)
    schemas.py     # Pydantic
    security.py    # bcrypt + JWT
    deps.py        # session BD + usuario actual
    rate_limit.py  # rate limiting por IP
    routers/       # health, auth, users
    services/      # email (SMTP o console)
  alembic/         # migraciones; versions/ 0001, 0002…
  tests/           # pytest (smoke + rate limit)
  pyproject.toml   # FUENTE DE VERDAD de dependencias + config ruff/pytest
frontend/
  src/             # React (pages/Login+Home, lib/api.ts, LoginPage.test.tsx)
  src-tauri/       # shell Rust; icons/, capabilities/, tauri.conf.json (CSP)
docker-compose.yml
run.ps1 / run.sh   # levanta backend + frontend (Windows / macOS-Linux)
render.sh          # convierte la copia en un proyecto nuevo (pedir nombre/slug)
graphify-out/      # grafo Graphify (no committear, gitignoreado)
```

## Comandos

Backend (desde `backend/`; usar `uv`, NO pip directo):

```bash
uv sync                                 # .venv + dependencias
uv run uvicorn app.main:app --reload    # API en http://localhost:8000
uv run pytest                           # tests (smoke + rate limit)
uv run ruff check . --fix               # lint
uv run ruff format .                    # formato
uv run alembic revision --autogenerate -m "descripcion"
uv run alembic upgrade head             # (al reiniciar uvicorn aplican solas)
```

Frontend (desde `frontend/`; usar `pnpm`, NO npm):

```bash
pnpm install
pnpm run tauri dev                        # ventana nativa (1ª build Rust ~min)
pnpm test                                 # vitest
pnpm run tauri build                      # instaladores (msi/dmg/deb…)
pnpm tauri android build --apk            # APK (firma: scripts/setup-android-signing.sh)
pnpm run tauri icon ruta/logo-1024.png    # regenera todos los íconos
```

Deploy:

```bash
bash scripts/build-docker.sh    # nombre de imagen del .env raíz; --dry-run para probar
docker compose up               # desde la raíz
```

## Reglas del proyecto

1. **uv es la fuente de verdad** de dependencias (backend/pyproject.toml).
   requirements.txt es solo respaldo. Agregar deps con `uv add`.
2. **Cambias un modelo en `app/models.py`** → genera la migración Alembic
   correspondiente en el mismo commit.
3. **No toques los límites de rate limiting** sin discutirlos: login 10/min,
   register y forgot-password 5/min (config por `backend/.env`, vars `RATE_LIMIT_*`).
4. **CORS**: `CORS_ORIGINS` (backend/.env) debe contener los orígenes en uso.
   Mantén coherente con `VITE_API_URL` del `.env` raíz.
5. **Secrets**: `.env` gitignoreado (raíz y backend). Cada proyecto derivado
   debe tener SU `SECRET_KEY` — nunca reciclar keystores de Android del template.
6. **Ruff tapa el estilo** — no es asunto de debate: `ruff format .` manda.
7. Tests: pytest en `backend/tests/`, vitest en `frontend/src/*.test.tsx`.
   Todo cambio de comportamiento lleva su test.
8. `frontend/src-tauri/gen/` y `target/` no están en git: se regeneran local
   (`pnpm tauri android init`, re-build).
9. Commits: imperativos, separa cambios de backend y frontend si son temas distintos.

## Graphify (grafo de conocimiento + MCP)

- El grafo vive en `graphify-out/` (output gitignoreado):
  - `graph.html` — grafo interactivo, ábrelo en navegador.
  - `GRAPH_REPORT.md` — reporte de auditoría/comunidades/god nodes.
  - `graph.json` — datos crudos del grafo.
- **El repo trae `ai-kit/` commiteado** (grafo + caché de extracción pre-trenzados,
  <1 MB): al bajar el repo, correr el skill `ai-bootstrap` restaura el estado y
  re-extracta SOLO lo que cambió — **casi 0 tokens LLM**. Tras cambios grandes,
  regenera el kit (`95_build_kit.py`) y committea `ai-kit/`.
- **MCP ya configurado** en `opencode.json` de la raíz: servidor local
  `graphify.serve` sobre graph.json (tools: `query_graph`, `get_node`,
  `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`,
  `shortest_path`; en OpenCode Code Mode: `tools.graphify.<tool>(...)`).
- Preguntas de arquitectura: consulta el grafo ANTES de grep/leer archivos
  (`graphify query "<pregunta>"` o el MCP): ahorra búsquedas y da contexto
  estructural que text-search no ve.
- Tras cambios grandes de código: `graphify --update` (solo re-extrae nuevos/
  cambiados). **Recomendado en cada clon nuevo** (los hooks viven en `.git/hooks/`
  y NO viajan con el repo): `graphify hook install` — reconstruye el grafo
  automáticamente en cada `git commit`, re-extractando solo lo cambiado (0 LLM).
- Al renderizar un proyecto NUEVO (render.sh): correr el skill `ai-bootstrap`
  en la raíz para regenerar grafo, MCP y este AGENTS.md.

## Entorno

- Windows dev: `powershell -File run.ps1`. macOS/Linux: `bash run.sh`.
- Docs API: http://localhost:8000/docs en modo dev.
- Python: usar siempre el venv (`uv run ...`), nunca instalar global.
- Docker en Raspberry Pi 64 bits: `TARGET_PLATFORM=linux/arm64` (ver README).
