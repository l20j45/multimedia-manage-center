"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Generado con: uv run alembic revision --autogenerate -m "${message}"
"""
from alembic import op  # noqa: I001
import sqlalchemy as sa
${imports if imports else ""}

# Identificadores de la revisión (no tocar a mano)
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
