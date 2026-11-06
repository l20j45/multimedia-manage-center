"""Router /auth: registro, login, perfil y recuperación de contraseña."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import schemas, security
from app.database import get_db
from app.deps import get_current_user
from app.models import PasswordResetToken, User
from app.routers.admin import registration_is_open_effective
from app.services import email as email_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Vida del código para restablecer contraseña (minutos)
RESET_TTL_MINUTES = 30


@router.get("/registration", response_model=schemas.RegistrationOut)
def registration_status(db: Session = Depends(get_db)) -> schemas.RegistrationOut:
    """¿El registro está abierto? Público: la pantalla de login adapta su tab."""
    return schemas.RegistrationOut(open=registration_is_open_effective(db))


@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(
    data: schemas.UserCreate, background: BackgroundTasks, db: Session = Depends(get_db)
) -> User:
    """Crea una cuenta nueva y envía un correo de bienvenida (si hay SMTP).

    - El PRIMER usuario de la instalación queda como super admin.
    - Si el admin cerró el registro, no se aceptan cuentas nuevas (403);
      una BD sin usuarios siempre deja entrar a su primer admin.
    """
    if not registration_is_open_effective(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El registro está cerrado: contacta al administrador",
        )
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El correo ya está registrado"
        )

    first_user = db.query(User).count() == 0
    user = User(
        email=data.email,
        name=data.name,
        hashed_password=security.hash_password(data.password),
        is_admin=first_user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    background.add_task(email_service.send_welcome_email, user.email, data.name)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    remember: bool = Form(False),
    db: Session = Depends(get_db),
) -> schemas.Token:
    """Login con email (campo `username`) y contraseña. Devuelve un token JWT.

    `remember=true` extiende la sesión a 30 días (default 24h).
    """
    user = db.query(User).filter(User.email == form.username).first()
    if user is None or not security.verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas"
        )
    expires = timedelta(days=30) if remember else None
    return schemas.Token(access_token=security.create_access_token(user.email, expires))


@router.get("/me", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Perfil del usuario autenticado."""
    return user


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(
    data: schemas.ForgotPasswordIn, background: BackgroundTasks, db: Session = Depends(get_db)
) -> None:
    """Pide un código de recuperación. Siempre responde 204 (sin revelar si el correo existe)."""
    user = (
        db.query(User)
        .filter(User.email == data.email, User.is_active.is_(True))  # type: ignore[union-attr]
        .first()
    )
    if user is not None:
        # Un código activo por usuario: invalida los anteriores
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),  # type: ignore[union-attr]
        ).delete()
        code, code_hash = security.create_reset_code()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                code_hash=code_hash,
                expires_at=datetime.now(UTC) + timedelta(minutes=RESET_TTL_MINUTES),
            )
        )
        db.commit()
        background.add_task(email_service.send_password_reset_email, user.email, user.name, code)


@router.post("/reset-password", response_model=schemas.Message)
def reset_password(data: schemas.ResetPasswordIn, db: Session = Depends(get_db)) -> schemas.Message:
    """Restablece la contraseña con el código de 6 dígitos recibido por correo."""
    user = db.query(User).filter(User.email == data.email).first()
    now = datetime.now(UTC)
    active: list[PasswordResetToken] = []
    if user is not None:
        active = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),  # type: ignore[union-attr]
                PasswordResetToken.expires_at > now,  # type: ignore[type-var]
            )
            .all()
        )

    code_hash = security.hash_code(data.code)
    if user is None or not any(t.code_hash == code_hash for t in active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Código inválido o expirado"
        )

    token_row = next(t for t in active if t.code_hash == code_hash)
    token_row.used_at = now  # un solo uso
    user.hashed_password = security.hash_password(data.new_password)
    db.commit()
    return schemas.Message(msg="Contraseña actualizada. Ya puedes iniciar sesión.")
