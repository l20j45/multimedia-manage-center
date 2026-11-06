"""Dependencias reutilizables de FastAPI."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extrae y valida el token Bearer, y devuelve el usuario asociado."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error
    user = db.query(User).filter(User.email == subject).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Guard para endpoints de administración (solo super admin)."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador puede hacer esto",
        )
    return user


def get_current_user_flexible(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Como get_current_user, pero acepta también ?access_token=... en la URL.

    Necesario para <img>/<video>/<audio>: el navegador no manda el header
    Authorization en esos recursos. Solo se expone así en /media/*.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token: str | None = None
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:]
    if not token:
        token = request.query_params.get("access_token")
    if not token:
        raise credentials_error
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error
    user = db.query(User).filter(User.email == subject).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user
