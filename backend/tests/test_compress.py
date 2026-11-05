"""Tests de compresión de video ASYNC: cola background + notificación.

Corre con:  uv run pytest
Genera un mp4 real con ffmpeg (skip si no hay ffmpeg en el entorno).

La subida NO comprime en línea: devuelve el item con compress_job_id y
el cliente consulta GET /media/jobs/latest/{id} hasta done/failed.
"""

import subprocess
import time
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
    """Mp4 fuente pesado (mpeg4 qscale 1 sobre mandelbrot, contenido real)."""
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


def wait_job(token: str, item_id: int, timeout_s: float = 60) -> dict:
    """Polls /jobs/latest hasta done|failed ( parade de tests para tareas web)."""
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        r = client.get(f"/media/jobs/latest/{item_id}", headers=auth(token))
        assert r.status_code == 200, r.text
        last = r.json()
        if last["status"] in ("done", "failed"):
            return last
        time.sleep(0.25)
    pytest.fail(f"job no terminó en {timeout_s}s: status={last.get('status')}")


def fetch_item(token: str, item_id: int) -> dict:
    """Recarga el item del listado (no hay GET unitario; así evitamos añadirlo)."""
    res = client.get("/media", params={"limit": 200}, headers=auth(token))
    assert res.status_code == 200
    for it in res.json()["items"]:
        if it["id"] == item_id:
            return it
    pytest.fail(f"item {item_id} no encontrado en el listado")


def upload_mp4(token: str, name: str, title: str) -> dict:
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": title, "tags": ""},
        files={"file": (name, make_fat_mp4(), "video/mp4")},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_upload_video_encola_job_y_avisa_id() -> None:
    """Upload de video → 201 inmediato + compress_job_id para la notificación."""
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
    assert item["compress_job_id"], "el upload devuelve el job para pollear"
    assert item["size"] == len(mp4), "201 con el ORIGINAL (compresión es async)"

    job = wait_job(token, item["id"])
    assert job["status"] == "done", job["error"] or job
    final = fetch_item(token, item["id"])
    assert final["size"] < len(mp4), "al terminar, la BD guarda el comprimido"
    assert final["mime"] == "video/mp4"
    assert (media_svc.media_root() / final["path"]).exists()


def test_compress_endpoint_202_y_notifica_bajada(monkeypatch) -> None:
    """POST /compress → 202 {job_id} sin esperar; done tras el poll."""
    _require_ffmpeg()
    token = register_and_login("compress")
    # sube SIN compresión en cola para comprimir solo con el botón
    monkeypatch.setattr(settings, "COMPRESS_ENABLED", False)
    item = upload_mp4(token, "pesado.mp4", "Pesado")
    assert item["compress_job_id"] is None

    r = client.post(f"/media/{item['id']}/compress", headers=auth(token))
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]

    job = wait_job(token, item["id"])
    assert job["job_id"] == jid
    assert job["status"] == "done"
    final = fetch_item(token, item["id"])
    assert final["size"] < item["size"] * 0.9, "mandelbrot consigue menos peso"
    assert final["mime"] == "video/mp4"


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
    """Re-comprimir no agranda: la 2ª pasada deja <= la 1ª (solo swap si pesa menos)."""
    _require_ffmpeg()
    token = register_and_login("compress-2")
    item = upload_mp4(token, "dos.mp4", "Dos")
    assert item["compress_job_id"], "auto encola"
    wait_job(token, item["id"])
    after1 = fetch_item(token, item["id"])

    r = client.post(f"/media/{item['id']}/compress", headers=auth(token))
    assert r.status_code == 202
    job = wait_job(token, item["id"])
    assert job["status"] == "done"
    after2 = fetch_item(token, item["id"])
    assert after2["size"] <= after1["size"], "la 2ª pasada nunca agranda"


def test_compresion_deshabilitada_sin_job(monkeypatch) -> None:
    """COMPRESS_ENABLED=0: upload guarda el tal cual y NO encola job."""
    _require_ffmpeg()
    monkeypatch.setattr(settings, "COMPRESS_ENABLED", False)
    token = register_and_login("compress-off")
    item = upload_mp4(token, "sin.mp4", "Sin compresion")
    assert item["compress_job_id"] is None
    assert item["size"] > 0
    job = client.get(f"/media/jobs/latest/{item['id']}", headers=auth(token)).json()
    assert job["status"] == "none"
