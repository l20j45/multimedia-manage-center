"""share_token por colección (enlace público revocable)

Revision ID: 0007
Revises: 0006
Create Date: 2026
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("share_token", sa.String(length=43), nullable=True))
    op.create_index(op.f("ix_collections_share_token"), "collections", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_collections_share_token"), table_name="collections")
    op.drop_column("collections", "share_token")
