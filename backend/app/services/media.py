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

import io
import shutil
import subprocess
import uuid
from datetime import UTC
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
) -> tuple[str, int, str, str]:
    """Guarda el stream del UploadFile en disco.

    Devuelve (ruta_relativa, size_bytes, mime, sha256). Lanza 413 (la router
    lo mapea) si excede MAX_UPLOAD_MB. El sha256 es del CONTENIDO: sirve para
    detectar duplicados aunque el usuario re-suba con otro nombre.
    """
    import hashlib

    from fastapi import HTTPException, status

    ext = Path(original_name).suffix.lower()
    root = media_root()
    subdir = root / str(owner_id)
    subdir.mkdir(exist_ok=True)
    rel_path = Path(str(owner_id)) / f"{uuid.uuid4().hex}{ext}"
    dst = root / rel_path

    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    hasher = hashlib.sha256()
    with dst.open("wb") as out:
        while chunk := fileobj.read(CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                dst.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Archivo excede el límite de {settings.MAX_UPLOAD_MB} MB",
                )
            hasher.update(chunk)
            out.write(chunk)
    if size == 0:
        dst.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")
    mime = mime or "application/octet-stream"
    return str(rel_path), size, mime, hasher.hexdigest()


def exif_meta(abs_path: Path, mime: str) -> tuple[str, str]:
    """(camera, fecha_orig) de los EXIF de una imagen; si no hay, ('', '')."""
    if mime not in ("image/jpeg", "image/tiff"):
        return "", ""
    try:
        from PIL import Image

        img = Image.open(abs_path)
        exif = img.getexif()
        make = str(exif.get(0x010F, "") or "")
        model = str(exif.get(0x0110, "") or "")
        date_raw = str(exif.get(0x0132, "") or "")
        camera = f"{make} {model}".strip()
        fecha = date_raw.split(" ")[0].replace(":", "-", 2) if date_raw else ""
        return camera, fecha
    except Exception:  # noqa: BLE001
        return "", ""


def ffmpeg_bin() -> str | None:
    """Ruta de ffmpeg: FFMPEG_PATH del .env si existe, si no `which`.

    (El PATH del proceso del server puede no ver mise/apps GUI — override.
    """
    if settings.FFMPEG_PATH:
        from pathlib import Path as _P

        p = _P(settings.FFMPEG_PATH)
        if p.exists():
            return str(p)
    return shutil.which("ffmpeg")


def ffprobe_bin() -> str | None:
    if settings.FFPROBE_PATH:
        from pathlib import Path as _P

        p = _P(settings.FFPROBE_PATH)
        if p.exists():
            return str(p)
    return shutil.which("ffprobe")


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
        elif kind == "audio" and ffmpeg_bin():
            cmd = [
                ffmpeg_bin(),
                "-loglevel",
                "error",
                "-i",
                str(src),
                "-filter_complex",
                "showwavespic=s=480x160:colors=#6366f1",
                "-frames:v",
                "1",
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


def extract_audio(rel_path: str, kind: str) -> str | None:
    """Extrae la pista de audio de un VIDEO → MP3 nuevo (para SFX).

    Recodifica a mp3 `-q:a 2` (universal: te sirve aunque el original sea
    AAC/opus/desktop). Devuelve la ruta relativa del audio o None.
    """
    ff = ffmpeg_bin()
    if not ff:
        return None
    root = media_root()
    src = root / rel_path
    dst_name = f"{Path(rel_path).stem}_audio_{uuid.uuid4().hex[:6]}.mp3"
    dst_abs = src.parent / dst_name
    cmd = [
        ff,
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vn",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        "-y",
        str(dst_abs),
    ]
    try:
        subprocess.run(cmd, timeout=300, check=True, capture_output=True)
    except Exception:  # noqa: BLE001
        dst_abs.unlink(missing_ok=True)
        return None
    if not dst_abs.exists():
        return None
    return str(Path(rel_path).parent / dst_name)


def trim_segment(rel_path: str, kind: str, start: float, end: float | None) -> str | None:
    """Corta [start→end] de un clip con ffmpeg -c copy → NUEVO fichero.

    Devuelve la ruta relativa del fragmento o None si no hay ffmpeg/falló.
    """
    ff = ffmpeg_bin()
    if not ff:
        return None
    root = media_root()
    src = root / rel_path
    frag_name = f"{Path(rel_path).stem}_corte_{uuid.uuid4().hex[:6]}{Path(rel_path).suffix}"
    dst_abs = src.parent / frag_name
    cmd = [ff, "-loglevel", "error", "-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += ["-i", str(src), "-c", "copy", "-y", str(dst_abs)]
    try:
        subprocess.run(cmd, timeout=300, check=True, capture_output=True)
    except Exception:  # noqa: BLE001
        dst_abs.unlink(missing_ok=True)
        return None
    if not dst_abs.exists():
        return None
    return str(Path(rel_path).parent / frag_name)


def rethumbnail_at(rel_path: str, at_seconds: float) -> str | None:
    """Regenera el thumbnail de un VIDEO tomándolo en `at_seconds`.

    Sobreescribe el thumb. Best-effort: None si no hay ffmpeg o falla.
    """
    root = media_root()
    src = root / rel_path
    dst_name = Path(rel_path).with_name(f"{Path(rel_path).stem}_t.jpg")
    dst_abs = src.parent / dst_name.name
    ff = ffmpeg_bin()
    if not ff:
        return None
    try:
        cmd = [
            ff,
            "-loglevel",
            "error",
            "-ss",
            str(max(0.0, at_seconds)),
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
    except Exception:  # noqa: BLE001
        dst_abs.unlink(missing_ok=True)
        return None
    return str(Path(rel_path).parent / dst_name.name)


def probe_duration(rel_path: str, kind: str) -> float | None:
    """Duración en segundos para audio/video via ffprobe (None si no disponible)."""
    if kind not in ("audio", "video"):
        return None
    ffprobe = ffprobe_bin()
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


def compress_video(rel_path: str) -> tuple[str, int, bool] | None:
    """Comprime un VIDEO: H.264 (COMPRESS_CRF) + escala a COMPRESS_MAX_HEIGHT
    + audio AAC (COMPRESS_AUDIO_KBPS) + faststart (sirve bien por web).

    Devuelve (ruta_final_rel, size_final, reemplazo) o None si no hay ffmpeg/
    falló:
      - reemplazo=True: el comprimido pesa MENOS → borra el original,
        la ruta final es la del comprimido (quien llama actualiza la BD).
      - reemplazo=False: NO convivió → borra el comprimido y devuelve la
        ruta original intacta (no tocar nada).
    """
    ff = ffmpeg_bin()
    if not ff:
        return None
    root = media_root()
    src = root / rel_path
    if not src.exists():
        return None
    dst_name = f"{Path(rel_path).stem}_c{uuid.uuid4().hex[:6]}.mp4"
    dst_abs = src.parent / dst_name
    cmd = [
        ff,
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-c:v",
        "libx264",
        "-crf",
        str(settings.COMPRESS_CRF),
        "-preset",
        "medium",
        "-vf",
        f"scale=-2:'min({settings.COMPRESS_MAX_HEIGHT},ih)'",
        "-c:a",
        "aac",
        "-b:a",
        f"{settings.COMPRESS_AUDIO_KBPS}k",
        "-movflags",
        "+faststart",
        "-y",
        str(dst_abs),
    ]
    try:
        # videos largos pueden tardar; 1h de margen (timeout generoso)
        subprocess.run(cmd, timeout=3600, check=True, capture_output=True)
    except Exception:  # noqa: BLE001 - compresión es best-effort
        dst_abs.unlink(missing_ok=True)
        return None
    if not dst_abs.exists() or dst_abs.stat().st_size == 0:
        dst_abs.unlink(missing_ok=True)
        return None
    new_size = dst_abs.stat().st_size
    if new_size < src.stat().st_size:
        src.unlink(missing_ok=True)
        return str(Path(rel_path).parent / dst_name), new_size, True
    dst_abs.unlink(missing_ok=True)
    return rel_path, src.stat().st_size, False


def compress_image(rel_path: str) -> tuple[str, int, bool] | None:
    """Comprime una IMAGEN (Pillow, sin ffmpeg): JPEG q85; WebP q80 si trae
    transparencia (mantiene alfa). Sólo si pesa > COMPRESS_IMG_MIN_KB.

    Mismo contrato que compress_video: (ruta_final, size, reemplazo) o None.
    Si el resultado NO pesa menos borra el comprimido y queda el original.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow es dependencia base
        return None
    root = media_root()
    src = root / rel_path
    if not src.exists() or src.stat().st_size <= settings.COMPRESS_IMG_MIN_KB * 1024:
        return None
    name = Path(rel_path)
    dst_abs: Path | None = None
    try:
        img = Image.open(src)
        has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
        ext = ".webp" if has_alpha else ".jpg"
        dst_name = f"{name.stem}_c{uuid.uuid4().hex[:6]}{ext}"
        dst_abs = src.parent / dst_name
        if has_alpha:
            img.save(dst_abs, "WEBP", quality=80)
        else:
            img.convert("RGB").save(dst_abs, "JPEG", quality=85)
    except Exception:  # noqa: BLE001 - compresión best-effort
        if dst_abs:
            dst_abs.unlink(missing_ok=True)
        return None
    finally:
        try:
            img.close()
        except Exception:  # noqa: BLE001
            pass
    if not dst_abs.exists() or dst_abs.stat().st_size == 0:
        dst_abs.unlink(missing_ok=True)
        return None
    new_size = dst_abs.stat().st_size
    if new_size < src.stat().st_size:
        src.unlink(missing_ok=True)
        return f"{name.parent / dst_name}", new_size, True
    dst_abs.unlink(missing_ok=True)
    return rel_path, src.stat().st_size, False


IMG_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def phash_image(path: Path | str, data: bytes | None = None) -> str | None:
    """Hash PERCEPTUAL dHash de 64 bits (hex de 16 chars) para imágenes.

    Gris 9x8 (LANCZOS) → cada pixel contra su vecino derecho → 64 bits.
    Robusto a re-compression/re-save: el mismo look da el MISMO hash aunque
    los bytes cambien (tu meme re-descargado / re-guardado). Pequeños
    recortes/rotaciones cambian el hash — límite honesto del método.

    `data` (bytes) o `path`; para bytes usa `phash_image_bytes`.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data) if data is not None else path)
        try:
            gray = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            raw = gray.tobytes()  # 8 filas x 9 bytes (L = 1 byte por pixel)
        finally:
            img.close()
        bits = 0
        bit_index = 0
        for row in range(8):
            start = row * 9
            for col in range(8):
                if raw[start + col] > raw[start + col + 1]:
                    bits |= 1 << bit_index
                bit_index += 1
        return f"{bits:016x}"
    except Exception:  # noqa: BLE001 - hash best-effort
        return None


def phash_image_bytes(data: bytes) -> str | None:
    """dHash directo de bytes (tests y flujos en memoria)."""
    return phash_image("", data=data)


def phash_reliable(a: str | None, b: str | None, maxbits: int = 5) -> bool:
    """True si dos hashes perceptuales son 'gemelos visuales' (<= maxbits)."""
    if not a or not b or len(a) != 16 or len(b) != 16:
        return False
    try:
        ia, ib = int(a, 16), int(b, 16)
    except ValueError:
        return False
    return bin(ia ^ ib).count("1") <= maxbits


phash_images_related = phash_reliable  # alias testable


def split_by_silence(
    rel_path: str, noise_db: int = -40, min_len: float = 1.0, max_parts: int = 100
) -> list[str] | None:
    """Separa un AUDIO en trozos por silencios (poder del `silencedetect`).

    Cada rango de sonido continuo (entre silencios >= min_len) se corta con
    `trim_segment` (-c copy: rapido, sin recodificar). Devuelve las rutas
    relativas de los fragmentos o None si no hay ffmpeg/falló.
    """
    import re

    ff = ffmpeg_bin()
    if not ff:
        return None
    src = media_root() / rel_path
    try:
        res = subprocess.run(
            [
                ff,
                "-hide_banner",
                "-nostats",
                "-i",
                str(src),
                "-af",
                f"silencedetect=noise={noise_db}dB:d={min_len}",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=300,
            text=True,
        )
    except Exception:  # noqa: BLE001
        return None
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", res.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    if not starts:
        return []  # sin silencios: el audio es continuo, nada que separar
    duration = probe_duration(rel_path, "audio")

    # Rangos de sonido = lo que queda ENTRE silencios.
    ranges: list[tuple[float, float | None]] = []
    cursor = 0.0
    for i, s in enumerate(starts):
        if s > cursor:
            ranges.append((cursor, s))
        cursor = ends[i] if i < len(ends) else None
        if cursor is None:
            break
    if cursor is not None and duration is not None and cursor < duration - 0.05:
        ranges.append((cursor, duration))

    frags: list[str] = []
    for start, end in ranges[:max_parts]:
        start = max(0.0, start)
        if end is not None and end - start < 0.05:
            continue
        rel = trim_segment(rel_path, "audio", start, end)
        if rel:
            frags.append(rel)
    return frags


def delete_files(rel_paths: list[str | None]) -> None:
    """Borra ficheros físicos (best-effort): main + thumbs de un item."""
    for rel in rel_paths:
        if not rel:
            continue
        p = media_root() / rel
        p.unlink(missing_ok=True)


def backfill_hashes() -> int:
    """Recalcula hashes de items que quedaron sin ellos (uploads legacy).

    Corre al arrancar el backend (silencioso) activos: sha256 que quedó
    None INVISIBLE para el detector de duplicados y phash de imágenes para
    el lab de gemelos visuales. Devuelve la cantidad de filas tocadas.
    """
    import hashlib

    from app.database import SessionLocal
    from app.models import MediaItem

    root = media_root()
    db = SessionLocal()
    n = 0
    try:
        rows = (
            db.query(MediaItem)
            .filter(
                MediaItem.deleted_at.is_(None),
                (MediaItem.sha256.is_(None)) | (MediaItem.phash.is_(None)),
            )
            .all()
        )
        for it in rows:
            path = root / it.path
            if not path.is_file():
                continue
            touched = False
            if it.sha256 is None:
                h = hashlib.sha256()
                with path.open("rb") as f:
                    for chunk in iter(lambda: f.read(CHUNK), b""):
                        h.update(chunk)
                it.sha256 = h.hexdigest()
                touched = True
            if it.kind == "image" and it.phash is None:
                it.phash = phash_image(path)
                touched = touched or it.phash is not None
            if touched:
                n += 1
        if n:
            db.commit()
    finally:
        db.close()
    return n


def purge_expired_trash(max_age_days: int | None = None) -> int:
    """Purga DEFINITIVA de lo que lleva más de N días en la papelera.

    Se corre al arrancar el backend (main.py, silencioso). Devuelve la
    cantidad purgada. max_age_days override para tests.
    """
    from datetime import datetime, timedelta

    from app.database import SessionLocal
    from app.models import CollectionItem, MediaItem

    days = max_age_days if max_age_days is not None else settings.TRASH_RETENTION_DAYS
    cutoff = datetime.now(UTC) - timedelta(days=days)
    db = SessionLocal()
    try:
        expired = (
            db.query(MediaItem)
            .filter(MediaItem.deleted_at.is_not(None), MediaItem.deleted_at < cutoff)
            .all()
        )
        if not expired:
            return 0
        files: list[str | None] = []
        for it in expired:
            files.extend([it.path, it.thumb_path])
        ids = [it.id for it in expired]
        db.query(CollectionItem).filter(CollectionItem.media_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(MediaItem).filter(MediaItem.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        delete_files(files)
        return len(ids)
    finally:
        db.close()
