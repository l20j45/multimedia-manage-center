# Migraciones y backups de la base de datos

Esta app usa **SQLite** (`backend/app.db` por defecto, configurable con
`DATABASE_URL` en `backend/.env`) con migraciones **Alembic** que se aplican
solas en cada arranque (`uv run uvicorn app.main:app --reload` → `run_migrations()`).

## Roles e infraestructura de acceso que viven en la BD

A partir de la migración `0009` la base de datos NO es solo multimedia: guarda
el control de acceso de toda la instalación.

| Tabla / columna | Qué es |
|---|---|
| `users.is_admin` | Super admin: **el primer usuario registrado** queda como admin; en BDs previas la migración promovió al usuario más antiguo (`MIN(id)`) |
| `app_settings` (`registration_open`) | Toggle del registro (cerrado = la instancia queda "solo por invitación") |
| `teams` / `team_members` | Equipos para compartir recursos |
| `media_items.team_id` | Compartir un recurso a UN equipo concreto (NULL + `visibility='team'` = todos los equipos del dueño) |

> **Consecuencia**: borrar `app.db` sin backup borrar admins, equipos y el
> estado del registro — no solo los recursos (los ficheros están en `MEDIA_DIR/`).

## Migraciones: manualmente

```bash
cd backend
uv run alembic upgrade head        # aplicar pendientes (también al arrancar uvicorn)
uv run alembic revision --autogenerate -m "..."   # nueva tras tocar app/models.py
uv run alembic downgrade -1        # solo en dev; con datos reales, evita downgrades
```

Verificación rápida de consistencia tras un upgrade (SQLite):

```bash
uv run sqlite3 app.db "SELECT id, email, is_admin FROM users ORDER BY id LIMIT 5;"
uv run sqlite3 app.db "PRAGMA integrity_check;"
```

Espera la salida `ok`.

## Backups (recomendado: diario + antes de cada deploy)

SQLite se puede copiar "en caliente" porque la API hace checkpoint del WAL,
pero lo limpio es usar el comando de backup:

```bash
cd backend
uv run sqlite3 app.db ".backup 'backups/app-$(date +%Y%m%d).db'"   # Linux/macOS
# Windows (PowerShell):
#   uv run python -c "import sqlite3; src=sqlite3.connect('app.db'); dst=sqlite3.connect(r'..\backups\app-%Y%m%d.db'); src.backup(dst)"
```

Sugerencia de rotación: conservar ~14 diarios + 4 semanales. Ejemplo con cron
(o Programador de tareas de Windows):

```cron
0 3 * * * cd /ruta/backend && uv run sqlite3 app.db ".backup 'backups/app-$(date +\%Y\%m\%d).db'"
```

Y **prueba el restore al menos una vez**: reemplaza `app.db` por el backup con
el backend parado y arranca; `uv run pytest` NO debe tocar tu app.db (los
tests usan una BD temporal aparte).
