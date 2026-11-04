"""Tests /collections: CRUD de colecciones + pertenencia + cable con /media.

Corre con:  uv run pytest
La BD/MEDIA_DIR quedan aislados por conftest.py y el fixture de test_media.
"""

import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def make_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(30, 200, 120)).save(buf, "PNG")
    return buf.getvalue()


def register_and_login(user: str) -> str:
    email = f"{user}-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "clavelarga123"})
    assert res.status_code == 201, res.text
    res = client.post("/auth/login", data={"username": email, "password": "clavelarga123"})
    return res.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload_png(token: str, name: str, title: str, tags: str = "") -> dict:
    files = {"file": (name, make_png(), "image/png")}
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": title, "tags": tags},
        files=files,
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_ciclo_completo_de_coleccion() -> None:
    token = register_and_login("col")

    # Crea
    res = client.post("/collections", headers=auth(token), json={"name": "B-roll 2026"})
    assert res.status_code == 201, res.text
    col = res.json()
    assert col["item_count"] == 0

    # Nombre duplicado → 409
    res = client.post("/collections", headers=auth(token), json={"name": "B-roll 2026"})
    assert res.status_code == 409

    # Agrega dos recursos propios
    a = upload_png(token, "clip1.png", "Calle", "b-roll")
    b = upload_png(token, "clip2.png", "Atardecer")
    res = client.post(
        f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": a["id"]}
    )
    assert res.status_code == 201
    assert res.json()["item_count"] == 1
    res = client.post(
        f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": b["id"]}
    )
    assert res.json()["item_count"] == 2

    # Duplicado → 409
    res = client.post(
        f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": a["id"]}
    )
    assert res.status_code == 409

    # Listado con conteos
    res = client.get("/collections", headers=auth(token))
    cols = res.json()
    assert len(cols) == 1 and cols[0]["item_count"] == 2

    # Items en orden, con datos de media
    res = client.get(f"/collections/{col['id']}/items", headers=auth(token))
    titles = [i["title"] for i in res.json()]
    assert titles == ["Calle", "Atardecer"]

    # /media filtra por colección
    res = client.get("/media", params={"collection": col["id"]}, headers=auth(token))
    assert res.json()["total"] == 2
    res = client.get("/media", params={"collection": col["id"], "q": "calle"}, headers=auth(token))
    assert res.json()["total"] == 1

    # Quita uno
    res = client.delete(f"/collections/{col['id']}/items/{a['id']}", headers=auth(token))
    assert res.status_code == 204
    res = client.get(f"/collections/{col['id']}/items", headers=auth(token))
    assert [i["title"] for i in res.json()] == ["Atardecer"]
    # el recurso sigue en la biblioteca
    res = client.get("/media", headers=auth(token))
    assert res.json()["total"] == 2

    # Borrar colección NO borra recursos; solo la pertenencia
    res = client.delete(f"/collections/{col['id']}", headers=auth(token))
    assert res.status_code == 204
    res = client.get("/collections", headers=auth(token))
    assert res.json() == []
    res = client.get("/media", headers=auth(token))
    assert res.json()["total"] == 2


def test_privacidad_de_colecciones() -> None:
    mine = register_and_login("colmine")
    theirs = register_and_login("coltheirs")

    col = client.post("/collections", headers=auth(mine), json={"name": "Privada"}).json()
    media = upload_png(mine, "solo mio.png", "Personal")

    # ajeno: ni ve mis colecciones ni puede agregar/quitar
    assert client.get("/collections", headers=auth(theirs)).json() == []
    res = client.post(
        f"/collections/{col['id']}/items", headers=auth(theirs), json={"media_id": media["id"]}
    )
    assert res.status_code == 404
    res = client.get(f"/collections/{col['id']}/items", headers=auth(theirs))
    assert res.status_code == 404
    res = client.delete(f"/collections/{col['id']}/items/{media['id']}", headers=auth(theirs))
    assert res.status_code == 404

    # media ajeno a mi colección → 404
    res = client.post(
        f"/collections/{col['id']}/items", headers=auth(mine), json={"media_id": 999999}
    )
    assert res.status_code == 404


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"name": ""}, 422),
        ({"nada": "x"}, 422),
    ],
)
def test_validacion_crear_coleccion(payload: dict, expected: int) -> None:
    token = register_and_login("colval")
    res = client.post("/collections", headers=auth(token), json=payload)
    assert res.status_code == expected
