"""rating 0-5 por recurso (favoritos / mejor valorados)

Revision ID: 0006
Revises: 0005
Create Date: 2026
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_items",
        sa.Column("rating", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("media_items", "rating")
