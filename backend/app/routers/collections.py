"""Router /collections: colecciones (álbumes/playlists) de la biblioteca.

Colecciones privadas del usuario con N:M hacia /media. En SQLite el borrado
en cascada no está garantizado sin PRAGMA foreign_keys=ON, así que los
endpoints limpian las filas hijas manualmente.
"""

import zipfile
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_user
from app.models import Collection, CollectionItem, MediaItem, User
from app.routers.media import _owned_item
from app.services import media as media_svc

router = APIRouter(prefix="/collections", tags=["collections"])


def _owned_collection(db: Session, user: User, collection_id: int) -> Collection:
    col = (
        db.query(Collection)
        .filter(Collection.id == collection_id, Collection.owner_id == user.id)
        .first()
    )
    if col is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Colección no encontrada")
    return col


@router.get("", response_model=list[schemas.CollectionOut])
def list_collections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.CollectionOut]:
    """Colecciones propias con el conteo de recursos de cada una."""
    collections = (
        db.query(Collection).filter(Collection.owner_id == user.id).order_by(Collection.name).all()
    )
    counts: dict[int, int] = defaultdict(int)
    rows = (
        db.query(CollectionItem.collection_id)
        .join(Collection, CollectionItem.collection_id == Collection.id)
        .filter(Collection.owner_id == user.id)
        .all()
    )
    for (col_id,) in rows:
        counts[col_id] += 1
    return [schemas.CollectionOut.from_col(c, counts[c.id]) for c in collections]


@router.post("", response_model=schemas.CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    data: schemas.CollectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.CollectionOut:
    """Crea una colección (el nombre es único por usuario)."""
    exists = (
        db.query(Collection)
        .filter(Collection.owner_id == user.id, Collection.name == data.name.strip())
        .first()
    )
    if exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Ya existe una colección llamada '{data.name.strip()}'",
        )
    col = Collection(owner_id=user.id, name=data.name.strip(), is_project=data.is_project)
    db.add(col)
    db.commit()
    db.refresh(col)
    return schemas.CollectionOut.from_col(col, 0)


@router.patch("/{collection_id}", response_model=schemas.CollectionOut)
def update_collection(
    collection_id: int,
    data: schemas.CollectionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.CollectionOut:
    """Renombra o marca/des-marca como proyecto (edición)."""
    col = _owned_collection(db, user, collection_id)
    if data.name is not None:
        name = data.name.strip()
        dup = (
            db.query(Collection)
            .filter(
                Collection.owner_id == user.id,
                Collection.name == name,
                Collection.id != col.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"Ya existe una colección llamada '{name}'"
            )
        col.name = name
    if data.is_project is not None:
        col.is_project = data.is_project
    db.commit()
    db.refresh(col)
    total = db.query(CollectionItem).filter(CollectionItem.collection_id == col.id).count()
    return schemas.CollectionOut.from_col(col, total)


@router.get("/{collection_id}/export-zip")
def export_collection_zip(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Descarga la colección completa como .zip con los ficheros reales.

    Nombres dentro del zip: NNN_titulo.ext (orden de posición) — sin colisiones
    y legibles en cualquier NLE. Requiere streaming a un fichero temporal
    (bibliotecas de cientos de MB no caben en RAM, menos en una Pi).
    """
    import tempfile

    col = _owned_collection(db, user, collection_id)
    items = (
        db.query(MediaItem)
        .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
        .filter(CollectionItem.collection_id == col.id, MediaItem.deleted_at.is_(None))
        .order_by(CollectionItem.position, CollectionItem.id)
        .all()
    )
    safe_name = "".join(c for c in col.name if c.isalnum() or c in " -_").strip() or "coleccion"

    tmp = tempfile.NamedTemporaryFile(prefix="export_", suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for idx, it in enumerate(items, start=1):
            src = media_svc.media_root() / it.path
            if not src.exists():
                continue  # huérfano físico: se omite con pena
            ext = Path(it.filename).suffix or Path(src).suffix
            member = f"{idx:03d}_{cols_safe(it.title) or it.id}{ext}"
            zf.write(src, arcname=member)
        # lista.csv de acompañamiento
        lines = ["titulo,tipo,tags,duracion_seg,tamano_mb"]
        for it in items:
            fields = [
                it.title.replace('"', '""'),
                it.kind,
                ",".join(schemas.parse_tags(it.tags)).replace('"', '""'),
                str(it.duration_s or ""),
                f"{it.size / (1024 * 1024):.2f}",
            ]
            lines.append(",".join(f'"{f}"' for f in fields))
        zf.writestr("_lista.csv", "\n".join(lines) + "\n")
    tmp.close()
    size = Path(tmp.name).stat().st_size
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=f"{safe_name}.zip",
        headers={"Content-Length": str(size)},
    )


def cols_safe(title: str) -> str:
    return "".join(c for c in title if c.isalnum() or c in " -_").strip()[:60]


@router.get("/{collection_id}/export")
def export_collection(
    collection_id: int,
    format: str = Query("txt", pattern="^(txt|csv)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Exporta la lista de la colección a .txt o .csv (para NLE o edición)."""
    from fastapi.responses import PlainTextResponse

    col = _owned_collection(db, user, collection_id)
    items = (
        db.query(MediaItem)
        .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
        .filter(CollectionItem.collection_id == col.id, MediaItem.deleted_at.is_(None))
        .order_by(CollectionItem.position, CollectionItem.id)
        .all()
    )
    safe_name = "".join(c for c in col.name if c.isalnum() or c in " -_").strip() or "lista"
    if format == "csv":
        lines = ["titulo,tipo,tags,descripcion,duracion_seg,tamano_mb"]
        for it in items:
            fields = [
                it.title.replace('"', '""'),
                it.kind,
                ",".join(schemas.parse_tags(it.tags)).replace('"', '""'),
                (it.description or "").replace('"', '""'),
                str(it.duration_s or ""),
                f"{it.size / (1024 * 1024):.2f}",
            ]
            lines.append(",".join(f'"{f}"' for f in fields))
        content = "\n".join(lines) + "\n"
        media_type = "text/csv"
        filename = f"{safe_name}.csv"
    else:
        lines = [f"Lista: {col.name}", ""]
        for it in items:
            dur = f" · {it.duration_s}s" if it.duration_s else ""
            size = f"{it.size / (1024 * 1024):.1f} MB"
            tags = ", ".join(schemas.parse_tags(it.tags))
            lines.append(f"- {it.title} [{it.kind}] · {size}{dur}" + (f" · {tags}" if tags else ""))
        content = "\n".join(lines) + "\n"
        media_type = "text/plain"
        filename = f"{safe_name}.txt"
    return PlainTextResponse(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Borra la colección (los recursos NO se borran, solo su pertenencia)."""
    col = _owned_collection(db, user, collection_id)
    db.query(CollectionItem).filter(CollectionItem.collection_id == col.id).delete()
    db.delete(col)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{collection_id}/share", response_model=schemas.ShareOut)
def create_share(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ShareOut:
    """Genera/rota el token de enlace público de la colección."""
    import secrets

    col = _owned_collection(db, user, collection_id)
    if not col.share_token:
        col.share_token = secrets.token_urlsafe(24)
        db.commit()
    return schemas.ShareOut(token=col.share_token, url=f"/share/{col.share_token}")


@router.delete("/{collection_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Revoca el enlace público (el token deja de servir)."""
    col = _owned_collection(db, user, collection_id)
    col.share_token = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{collection_id}/items", response_model=list[schemas.MediaOut])
def collection_items(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.MediaOut]:
    """Recursos de una colección, en orden de posición."""
    col = _owned_collection(db, user, collection_id)
    items = (
        db.query(MediaItem)
        .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
        .filter(CollectionItem.collection_id == col.id)
        .order_by(CollectionItem.position, CollectionItem.id)
        .all()
    )
    return [schemas.MediaOut.from_item(i) for i in items]


@router.post("/{collection_id}/items", status_code=status.HTTP_201_CREATED)
def add_item(
    collection_id: int,
    data: schemas.CollectionAddItem,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.CollectionOut:
    """Agrega un recurso propio a la colección."""
    col = _owned_collection(db, user, collection_id)
    media = _owned_item(db, user, data.media_id)  # 404 si no es suyo
    dup = (
        db.query(CollectionItem)
        .filter(
            CollectionItem.collection_id == col.id,
            CollectionItem.media_id == media.id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="El recurso ya está en la colección")
    position = (
        max(
            (
                p
                for (p,) in db.query(CollectionItem.position)
                .filter(CollectionItem.collection_id == col.id)
                .all()
            ),
            default=0,
        )
        + 1
    )
    db.add(CollectionItem(collection_id=col.id, media_id=media.id, position=position))
    db.commit()
    total = db.query(CollectionItem).filter(CollectionItem.collection_id == col.id).count()
    return schemas.CollectionOut.from_col(col, total)


@router.delete("/{collection_id}/items/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    collection_id: int,
    media_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Quita un recurso de la colección (sin borrar el recurso)."""
    col = _owned_collection(db, user, collection_id)
    _owned_item(db, user, media_id)
    rows = db.query(CollectionItem).filter(
        CollectionItem.collection_id == col.id, CollectionItem.media_id == media_id
    )
    if rows.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No está en la colección")
    rows.delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
