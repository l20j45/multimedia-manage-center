"""Tests de detección anti-duplicado en la subida y backfill de sha256.

Corre con:  uv run pytest
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, make_png, register_and_login

client = TestClient(app)


def test_upload_duplicado_responde_duplicate_of() -> None:
    """Subir DOS veces el MISMO contenido → la 2ª avisa con de quién es copia."""
    token = register_and_login("dupcheck")
    files = {"file": ("a.png", make_png(), "image/png")}
    first = client.post("/media", headers=auth(token), data={"title": "Uno"}, files=files)
    assert first.status_code == 201
    assert first.json()["duplicate_of"] is None, "el primero es el original"

    files = {"file": ("b.png", make_png(), "image/png")}  # otro NOMBRE, mismo bytes
    second = client.post("/media", headers=auth(token), data={"title": "Dos"}, files=files)
    assert second.status_code == 201
    out = second.json()
    assert out["duplicate_of"] is not None, "la 2ª subida detecta el mismo contenido"
    assert out["duplicate_of"]["id"] == first.json()["id"]
    assert out["duplicate_of"]["title"] == "Uno"

    # y el detector de duplicados los agrupa
    dupes = client.get("/media/duplicates", headers=auth(token)).json()
    assert len(dupes["groups"]) == 1
    assert {i["id"] for i in dupes["groups"][0]} == {first.json()["id"], second.json()["id"]}


def test_backfill_hashes_rescata_legacy() -> None:
    """Item sin sha256 (uploads pre-hash) → backfill lo calcula del fichero."""
    token = register_and_login("backfill")
    files = {"file": ("x.png", make_png(), "image/png")}
    item = client.post("/media", headers=auth(token), data={"title": "X"}, files=files).json()
    # simula legacy: quita el hash a mano
    import hashlib
    from pathlib import Path

    from app.config import settings
    from app.database import SessionLocal
    from app.models import MediaItem

    db = SessionLocal()
    row = db.query(MediaItem).filter(MediaItem.id == item["id"]).first()
    assert row is not None
    expected = hashlib.sha256((Path(settings.MEDIA_DIR) / row.path).read_bytes()).hexdigest()
    row.sha256 = None
    db.commit()
    db.close()

    n = media_svc.backfill_hashes()
    assert n >= 1
    db = SessionLocal()
    row = db.query(MediaItem).filter(MediaItem.id == item["id"]).first()
    assert row.sha256 == expected
    db.close()
