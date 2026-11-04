"""Config común de pytest para el backend.

- BD aislada por sesión de tests (los tests NUNCA tocan la app.db de dev).
- Contadores de rate limiting por test (evita 429 cruzados entre tests).
- Se aplica antes de cualquier import de app.main (que corre migraciones al import).
"""

import os
import tempfile

import pytest

_TMPDB = os.path.join(tempfile.mkdtemp(prefix="biblioteca-test-db-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDB}"

# Se importa DESPUÉS de fijar la BD (app.main aplica migraciones al importar).
from app.rate_limit import reset_rate_limits  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_rate_limit_buckets():
    reset_rate_limits()
    yield
    reset_rate_limits()
