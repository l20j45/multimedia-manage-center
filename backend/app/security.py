"""Utilidades de seguridad: hash de contraseñas, tokens JWT y códigos de reset."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    """Crea un JWT con el email del usuario como `sub`."""
    expires = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "exp": expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Devuelve el `sub` (email) o None si el token no es válido/expiró."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None


# ---------------------------------------------------------------- codes de reset


def create_reset_code() -> tuple[str, str]:
    """Genera un código numérico de 6 dígitos y su hash.

    Devuelve `(codigo, hash)`. Solo el hash se guarda en la BD.
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    return code, hash_code(code)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
