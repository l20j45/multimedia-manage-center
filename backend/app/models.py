"""Modelos de la base de datos."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    """Token un-solo-uso para restablecer la contraseña (expira en ~30 min)."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaItem(Base):
    """Recurso de la biblioteca (audio / imagen / video) de un usuario.

    Los ficheros viven en MEDIA_DIR/{owner_id}/ (no en la BD); aquí solo
    metadata. Los tags van como CSV en una columna: la búsqueda por tag
    (LIKE) escala bien para bibliotecas personales.
    """

    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), index=True, nullable=False)  # audio|image|video
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    tags: Mapped[str] = mapped_column(String(500), default="", server_default="")  # CSV minúsculas
    description: Mapped[str] = mapped_column(
        sa.Text, default="", server_default=""
    )  # notas (en búsqueda)
    meta: Mapped[dict | None] = mapped_column(
        sa.JSON, nullable=True
    )  # {camera, proyecto, ...} campos libres
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # nombre original al subir
    path: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )  # relativo a MEDIA_DIR
    thumb_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # relativo a MEDIA_DIR
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(nullable=False)  # bytes
    sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)  # duplicados
    duration_s: Mapped[float | None] = mapped_column(nullable=True)  # audio/video (ffprobe)
    visibility: Mapped[str] = mapped_column(
        String(10), index=True, default="private", server_default="private"
    )  # private|team
    rating: Mapped[int] = mapped_column(default=0, server_default=sa.text("0"))  # 0..5 estrellas
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # papelera
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Collection(Base):
    """Colección (álbum/playlist/edición) de la biblioteca de un usuario."""

    __tablename__ = "collections"
    __table_args__ = (sa.UniqueConstraint("owner_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_project: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa.text("0"))
    share_token: Mapped[str | None] = mapped_column(
        String(43), unique=True, index=True, nullable=True
    )  # link público revocable (/share/<token>)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionItem(Base):
    """Un recurso de la biblioteca dentro de una colección (N:M, ordenable)."""

    __tablename__ = "collection_items"
    __table_args__ = (sa.UniqueConstraint("collection_id", "media_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id"), index=True, nullable=False
    )
    media_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
