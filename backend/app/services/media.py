"""Servicio de almacenamiento de la biblioteca: ficheros, thumbnails, duración.

Los ficheros viven en MEDIA_DIR (config) organizados por owner:
  MEDIA_DIR/{owner_id}/{uuid}{ext} y MEDIA_DIR/{owner_id}/thumbs/{uuid}_t.jpg
Las rutas de BD se guardan RELATIVAS a MEDIA_DIR (portables si se mueve la carpeta).

Thumbnails:
  - imagen: Pillow (misma dependencia del venv, siempre disponible)
  - video: primer frame via ffmpeg (binario externo; si no está, queda None
    y la UI muestra el ícono del tipo)
  - audio: sin thumbnail (la UI muestra reproductor)
"""

import shutil
import subprocess
import uuid
from pathlib import Path

from app.config import settings

# Categorías por extensión (minúsculas, sin punto)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".aac", ".opus", ".weba"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}

CHUNK = 1024 * 1024  # stream de 1 MB al guardar


def detect_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    raise ValueError(f"Extensión de archivo no soportada: {ext or '(sin extensión)'}")


def media_root() -> Path:
    """Carpeta base de ficheros (creada on-demand)."""
    root = Path(settings.MEDIA_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_stream(
    fileobj, original_name: str, owner_id: int, mime: str | None = None
) -> tuple[str, int, str]:
    """Guarda el stream del UploadFile en disco.

    Devuelve (ruta_relativa, size_bytes, mime). Lanza 413 (HTTPException mapeada
    en el router) si excede MAX_UPLOAD_MB.
    """
    from fastapi import HTTPException, status

    ext = Path(original_name).suffix.lower()
    root = media_root()
    subdir = root / str(owner_id)
    subdir.mkdir(exist_ok=True)
    rel_path = Path(str(owner_id)) / f"{uuid.uuid4().hex}{ext}"
    dst = root / rel_path

    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with dst.open("wb") as out:
        while chunk := fileobj.read(CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                dst.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Archivo excede el límite de {settings.MAX_UPLOAD_MB} MB",
                )
            out.write(chunk)
    if size == 0:
        dst.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")
    mime = mime or "application/octet-stream"
    return str(rel_path), size, mime


def ffmpeg_bin() -> str | None:
    """Ruta de ffmpeg si está disponible en PATH (si no, None): degradación suave."""
    return shutil.which("ffmpeg")


def make_thumbnail(rel_path: str, kind: str) -> str | None:
    """Genera thumbnail y devuelve su ruta RELATIVA a MEDIA_DIR (o None).

    Imagen: copia reducida máx 512px. Video: primer frame con ffmpeg.
    Nunca lanza: una biblioteca no puede fallar por un thumb deficiente.
    """
    root = media_root()
    src = root / rel_path
    dst_name = Path(rel_path).with_name(f"{Path(rel_path).stem}_t.jpg")
    dst_abs = src.parent / dst_name.name

    try:
        if kind == "image":
            from PIL import Image

            with Image.open(src) as img:
                img = img.convert("RGB")
                img.thumbnail((512, 512))
                img.save(dst_abs, "JPEG", quality=85)
        elif kind == "video" and ffmpeg_bin():
            cmd = [
                ffmpeg_bin(),
                "-loglevel",
                "error",
                "-ss",
                "0",
                "-i",
                str(src),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(512,iw)':-2",
                "-y",
                str(dst_abs),
            ]
            subprocess.run(cmd, timeout=60, check=True, capture_output=True)
            if not dst_abs.exists():
                return None
        else:
            return None
    except Exception:  # noqa: BLE001 - el thumb es best-effort
        dst_abs.unlink(missing_ok=True)
        return None
    return str(Path(rel_path).parent / dst_name.name)


def probe_duration(rel_path: str, kind: str) -> float | None:
    """Duración en segundos para audio/video via ffprobe (None si no disponible)."""
    if kind not in ("audio", "video"):
        return None
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    src = media_root() / rel_path
    try:
        res = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(src),
            ],
            capture_output=True,
            check=True,
            timeout=30,
            text=True,
        )
        return round(float(res.stdout.strip()), 2)
    except Exception:  # noqa: BLE001
        return None


def delete_files(rel_paths: list[str | None]) -> None:
    """Borra ficheros físicos (best-effort): main + thumbs de un item."""
    for rel in rel_paths:
        if not rel:
            continue
        p = media_root() / rel
        p.unlink(missing_ok=True)
