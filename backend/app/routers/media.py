"""Router /media: biblioteca privada de recursos del usuario autenticado.

Subida (multipart), búsqueda por nombre O tags, filtro por tipo, listar tags,
editar (título/tags), eliminar y servir fichero/thumbnail. Cada endpoint
filtra por owner: solo se ve lo del usuario autenticado.
"""

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_user, get_current_user_flexible
from app.models import CollectionItem, MediaItem, User
from app.services import media as media_svc

router = APIRouter(prefix="/media", tags=["media"])

# Orden de descargas: filename se QP-escapa en FileResponse; mime por tipo
MEDIA_TYPES = {
    "image": "image/jpeg",
    "audio": "audio/mpeg",
    "video": "video/mp4",
}


def _owned_item(db: Session, user: User, item_id: int) -> MediaItem:
    item = (
        db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.owner_id == user.id).first()
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return item


@router.post("", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED)
def upload(
    file: UploadFile = File(...),
    title: str = Form(""),
    tags: str = Form("", description="CSV de tags"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Sube un recurso a la biblioteca del usuario (audio/imagen/video)."""
    original = file.filename or ""
    try:
        kind = media_svc.detect_kind(original)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    rel_path, size, mime = media_svc.save_stream(file.file, original, user.id, file.content_type)
    item = MediaItem(
        owner_id=user.id,
        kind=kind,
        title=(title.strip() or Path(original).stem)[:200],
        tags=schemas.tags_csv(schemas.parse_tags(tags)),
        filename=original[:255],
        path=rel_path,
        mime=mime[:100],
        size=size,
    )
    item.thumb_path = media_svc.make_thumbnail(rel_path, kind)
    if media_svc.ffmpeg_bin():
        item.duration_s = media_svc.probe_duration(rel_path, kind)
    db.add(item)
    db.commit()
    db.refresh(item)
    return schemas.MediaOut.from_item(item)


@router.get("", response_model=schemas.MediaList)
def list_media(
    q: str | None = Query(None, max_length=100, description="Busca en título O tags"),
    kind: schemas.MediaKind | None = None,
    tag: str | None = Query(None, max_length=50, description="Filtra por UN tag"),
    collection: int | None = Query(None, description="Solo recursos de esta colección"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaList:
    """Lista/búsqueda de la biblioteca del usuario (por nombre o tags)."""
    base = (
        db.query(MediaItem)
        .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
        .filter(
            MediaItem.owner_id == user.id,
            CollectionItem.collection_id == collection,
        )
        if collection is not None
        else db.query(MediaItem).filter(MediaItem.owner_id == user.id)
    )
    if kind:
        base = base.filter(MediaItem.kind == kind)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        base = base.filter(MediaItem.title.ilike(needle) | MediaItem.tags.ilike(needle))
    elif tag and tag.strip():
        base = base.filter(MediaItem.tags.ilike(f"%{tag.strip().lower()}%"))

    total = base.count()
    items = (
        base.order_by(MediaItem.created_at.desc(), MediaItem.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return schemas.MediaList(
        items=[schemas.MediaOut.from_item(i) for i in items],
        total=total,
    )


@router.get("/tags", response_model=list[schemas.TagCount])
def list_tags(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.TagCount]:
    """Tags propios con su conteo (para chips de filtro en la UI)."""
    counts: dict[str, int] = {}
    rows = db.query(MediaItem.tags).filter(MediaItem.owner_id == user.id).all()
    for (csv_tags,) in rows:
        for tag in schemas.parse_tags(csv_tags):
            counts[tag] = counts.get(tag, 0) + 1
    return [schemas.TagCount(tag=t, count=c) for t, c in sorted(counts.items())]


@router.patch("/{item_id}", response_model=schemas.MediaOut)
def update_item(
    item_id: int,
    data: schemas.MediaUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Renombra el título y/o reemplaza los tags de un recurso propio."""
    item = _owned_item(db, user, item_id)
    if data.title is not None:
        item.title = data.title.strip()[:200] or item.title
    if data.tags is not None:
        item.tags = schemas.tags_csv(data.tags)
    db.commit()
    db.refresh(item)
    return schemas.MediaOut.from_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Elimina un recurso propio (fila + ficheros físicos + pertenencias)."""
    item = _owned_item(db, user, item_id)
    # SQLite no asegura cascada sin PRAGMA: limpia colecciones manualmente
    db.query(CollectionItem).filter(CollectionItem.media_id == item.id).delete()
    db.delete(item)
    db.commit()
    media_svc.delete_files([item.path, item.thumb_path])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{item_id}/file")
def get_file(
    item_id: int,
    user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Sirve el fichero original (auth por header o ?access_token= para la UI)."""
    item = _owned_item(db, user, item_id)
    abs_path = media_svc.media_root() / item.path
    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fichero no está en disco")
    return FileResponse(abs_path, media_type=item.mime, filename=item.filename)


@router.get("/{item_id}/thumb")
def get_thumb(
    item_id: int,
    user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Thumbnail JPEG (auth por header o ?access_token=)."""
    item = _owned_item(db, user, item_id)
    if not item.thumb_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sin thumbnail")
    abs_path = media_svc.media_root() / item.thumb_path
    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Thumbnail no está en disco")
    return FileResponse(abs_path, media_type="image/jpeg")


@router.get("/stats/count")
def count_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Conteos por tipo (para títulos de pestañas, todo privado del usuario)."""
    rows = (
        db.query(MediaItem.kind, func.count(MediaItem.id))
        .filter(MediaItem.owner_id == user.id)
        .group_by(MediaItem.kind)
        .all()
    )
    counts = {"audio": 0, "image": 0, "video": 0}
    for kind, n in rows:
        counts[kind] = n
    return counts
