"""Tests: ZIP de colección, stats overview y búsqueda por hash (anti-dup)."""

import io
import zipfile

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from tests.test_media import auth, register_and_login

client = TestClient(app)


def png(color):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color=color).save(buf, "PNG")
    buf.seek(0)
    return buf.getvalue()


def test_zip_export_contiene_ficheros_y_lista() -> None:
    token = register_and_login("zip")
    files = {"file": ("uno.png", png((10, 20, 30)), "image/png")}
    a = client.post(
        "/media", headers=auth(token), data={"title": "Uno *pro*", "tags": "x"}, files=files
    ).json()
    files = {"file": ("dos.png", png((40, 50, 60)), "image/png")}
    b = client.post(
        "/media", headers=auth(token), data={"title": "Dos", "tags": "y"}, files=files
    ).json()
    col = client.post("/collections", headers=auth(token), json={"name": "Meme Pack #1"}).json()
    client.post(f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": a["id"]})
    client.post(f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": b["id"]})

    res = client.get(f"/collections/{col['id']}/export-zip", headers=auth(token))
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = zf.namelist()
    assert len([n for n in names if n.endswith(".png")]) == 2
    assert "_lista.csv" in names, "el listado de guia viaja dentro"
    # titulos saneados en los nombres del zip
    assert any("Uno" in n for n in names) and "*" not in "".join(names)
    # el zip es valido y los ficheros pesan igual que el original
    info = [i for i in zf.infolist() if "Dos" in i.filename][0]
    assert info.file_size == b["size"]


def test_zip_de_coleccion_ajena_404() -> None:
    owner = register_and_login("zipown")
    col = client.post("/collections", headers=auth(owner), json={"name": "Privada"}).json()
    other = register_and_login("zipother")
    assert (
        client.get(f"/collections/{col['id']}/export-zip", headers=auth(other)).status_code == 404
    )


def test_stats_overview_cuentas_pesos_tags() -> None:
    token = register_and_login("stats")
    files = {"file": ("im1.png", png((1, 2, 3)), "image/png")}
    client.post("/media", headers=auth(token), data={"title": "I1", "tags": "meme"}, files=files)
    files = {"file": ("im2.png", png((4, 5, 6)), "image/png")}
    client.post(
        "/media", headers=auth(token), data={"title": "I2", "tags": "meme,formato"}, files=files
    )

    res = client.get("/media/stats/overview", headers=auth(token))
    assert res.status_code == 200
    s = res.json()
    assert s["by_kind"]["image"]["count"] == 2
    assert s["by_kind"]["image"]["size"] > 0
    assert s["by_kind"]["audio"]["count"] == 0
    assert s["top_tags"][0]["tag"] == "meme" and s["top_tags"][0]["count"] == 2
    assert s["months"] and s["months"][-1]["count"] >= 2
    assert s["trash_count"] == 0


def test_by_hash_anti_dup() -> None:
    import hashlib

    token = register_and_login("hash")
    body = png((123, 111, 90))
    files = {"file": ("uno.png", body, "image/png")}
    a = client.post("/media", headers=auth(token), data={"title": "Uno"}, files=files).json()

    sha = hashlib.sha256(body).hexdigest()
    res = client.get(f"/media/by-hash/{sha}", headers=auth(token))
    assert res.status_code == 200
    assert res.json()["id"] == a["id"]

    # hash de contenido que NO subiste → 404 (no se filtran datos ajenos)
    other = register_and_login("hashother")
    assert client.get(f"/media/by-hash/{sha}", headers=auth(other)).status_code == 404
    assert client.get("/media/by-hash/deadbeef", headers=auth(token)).status_code == 404
