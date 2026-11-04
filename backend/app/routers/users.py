"""Router /users: gestión del perfil del usuario autenticado."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas, security
from app.database import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    data: schemas.UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Actualiza el nombre y/o la contraseña del usuario actual."""
    if data.new_password is not None:
        if data.current_password is None or not security.verify_password(
            data.current_password, user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere current_password correcta para cambiar la contraseña",
            )
        user.hashed_password = security.hash_password(data.new_password)

    if data.name is not None:
        user.name = data.name

    db.commit()
    db.refresh(user)
    return user
