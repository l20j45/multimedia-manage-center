"""Esquemas Pydantic (entrada/salida de la API)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import MediaItem


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, description="Mínimo 8 caracteres")


class UserUpdate(BaseModel):
    name: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(None, min_length=8)


class UserOut(UserBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Message(BaseModel):
    msg: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str = Field(
        min_length=6, max_length=6, description="Código de 6 dígitos enviado por correo"
    )
    new_password: str = Field(min_length=8)


# ------------------------------------------------------------ Biblioteca de medios
MediaKind = Literal["audio", "image", "video"]


def parse_tags(csv_tags: str) -> list[str]:
    """CSV de tags → lista limpia, minúsculas, sin duplicados."""
    seen: dict[str, None] = {}
    for raw in csv_tags.split(",") if csv_tags else []:
        tag = raw.strip().lower()
        if tag:
            seen.setdefault(tag, None)
    return list(seen)[:20]


def tags_csv(tags: list[str]) -> str:
    """Tags → CSV normalizado para la BD (por parse_tags)."""
    return ",".join(parse_tags(",".join(tags)))


class MediaOut(BaseModel):
    id: int
    kind: MediaKind
    title: str
    tags: list[str]
    filename: str
    path: str
    mime: str
    size: int
    duration_s: float | None
    has_thumb: bool
    created_at: datetime

    @classmethod
    def from_item(cls, item: MediaItem) -> MediaOut:
        return cls(
            id=item.id,
            kind=item.kind,  # type: ignore[arg-type]
            title=item.title,
            tags=parse_tags(item.tags),
            filename=item.filename,
            path=item.path,
            mime=item.mime,
            size=item.size,
            duration_s=item.duration_s,
            has_thumb=item.thumb_path is not None,
            created_at=item.created_at,
        )


class MediaList(BaseModel):
    items: list[MediaOut]
    total: int


class MediaUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    tags: list[str] | None = Field(None, description="Lista de tags (reemplaza las anteriores)")


class TagCount(BaseModel):
    tag: str
    count: int
