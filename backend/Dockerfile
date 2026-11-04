# Backend FastAPI de la app — imagen de producción de la API.
# El nombre de la imagen sale del .env raíz (PROJECT_SLUG), no va hardcodeado.
#
# Construcción:  bash scripts/build-docker.sh   (o docker compose build)
# Ejecución:     docker compose up              (desde la raíz del proyecto)
#
# Nota: la imagen solo incluye la API + SQLite. El frontend Tauri se
# compila por plataforma y no se dockeriza.

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Primero las dependencias (layer cacheable)
COPY pyproject.toml ./
RUN uv sync --no-dev

# Después el código (app + migraciones Alembic)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000

# Al arrancar, app/main.py aplica las migraciones automáticamente.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
