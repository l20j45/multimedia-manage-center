"""media_items: biblioteca privada de recursos del usuario

Revision ID: 0003
Revises: 0002
Create Date: 2026

Tabla de audio/imagen/video subidos por el usuario. Los ficheros viven
en MEDIA_DIR (fuera de la BD); path/thumb_path son rutas relativas a esa carpeta.
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("tags", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("thumb_path", sa.String(length=255), nullable=True),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.UniqueConstraint("path"),
    )
    op.create_index(op.f("ix_media_items_id"), "media_items", ["id"])
    op.create_index(op.f("ix_media_items_owner_id"), "media_items", ["owner_id"])
    op.create_index(op.f("ix_media_items_kind"), "media_items", ["kind"])


def downgrade() -> None:
    op.drop_index(op.f("ix_media_items_kind"), table_name="media_items")
    op.drop_index(op.f("ix_media_items_owner_id"), table_name="media_items")
    op.drop_index(op.f("ix_media_items_id"), table_name="media_items")
    op.drop_table("media_items")
