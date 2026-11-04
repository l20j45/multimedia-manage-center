"""Rate limiting por IP para los endpoints de escritura sensibles (login, registro,
recuperación de contraseña).

Implementación simple en memoria con ventana fija por IP (suficiente para un
solo proceso de uvicorn). Si algún día corres multiple workers/instancias detrás
de un balanceador, cámbialo por Redis o similar.

Se puede desactivar con RATE_LIMIT_ENABLED=false en backend/.env (útil en tests).
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

# (ip, ruta) → timestamps de las peticiones dentro de la ventana
_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)

# límite de peticiones por ruta y ventana (definidos en Settings)
_ROUTE_LIMITS: dict[str, int] = {
    "/auth/register": settings.RATE_LIMIT_REGISTER,
    "/auth/login": settings.RATE_LIMIT_LOGIN,
    "/auth/forgot-password": settings.RATE_LIMIT_PASSWORD_RESET,
    "/auth/reset-password": settings.RATE_LIMIT_PASSWORD_RESET,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Bloquea con 429 las peticiones que superan el límite por IP y ruta."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if settings.RATE_LIMIT_ENABLED:
            path = request.url.path
            limit = _ROUTE_LIMITS.get(path)
            if limit is not None and request.method in ("POST", "PATCH"):
                # Detrás de un proxy (nginx/Caddy) la IP real llega vía header
                ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
                    request.client.host if request.client else "unknown"
                )
                key = (ip, path)
                now = time.monotonic()
                bucket = _BUCKETS[key]
                while bucket and bucket[0] <= now - settings.RATE_LIMIT_WINDOW:
                    bucket.popleft()
                if len(bucket) >= limit:
                    retry_after = max(1, math.ceil(settings.RATE_LIMIT_WINDOW - (now - bucket[0])))
                    return JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={"detail": "Demasiadas peticiones. Espera un momento."},
                    )
                bucket.append(now)
        return await call_next(request)


def reset_rate_limits() -> None:
    """Vacía los contadores (helper para tests y entornos de larga vida)."""
    _BUCKETS.clear()
