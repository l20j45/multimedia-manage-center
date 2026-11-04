"""Router /settings: configuración editable DESDE LA APP (sin tocar .env).

Hoy: GEMINI_API_KEY para el auto-tag. La llave vive en la tabla app_settings
(persiste con la BD); si no está ahí, cae a backend/.env. La UI nunca la
muestra completa, solo si está configurada y su cola (4 chars).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import AppSetting, User

router = APIRouter(prefix="/settings", tags=["settings"])

GEMINI_KEY_SETTING = "gemini_api_key"


class GeminiKeyIn(BaseModel):
    value: str


@router.get("/gemini-key")
def get_gemini_key_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Estado de la llave: si está configurada y su cola (la UI no la lee)."""
    row = db.get(AppSetting, GEMINI_KEY_SETTING)
    if row and row.value:
        return {"set": True, "tail": f"…{row.value[-4:]}", "source": "app"}
    if settings.GEMINI_API_KEY:
        return {"set": True, "tail": f"…{settings.GEMINI_API_KEY[-4:]}", "source": "env"}
    return {"set": False, "tail": "", "source": "none"}


@router.put("/gemini-key")
def set_gemini_key(
    data: GeminiKeyIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Guarda (o borra con string vacío) la llave en la BD."""
    value = data.value.strip()
    row = db.get(AppSetting, GEMINI_KEY_SETTING)
    if not value:
        if row:
            db.delete(row)
            db.commit()
        return {"set": False, "tail": "", "source": "none"}
    if len(value) < 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Llave demasiado corta")
    if not row:
        row = AppSetting(key=GEMINI_KEY_SETTING)
    row.value = value
    db.add(row)
    db.commit()
    return {"set": True, "tail": f"…{value[-4:]}", "source": "app"}


def get_gemini_api_key(db: Session) -> str:
    """Llave EFECTIVA: app_settings > .env (usada por services/autotag)."""
    row = db.get(AppSetting, GEMINI_KEY_SETTING)
    if row and row.value:
        return row.value
    return settings.GEMINI_API_KEY
