"""Tests de compresión de video: auto al subir + endpoint /compress.

Corre con:  uv run pytest
Genera un mp4 real con ffmpeg (skip si no hay ffmpeg en el entorno).
"""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, register_and_login

client = TestClient(app)


def _require_ffmpeg():
    if not media_svc.ffmpeg_bin():
        pytest.skip("ffmpeg no disponible")


def make_fat_mp4() -> bytes:
    """Mp4 fuente pesado (mpeg4 qscale 1 sobre mandelbrot, contenido real).

    Grande a propósito: el re-encode H.264 crf 26 sobre contenido orgánico
    lo reduce con margen de sobra.
    """
    tmp = Path(settings.MEDIA_DIR) / "_fat.mp4"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            media_svc.ffmpeg_bin(),
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "mandelbrot=s=320x240",
            "-c:v",
            "mpeg4",
            "-qscale:v",
            "1",
            "-t",
            "2",
            str(tmp),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    data = tmp.read_bytes()
    tmp.unlink()
    return data


def test_upload_video_comprime_auto() -> None:
    """Con COMPRESS_ENABLED (default): el upload deja un mp4 re-encodeado."""
    _require_ffmpeg()
    token = register_and_login("compress-auto")
    mp4 = make_fat_mp4()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Pesado", "tags": ""},
        files={"file": ("pesado.mp4", mp4, "video/mp4")},
    )
    assert res.status_code == 201, res.text
    item = res.json()
    # el re-encode reduces el mandelbrot ~30%+, y en especial el original fat
    assert item["size"] < len(mp4), "auto-compresión redujo el original"
    assert (media_svc.media_root() / item["path"]).exists()


def test_compress_endpoint_reemplaza_y_actualiza_bd(monkeypatch) -> None:
    """POST /compress: re-encodea, cambia path/size/mime y libera espacio."""
    _require_ffmpeg()
    token = register_and_login("compress")
    mp4 = make_fat_mp4()
    # sube SIN compresión para comprimir solo el item real (no dos pasadas)
    monkeypatch.setattr(settings, "COMPRESS_ENABLED", False)
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Pesado", "tags": ""},
        files={"file": ("pesado.mp4", mp4, "video/mp4")},
    )
    assert res.status_code == 201, res.text
    item = res.json()

    r = client.post(f"/media/{item['id']}/compress", headers=auth(token))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["mime"] == "video/mp4"
    if out["size"] < item["size"]:
        # reemplazó: mandelbrot consigue ≥30% menos
        assert out["size"] < item["size"] * 0.7

    root = media_svc.media_root()
    assert (root / out["path"]).exists()
    assert (root / out["path"]).stat().st_size == out["size"]


def test_compress_video_no_video_400() -> None:
    token = register_and_login("compress-nv")
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


def test_compress_idempotente_no_expande() -> None:
    """Comprimir algo ya comprimido: o reduce o deja el original intacto."""
    _require_ffmpeg()
    token = register_and_login("compress-2")
    mp4 = make_fat_mp4()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Dos", "tags": ""},
        files={"file": ("dos.mp4", mp4, "video/mp4")},
    )
    assert res.status_code == 201
    item = res.json()
    r1 = client.post(f"/media/{item['id']}/compress", headers=auth(token))
    assert r1.status_code == 200
    after1 = r1.json()
    r2 = client.post(f"/media/{item['id']}/compress", headers=auth(token))
    assert r2.status_code == 200
    after2 = r2.json()
    assert after2["size"] <= after1["size"], "la 2ª pasada nunca agranda"


def test_compresion_deshabilitada_no_comprime(monkeypatch) -> None:
    """COMPRESS_ENABLED=0: el upload guarda el tal cual (sin re-encode)."""
    _require_ffmpeg()
    monkeypatch.setattr(settings, "COMPRESS_ENABLED", False)
    token = register_and_login("compress-off")
    mp4 = make_fat_mp4()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Sin compresion", "tags": ""},
        files={"file": ("sin.mp4", mp4, "video/mp4")},
    )
    assert res.status_code == 201, res.text
    item = res.json()
    assert item["size"] == len(mp4), "guarda el archivo tal cual subió"
