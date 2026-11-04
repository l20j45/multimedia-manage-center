"""Router /health: verificación de estado de la API."""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "project": "Biblioteca de Recursos Multimedia"}
