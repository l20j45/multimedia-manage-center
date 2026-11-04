"""collections: colecciones de la biblioteca (N:M con media_items)

Revision ID: 0004
Revises: 0003
Create Date: 2026
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.UniqueConstraint("owner_id", "name"),
    )
    op.create_index(op.f("ix_collections_id"), "collections", ["id"])
    op.create_index(op.f("ix_collections_owner_id"), "collections", ["owner_id"])

    op.create_table(
        "collection_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["media_items.id"]),
        sa.UniqueConstraint("collection_id", "media_id"),
    )
    op.create_index(op.f("ix_collection_items_id"), "collection_items", ["id"])
    op.create_index(
        op.f("ix_collection_items_collection_id"), "collection_items", ["collection_id"]
    )
    op.create_index(op.f("ix_collection_items_media_id"), "collection_items", ["media_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_collection_items_media_id"), table_name="collection_items")
    op.drop_index(op.f("ix_collection_items_collection_id"), table_name="collection_items")
    op.drop_index(op.f("ix_collection_items_id"), table_name="collection_items")
    op.drop_table("collection_items")
    op.drop_index(op.f("ix_collections_owner_id"), table_name="collections")
    op.drop_index(op.f("ix_collections_id"), table_name="collections")
    op.drop_table("collections")
