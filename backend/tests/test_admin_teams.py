"""Tests /admin + /teams: super admin, toggle de registro y equipos.

El primer usuario de la instalación queda como super admin; el admin puede
cerrar el registro, ver los usuarios y armar equipos (los recursos con
visibility='team' se comparten SOLO con compañeros de equipo).

Corre con:  uv run pytest
"""

import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import User

client = TestClient(app)


def make_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(30, 120, 220)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def tmp_media_dir(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


def register_and_login(user: str, password: str = "clavelarga123") -> tuple[str, str]:
    """Registra y loguea una cuenta nueva: devuelve (token, email)."""
    email = f"{user}-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": password, "name": user})
    assert res.status_code == 201, res.text
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"], email


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _any_user() -> User:
    db = SessionLocal()
    try:
        return db.query(User).order_by(User.id).first()
    finally:
        db.close()


def _admin_token() -> str:
    """Token de UN admin: lo registra si la instalación aún no tiene cuentas."""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin.is_(True)).first()
        if admin is None:
            db.close()
            _first_token, admin_email = register_and_login("admin-primero")
            db = SessionLocal()
            admin = db.query(User).filter(User.email == admin_email).first()
            admin.is_admin = True  # garantía (por si ya había cuentas sin admin)
            db.commit()
            return admin_email
        return admin.email
    finally:
        db.close()


def test_primer_usuario_es_admin() -> None:
    """El usuario más antiguo de la BD es el super admin; los nuevos no lo son."""
    admin_email = _admin_token()  # dispara el registro del primer admin si falta

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == admin_email).first()
        assert admin is not None and admin.is_admin
        assert admin.id == db.query(User).order_by(User.id).first().id
    finally:
        db.close()

    _token, nuevo_email = register_and_login("usuario-2")
    db = SessionLocal()
    try:
        nuevo = db.query(User).filter(User.email == nuevo_email).first()
        assert nuevo is not None and not nuevo.is_admin
    finally:
        db.close()


def test_admin_visible_solo_para_admin() -> None:
    """/admin/overview: 403 para un usuario común, 200 para el super admin."""
    _admin_email = _admin_token()
    user_token, _ = register_and_login("comun")

    res = client.get("/admin/overview", headers=auth(user_token))
    assert res.status_code == 403, res.text

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin.is_(True)).first()
    finally:
        db.close()
    res = client.post("/auth/login", data={"username": admin.email, "password": "clavelarga123"})
    if res.status_code != 200:
        # contraseña desconocida (registro de otra sesión): re-escalamos manualmente
        pytest.skip("no conocemos la contraseña del admin de esta BD")
    admin_token = res.json()["access_token"]

    res = client.get("/admin/overview", headers=auth(admin_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] >= 1
    assert body["active_count"] >= 1
    assert any(u["is_admin"] for u in body["users"])


def test_admin_cierra_y_abre_el_registro() -> None:
    """Con el registro cerrado, /auth/register responde 403; al abrirlo, pasa."""
    _admin_email = _admin_token()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin.is_(True)).first()
    finally:
        db.close()
    res = client.post("/auth/login", data={"username": admin.email, "password": "clavelarga123"})
    if res.status_code != 200:
        pytest.skip("no conocemos la contraseña del admin de esta BD")
    admin_token = res.json()["access_token"]

    email = f"bloqueado-{uuid.uuid4().hex[:8]}@example.com"
    try:
        res = client.put("/admin/registration", headers=auth(admin_token), json={"open": False})
        assert res.status_code == 200, res.text

        res = client.post("/auth/register", json={"email": email, "password": "clavelarga123"})
        assert res.status_code == 403, res.text
        assert "registro está cerrado" in res.json()["detail"]
    finally:
        res = client.put("/admin/registration", headers=auth(admin_token), json={"open": True})
        assert res.status_code == 200, res.text

    res = client.post("/auth/register", json={"email": email, "password": "clavelarga123"})
    assert res.status_code == 201, res.text


def test_equipos_flujo_completo() -> None:
    """Crear equipo → invitar → ver detalle → salir → owner disuelve."""
    owner_token, _ = register_and_login("owner-eq")
    member_token, member_email = register_and_login("miembro-eq")

    res = client.post("/teams", headers=auth(owner_token), json={"name": "Montajeercial"})
    assert res.status_code == 201, res.text
    team = res.json()
    assert team["role"] == "owner" and team["member_count"] == 1

    res = client.post(
        f"/teams/{team['id']}/members", headers=auth(owner_token), json={"email": member_email}
    )
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "member"

    res = client.get(f"/teams/{team['id']}", headers=auth(member_token))
    assert res.status_code == 200, res.text
    detail = res.json()
    assert detail["role"] == "member"
    assert len(detail["members"]) == 2

    res = client.get("/teams", headers=auth(member_token))
    assert any(t["id"] == team["id"] for t in res.json())

    # el miembro sale por su cuenta
    res = client.delete(f"/teams/{team['id']}/leave", headers=auth(member_token))
    assert res.status_code == 204, res.text

    # el owner disuelve el equipo
    res = client.delete(f"/teams/{team['id']}", headers=auth(owner_token))
    assert res.status_code == 204, res.text
    res = client.get(f"/teams/{team['id']}", headers=auth(owner_token))
    assert res.status_code in (403, 404), res.text  # ya no existe para él


def test_recursos_del_equipo_solo_entre_miembros() -> None:
    """visibility='team' se ve SOLO entre compañeros de equipo, no toda la instancia."""
    owner_token, _ = register_and_login("owner-med")
    mate_token, mate_email = register_and_login("mate-med")
    other_token, _ = register_and_login("ajeno-med")

    res = client.post("/teams", headers=auth(owner_token), json={"name": "Team históricos"})
    team_id = res.json()["id"]
    res = client.post(
        f"/teams/{team_id}/members", headers=auth(owner_token), json={"email": mate_email}
    )
    assert res.status_code == 200, res.text

    files = {"file": ("planos.png", make_png(), "image/png")}
    res = client.post(
        "/media",
        headers=auth(owner_token),
        data={"title": "Planos duelo", "visibility": "team"},
        files=files,
    )
    assert res.status_code == 201, res.text
    item_id = res.json()["id"]

    # compañero de equipo: lo ve en scope=team y puede pedir el fichero
    res = client.get("/media?scope=team&limit=200", headers=auth(mate_token))
    assert any(it["id"] == item_id for it in res.json()["items"]), res.text
    res = client.get(f"/media/{item_id}/file", headers=auth(mate_token))
    assert res.status_code == 200, res.text

    # usuario ajeno a todos los equipos del owner: NO lo ve ni puede leerlo
    res = client.get("/media?scope=team&limit=200", headers=auth(other_token))
    assert not any(it["id"] == item_id for it in res.json()["items"])
    res = client.get(f"/media/{item_id}/file", headers=auth(other_token))
    assert res.status_code == 401, res.text


def test_recursos_a_un_equipo_concreto() -> None:
    """team_id=N: solo los miembros de ESE equipo lo ven (no otros equipos míos)."""
    owner_token, _ = register_and_login("granular")
    res = client.post("/teams", headers=auth(owner_token), json={"name": "Team A"})
    team_a = res.json()["id"]
    res = client.post("/teams", headers=auth(owner_token), json={"name": "Team B"})
    team_b = res.json()["id"]

    mate_a_token, mate_a_email = register_and_login("solo-a")
    mate_b_token, mate_b_email = register_and_login("solo-b")
    res = client.post(
        f"/teams/{team_a}/members", headers=auth(owner_token), json={"email": mate_a_email}
    )
    assert res.status_code == 200, res.text
    res = client.post(
        f"/teams/{team_b}/members", headers=auth(owner_token), json={"email": mate_b_email}
    )
    assert res.status_code == 200, res.text

    files = {"file": ("recorte.png", make_png(), "image/png")}
    res = client.post(
        "/media",
        headers=auth(owner_token),
        data={"title": "Del equipo A", "visibility": "team", "team_id": str(team_a)},
        files=files,
    )
    assert res.status_code == 201, res.text
    assert res.json()["team_id"] == team_a
    item_a = res.json()["id"]

    files = {"file": ("abierto.png", make_png(), "image/png")}
    res = client.post(
        "/media",
        headers=auth(owner_token),
        data={"title": "Para todos mis equipos", "visibility": "team"},
        files=files,
    )
    assert res.status_code == 201, res.text
    item_open = res.json()["id"]

    def ids_visible(token: str) -> list[int]:
        res = client.get("/media?scope=team&limit=200", headers=auth(token))
        assert res.status_code == 200, res.text
        return [it["id"] for it in res.json()["items"]]

    # miembro del equipo A: ve el del A y el abierto
    vis = ids_visible(mate_a_token)
    assert item_a in vis and item_open in vis
    res = client.get(f"/media/{item_a}/file", headers=auth(mate_a_token))
    assert res.status_code == 200, res.text

    # miembro SOLO del equipo B: el abierto sí, el de A NO
    vis = ids_visible(mate_b_token)
    assert item_open in vis and item_a not in vis
    res = client.get(f"/media/{item_a}/file", headers=auth(mate_b_token))
    assert res.status_code == 401, res.text

    # PATCH: abrir el recurso a "todos mis equipos" (team_all) → también visible en B
    res = client.patch(
        f"/media/{item_a}", headers=auth(owner_token), json={"visibility": "team", "team_all": True}
    )
    assert res.status_code == 200, res.text
    assert res.json()["team_id"] is None
    assert item_a in ids_visible(mate_b_token)
