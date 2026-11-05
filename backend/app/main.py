"""Punto de entrada de la API FastAPI."""

from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alembic import command
from app.config import settings
from app.rate_limit import RateLimitMiddleware
from app.routers import auth, collections, health, media, users
from app.routers.settings import router as settings_router

BASE_DIR = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    """Aplica las migraciones de Alembic pendientes en cada arranque."""
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "alembic"))
    command.upgrade(config, "head")


run_migrations()

# Papelera: purga lo que lleva más de TRASH_RETENTION_DAYS borrado (silencioso).
from app.services.media import backfill_hashes, purge_expired_trash  # noqa: E402

try:
    purged = purge_expired_trash()
    if purged:
        print(f"papelera: purgados {purged} recurso(s) expirados")
except Exception:  # noqa: BLE001 - nunca bloquea el arranque
    pass

# Duplicados: legacy sin sha256/phash quedaban invisibles; se recalculan al vuelo.
try:
    filled = backfill_hashes()
    if filled:
        print(f"duplicados: rescatados hashes de {filled} recurso(s)")
except Exception:  # noqa: BLE001 - nunca bloquea el arranque
    pass

app = FastAPI(title=settings.PROJECT_NAME)

# Rate limiting ANTES de CORS: así el middleware de CORS (añadido después)
# queda lo más externo y añade headers a las respuestas 429 también.
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(media.router)
app.include_router(collections.router)
app.include_router(settings_router)
