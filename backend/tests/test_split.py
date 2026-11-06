"""Tests de separación de audio por silencios (/media/{id}/split).

Corre con:  uv run pytest
Genera un WAV determinístico (stdlib `wave`) con 2 trozos de sonido
separados por silencio de 1.1s — sin depender de numpy ni filtros lavfi.
"""

import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, register_and_login

client = TestClient(app)

SR = 22050


def make_ad_wav() -> bytes:
    """0.8s sonido (500 Hz) · 1.1s silencio · 0.8s sonido (900 Hz)."""

    def seg(freq: float, seconds: float, amp: int = 20000) -> list[int]:
        n = int(SR * seconds)
        return [int(amp * math.sin(2 * math.pi * freq * (i / SR))) for i in range(n)]

    samples = seg(500, 0.8) + [0] * int(SR * 1.1) + seg(900, 0.8)
    buf = Path(settings.MEDIA_DIR) / "_ad.wav"
    buf.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(buf), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    data = buf.read_bytes()
    buf.unlink()
    return data


def upload_audio(token: str) -> dict:
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Spot grabado", "tags": "radio"},
        files={"file": ("spot.wav", make_ad_wav(), "audio/wav")},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_split_detecta_dos_partes() -> None:
    if not media_svc.ffprobe_bin():
        pytest.skip("ffprobe no disponible")
    token = register_and_login("split")
    item = upload_audio(token)
    assert item["duration_s"] is not None and 2.6 < item["duration_s"] < 3.0

    r = client.post(f"/media/{item['id']}/split", headers=auth(token), json={})
    assert r.status_code == 201, r.text
    frags = r.json()
    assert frags["total"] == 2, "dos trozos de sonido separados por el silencio"
    parts = frags["items"]
    assert parts[0]["title"] == "Spot grabado (parte 1/2)"
    assert parts[0]["tags"] == ["radio"], "hereda los tags"
    # duraciones ~0.8s cada una (con margen para frames de copy)
    for p in parts:
        assert p["kind"] == "audio"
        assert 0.5 < (p["duration_s"] or 0) <= 1.6
        assert p["size"] > 0
        # físicamente existe y es LEIBLE
        assert (media_svc.media_root() / p["path"]).exists()
    # el original queda intacto
    lista = client.get("/media", params={"limit": 100}, headers=auth(token)).json()
    orig = next(i for i in lista["items"] if i["id"] == item["id"])
    assert orig["deleted"] is False


def test_split_sin_silencios_400() -> None:
    """Un audio continuo (solo sonido) no produce partes: 400 con hint."""
    if not media_svc.ffmpeg_bin():
        pytest.skip("ffmpeg no disponible")
    token = register_and_login("split-cont")
    # wav de sonido continuo: el fetch de make_ad_wav NO sirve; genero ahora
    buf = Path(settings.MEDIA_DIR) / "_cont.wav"
    buf.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(buf), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(
            b"".join(
                struct.pack("<h", int(15000 * math.sin(2 * math.pi * 700 * (i / SR))))
                for i in range(SR * 2)
            )
        )
    data = buf.read_bytes()
    buf.unlink()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Continuo", "tags": ""},
        files={"file": ("c.wav", data, "audio/wav")},
    )
    assert res.status_code == 201
    r = client.post(f"/media/{res.json()['id']}/split", headers=auth(token), json={})
    assert r.status_code == 400
    assert "silencios" in r.json()["detail"]


def test_split_imagen_400() -> None:
    token = register_and_login("split-img")
    from tests.test_media import make_png

    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "png", "tags": ""},
        files={"file": ("p.png", make_png(), "image/png")},
    )
    assert res.status_code == 201
    r = client.post(f"/media/{res.json()['id']}/split", headers=auth(token), json={})
    assert r.status_code == 400


def test_split_parametros_valen_rango() -> None:
    """El parámetro noise_db/min_len fuera de rango → 422 (validación pydantic)."""
    token = register_and_login("split-arg")
    item = upload_audio(token)
    r = client.post(f"/media/{item['id']}/split", headers=auth(token), json={"noise_db": 50})
    assert r.status_code == 422
    r = client.post(f"/media/{item['id']}/split", headers=auth(token), json={"min_len": 0})
    assert r.status_code == 422
