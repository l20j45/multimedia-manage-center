"""Tests /media: subida, búsqueda por nombre/tags, edición, descarga y borrado.

Los ficheros de prueba se escriben en un MEDIA_DIR temporal (monkeypatch).
Corre con:  uv run pytest
"""

import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.services import media as media_svc

client = TestClient(app)


def make_png() -> bytes:
    """PNG 64x64 válido generado con Pillow (dependencia del proyecto)."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def tmp_media_dir(tmp_path, monkeypatch) -> Path:
    """MEDIA_DIR por test: ningún fichero toca el disco del proyecto."""
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


def register_and_login(user: str) -> str:
    email = f"{user}-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/auth/register", json={"email": email, "password": "clavelarga123", "name": user}
    )
    assert res.status_code == 201, res.text
    res = client.post("/auth/login", data={"username": email, "password": "clavelarga123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload(client_: TestClient, token: str, name: str, title: str, tags: str) -> dict:
    data = {"title": title, "tags": tags}
    files = {"file": (name, make_png(), "image/png")}
    res = client_.post("/media", headers=auth(token), data=data, files=files)
    assert res.status_code == 201, res.text
    return res.json()


def test_subida_busqueda_por_nombre_y_tags() -> None:
    """Sube dos recursos y los encuentra por título y por tag."""
    token = register_and_login("media")

    first = upload(client, token, "logo principal.png", "Intro Amaro", "intro,logo")
    upload(client, token, "trailer png.png", "Traileraycast", "trailer")

    assert first["kind"] == "image"
    assert first["tags"] == ["intro", "logo"]
    assert first["has_thumb"] is True
    assert Path(settings.MEDIA_DIR, first["path"]).exists(), "el fichero físico existe"

    # Por nombre (ilike, parcial)
    res = client.get("/media", params={"q": "intro amaro"}, headers=auth(token))
    assert res.status_code == 200
    assert res.json()["total"] == 1

    # Por tag embebido en la búsqueda general (q matchea título O tags)
    res = client.get("/media", params={"q": "trailer"}, headers=auth(token))
    assert res.json()["total"] == 1
    res = client.get("/media", params={"q": "logo"}, headers=auth(token))
    assert res.json()["total"] == 1

    # Filtro por kind
    res = client.get("/media", params={"kind": "audio"}, headers=auth(token))
    assert res.json()["total"] == 0
    res = client.get("/media", params={"kind": "image"}, headers=auth(token))
    assert res.json()["total"] == 2
    # Filtro por tag dedicado
    res = client.get("/media", params={"tag": "intro"}, headers=auth(token))
    assert res.json()["total"] == 1

    # Listado de tags con conteo
    res = client.get("/media/tags", headers=auth(token))
    assert {t["tag"] for t in res.json()} == {"intro", "logo", "trailer"}
    assert res.json()[0]["count"] >= 1


def test_thumbnails_audio_video_degradacion_suave(monkeypatch) -> None:
    """Audio: sin thumb; video: no explota si ffmpeg no está disponible."""
    token = register_and_login("avmedia")

    monkeypatch.setattr(media_svc, "ffmpeg_bin", lambda: None)
    audio = upload(client, token, "sfx whoosh.wav", "Whoosh", "sfx")
    assert audio["kind"] == "audio"
    assert audio["has_thumb"] is False
    # Sin thumbnail el endpoint responde 404 (la UI muestra su ícono)
    res = client.get(f"/media/{audio['id']}/thumb?access_token={token}")
    assert res.status_code == 404

    video = upload(client, token, "clip B-roll.mp4", "B-roll calle", "b-roll,exterior")
    assert video["kind"] == "video"
    assert video["has_thumb"] is False  # ffmpeg apagado → degradación, no error


def test_fichero_y_thumb_con_token_query_borrado() -> None:
    token = register_and_login("files")

    item = upload(client, token, "icono app.png", "Icono", "ui")
    # descarga vía ?access_token= (como hace <img src> del frontend)
    res = client.get(f"/media/{item['id']}/file?access_token={token}")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/png")

    # thumbnail via query token también
    res = client.get(f"/media/{item['id']}/thumb?access_token={token}")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/jpeg")

    # token inválido → 401
    res = client.get(f"/media/{item['id']}/file?access_token=no-sirve")
    assert res.status_code == 401

    # sin token → 401
    res = client.get(f"/media/{item['id']}/file")
    assert res.status_code == 401

    # editar título y tags
    res = client.patch(
        f"/media/{item['id']}",
        headers=auth(token),
        json={"title": "Icono v2", "tags": ["ui", "app"]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["title"] == "Icono v2"
    assert res.json()["tags"] == ["ui", "app"]

    # otro usuario NO ve el recurso (privado por usuario)
    other = register_and_login("otro")
    res = client.get(f"/media/{item['id']}/file", headers=auth(other))
    assert res.status_code == 404
    res = client.get("/media", params={"q": "icono"}, headers=auth(other))
    assert res.json()["total"] == 0

    # borrar → fila + ficheros fuera
    rel = item["path"]
    res = client.delete(f"/media/{item['id']}", headers=auth(token))
    assert res.status_code == 204
    assert not Path(settings.MEDIA_DIR, rel).exists()
    res = client.get("/media", headers=auth(token))
    assert res.json()["total"] == 0


def test_tipo_no_soportado_y_limite_de_tamano(monkeypatch) -> None:
    token = register_and_login("edge")

    # extensión no soportada
    files = {"file": ("informe.pdf", b"%PDF-1.4 test", "application/pdf")}
    res = client.post("/media", headers=auth(token), data={"title": "x"}, files=files)
    assert res.status_code == 400

    # límite de tamaño (1 MB configurado en el test)
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    files = {
        "file": ("grande.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024), "image/png")
    }
    res = client.post("/media", headers=auth(token), data={"title": "x"}, files=files)
    assert res.status_code == 413
