"""Tests: enlace público de colección (share) y renombrado en lote."""

from fastapi.testclient import TestClient

from app.main import app
from tests.test_media import auth, register_and_login
from tests.test_workflow import upload_file

client = TestClient(app)


def test_share_publico_ciclo_completo() -> None:
    owner = register_and_login("share")
    a = upload_file(owner, "a.png", "Público uno", tags="showcase")
    b = upload_file(owner, "b.png", "Privado fuera")
    col = client.post(
        "/collections", headers=auth(owner), json={"name": "Memes de la semana"}
    ).json()
    client.post(f"/collections/{col['id']}/items", headers=auth(owner), json={"media_id": a["id"]})

    # crear enlace
    res = client.post(f"/collections/{col['id']}/share", headers=auth(owner))
    assert res.status_code == 200
    token = res.json()["token"]
    assert res.json()["url"].startswith("/share/")

    # el endpoint público funciona SIN login
    r = client.get(f"/media/public/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Memes de la semana"
    assert [i["id"] for i in body["items"]] == [a["id"]]

    # descarga con ?share= de un item de la colección OK
    r = client.get(f"/media/{a['id']}/file", params={"share": token})
    assert r.status_code == 200
    r = client.get(f"/media/{a['id']}/thumb", params={"share": token})
    assert r.status_code == 200

    # item FUERA de la colección → 401 aún con token bueno
    r = client.get(f"/media/{b['id']}/file", params={"share": token})
    assert r.status_code == 401

    # sin token ni login → 401
    assert client.get(f"/media/{a['id']}/file").status_code == 401

    # revocar → enlace muere
    res = client.delete(f"/collections/{col['id']}/share", headers=auth(owner))
    assert res.status_code == 204
    assert client.get(f"/media/public/{token}").status_code == 404
    assert client.get(f"/media/{a['id']}/file", params={"share": token}).status_code == 401

    # otro usuario no puede crear share de una colección ajena
    other = register_and_login("share2")
    res = client.post(f"/collections/{col['id']}/share", headers=auth(other))
    assert res.status_code == 404


def test_bulk_rename_con_patron() -> None:
    token = register_and_login("re")
    a = upload_file(token, "r1.png", "Primero", tags="x")
    b = upload_file(token, "r2.png", "Segundo", tags="x")

    res = client.post(
        "/media/bulk",
        headers=auth(token),
        json={"ids": [a["id"], b["id"]], "action": "rename", "pattern": "meme-{date}-{n}"},
    )
    assert res.json()["done"] == 2
    res = client.get("/media", params={"order": "created", "direction": "asc"}, headers=auth(token))
    titles = [i["title"] for i in res.json()["items"]]
    assert any("-001" in t and t.startswith("meme-") for t in titles)
    assert any("-002" in t and t.startswith("meme-") for t in titles)

    # patrón con {title} conserva el nombre original
    res = client.post(
        "/media/bulk",
        headers=auth(token),
        json={"ids": [a["id"]], "action": "rename", "pattern": "fijo-{title}"},
    )
    res = client.get("/media", params={"q": "fijo-"}, headers=auth(token))
    assert res.json()["total"] == 1
    assert "Segundo" not in res.json()["items"][0]["title"]
