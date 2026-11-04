"""Esquemas Pydantic (entrada/salida de la API)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Collection, MediaItem


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
    description: str
    meta: dict | None
    filename: str
    path: str
    mime: str
    size: int
    duration_s: float | None
    has_thumb: bool
    visibility: str
    rating: int
    deleted: bool
    created_at: datetime

    @classmethod
    def from_item(cls, item: MediaItem) -> MediaOut:
        return cls(
            id=item.id,
            kind=item.kind,  # type: ignore[arg-type]
            title=item.title,
            tags=parse_tags(item.tags),
            description=item.description or "",
            meta=item.meta,
            filename=item.filename,
            path=item.path,
            mime=item.mime,
            size=item.size,
            duration_s=item.duration_s,
            has_thumb=item.thumb_path is not None,
            visibility=getattr(item, "visibility", "private") or "private",
            rating=int(getattr(item, "rating", 0) or 0),
            deleted=getattr(item, "deleted_at", None) is not None,
            created_at=item.created_at,
        )


class MediaList(BaseModel):
    items: list[MediaOut]
    total: int


class MediaUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    tags: list[str] | None = Field(None, description="Lista de tags (reemplaza las anteriores)")
    description: str | None = Field(None, max_length=2000)
    meta: dict | None = Field(None, description="Campos libres: {camera, proyecto, ...}")
    visibility: str | None = Field(None, description="private|team")
    rating: int | None = Field(None, ge=0, le=5, description="Estrellas 0-5")


class TrimIn(BaseModel):
    start: float = Field(..., ge=0, description="Segundo inicial")
    end: float | None = Field(None, description="Segundo final (None = hasta el final del clip)")
    title: str | None = Field(None, max_length=200, description="Título del fragmento nuevo")
    tags: list[str] | None = Field(None, description="Tags del fragmento nuevo")


class BulkRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    action: Literal[
        "add_tag", "remove_tag", "set_visibility", "delete", "restore", "purge", "add_to_collection"
    ]
    tags: list[str] | None = None
    visibility: str | None = None
    collection_id: int | None = None


class BulkResult(BaseModel):
    done: int
    requested: int


class RethumbIn(BaseModel):
    at: float = Field(0.0, description="Segundos del frame (negativo = cuenta atrás desde el fin)")


class AutotagOut(BaseModel):
    suggestions: list[str]
    source: str


class DuplicateGroups(BaseModel):
    groups: list[list[MediaOut]]


class TagCount(BaseModel):
    tag: str
    count: int


# ------------------------------------------------------------- Colecciones
class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_project: bool = Field(False, description="True = edición/rapporte (proyecto)")


class CollectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    is_project: bool | None = None


class CollectionAddItem(BaseModel):
    media_id: int


class CollectionOut(BaseModel):
    id: int
    name: str
    item_count: int
    is_project: bool

    @classmethod
    def from_col(cls, col: Collection, count: int = 0) -> CollectionOut:
        return cls(
            id=col.id,
            name=col.name,
            is_project=bool(getattr(col, "is_project", False)),
            item_count=count,
        )
