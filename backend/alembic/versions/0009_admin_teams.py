"""is_admin en users + teams/team_members para compartir por equipos

El PRIMER usuario de la instalación (el más antiguo en la BD) queda como
super admin en la migración; en el runtime, el primero que registre recibe
el flag al registrarse.

Revision ID: 0009
Revises: e7582b5d2320
Create Date: 2026
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0009"
down_revision = "e7582b5d2320"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    # Retro-compatibilidad: la instalación ya en marcha respeta a su dueño
    # original (usuario más antiguo) como super admin.
    op.execute("UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users)")

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role", sa.String(length=10), server_default="member", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )


def downgrade() -> None:
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_column("users", "is_admin")
