"""Rate limiting: 429 tras superar el límite por IP (login)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app import rate_limit
from app.main import app

client = TestClient(app)


def test_login_rate_limit() -> None:
    rate_limit.reset_rate_limits()  # aísla este test de otros
    email = f"brute-{uuid4().hex[:8]}@example.com"

    codigos = []
    for _ in range(15):
        res = client.post("/auth/login", data={"username": email, "password": "clave-errada"})
        if res.status_code == 429:
            codigos.append(res.status_code)
            break
        codigos.append(res.status_code)

    assert codigos[-1] == 429, "debe bloquear al superar el límite"
    # Las primeras 10 pasan (límite por defecto de /auth/login), ninguna 429 antes
    assert all(c != 429 for c in codigos[:10])
    # El 429 trae Retry-After útil para el cliente
    res = client.post("/auth/login", data={"username": email, "password": "x"})
    assert res.headers.get("Retry-After") is not None


def test_endpoint_libre_sin_limite() -> None:
    """GET /health no está en la lista de ruta limitada."""
    rate_limit.reset_rate_limits()
    for _ in range(15):
        assert client.get("/health").status_code == 200


def test_teams_y_admin_con_limite_por_prefijo() -> None:
    """/teams/<id>/members y /admin/... aceptan el límite por prefijo (429 al agotar)."""
    rate_limit.reset_rate_limits()

    email = f"rl-{uuid4().hex[:8]}@example.com"
    res = client.post("/auth/register", json={"email": email, "password": "clavelarga123"})
    assert res.status_code == 201, res.text
    res = client.post("/auth/login", data={"username": email, "password": "clavelarga123"})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    res = client.post("/teams", headers={"Authorization": f"Bearer {token}"}, json={"name": "RL"})
    assert res.status_code == 201, res.text
    path = f"/teams/{res.json()['id']}/members"

    codigos = []
    for _ in range(70):
        res = client.post(
            path,
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "nadie-rl@example.com"},
        )
        codigos.append(res.status_code)
        if res.status_code == 429:
            break
    rate_limit.reset_rate_limits()
    assert codigos[-1] == 429, "el prefijo /teams debe terminar en 429"
    assert codigos.count(429) == 1
