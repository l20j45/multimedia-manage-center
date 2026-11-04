"""Auto-tagging de recursos: sugerencias de tags para un MediaItem.

Dos niveles (degradación elegante):
1. HEURÍSTICA (siempre disponible): datos objetivos del fichero + keywords del
   nombre — duración (sfx corto vs clip largo), orientación, resolución,
   familia de formato, tokens del nombre original ("whoosh", "impact-02"...).
2. VISUAL (opcional): si GEMINI_API_KEY está en backend/.env, llama a Gemini
   Flash con el thumbnail/fichero para describir contenido → tags en español-
   inglés corto. Nunca bloquea la subida: errores → heurística.

Las sugerencias NUNCA se aplican solas: el router las devuelve y la UI las
muestra como chips clicables (el usuario decide qué aplicar).
"""

import json
import re
import urllib.request
from pathlib import Path

from app.config import settings
from app.models import MediaItem
from app.services.media import media_root


def heuristic_tags(item: MediaItem) -> list[str]:
    """Tags objetivos a partir de datos que ya conocemos, sin modelo."""
    tags: list[str] = []

    # duración / familia de uso
    dur = item.duration_s
    if item.kind == "audio":
        if dur is not None and dur <= 5:
            tags.append("sfx-corto")
        elif dur is not None and dur <= 20:
            tags.append("sfx")
        elif item.size < 2 * 1024 * 1024:
            tags.append("sfx-corto")  # pequeño sin ffprobe: casi seguro un SFX
        else:
            tags.append("audio-largo")
    elif item.kind == "video":
        if dur is not None and dur <= 10:
            tags.append("clip-corto")
        elif dur is not None and dur <= 60:
            tags.append("clip")
        else:
            tags.append("video-largo")
    elif item.kind == "image":
        tags.append("imagen")

    # tamaño/aspecto (si ffmpeg puede leer dimensiones)
    if item.kind in ("image", "video"):
        dims = _probe_dimensions(item)
        if dims:
            w, h = dims
            if h > w:
                tags.append("vertical")
            elif w > h * 1.6:
                tags.append("panoramico")
            if max(w, h) >= 2500:
                tags.append("hd")
            if max(w, h) <= 480:
                tags.append("low-res")

    # keywords del nombre original (whoosh, explosion, intro-canal.mp4...)
    stem = Path(item.filename).stem.lower()
    words = re.split(r"[-_ \.\d]+", stem)
    noise = {
        "mp4",
        "mp3",
        "png",
        "jpg",
        "final",
        "copy",
        "nuevo",
        "video",
        "audio",
        "img",
        "screenshot",
    }
    for w in words:
        w = w.strip()
        if len(w) >= 3 and w.isalnum() and w not in noise:
            tags.append(w)

    # dedup + límite
    seen: dict[str, None] = {}
    for t in tags[:18]:
        seen.setdefault(t, None)
    return list(seen)


def _probe_dimensions(item: MediaItem) -> tuple[int, int] | None:
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        import subprocess

        res = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(media_root() / item.path),
            ],
            capture_output=True,
            timeout=30,
            text=True,
            check=True,
        )
        streams = json.loads(res.stdout).get("streams") or []
        if streams and streams[0].get("width") and streams[0].get("height"):
            return int(streams[0]["width"]), int(streams[0]["height"])
    except Exception:  # noqa: BLE001
        pass
    return None


def gemini_tags(item: MediaItem) -> list[str] | None:
    """Tags via Gemini vision (solo si GEMINI_API_KEY). None sin llave/error."""
    import base64

    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key:
        return None
    src = media_root() / (item.thumb_path or item.path)
    if not src.exists():
        return None
    mime = "image/jpeg" if src.suffix.lower() in {".jpg", ".jpeg"} else item.mime
    data_bytes = src.read_bytes()
    # imágenes muy pesadas: reescala en memoria antes de mandar
    if len(data_bytes) > 1.5 * 1024 * 1024 and item.kind == "image":
        try:
            import io

            from PIL import Image

            img = Image.open(src).convert("RGB")
            img.thumbnail((512, 512))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)
            data_bytes, mime = buf.getvalue(), "image/jpeg"
        except Exception:  # noqa: BLE001
            return None
    prompt = (
        "Describe este recurso de una biblioteca de edición de video/memes con "
        "3 a 6 TAGS MUY CORTAS en minúsculas (español o jerga de YouTube/TikTok: "
        "meme, sfx, whoosh, b-roll, intro, outro, risa, glitch, transición...). "
        'Responde SOLO JSON: {"tags": ["a","b"]}'
    )
    b64 = base64.b64encode(data_bytes).decode()
    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 120},
        }
    ).encode()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={key}"
    )
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        m = re.search(r"\{.*\}", text, re.DOTALL)
        tags_raw = json.loads(m.group(0))["tags"] if m else []
        out: list[str] = []
        for t in tags_raw[:8]:
            t = str(t).strip().lower().replace(" ", "-")
            if 2 <= len(t) <= 24 and re.fullmatch(r"[a-z0-9-]+", t):
                out.append(t)
        return list(dict.fromkeys(out))
    except Exception:  # noqa: BLE001 — nunca rompe la app
        return None


def _compact_copy(item: MediaItem) -> Path | None:
    """Copia JPEG ≤ 300KB del thumb para mandar al modelo (o None)."""
    try:
        from PIL import Image

        src = media_root() / (item.thumb_path or item.path)
        if src.suffix.lower() == ".jpg":
            return src
        out = src.with_name(src.stem + "_ai.jpg")
        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail((512, 512))
            img.save(out, "JPEG", quality=80)
        return out
    except Exception:  # noqa: BLE001
        return None


def suggest_tags(item: MediaItem) -> list[str]:
    """Union de heurística + visual (visual solo si la llave está)."""
    base = heuristic_tags(item)
    gemini = gemini_tags(item)
    if gemini:
        seen: dict[str, None] = {}
        for t in [*base, *gemini]:
            if len(seen) >= 20:
                break
            seen.setdefault(t, None)
        return list(seen)
    return base
