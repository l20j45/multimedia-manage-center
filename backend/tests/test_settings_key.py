"""Tests /settings/gemini-key: guardada en BD sobrevive y la lee el autotag."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.routers.settings import get_gemini_api_key
from app.services import autotag as autotag_svc
from tests.test_media import auth, register_and_login

client = TestClient(app)


def test_llave_flujo_completo_y_aultotag(monkeypatch) -> None:
    token = register_and_login("apikey")
    h = auth(token)

    # sin llave: heuristica
    assert client.get("/settings/gemini-key", headers=h).json()["set"] is False
    _db = SessionLocal()
    assert get_gemini_api_key(_db) == ""  # ni .env ni BD en test
    item = client.post(
        "/media",
        headers=h,
        files={"file": ("meme.png", _fake_png(), "image/png")},
        data={"title": "Meme"},
    ).json()
    r = client.post(f"/media/{item['id']}/autotag", headers=h)
    assert r.json()["source"] == "heuristica"

    # guardar llave invalida
    assert client.put("/settings/gemini-key", headers=h, json={"value": "corta"}).status_code == 400

    # guardar llave valida
    fake = "AIzaValidaParaUnitTest_1234567890"
    res = client.put("/settings/gemini-key", headers=h, json={"value": fake})
    assert res.json()["source"] == "app"
    assert res.json()["tail"] == "…7890"

    # GET devuelve cola (nunca la llave completa)
    status_json = client.get("/settings/gemini-key", headers=h).json()
    assert status_json["set"] is True
    assert fake not in str(status_json)

    # el autotag NOW reporta la fuente gemini (via llave de la BD)
    monkeypatch.setattr(autotag_svc, "gemini_tags", lambda it, key: ["ia-tag"])
    r = client.post(f"/media/{item['id']}/autotag", headers=h)
    assert "ia-tag" in r.json()["suggestions"]
    assert r.json()["source"] == "gemini+heuristica"

    _db = SessionLocal()
    assert get_gemini_api_key(_db) == fake  # efectiva desde la BD
    _db.close()

    # borrar con vacio
    res = client.put("/settings/gemini-key", headers=h, json={"value": ""})
    assert res.json()["set"] is False
    assert client.get("/media/by-hash/xx", headers=h).status_code == 404


def _fake_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (1, 2, 3)).save(buf, "PNG")
    return buf.getvalue()
