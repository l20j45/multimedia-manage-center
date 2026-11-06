"""Router /admin: gestión de la instalación (solo super admin).

- Ver usuarios registrados (conteo + activos) y sus roles.
- Activar/desactivar cuentas y promover/retirar admins.
- Cerrar/abrir el REGISTRO de cuentas nuevas (el primer usuario puede
  cerrarlo para convertir la instancia en "solo por invitación").

El cierre del registro vive en app_settings (persistente con la BD). Si la
BD aún no tiene usuarios, el registro sigue abierto: alguien tiene que
crear LA primera cuenta (que será el admin).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_admin
from app.models import AppSetting, User

router = APIRouter(prefix="/admin", tags=["admin"])

REGISTRATION_SETTING = "registration_open"
_OPEN = "1"


def registration_is_open(db: Session) -> bool:
    """Toggle del registro: abierto por defecto; '0' = cerrado por el admin."""
    row = db.get(AppSetting, REGISTRATION_SETTING)
    if row is None:
        return True
    return row.value == _OPEN


def registration_is_open_effective(db: Session) -> bool:
    """Versión operativa: una instalación SIN usuarios siempre acepta el
    registro (nadie podría crear la cuenta del primer admin)."""
    if db.query(User).count() == 0:
        return True
    return registration_is_open(db)


@router.get("/overview")
def admin_overview(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> schemas.AdminOverview:
    """Vista de usuarios: total, activos, roles y estado del registro."""
    users = db.query(User).order_by(User.id).all()
    return schemas.AdminOverview(
        users=[schemas.AdminUserOut.model_validate(u) for u in users],
        total=len(users),
        active_count=sum(1 for u in users if u.is_active),
        registration_open=registration_is_open(db),
    )


@router.patch("/users/{user_id}", response_model=schemas.AdminUserOut)
def admin_patch_user(
    user_id: int,
    data: schemas.AdminUserPatch,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> User:
    """Activa/desactiva una cuenta o la marca/retira como admin.

    - No puedes desactivarte a ti mismo (te quedarías fuera).
    - No puedes dejar la instalación sin admins.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if data.is_active is False and user.id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="No puedes desactivar tu propia cuenta"
        )
    if data.is_admin is False and user.is_admin:
        admins_left = (
            db.query(User).filter(User.is_admin.is_(True), User.id != user.id).count()  # type: ignore[union-attr]
        )
        if admins_left == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="La instalación no puede quedarse sin admin"
            )

    if data.is_active is not None:
        user.is_active = data.is_active
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    db.commit()
    db.refresh(user)
    return user


@router.put("/registration", response_model=schemas.AdminDecision)
def admin_set_registration(
    data: schemas.AdminDecision,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> schemas.AdminDecision:
    """Cierra/abre el registro de nuevas cuentas (toggle del admin)."""
    row = db.get(AppSetting, REGISTRATION_SETTING)
    if row is None:
        row = AppSetting(key=REGISTRATION_SETTING)
    row.value = _OPEN if data.open else "0"
    db.add(row)
    db.commit()
    return schemas.AdminDecision(open=registration_is_open(db))
