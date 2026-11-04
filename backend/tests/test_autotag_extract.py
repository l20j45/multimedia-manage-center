"""Tests de auto-tag (heurística, sin llave Gemini) y extracción de audio.

La rama con GEMINI_API_KEY se mockea (no depende de red); sin llave devuelve
la heurística local igual de útil.
"""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import autotag as autotag_svc
from app.services import media as media_svc
from tests.test_media import auth, register_and_login
from tests.test_workflow import upload_file

client = TestClient(app)


def test_autotag_heuristic_audio_sfx(monkeypatch) -> None:
    """wav corto de 1-2 seg → tags sfx-corto + keywords del nombre."""
    token = register_and_login("at")
    # crear un audio si ffmpeg no está: la heurística también usa filesize;
    # con make_png el tipo real no puede ser audio, así que generamos body wav crudo
    wav_head = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVEfmt " + b"\x00" * 40
    files = {"file": ("whoosh_impact-02.wav", wav_head, "audio/wav")}
    res = client.post(
        "/media", headers=auth(token), data={"title": "Whoosh", "tags": ""}, files=files
    )
    assert res.status_code == 201, res.text
    item = res.json()

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    res = client.post(f"/media/{item['id']}/autotag", headers=auth(token))
    assert res.status_code == 200
    out = res.json()
    assert out["source"] == "heuristica"
    for tag in ("sfx-corto", "whoosh", "impact"):
        assert tag in out["suggestions"], out["suggestions"]


def test_autotag_no_aplica_solo_sugiere_y_llave_gemini(monkeypatch) -> None:
    """Sin aplicar: el recurso conserva sus tags EXACTOS tras la llamada."""
    token = register_and_login("at2")
    item = upload_file(token, "meme_vertical.png", "Meme", tags="meme")
    before = item["tags"]
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    res = client.post(f"/media/{item['id']}/autotag", headers=auth(token))
    assert res.status_code == 200
    found_items = client.get("/media", params={"q": "meme"}, headers=auth(token)).json()["items"]
    target = [i for i in found_items if i["id"] == item["id"]][0]
    assert target["tags"] == before, "LA INTERFAZ NUNCA aplica por su cuenta"

    # con llave mockeada: sugerencias combinadas (heurística + gemini fake)
    monkeypatch.setattr(autotag_svc, "gemini_tags", lambda it, key: ["copypasta", "risa"])
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "FAKE-KEY")
    res = client.post(f"/media/{item['id']}/autotag", headers=auth(token))
    out = res.json()
    assert "copypasta" in out["suggestions"]
    assert "meme" not in out["suggestions"], "no sugiere lo ya presente"


@pytest.mark.skipif(media_svc.ffmpeg_bin() is None, reason="ffmpeg no disponible")
def test_extract_audio_de_video(monkeypatch) -> None:
    token = register_and_login("sfx")
    tmp = Path(settings.MEDIA_DIR) / "_v.mp4"
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
            "testsrc=duration=2:size=64x64:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=600:duration=2",
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
    files = {"file": ("paquete sfx.mp4", mp4, "video/mp4")}
    src = client.post(
        "/media",
        headers=auth(token),
        data={"title": "Paquete SFX", "tags": "sfx,paquete"},
        files=files,
    ).json()

    res = client.post(f"/media/{src['id']}/extract-audio", headers=auth(token))
    assert res.status_code == 201, res.text
    audio = res.json()
    assert audio["kind"] == "audio"
    assert audio["mime"] == "audio/mpeg"
    assert audio["has_thumb"] is True, "también genera waveform del audio extraído"
    assert audio["duration_s"] is not None and 1.5 <= audio["duration_s"] <= 2.5
    assert sorted(audio["tags"]) == ["paquete", "sfx"], "hereda los tags"
    assert "Paquete SFX" in audio["description"]
    p = Path(settings.MEDIA_DIR) / audio["path"]
    assert p.exists()

    # el audio nuevo también se recorta con el flujo trim
    r = client.post(
        f"/media/{audio['id']}/trim",
        headers=auth(token),
        json={"start": 0.2, "end": 1.2, "title": "SFX final"},
    )
    assert r.status_code == 201
    frag = r.json()
    assert frag["kind"] == "audio" and frag["title"] == "SFX final"

    # imagen → 400
    img = upload_file(token, "x.png", "img")
    res = client.post(f"/media/{img['id']}/extract-audio", headers=auth(token))
    assert res.status_code == 400
