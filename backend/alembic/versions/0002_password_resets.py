"""password_resets: tokens de recuperación de contraseña

Revision ID: 0002
Revises: 0001
Create Date: 2026

Tabla de códigos de un solo uso para /auth/forgot-password y /auth/reset-password.
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_password_resets_id"), "password_resets", ["id"])
    op.create_index(op.f("ix_password_resets_user_id"), "password_resets", ["user_id"])
    op.create_index(
        op.f("ix_password_resets_code_hash"), "password_resets", ["code_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_password_resets_code_hash"), table_name="password_resets")
    op.drop_index(op.f("ix_password_resets_user_id"), table_name="password_resets")
    op.drop_index(op.f("ix_password_resets_id"), table_name="password_resets")
    op.drop_table("password_resets")
