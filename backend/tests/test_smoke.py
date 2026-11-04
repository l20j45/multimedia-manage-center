"""Test de humo: /health + ciclo completo registro → login → perfil + recuperación.

Se ejecuta con:  uv run pytest
Se usa aleatoriedad en el email para poder repetirlo contra la misma BD.
"""

import re
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services import email as email_service

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_ciclo_registro_login_perfil() -> None:
    email = f"demo-{uuid.uuid4().hex[:8]}@example.com"

    # Registro
    res = client.post(
        "/auth/register",
        json={"email": email, "password": "superclave123", "name": "Demo"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["email"] == email

    # Login → token
    res = client.post("/auth/login", data={"username": email, "password": "superclave123"})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    # Perfil autenticado
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.json()["email"] == email


def test_recuperacion_contrasena(monkeypatch) -> None:
    """Flujo completo: forgot-password → código (correo capturado) → reset → login.

    Se intercepta send_email (lo mismo que hace el tramo de SMTP) para poder leer
    el correo del código sin depender del logging ni de tener SMTP configurado.
    """
    email = f"reset-{uuid.uuid4().hex[:8]}@example.com"
    nueva = "nuevaclave456"

    capturado: dict[str, str] = {}

    def fake_send(to: str, subject: str, html: str) -> bool:
        capturado["to"], capturado["subject"], capturado["html"] = to, subject, html
        return False

    monkeypatch.setattr(email_service, "send_email", fake_send)

    # Cuenta existente
    res = client.post("/auth/register", json={"email": email, "password": "clavelarga123"})
    assert res.status_code == 201, res.text

    # Pide el código (con TestClient los BackgroundTasks corren tras la respuesta)
    res = client.post("/auth/forgot-password", json={"email": email})
    assert res.status_code == 204, res.text

    match = re.search(r">\s*(\d{6})\s*<", capturado.get("html", ""))
    assert match, f"No se capturó el correo con el código: {capturado}"
    code = match.group(1)
    assert capturado["to"] == email

    # Restablece con el código
    res = client.post(
        "/auth/reset-password", json={"email": email, "code": code, "new_password": nueva}
    )
    assert res.status_code == 200, res.text

    # El código se consume (un solo uso)
    res = client.post(
        "/auth/reset-password", json={"email": email, "code": code, "new_password": "otraclave999"}
    )
    assert res.status_code == 400, res.text

    # Login con la contraseña nueva OK; la vieja ya no sirve
    res = client.post("/auth/login", data={"username": email, "password": nueva})
    assert res.status_code == 200, res.text
    res = client.post("/auth/login", data={"username": email, "password": "clavelarga123"})
    assert res.status_code == 401

    # Correo desconocido → misma respuesta (sin revelar si existe)
    res = client.post(
        "/auth/forgot-password", json={"email": f"nadie-{uuid.uuid4().hex[:6]}@x.com"}
    )
    assert res.status_code == 204
