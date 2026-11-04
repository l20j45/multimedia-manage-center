"""Config común de pytest para el backend.

- BD aislada por sesión de tests (los tests NUNCA tocan la app.db de dev).
- Se aplica antes de cualquier import de app.main (que corre migraciones al import).
"""

import os
import tempfile

_TMPDB = os.path.join(tempfile.mkdtemp(prefix="biblioteca-test-db-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDB}"
