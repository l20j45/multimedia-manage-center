"""Tests de jobs de compresión PERSISTIDOS (SQLite) + recuperación de huérfanos.

Corre con:  uv run pytest
"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import jobs as jobs_svc
from app.services import media as media_svc
from tests.test_media import auth, register_and_login

client = TestClient(app)


def _fat_mp4() -> bytes:
    if not media_svc.ffmpeg_bin():
        pytest.skip("ffmpeg no disponible")
    tmp = Path(settings.MEDIA_DIR) / "_j.mp4"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    media_svc._ffmpeg_run(
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
        60,
    )
    data = tmp.read_bytes()
    tmp.unlink()
    return data


def wait_job(token: str, item_id: int, timeout=40) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/media/jobs/latest/{item_id}", headers=auth(token)).json()
        if j["status"] in ("done", "failed", "lost"):
            return j
        time.sleep(0.2)
    raise AssertionError("job no terminó")


def test_job_persistido_en_bd() -> None:
    """El job existe como ROW en compression_jobs (no RAM) ya en 'queued'."""
    token = register_and_login("jobdb")
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "V", "tags": ""},
        files={"file": ("v.mp4", _fat_mp4(), "video/mp4")},
    )
    item = res.json()
    jid = item["compress_job_id"]
    assert jid

    from app.database import SessionLocal
    from app.models import CompressionJob

    db = SessionLocal()
    row = db.query(CompressionJob).filter(CompressionJob.id == jid).first()
    assert row is not None and row.kind == "video" and row.item_id == item["id"]
    db.close()

    wait_job(token, item["id"])
    db = SessionLocal()
    row = db.query(CompressionJob).filter(CompressionJob.id == jid).first()
    assert row.status == "done"
    db.close()


def test_recover_stale_marca_huerfanos() -> None:
    """Tras un 'crash' (rows running/queued), recover_stale los pone 'lost'."""
    token = register_and_login("jobrec")
    # sin ffmpeg encola nada… fuerzo el camino manual
    if not media_svc.ffmpeg_bin():
        pytest.skip("ffmpeg no disponible")
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "CR", "tags": ""},
        files={"file": ("v.mp4", _fat_mp4(), "video/mp4")},
    )
    item = res.json()
    wait_job(token, item["id"])

    # simulo un crash ANTERIOR: inserto un job colgado 'running' para el mismo item
    from app.database import SessionLocal
    from app.models import CompressionJob

    db = SessionLocal()
    ghost = CompressionJob(id="ghost12", item_id=item["id"], kind="video", status="running")
    db.add(ghost)
    db.commit()
    db.close()

    n = jobs_svc.recover_stale()
    assert n >= 1
    db = SessionLocal()
    db.expire_all()
    row = db.query(CompressionJob).filter(CompressionJob.id == "ghost12").first()
    assert row.status == "lost"
    assert "reinició" in row.error
    db.close()

    # y el endpoint lo reporta al cliente (deja de poller)
    j = client.get(f"/media/jobs/latest/{item['id']}", headers=auth(token)).json()
    assert j["job_id"] == "ghost12" and j["status"] == "lost"


def test_enqueue_idempotente_devuelve_job_activo() -> None:
    """Si el item ya tiene job en cola, re-encolar devuelve ESE job_id."""
    if not media_svc.ffmpeg_bin():
        pytest.skip("ffmpeg no disponible")
    jid1 = jobs_svc.enqueue_compress(999999, "video")
    jid2 = jobs_svc.enqueue_compress(999999, "video")
    assert jid1 == jid2
    jobs_svc.recover_stale()  # limpia el fantasma para otros tests
