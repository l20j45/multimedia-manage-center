# CORS: lista exacta + patrón regex (varias páginas/subdominios del proyecto).
# Las IPs de los CLIENTES no participan: CORS es sobre el ORIGEN que sirve
# una página en un navegador. Apps nativas/APK no les aplica.

from fastapi.testclient import TestClient

REGEX = r"https://.*\.l20j45\.us(:\d+)?"


def client_with(monkeypatch, extra_origins: str = "", regex: str = "") -> TestClient:
    from app.main import app  # noqa: PLC0415 — lazy: aplica settings de test

    app = app  # re-import barato; TestClient checa middleware por instancia
    monkeypatch.setenv("CORS_ORIGINS", extra_origins)
    monkeypatch.setenv("CORS_ORIGIN_REGEX", regex)
    # recrear la app NO re-lee settings (settings es singleton al import)…
    # así que testeamos contra la config real cargada por env antes del import:
    import importlib

    import app.config as config

    config.settings = config.Settings(CORS_ORIGINS=extra_origins, CORS_ORIGIN_REGEX=regex)
    mod = importlib.import_module("app.main")
    importlib.reload(mod)
    return TestClient(mod.app)


def test_preflight_origen_que_matchea_regex(monkeypatch) -> None:
    c = client_with(monkeypatch, "https://www.l20j45.us", REGEX)
    r = c.options(
        "/media",
        headers={
            "Origin": "https://panel.midProyecto.l20j45.us",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["access-control-allow-origin"] == "https://panel.midProyecto.l20j45.us"


def test_preflight_origen_desconocido_queda_fuera(monkeypatch) -> None:
    c = client_with(monkeypatch, "https://www.l20j45.us", REGEX)
    r = c.options(
        "/media",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 400 or "access-control-allow-origin" not in r.headers
