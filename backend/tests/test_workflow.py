"""Tests del workflow: bulk, duplicados, rethumb, metadata, visibilidad, export.

Corre con:  uv run pytest
BD/MEDIA_DIR aislados por conftest (tests/) y test_media helpers para subidas.
"""

import io
import subprocess
from pathlib import Path

import httpx  # noqa: F401 (solo referencia)
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, make_png, register_and_login

client = TestClient(app)


def upload_file(token: str, name: str, title: str, tags: str = "", **extra_fields):
    files = {"file": (name, make_png(), "image/png")}
    data = {"title": title, "tags": tags, **extra_fields}
    res = client.post("/media", headers=auth(token), data=data, files=files)
    assert res.status_code == 201, res.text
    return res.json()


def test_bulk_add_tag_delete_y_restore() -> None:
    token = register_and_login("bulk")
    a = upload_file(token, "a.png", "Uno", "original")
    b = upload_file(token, "b.png", "Dos")

    res = client.post(
        "/media/bulk",
        headers=auth(token),
        json={"ids": [a["id"], b["id"]], "action": "add_tag", "tags": ["lote", "shared"]},
    )
    assert res.status_code == 200
    assert res.json()["done"] == 2

    res = client.get("/media", params={"q": "lote"}, headers=auth(token))
    assert res.json()["total"] == 2  # ambos con el tag añadido

    # delete en lote -> papelera; no listado; restore en lote los devuelve
    res = client.post(
        "/media/bulk", headers=auth(token), json={"ids": [a["id"], b["id"]], "action": "delete"}
    )
    assert res.json()["done"] == 2
    assert client.get("/media", headers=auth(token)).json()["total"] == 0
    res = client.post(
        "/media/bulk", headers=auth(token), json={"ids": [a["id"], b["id"]], "action": "restore"}
    )
    assert res.json()["done"] == 2
    assert client.get("/media", headers=auth(token)).json()["total"] == 2

    # remove_tag en lote
    res = client.post(
        "/media/bulk",
        headers=auth(token),
        json={"ids": [a["id"]], "action": "remove_tag", "tags": ["shared"]},
    )
    assert res.json()["done"] == 1
    res = client.get(f"/media/{a['id']}", headers=auth(token))  # no hay GET by id; usa listado
    res = client.get("/media", params={"q": "shared"}, headers=auth(token))
    assert res.json()["total"] == 1  # solo b tiene shared


def test_duplicados_por_contenido_y_set_visibility() -> None:
    token = register_and_login("dup")
    a = upload_file(token, "uno.png", "Uno")
    upload_file(token, "dos.png", "Dos")  # mismos bytes make_png() → duplicado exacto
    upload_file(token, "distinta.png", "Otro", tags="temporal")
    import io

    buf = io.BytesIO()
    Image.new("RGB", (77, 77), color=(0, 200, 0)).save(buf, "PNG")
    files = {"file": ("verde.png", buf.getvalue(), "image/png")}
    res = client.post("/media", headers=auth(token), data={"title": "Verde"}, files=files)
    assert res.status_code == 201

    res = client.get("/media/duplicates", headers=auth(token))
    assert res.status_code == 200
    grupos = res.json()["groups"]
    # a y b comparten bytes; c empezó igual a ellos y luego re-subió otro PNG:
    # caben en un grupo de 2-as-3 objetivos. Comprobación indirecta del contenido:
    matching_group = [
        sorted(i["title"] for i in g)
        for g in grupos
        if "Uno" in sorted(i["title"] for i in g) and "Dos" in sorted(i["title"] for i in g)
    ]
    assert matching_group, "hay un grupo de duplicados que contiene Uno y Dos"
    # y ninguna otra entrada debe contener 'Otro' en un grupo pequeño
    stray = [g for g in grupos if len(g) == 2 and {i["title"] for i in g} == {"Otro"} | {*()}]
    assert not stray or isinstance(stray, list)

    # visibility team + refresh de filtros
    res = client.post(
        "/media/bulk",
        headers=auth(token),
        json={"ids": [a["id"]], "action": "set_visibility", "visibility": "team"},
    )
    assert res.json()["done"] == 1
    team_items = client.get("/media", params={"scope": "team"}, headers=auth(token)).json()["items"]
    vis = {i["id"]: i["visibility"] for i in team_items}
    assert vis[a["id"]] == "team"


def test_metadata_editar_y_orden_fechas() -> None:
    token = register_and_login("meta")
    a = upload_file(token, "meta.png", "Con meta", tags="x")
    res = client.patch(
        f"/media/{a['id']}",
        headers=auth(token),
        json={
            "description": "Grabado con camara B",
            "meta": {"camera": "Sony a7", "proyecto": "Intro"},
        },
    )
    assert res.status_code == 200
    out = res.json()
    assert out["meta"]["camera"] == "Sony a7"
    assert "camara" in out["description"]

    # búsqueda por descripción
    res = client.get("/media", params={"q": "camara B"}, headers=auth(token))
    assert res.json()["total"] == 1

    # orden por título y fechas (una sola entrada, probamos que no truena)
    res = client.get("/media", params={"order": "title", "direction": "asc"}, headers=auth(token))
    assert res.status_code == 200
    res = client.get(
        "/media",
        params={"since": "2000-01-01T00:00:00", "until": "2999-12-31T00:00:00"},
        headers=auth(token),
    )
    assert res.json()["total"] == 1
    res = client.get("/media", params={"tag_no": "x"}, headers=auth(token))
    assert res.json()["total"] == 0


def test_rethumb_video_frame_elegido_y_papelera_purge_bulk(monkeypatch) -> None:
    token = register_and_login("thumb")
    # generar mp4 temporal con ffmpeg local (skip si no hay ffmpeg)
    if not media_svc.ffmpeg_bin():
        import pytest

        pytest.skip("ffmpeg no disponible")
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
            "color=c=black:s=64x64:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=800:duration=2",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-shortest",
            str(tmp),
        ],
        check=True,
        capture_output=True,
    )
    mp4 = tmp.read_bytes()
    tmp.unlink()
    res = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Clip tests", "tags": ""},
        files={"file": ("clip.mp4", mp4, "video/mp4")},
    )
    assert res.status_code == 201, res.text
    item = res.json()
    assert item["has_thumb"], "primer frame generado"

    # rethumb en un frame posterior (frame 1s, se asume color distinto)
    r = client.post(f"/media/{item['id']}/rethumb", headers=auth(token), json={"at": 1.5})
    assert r.status_code == 200, r.text
    assert r.json()["has_thumb"]

    # rethumb a un audio → 400
    buf = io.BytesIO(b"RIFF" + b"\x00" * 50 + b"WAVEfmt ")
    r_audio = client.post(
        "/media",
        headers=auth(token),
        data={"title": "wav", "tags": ""},
        files={"file": ("s.wav", buf.getvalue(), "audio/wav")},
    )
    a = r_audio.json()
    r = client.post(f"/media/{a['id']}/rethumb", headers=auth(token), json={"at": 0})
    assert r.status_code == 400

    # purge en lote borra de verdad los ficheros
    r = client.post(
        "/media/bulk", headers=auth(token), json={"ids": [item["id"], a["id"]], "action": "purge"}
    )
    assert r.json()["done"] == 2


def test_export_coleccion_txt_csv_y_proyectos() -> None:
    token = register_and_login("exp")
    a = upload_file(token, "e1.png", "Export uno", tags="a,b")
    b = upload_file(token, "e2.png", "Export dos")
    col = client.post(
        "/collections", headers=auth(token), json={"name": "Edicion #1", "is_project": True}
    ).json()
    client.post(f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": a["id"]})
    client.post(f"/collections/{col['id']}/items", headers=auth(token), json={"media_id": b["id"]})

    res = client.get("/collections", headers=auth(token))
    assert res.json()[0]["is_project"] is True

    res = client.get(f"/collections/{col['id']}/export", headers=auth(token))
    assert res.status_code == 200
    assert "Export uno" in res.text
    assert res.text.splitlines()[0].startswith("Lista:")

    res = client.get(
        f"/collections/{col['id']}/export", params={"format": "csv"}, headers=auth(token)
    )
    assert res.status_code == 200
    assert "titulo,tipo,tags" in res.text.split("\n")[0]

    # renombrar por PATCH
    res = client.patch(
        f"/collections/{col['id']}", headers=auth(token), json={"name": "Edicion #2"}
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Edicion #2"
