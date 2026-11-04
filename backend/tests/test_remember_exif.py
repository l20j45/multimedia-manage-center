"""Tests: 'Recordarme' de 30 días y regeneración de thumbnail + EXIF."""

import io
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, make_png, register_and_login

client = TestClient(app)


def test_login_remember_token_de_30_dias() -> None:
    email = "remember@example.com"
    client.post("/auth/register", json={"email": email, "password": "clavelarga123"})

    res = client.post("/auth/login", data={"username": email, "password": "clavelarga123"})
    tok_normal = res.json()["access_token"]

    res = client.post(
        "/auth/login",
        data={"username": email, "password": "clavelarga123", "remember": "true"},
    )
    tok_30d = res.json()["access_token"]

    decode_1 = jwt.decode(
        tok_normal,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": False},
    )
    decode_2 = jwt.decode(
        tok_30d, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False}
    )
    exp_n = datetime.fromtimestamp(decode_1["exp"], tz=UTC)
    exp_2 = datetime.fromtimestamp(decode_2["exp"], tz=UTC)
    vida_n = exp_n - datetime.now(UTC)
    vida_2 = exp_2 - datetime.now(UTC)
    assert vida_n < timedelta(days=2)
    assert timedelta(days=29) < vida_2 < timedelta(days=31)


def test_rethumb_regenera_cualquier_tipo(monkeypatch) -> None:
    """Audio sin thumb (ffmpeg faltaba) → regenera la waveform sin re-subir."""
    token = register_and_login("rethumb")
    monkeypatch.setattr(media_svc, "ffmpeg_bin", lambda: None)
    wav = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVEfmt " + b"\x00" * 40
    files = {"file": ("sfx sin thumb.wav", wav, "audio/wav")}
    a = client.post(
        "/media", headers=auth(token), data={"title": "Sfx sin thumb"}, files=files
    ).json()
    assert a["has_thumb"] is False

    # con ffmpeg de vuelta: regenerar
    if media_svc.ffmpeg_bin():
        res = client.post(f"/media/{a['id']}/rethumb", headers=auth(token), json={})
        assert res.status_code == 200
        assert res.json()["has_thumb"] is True
    else:
        # sin ffmpeg en PATH: 503 y NO mangle del estado
        res = client.post(f"/media/{a['id']}/rethumb", headers=auth(token), json={})
        assert res.status_code == 503

    # imagen: rethumb (la copia jpg del origen reescala) — camino sin ffmpeg con Pillow
    files = {"file": ("img.png", make_png(), "image/png")}
    img = client.post("/media", headers=auth(token), data={"title": "img"}, files=files).json()
    # invalida thumb_path para forzar la regeneración
    from app.database import SessionLocal
    from app.models import MediaItem

    db = SessionLocal()
    row = db.query(MediaItem).filter(MediaItem.id == img["id"]).first()
    row.thumb_path = None
    db.commit()
    db.close()
    res = client.post(f"/media/{img['id']}/rethumb", headers=auth(token), json={})
    assert res.status_code == 200
    assert res.json()["has_thumb"] is True


def _jpeg_con_exif(make: str, model: str) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (80, 80), (120, 40, 90))
    exif = img.getexif()
    exif[0x010F] = make  # Make
    exif[0x0110] = model  # Model
    exif[0x0132] = "2026:11:03 20:15:00"  # DateTime
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_exif_camera_y_fecha_a_meta_en_upload() -> None:
    token = register_and_login("exif")
    files = {"file": ("foto.jpg", _jpeg_con_exif("Sony", "a7 III"), "image/jpeg")}
    res = client.post("/media", headers=auth(token), data={"title": "Foto"}, files=files)
    assert res.status_code == 201
    item = res.json()
    assert item["meta"]["camera"] == "Sony a7 III"
    assert item["meta"]["tomada_el"] == "2026-11-03"

    # PNG sin EXIF → meta None (no inventa)
    files = {"file": ("sin-exif.png", make_png(), "image/png")}
    another = client.post(
        "/media", headers=auth(token), data={"title": "Sin exif"}, files=files
    ).json()
    assert another["meta"] is None
