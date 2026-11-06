"""media_items.team_id: compartir un recurso a UN equipo concreto

visibility='team' + team_id → lo ven los miembros de ESE equipo.
visibility='team' + team_id NULL → lo ven los compañeros de CUALQUIER
equipo mío (comportamiento original).
"""

import sqlalchemy as sa

from alembic import op

# Identificadores de la revisión
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite no acepta ALTER TABLE ADD CONSTRAINT por FK: re-crear la tabla en
    # modo batch (conserva los datos) para llevar la FK de teams.
    with op.batch_alter_table("media_items") as batch:
        batch.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_index("ix_media_items_team_id", "media_items", ["team_id"])
    with op.batch_alter_table("media_items") as batch:
        batch.create_foreign_key("fk_media_items_team_id", "teams", ["team_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("media_items") as batch:
        batch.drop_column("team_id")
