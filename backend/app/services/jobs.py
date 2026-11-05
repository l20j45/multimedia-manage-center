"""Cola en background para compresión de video: no bloquea la petición HTTP.

Diseño:
- ThreadPoolExecutor de 2 hilos (ffmpeg suelta el GIL; 2 reencodes a la vez
  satura razonablemente sin dejar el equipo sin aire).
- Registry en RAM: job activo MÁXIMO uno por item (idempotente: si el item
  ya tiene un job queued/running, se devuelve ese mismo job_id).
- El worker hace TODO con su propia sesión de BD (sesiones de FastAPI no
  viajan a threads). El original se reemplaza solo si pesa menos — igual
  que la versión síncrona.
- Estado en RAM: al reiniciar el server se pierde (el item queda intacto o
  ya comprimido; recomprimir con el botón es idempotente y seguro).
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services import media as media_svc

# {job_id: {job_id, item_id, status: queued|running|done|failed,
#           old_size, new_size, error}}
_jobs: dict[str, dict[str, Any]] = {}
_last_by_item: dict[int, str] = {}
_lock = threading.Lock()

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="compress")


def enqueue_compress(item_id: int) -> str:
    """Encarga la compresión de un item. Devuelve el job_id (idempotente)."""
    with _lock:
        prev = _last_by_item.get(item_id)
        if prev and _jobs.get(prev, {}).get("status") in ("queued", "running"):
            return prev
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {
            "job_id": job_id,
            "item_id": item_id,
            "status": "queued",
            "old_size": None,
            "new_size": None,
            "error": None,
        }
        _last_by_item[item_id] = job_id
    _executor.submit(_run, job_id, item_id)
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def latest_job(item_id: int) -> dict[str, Any] | None:
    """Último job del item (cualquier estado), o None si nunca comprimió."""
    with _lock:
        jid = _last_by_item.get(item_id)
        job = _jobs.get(jid) if jid else None
        return dict(job) if job else None


def _set(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run(job_id: str, item_id: int) -> None:
    """Worker: comprime el item y actualiza su BD (sesión propia)."""
    from app.database import SessionLocal
    from app.models import MediaItem

    _set(job_id, status="running")
    db = SessionLocal()
    try:
        item = db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item or item.kind != "video" or item.deleted_at is not None:
            raise ValueError("item no disponible para comprimir")
        _set(job_id, old_size=item.size)
        comp = media_svc.compress_video(item.path)
        if comp is None:
            raise RuntimeError("ffmpeg no disponible o la codificación falló")
        if comp[2]:  # pesó menos → swap en BD (el svc borró el original)
            item.path, item.size, item.mime = comp[0], comp[1], "video/mp4"
            item.duration_s = media_svc.probe_duration(item.path, "video")
            item.thumb_path = media_svc.make_thumbnail(item.path, "video")
            db.commit()
            _set(job_id, new_size=comp[1])
        else:
            _set(job_id, new_size=comp[1])  # no pesó menos: item intacto, sin error
        _set(job_id, status="done")
    except Exception as exc:  # noqa: BLE001 - el job es best-effort
        _set(job_id, status="failed", error=str(exc))
    finally:
        db.close()
