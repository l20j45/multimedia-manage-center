"""Tests de rating (favoritos) y trim in/out de clips. Bórrame nunca, pytest rules."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, make_png, register_and_login

client = TestClient(app)


def test_rating_patch_filtro_y_orden() -> None:
    token = register_and_login("rate")
    files = {"file": ("a.png", make_png(), "image/png")}
    a = client.post("/media", headers=auth(token), data={"title": "A"}, files=files).json()
    files = {"file": ("b.png", make_png(), "image/png")}
    b = client.post("/media", headers=auth(token), data={"title": "B"}, files=files).json()

    # patch rating 5 y rating 0 de nuevo
    res = client.patch(f"/media/{a['id']}", headers=auth(token), json={"rating": 5})
    assert res.status_code == 200 and res.json()["rating"] == 5
    res = client.patch(f"/media/{b['id']}", headers=auth(token), json={"rating": 2})
    assert res.json()["rating"] == 2

    # rating fuera de rango → 422
    res = client.patch(f"/media/{a['id']}", headers=auth(token), json={"rating": 9})
    assert res.status_code == 422

    res = client.get("/media", params={"min_rating": 3}, headers=auth(token))
    assert res.json()["total"] == 1 and res.json()["items"][0]["title"] == "A"

    res = client.get("/media", params={"order": "rating", "direction": "desc"}, headers=auth(token))
    titles = [i["title"] for i in res.json()["items"]]
    assert titles.index("A") < titles.index("B")

    # regresar a 0 (sin estrellas)
    res = client.patch(f"/media/{a['id']}", headers=auth(token), json={"rating": 0})
    assert res.json()["rating"] == 0
    res = client.get("/media", params={"min_rating": 3}, headers=auth(token))
    assert res.json()["total"] == 0


@pytest.mark.skipif(media_svc.ffmpeg_bin() is None, reason="ffmpeg no disponible")
def test_trim_video_fragmento(monkeypatch) -> None:
    token = register_and_login("trim")
    # trim de trim: sin auto-compresión el ratio de bytes depende solo del copy
    monkeypatch.setattr(settings, "COMPRESS_ENABLED", False)
    tmp = Path(settings.MEDIA_DIR) / "_t.mp4"
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
            "testsrc=duration=4:size=64x64:rate=10",
            "-c:v",
            "mpeg4",
            str(tmp),
        ],
        check=True,
        capture_output=True,
    )
    mp4 = tmp.read_bytes()
    tmp.unlink()
    files = {"file": ("clip.mp4", mp4, "video/mp4")}
    src = client.post("/media", headers=auth(token), data={"title": "Clip 4s"}, files=files).json()

    res = client.post(
        f"/media/{src['id']}/trim",
        headers=auth(token),
        json={"start": 1.0, "end": 3.0, "title": "Meme central", "tags": ["meme"]},
    )
    assert res.status_code == 201, res.text
    frag = res.json()
    assert frag["title"] == "Meme central"
    assert frag["tags"] == ["meme"]
    assert frag["path"] != src["path"]
    assert frag["duration_s"] is not None and 1.0 <= frag["duration_s"] <= 2.5
    assert frag["size"] < src["size"] * 0.9, "el fragmento pesa menos que el entero"
    p = Path(settings.MEDIA_DIR) / frag["path"]
    assert p.exists()

    # la descripción referencia el origen
    assert "Clip 4s" in frag["description"]

    # trim end<=start → 400
    res = client.post(
        f"/media/{src['id']}/trim", headers=auth(token), json={"start": 2.0, "end": 1.0}
    )
    assert res.status_code == 400

    # trim a un PNG no aplica → 400
    files = {"file": ("img.png", make_png(), "image/png")}
    img = client.post("/media", headers=auth(token), data={"title": "img"}, files=files).json()
    res = client.post(f"/media/{img['id']}/trim", headers=auth(token), json={"start": 0, "end": 1})
    assert res.status_code == 400
