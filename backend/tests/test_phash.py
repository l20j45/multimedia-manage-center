"""Tests de duplicados VISUALES: dHash (phash) + sección `similar`.

Corre con:  uv run pytest
Crea gemelos visuales que NO comparten bytes (re-save con metadata PNG
distinta) y una no-duplicada para verificar que queda fuera.
"""

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from app.main import app
from app.services import media as media_svc
from tests.test_media import auth, register_and_login

client = TestClient(app)


def retina_png(meta_text: str) -> bytes:
    """Imagen con MISMO contenido de pixels, bytes DIFERENTES (metadata PNG).

    El truco del test de la vida real: la gente re-descarga/re-guarda iguales
    y el PNG lleva chunks diversos (fuente fechada, editor local...).
    """
    from io import BytesIO

    img = Image.new("RGB", (200, 140))
    for y in range(140):
        for x in range(200):
            img.putpixel((x, y), ((x * 3 + y * 5) % 256, (x * 7) % 256, (y * 11) % 256))
    meta = PngImagePlugin.PngInfo()
    meta.add_text("procedencia", meta_text)
    buf = BytesIO()
    img.save(buf, "PNG", pnginfo=meta)
    return buf.getvalue()


def other_png() -> bytes:
    """Contenido visual distinto (gradiente invertido sobre fondo plano)."""
    from io import BytesIO

    img = Image.new("RGB", (180, 180), "white")
    for i in range(180):
        img.putpixel((i, i), (0, 0, 0))
        img.putpixel((i, 179 - i), (128, 128, 128))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_phash_identico_aunque_bytes_diffieran() -> None:
    """Mismo look, bytes distintos → mismo dHash."""
    h1 = media_svc.phash_image_bytes(retina_png("subida del teléfono"))
    h2 = media_svc.phash_image_bytes(retina_png("re-guardado con metadata zeta"))
    assert h1 is not None and h2 is not None
    assert h1 == h2, f"{h1} != {h2}: el dHash debe ignorar los re-saves"
    # y una imagen visualmente distinta queda fuera
    h3 = media_svc.phash_image_bytes(other_png())
    assert not media_svc.phash_images_related(h1, h3)


def test_upload_imagen_rellena_phash() -> None:
    """El hash perceptual se calcula al subir (comprueba BD)."""
    token = register_and_login("phash-up")
    files = {"file": ("m.png", retina_png("directo"), "image/png")}
    res = client.post("/media", headers=auth(token), data={"title": "M"}, files=files)
    assert res.status_code == 201
    from app.database import SessionLocal
    from app.models import MediaItem

    db = SessionLocal()
    row = db.query(MediaItem).filter(MediaItem.id == res.json()["id"]).first()
    assert row.phash, f"phash presente: {row.phash}"
    assert len(row.phash) == 16
    db.close()


def test_duplicados_endpoint_expose_similar() -> None:
    """GET /duplicates: sección `similar` con el par de gemelos visuales."""
    token = register_and_login("phash-dup")
    for i, meta in enumerate(["original", "re-guardado fuera de la cámara"]):
        files = {"file": (f"d{i}.png", retina_png(meta), "image/png")}
        res = client.post("/media", headers=auth(token), data={"title": f"D{i}"}, files=files)
        assert res.status_code == 201
    # una que se ve distinta: NO entra en ningún grupo
    files = {"file": ("z.png", other_png(), "image/png")}
    r = client.post("/media", headers=auth(token), data={"title": "Z"}, files=files)
    z_id = r.json()["id"]

    out = client.get("/media/duplicates", headers=auth(token)).json()
    assert out["similar"], "hay 1 grupo de gemelos visuales"
    ids = {i["id"] for g in out["similar"] for i in g}
    assert len(ids) == 2, "solo las dos similares"
    assert z_id not in ids, "la imagen distinta no se reporta como gemela"
    assert out["groups"] == [], "bytes distintas → NO van como copias exactas"

    # sin gemelos: similar vacío
    other = register_and_login("phash-tonely")
    files = {"file": ("z.png", other_png(), "image/png")}
    res = client.post("/media", headers=auth(other), data={"title": "Unico"}, files=files)
    assert res.status_code == 201
    solo = client.get("/media/duplicates", headers=auth(other)).json()
    assert solo["groups"] == [] and solo["similar"] == []
