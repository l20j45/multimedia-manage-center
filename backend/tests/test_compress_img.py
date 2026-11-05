"""Tests de compresión de IMÁGENES en cola background (Pillow, sin ffmpeg).

Corre con:  uv run pytest
"""

import io
import time

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, register_and_login

client = TestClient(app)


def wait_job(token: str, item_id: int, timeout_s: float = 30) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        last = client.get(f"/media/jobs/latest/{item_id}", headers=auth(token)).json()
        if last["status"] in ("done", "failed"):
            return last
        time.sleep(0.15)
    raise AssertionError(f"job no terminó: {last}")


def big_png(kb_target: int = 500) -> bytes:
    """PNG plano grande: cuadros de colores pseudo-aleatorios (fotos-like)."""
    import random

    rng = random.Random(42)
    n = 400 if kb_target == 500 else int(kb_target)
    img = Image.new("RGB", (n, n))
    for y in range(n):
        for x in range(n):
            img.putpixel((x, y), (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_upload_imagen_grande_encola_y_pasa_a_jpeg() -> None:
    """Upload de PNG pesado → job en cola → termina re-encodeada a JPEG."""
    token = register_and_login("imgcomp")
    data = big_png()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Grande", "tags": ""},
        files={"file": ("g.png", data, "image/png")},
    )
    assert res.status_code == 201, res.text
    item = res.json()
    assert item["compress_job_id"], "imagen en cola"
    job = wait_job(token, item["id"])
    assert job["status"] == "done", job["error"] or job

    # el item ya apunta a un JPEG más chico (el ruido PNG es lo PEOR caso)
    lista = client.get("/media", params={"limit": 100}, headers=auth(token)).json()
    it = next(i for i in lista["items"] if i["id"] == item["id"])
    assert it["mime"] == "image/jpeg"
    assert it["size"] < item["size"]
    assert it["path"].endswith(".jpg")
    assert (media_svc.media_root() / it["path"]).exists()
    assert it["has_thumb"], "thumb regenerado del nuevo archivo"


def test_upload_imagen_chica_no_comprime() -> None:
    """Del trabajo de make_png() test_media (pocos KB): sin job, tal cual."""
    from tests.test_media import make_png

    token = register_and_login("imgsmall")
    data = make_png()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Chica", "tags": ""},
        files={"file": ("p.png", data, "image/png")},
    )
    assert res.status_code == 201
    item = res.json()
    assert item["compress_job_id"] is None, "bajo el umbral: no encola"
    assert item["mime"] == "image/png"


def test_compress_imagen_endpoint_202(monkeypatch) -> None:
    """POST /compress en imagen → 202 + job finishes con swap si conviene."""
    monkeypatch.setattr(settings, "COMPRESS_IMG_MIN_KB", 1)  # fuerzo umbral bajo
    token = register_and_login("imgcomp2")
    data = big_png(200)
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Medio", "tags": ""},
        files={"file": ("m.png", data, "image/png")},
    )
    assert res.status_code == 201
    monkeypatch.setattr(settings, "COMPRESS_ENABLED", False)  # no auto: a mano
    item = res.json()

    r = client.post(f"/media/{item['id']}/compress", headers=auth(token))
    assert r.status_code == 202, r.text
    job = wait_job(token, item["id"])
    assert job["status"] == "done"


def test_compress_audio_400() -> None:
    """Audios no se comprimen (ya están recodificados); 400."""
    token = register_and_login("imgcomp3")
    buf = b"RIFF" + b"\x00" * 50 + b"WAVEfmt "
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "wav", "tags": ""},
        files={"file": ("s.wav", buf, "audio/wav")},
    )
    assert res.status_code == 201
    r = client.post(f"/media/{res.json()['id']}/compress", headers=auth(token))
    assert r.status_code == 400
