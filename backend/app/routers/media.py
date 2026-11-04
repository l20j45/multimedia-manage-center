"""Router /media: biblioteca del usuario (privada por owner + opcional team).

Subida, búsqueda avanzada (título/tags/descripción, orden, fechas), papelera,
bulk, duplicados por contenido, re-thumbnail, editar metadata y servir
fichero/thumbnail. Cada endpoint filtra por owner salvo los items del EQUIPO
(visibility='team'), que se ven pero NO se pueden editar por otros.
"""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import schemas
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Collection, CollectionItem, MediaItem, User
from app.services import media as media_svc

router = APIRouter(prefix="/media", tags=["media"])

ORDER_COLUMNS = {
    "created": MediaItem.created_at,
    "title": MediaItem.title,
    "size": MediaItem.size,
    "duration": MediaItem.duration_s,
    "rating": MediaItem.rating,
}


def _owned_item(db: Session, user: User, item_id: int, include_deleted: bool = False) -> MediaItem:
    q = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.owner_id == user.id)
    if include_deleted:
        q = q.filter(or_(MediaItem.deleted_at.is_(None), MediaItem.deleted_at.is_not(None)))
    else:
        q = q.filter(MediaItem.deleted_at.is_(None))
    item = q.first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return item


@router.post("", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED)
def upload(
    file: UploadFile = File(...),
    title: str = Form(""),
    tags: str = Form("", description="CSV de tags"),
    description: str = Form("", max_length=2000),
    visibility: str = Form("private"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Sube un recurso (audio/imagen/video) con metadata opcional."""
    if visibility not in ("private", "team"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="visibility inválida")
    original = file.filename or ""
    try:
        kind = media_svc.detect_kind(original)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    rel_path, size, mime, sha = media_svc.save_stream(
        file.file, original, user.id, file.content_type
    )
    item = MediaItem(
        owner_id=user.id,
        kind=kind,
        title=(title.strip() or Path(original).stem)[:200],
        tags=schemas.tags_csv(schemas.parse_tags(tags)),
        description=description.strip(),
        visibility=visibility,
        filename=original[:255],
        path=rel_path,
        mime=mime[:100],
        size=size,
        sha256=sha,
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
    q: str | None = Query(None, max_length=100, description="Busca en título/tags/descripción"),
    kind: schemas.MediaKind | None = None,
    tag: str | None = Query(None, max_length=50, description="Debe CONTENER este tag"),
    tag_no: str | None = Query(None, max_length=50, description="NO debe contener este tag"),
    collection: int | None = Query(None, description="Solo de esta colección"),
    scope: str = Query("mine", pattern="^(mine|team)$"),
    order: str = Query("created", pattern="^(created|title|size|duration|rating)$"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    min_rating: int | None = Query(None, ge=1, le=5, description="Solo con rating >= n"),
    since: datetime | None = None,
    until: datetime | None = None,
    trash: bool = Query(False, description="Solo papelera"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaList:
    """Lista/búsqueda. `scope=team` añade los recursos públicos del equipo."""
    if scope == "mine":
        base = db.query(MediaItem).filter(MediaItem.owner_id == user.id)
    else:
        base = db.query(MediaItem).filter(
            (MediaItem.owner_id == user.id)
            | ((MediaItem.visibility == "team") & (MediaItem.owner_id != user.id))
        )
    base = base.filter(
        MediaItem.deleted_at.is_(None) if not trash else MediaItem.deleted_at.is_not(None)
    )
    if kind:
        base = base.filter(MediaItem.kind == kind)
    if collection is not None:
        base = (
            db.query(MediaItem)
            .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
            .filter(
                MediaItem.owner_id == user.id,
                CollectionItem.collection_id == collection,
            )
        )
        scope = "mine"
    if q and q.strip():
        needle = f"%{q.strip()}%"
        base = base.filter(
            MediaItem.title.ilike(needle)
            | MediaItem.tags.ilike(needle)
            | MediaItem.description.ilike(needle)
        )
    elif tag and tag.strip():
        base = base.filter(MediaItem.tags.ilike(f"%{tag.strip().lower()}%"))
    if tag_no and tag_no.strip():
        base = base.filter(MediaItem.tags.notilike(f"%{tag_no.strip().lower()}%"))
    if since:
        base = base.filter(MediaItem.created_at >= since)
    if until:
        base = base.filter(MediaItem.created_at <= until)
    if min_rating:
        base = base.filter(MediaItem.rating >= min_rating)

    col = ORDER_COLUMNS[order]
    base = base.order_by(col.desc() if direction == "desc" else col.asc(), MediaItem.id.desc())

    total = base.count()
    items = base.offset(offset).limit(limit).all()
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
    rows = (
        db.query(MediaItem.tags)
        .filter(MediaItem.owner_id == user.id, MediaItem.deleted_at.is_(None))
        .all()
    )
    for (csv_tags,) in rows:
        for tag in schemas.parse_tags(csv_tags):
            counts[tag] = counts.get(tag, 0) + 1
    return [schemas.TagCount(tag=t, count=c) for t, c in sorted(counts.items())]


@router.get("/public/{token}", response_model=schemas.PublicCollectionOut)
def public_collection(
    token: str,
    db: Session = Depends(get_db),
) -> schemas.PublicCollectionOut:
    """Enlace público SIN login: datos de la colección compartida (solo lectura).

    Los ficheros se sirven por GET /media/{id}/file?share=<token> — el
    endpoint valida que el recurso pertenezca a ESA colección.
    """
    col = db.query(Collection).filter(Collection.share_token == token).first()
    if col is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Enlace no válido")
    items = (
        db.query(MediaItem)
        .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
        .filter(CollectionItem.collection_id == col.id, MediaItem.deleted_at.is_(None))
        .order_by(CollectionItem.position, CollectionItem.id)
        .all()
    )
    return schemas.PublicCollectionOut(
        name=col.name,
        is_project=bool(col.is_project),
        items=[schemas.MediaOut.from_item(i) for i in items],
    )


@router.get("/duplicates", response_model=schemas.DuplicateGroups)
def duplicates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.DuplicateGroups:
    """Grupos de recursos con EXACTAMENTE el mismo contenido (por sha256)."""
    rows = (
        db.query(MediaItem.sha256, func.count(MediaItem.id))
        .filter(
            MediaItem.owner_id == user.id,
            MediaItem.sha256.is_not(None),
            MediaItem.deleted_at.is_(None),
        )
        .group_by(MediaItem.sha256)
        .having(func.count(MediaItem.id) >= 2)
        .all()
    )
    groups: list[list[schemas.MediaOut]] = []
    for sha, _ in rows:
        items = (
            db.query(MediaItem)
            .filter(
                MediaItem.owner_id == user.id,
                MediaItem.sha256 == sha,
                MediaItem.deleted_at.is_(None),
            )
            .order_by(MediaItem.created_at)
            .all()
        )
        groups.append([schemas.MediaOut.from_item(i) for i in items])
    return schemas.DuplicateGroups(groups=groups)


@router.patch("/{item_id}", response_model=schemas.MediaOut)
def update_item(
    item_id: int,
    data: schemas.MediaUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Edita propietario del recurso: título, tags, description, meta, visibilidad."""
    item = _owned_item(db, user, item_id)
    if data.title is not None:
        item.title = data.title.strip()[:200] or item.title
    if data.tags is not None:
        item.tags = schemas.tags_csv(data.tags)
    if data.description is not None:
        item.description = data.description.strip()[:2000]
    if data.meta is not None:
        item.meta = data.meta if isinstance(data.meta, dict) else None
    if data.visibility is not None:
        if data.visibility not in ("private", "team"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="visibility inválida")
        item.visibility = data.visibility
    if data.rating is not None:
        item.rating = int(data.rating)
    db.commit()
    db.refresh(item)
    return schemas.MediaOut.from_item(item)


@router.post(
    "/{item_id}/trim", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED
)
def trim_media(
    item_id: int,
    data: schemas.TrimIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Crea un NUEVO recurso con el fragmento [start → end] del clip.

    ffmpeg `-c copy` corta sin re-codificar (rápido, sin pérdida de calidad).
    El original queda intacto; el fragmento hereda kind/mime y se genera su
    propio thumbnail, duración y tags.
    """
    item = _owned_item(db, user, item_id)
    if item.kind not in ("video", "audio"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Solo clips de video o audio")
    end = data.end if data.end is not None else (item.duration_s or None)
    if end is not None and end <= data.start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="end debe ser mayor que start")

    rel = media_svc.trim_segment(
        item.path,
        item.kind,
        data.start,
        end,
    )
    if rel is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ffmpeg no disponible para cortar el fragmento",
        )
    size = (media_svc.media_root() / rel).stat().st_size
    desc = f"Corte de «{item.title}» ({data.start:g}s → {end if end is not None else 'fin'}s)"  # noqa: E501
    frag = MediaItem(
        owner_id=user.id,
        kind=item.kind,
        title=(data.title or f"{item.title} (corte {data.start:.0f}s–{end or '?'})")[:200],
        tags=schemas.tags_csv(data.tags or []),
        description=desc,
        visibility=item.visibility,
        filename=Path(item.filename).stem + "_corte" + Path(item.filename).suffix,
        path=rel,
        mime=item.mime,
        size=size,
    )
    frag.thumb_path = media_svc.make_thumbnail(rel, frag.kind)
    if media_svc.ffmpeg_bin():
        frag.duration_s = media_svc.probe_duration(rel, frag.kind)
    db.add(frag)
    db.commit()
    db.refresh(frag)
    return schemas.MediaOut.from_item(frag)


@router.post(
    "/{item_id}/extract-audio", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED
)
def extract_audio(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Extrae la pista de audio de un VIDEO como recurso .mp3 nuevo.

    Para el flujo SFX: subes un video de efectos, lo conviertes a audio con un
    clic y luego lo recortas en el player con I/O.
    """
    item = _owned_item(db, user, item_id)
    if item.kind != "video":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Solo aplica a videos")
    rel = media_svc.extract_audio(item.path, item.kind)
    if rel is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="ffmpeg no disponible para extraer audio"
        )
    size = (media_svc.media_root() / rel).stat().st_size
    audio = MediaItem(
        owner_id=user.id,
        kind="audio",
        title=f"{item.title} (audio)",
        tags=schemas.tags_csv(schemas.parse_tags(item.tags)),
        description=f"Audio extraído de «{item.title}»",
        visibility=item.visibility,
        filename=Path(item.filename).stem + "_audio.mp3",
        path=rel,
        mime="audio/mpeg",
        size=size,
    )
    audio.thumb_path = media_svc.make_thumbnail(rel, "audio")  # waveform
    if media_svc.ffmpeg_bin():
        audio.duration_s = media_svc.probe_duration(rel, "audio")
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return schemas.MediaOut.from_item(audio)


@router.post("/{item_id}/autotag", response_model=schemas.AutotagOut)
def autotag(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.AutotagOut:
    """SUGIERE tags para un recurso (no aplica nada por sí solo).

    Heurística local siempre; visión con Gemini solo si GEMINI_API_KEY está
    en backend/.env. La UI muestra los chips y el usuario decide cuáles aplicar.
    """
    from app.services import autotag as autotag_svc

    item = _owned_item(db, user, item_id)
    existing = set(schemas.parse_tags(item.tags))
    freshly = [t for t in autotag_svc.suggest_tags(item) if t not in existing][:12]
    return schemas.AutotagOut(
        suggestions=freshly,
        source="gemini+heuristica" if getattr(settings, "GEMINI_API_KEY", "") else "heuristica",
    )


@router.post("/{item_id}/rethumb", response_model=schemas.MediaOut)
def rethumb(
    item_id: int,
    data: schemas.RethumbIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Re-genera el thumbnail de un VIDEO usando el frame en `at` segundos."""
    item = _owned_item(db, user, item_id)
    if item.kind != "video":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Solo aplica a videos")
    at = data.at if data.at >= 0 else max(0.0, (item.duration_s or 0) + data.at)
    thumb = media_svc.rethumbnail_at(item.path, at)
    if thumb:
        item.thumb_path = thumb
        db.commit()
    return schemas.MediaOut.from_item(item)


@router.post("/{item_id}/restore", response_model=schemas.MediaOut)
def restore_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MediaOut:
    """Saca un recurso de la papelera."""
    item = _owned_item(db, user, item_id, include_deleted=True)
    item.deleted_at = None
    db.commit()
    db.refresh(item)
    return schemas.MediaOut.from_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Papelera: marca deleted_at (los ficheros quedan intactos hasta purge)."""
    item = _owned_item(db, user, item_id)
    item.deleted_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{item_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Borrado DEFINITIVO: fila + ficheros físicos."""
    item = _owned_item(db, user, item_id, include_deleted=True)
    db.query(CollectionItem).filter(CollectionItem.media_id == item.id).delete()
    db.delete(item)
    db.commit()
    media_svc.delete_files([item.path, item.thumb_path])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bulk", response_model=schemas.BulkResult)
def bulk(
    data: schemas.BulkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.BulkResult:
    """Operaciones en lote sobre varios recursos propios."""
    include_deleted = data.action in ("restore", "purge")
    q = db.query(MediaItem).filter(
        MediaItem.id.in_(data.ids),
        MediaItem.owner_id == user.id,
    )
    if not include_deleted:
        q = q.filter(MediaItem.deleted_at.is_(None))
    if data.action == "rename":
        q = q.order_by(MediaItem.created_at.asc(), MediaItem.id.asc())
    items = q.all()
    action = data.action
    done = 0
    counter = 0
    for item in items:
        match action:
            case "add_tag" | "remove_tag":
                cur = schemas.parse_tags(item.tags)
                wanted = schemas.parse_tags(",".join(data.tags or []))
                tags = (
                    list(dict.fromkeys(cur + wanted))
                    if action == "add_tag"
                    else [t for t in cur if t not in wanted]
                )
                item.tags = ",".join(tags)
            case "set_visibility":
                item.visibility = data.visibility or item.visibility
            case "delete":
                item.deleted_at = datetime.now(UTC)
            case "restore":
                item.deleted_at = None
            case "purge":
                db.query(CollectionItem).filter(CollectionItem.media_id == item.id).delete()
                db.delete(item)
                media_svc.delete_files([item.path, item.thumb_path])
            case "add_to_collection":
                if data.collection_id:
                    dup = (
                        db.query(CollectionItem)
                        .filter(
                            CollectionItem.collection_id == data.collection_id,
                            CollectionItem.media_id == item.id,
                        )
                        .first()
                    )
                    if not dup:
                        db.add(
                            CollectionItem(
                                collection_id=data.collection_id,
                                media_id=item.id,
                                position=0,
                            )
                        )
            case "rename":
                from datetime import date as _date

                pattern = data.pattern or "{title}"
                counter += 1
                new_title = (
                    pattern.replace("{n}", f"{counter:03d}")
                    .replace("{date}", _date.today().isoformat())
                    .replace("{title}", item.title)
                    .strip()
                )[:200] or item.title
                item.title = new_title
            case _:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="action inválido")
        done += 1
    db.commit()
    return schemas.BulkResult(done=done, requested=len(data.ids))


@router.get("/{item_id}/file")
def get_file(
    item_id: int,
    request: Request,
    share: str | None = Query(None),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Sirve el fichero original: owner/equipo (header o ?access_token=) o
    lectura pública de colección compartida con ?share=<token>."""
    item = _resolve_readable(request, db, item_id, share)
    abs_path = media_svc.media_root() / item.path
    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fichero no está en disco")
    return FileResponse(abs_path, media_type=item.mime, filename=item.filename)


@router.get("/{item_id}/thumb")
def get_thumb(
    item_id: int,
    request: Request,
    share: str | None = Query(None),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Thumbnail JPEG (owner/equipo o público por share token)."""
    item = _resolve_readable(request, db, item_id, share)
    if not item.thumb_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sin thumbnail")
    abs_path = media_svc.media_root() / item.thumb_path
    if not abs_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Thumbnail no está en disco")
    return FileResponse(abs_path, media_type="image/jpeg")


def _resolve_readable(
    request: Request, db: Session, item_id: int, share: str | None, include_deleted: bool = False
) -> MediaItem:
    """Acceso de lectura: Bearer/access_token (owner o team) o token de
    colección compartida (el recurso debe pertenecer a ESA colección)."""
    from app.security import decode_access_token

    # 1) token de usuario (header o query)
    auth = request.headers.get("Authorization")
    token = None
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:]
    if not token:
        token = request.query_params.get("access_token")
    if token:
        subject = decode_access_token(token)
        if subject:
            user = db.query(User).filter(User.email == subject).first()
            if user and user.is_active:
                q = db.query(MediaItem).filter(
                    MediaItem.id == item_id, MediaItem.owner_id == user.id
                )
                item = (
                    q.first()
                    if include_deleted
                    else q.filter(MediaItem.deleted_at.is_(None)).first()
                )
                if item is not None:
                    return item
                team_item = (
                    db.query(MediaItem)
                    .filter(
                        MediaItem.id == item_id,
                        MediaItem.visibility == "team",
                        MediaItem.deleted_at.is_(None),
                    )
                    .first()
                )
                if team_item is not None:
                    return team_item
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    # 2) enlace compartido
    if share:
        col = db.query(Collection).filter(Collection.share_token == share).first()
        if col is not None:
            belongs = (
                db.query(CollectionItem)
                .filter(
                    CollectionItem.collection_id == col.id,
                    CollectionItem.media_id == item_id,
                )
                .first()
            )
            if belongs is not None:
                item = (
                    db.query(MediaItem)
                    .filter(MediaItem.id == item_id, MediaItem.deleted_at.is_(None))
                    .first()
                )
                if item is not None:
                    return item
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Enlace compartido no válido")

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail="Se requiere token o enlace compartido"
    )


def _item_for_read(
    db: Session, user: User, item_id: int, include_deleted: bool = False
) -> MediaItem:
    """Item legible: PROPIO (aún en papelera si include_deleted) o del equipo (vivo)."""
    q = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.owner_id == user.id)
    item = q.first() if include_deleted else q.filter(MediaItem.deleted_at.is_(None)).first()
    if item is None:
        item = (
            db.query(MediaItem)
            .filter(
                MediaItem.id == item_id,
                MediaItem.visibility == "team",
                MediaItem.deleted_at.is_(None),
            )
            .first()
        )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return item


@router.get("/stats/count")
def count_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Conteos por tipo (excluye papelera)."""
    rows = (
        db.query(MediaItem.kind, func.count(MediaItem.id))
        .filter(MediaItem.owner_id == user.id, MediaItem.deleted_at.is_(None))
        .group_by(MediaItem.kind)
        .all()
    )
    counts = {"audio": 0, "image": 0, "video": 0}
    for kind, n in rows:
        counts[kind] = n
    return counts
