"""papelera, duplicados, metadata, visibilidad de equipo y proyectos

Revision ID: 0005
Revises: 0004
Create Date: 2026
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media_items", sa.Column("description", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("media_items", sa.Column("meta", sa.JSON(), nullable=True))
    op.add_column("media_items", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_media_items_sha256"), "media_items", ["sha256"])
    op.add_column(
        "media_items",
        sa.Column("visibility", sa.String(length=10), nullable=False, server_default="private"),
    )
    op.create_index(op.f("ix_media_items_visibility"), "media_items", ["visibility"])
    op.add_column("media_items", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "collections",
        sa.Column("is_project", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("collections", "is_project")
    op.drop_column("media_items", "deleted_at")
    op.drop_index(op.f("ix_media_items_visibility"), table_name="media_items")
    op.drop_column("media_items", "visibility")
    op.drop_index(op.f("ix_media_items_sha256"), table_name="media_items")
    op.drop_column("media_items", "sha256")
    op.drop_column("media_items", "meta")
    op.drop_column("media_items", "description")
