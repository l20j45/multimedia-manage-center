"""Lógica de equipos: membresías y alcance de lo "del equipo".

`teammate_owner_ids` es la pieza que conecta los equipos con la biblioteca:
los recursos con visibility='team' se ven SOLO entre miembros de los equipos
en común (antes se veían entre toda la gente de la instalación).
"""

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

from app.models import MediaItem, Team, TeamMember, User


def get_team_or_404(db: Session, team_id: int) -> Team:
    """Equipo por id o 404 (helper reusado por varios routers)."""
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado")
    return team


def my_teams(db: Session, user: User) -> list[tuple[Team, str]]:
    """[(equipo, rol)] de los equipos a los que pertenece `user`."""
    me = aliased(TeamMember)
    rows = (
        db.query(Team, me.role)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user.id)
        .order_by(Team.id)
        .all()
    )
    return [(team, role or "member") for team, role in rows]


def my_team_ids(db: Session, user: User) -> list[int]:
    """IDs de los equipos a los que pertenezco (para filtrar SQL)."""
    return [
        tid for (tid,) in (db.query(TeamMember.team_id).filter(TeamMember.user_id == user.id).all())
    ]


def team_share_condition(db: Session, user: User):
    """Cláusula SQL: recursos `visibility='team'` legibles por `user`.

    Un recurso del equipo es legible si:
    - team_id es NULL y el dueño comparte CUALQUIER equipo con `user`, o
    - team_id apunta a un equipo del que `user` es miembro (aunque no
      comparta otros equipos con su dueño).
    """
    mates = teammate_owner_ids(db, user)
    teams_mine = my_team_ids(db, user)
    return or_(
        and_(
            MediaItem.visibility == "team",
            MediaItem.team_id.is_(None),
            MediaItem.owner_id.in_(mates),
        ),
        and_(
            MediaItem.visibility == "team",
            MediaItem.team_id.in_(teams_mine),
        ),
    )


def teammate_owner_ids(db: Session, user: User) -> list[int]:
    """IDs de AUTORES que comparten algún equipo con `user` (sin él mismo).

    Determina qué recursos visibility='team' le son legibles: los de los
    dueños con quien comparte equipo.
    """
    my_team_ids = (
        db.query(TeamMember.team_id).filter(TeamMember.user_id == user.id).scalar_subquery()
    )
    rows = (
        db.query(TeamMember.user_id)
        .filter(TeamMember.team_id.in_(my_team_ids), TeamMember.user_id != user.id)
        .distinct()
        .all()
    )
    return [uid for (uid,) in rows]


def is_in_team(db: Session, team: Team, user: User) -> str | None:
    """Si `user` pertenece al equipo, devuelve su rol (owner|member); None si no."""
    row = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
        .first()
    )
    return row.role if row else None


def team_members(db: Session, team: Team) -> list[User]:
    """Usuarios miembro del equipo (dueño incluido)."""
    return (
        db.query(User)
        .join(TeamMember, TeamMember.user_id == User.id)
        .filter(TeamMember.team_id == team.id)
        .order_by(TeamMember.id)
        .all()
    )


def member_role(db: Session, team: Team, user: User) -> str:
    """Rol de `user` en el equipo: owner si es el creador, member si pertenece."""
    row = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
        .first()
    )
    if row:
        return row.role
    return "member"
