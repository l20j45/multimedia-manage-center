"""Tests del auto-purga de papelera tras N días."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, make_png, register_and_login

client = TestClient(app)


def test_purge_expirados_solo_los_viejos() -> None:
    token = register_and_login("purge")
    files = {"file": ("a.png", make_png(), "image/png")}
    a = client.post("/media", headers=auth(token), data={"title": "Viejo"}, files=files).json()
    files = {"file": ("b.png", make_png(), "image/png")}
    b = client.post("/media", headers=auth(token), data={"title": "Reciente"}, files=files).json()

    # borrar los dos (soft)
    client.delete(f"/media/{a['id']}", headers=auth(token))
    client.delete(f"/media/{b['id']}", headers=auth(token))

    # a fue 'borrado' hace 40 días: parchear su deleted_at en la BD de tests

    from app.database import SessionLocal
    from app.models import MediaItem

    db = SessionLocal()
    old = db.query(MediaItem).filter(MediaItem.id == a["id"]).first()
    old.deleted_at = datetime.now(UTC) - timedelta(days=40)
    db.commit()
    db.close()

    purged = media_svc.purge_expired_trash(settings.TRASH_RETENTION_DAYS)
    assert purged == 1

    # el viejo desapareció FÍSICAMENTE y de la BD; el reciente sigue en papelera
    from pathlib import Path

    assert not Path(settings.MEDIA_DIR, a["path"]).exists()
    db = SessionLocal()
    assert db.query(MediaItem).filter(MediaItem.id == a["id"]).first() is None
    leftover = db.query(MediaItem).filter(MediaItem.id == b["id"]).first()
    db.close()
    assert leftover is not None, "el reciente NO se purga"
    assert Path(settings.MEDIA_DIR, b["path"]).exists()

    # cleanup del test
    client.delete(f"/media/{b['id']}/purge", headers=auth(token))
