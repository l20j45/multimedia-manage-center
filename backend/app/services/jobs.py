"""Cola de compresión de video/imagen PERSISTIDA en SQLite.

- ThreadPoolExecutor: 2 workers por defecto; 1 en ARM (`COMPRESS_WORKERS=0`
  auto-detecta: saturar una Rasp Pi con ffmpeg congela toda la casa).
- Los jobs viven en la tabla `compression_jobs`: si el server muere a media
  compresión el aviso no se pierde — el item queda intacto y el job queda
  `running` huérfano; `recover_stale()` lo marca `lost` al arrancar.
- Un job ACTIVO máximo por item (queued/running): encola de nuevo es
  idempotente, devuelve el mismo job_id.
- El worker usa su propia sesión de BD; el original se reemplaza SIEMPRE
  solo si el resultado pesa menos.
"""

import platform
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.services import media as media_svc


def _default_workers() -> int:
    if settings.COMPRESS_WORKERS > 0:
        return settings.COMPRESS_WORKERS
    return 1 if platform.machine().startswith(("arm", "aarch64")) else 2


_executor = ThreadPoolExecutor(
    max_workers=_default_workers(), thread_name_prefix="compress"
)
_lock = threading.Lock()  # serializa de-dup de encuestas concurrentes


def _job_dict(row: Any) -> dict[str, Any]:
    return {
        "job_id": row.id,
        "item_id": row.item_id,
        "status": row.status,
        "old_size": row.old_size,
        "new_size": row.new_size,
        "error": row.error,
    }


def enqueue_compress(item_id: int, kind: str) -> str:
    """Encarga la compresión de un item. Devuelve job_id (idempotente)."""
    from app.database import SessionLocal
    from app.models import CompressionJob

    with _lock:  # evita encuestas espejo del mismo item en simultáneo
        db = SessionLocal()
        try:
            active = (
                db.query(CompressionJob)
                .filter(
                    CompressionJob.item_id == item_id,
                    CompressionJob.status.in_(("queued", "running")),
                )
                .first()
            )
            if active:
                return active.id
            job_id = uuid.uuid4().hex[:12]
            db.add(
                CompressionJob(
                    id=job_id, item_id=item_id, kind=kind, status="queued"
                )
            )
            db.commit()
        finally:
            db.close()
    _executor.submit(_run, job_id, item_id, kind)
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    from app.database import SessionLocal
    from app.models import CompressionJob

    db = SessionLocal()
    try:
        row = db.query(CompressionJob).filter(CompressionJob.id == job_id).first()
        return _job_dict(row) if row else None
    finally:
        db.close()


def latest_job(item_id: int) -> dict[str, Any] | None:
    """Último job del item (cualquier estado), o None si nunca comprimió."""
    from app.database import SessionLocal
    from app.models import CompressionJob

    db = SessionLocal()
    try:
        row = (
            db.query(CompressionJob)
            .filter(CompressionJob.item_id == item_id)
            .order_by(CompressionJob.created_at.desc(), CompressionJob.id.desc())
            .first()
        )
        return _job_dict(row) if row else None
    finally:
        db.close()


def recover_stale() -> int:
    """Al arrancar: jobs `running` huérfanos del proceso anterior → `lost`.

    El item NO se toca: la compresión a medias ya borró su original o no lo
    hizo — el estado del item sigue íntegro. Devuelve la cantidad marcada.
    """
    from app.database import SessionLocal
    from app.models import CompressionJob

    db = SessionLocal()
    try:
        n = (
            db.query(CompressionJob)
            .filter(CompressionJob.status.in_(("queued", "running")))
            .update(
                {CompressionJob.status: "lost",
                 CompressionJob.error: "el server se reinició a mitad del job"},
                synchronize_session=False,
            )
        )
        if n:
            db.commit()
        return n
    finally:
        db.close()


def _set(job_id: str, **fields: Any) -> None:
    from app.database import SessionLocal
    from app.models import CompressionJob

    db = SessionLocal()
    try:
        row = db.query(CompressionJob).filter(CompressionJob.id == job_id).first()
        if not row:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()


def _run(job_id: str, item_id: int, kind: str) -> None:
    """Worker: comprime el item y actualiza su BD (sesión propia)."""
    from app.database import SessionLocal
    from app.models import MediaItem

    _set(job_id, status="running")
    db = SessionLocal()
    try:
        item = db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item or item.deleted_at is not None:
            raise ValueError("item no disponible para comprimir")
        if kind == "video":
            _compress_video(job_id, item, db)
        elif kind == "image":
            _compress_image(job_id, item, db)
        else:
            raise ValueError(f"kind no comprimible: {kind}")
        _set(job_id, status="done")
    except Exception as exc:  # noqa: BLE001 - el job es best-effort
        _set(job_id, status="failed", error=str(exc))
    finally:
        db.close()


def _compress_video(job_id: str, item: Any, db: Any) -> None:
    """Video: H.264 + escala máx altura + AAC; swap solo si pesa menos."""
    if media_svc.ffmpeg_bin() is None:
        raise RuntimeError("ffmpeg no disponible")
    _set(job_id, old_size=item.size)
    comp = media_svc.compress_video(item.path)
    if comp is None:
        raise RuntimeError("la codificación falló")
    if comp[2]:  # pesó menos → swap en BD (el svc ya borró el original)
        item.path, item.size, item.mime = comp[0], comp[1], "video/mp4"
        item.duration_s = media_svc.probe_duration(item.path, "video")
        item.thumb_path = media_svc.make_thumbnail(item.path, "video")
        item.phash = media_svc.phash_for_media(item.thumb_path or "", "video")
        db.commit()
        _set(job_id, new_size=comp[1])
    else:
        _set(job_id, new_size=comp[1])  # no pesó menos: item intacto


def _compress_image(job_id: str, item: Any, db: Any) -> None:
    """Imagen: JPEG q85 (WebP q80 con alfa). Al reemplazar cambia ext/mime."""
    _set(job_id, old_size=item.size)
    comp = media_svc.compress_image(item.path)
    if comp is None:
        _set(job_id, new_size=item.size)  # bajo el umbral, o fallo benigno
        return
    if comp[2]:
        item.path, item.size = comp[0], comp[1]
        item.mime = media_svc.IMG_MIME.get(
            Path(comp[0]).suffix.lower(), item.mime
        )
        item.thumb_path = media_svc.make_thumbnail(item.path, "image")
        item.phash = media_svc.phash_for_media(item.path, "image")
        db.commit()
        _set(job_id, new_size=comp[1])
    else:
        _set(job_id, new_size=comp[1])
