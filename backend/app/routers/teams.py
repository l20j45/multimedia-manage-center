"""Router /teams: equipos para compartir recursos dentro del proyecto.

Un usuario crea un equipo (queda como owner), invita por correo a la gente
registrada y los recursos con visibility='team' del dueño se ven solo entre
compañeros de equipo. Los miembros pueden salir del equipo por su cuenta;
el owner gestiona la lista completa (o disuelve el equipo).
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_user
from app.models import Team, TeamMember, User
from app.services import teams as teams_svc

router = APIRouter(prefix="/teams", tags=["teams"])


def _team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado")
    return team


def _owner_of(team: Team, user: User) -> None:
    """Solo el owner (o un admin) gestiona la membrecía del equipo."""
    if team.owner_id != user.id and not user.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Solo el dueño del equipo (o un admin)"
        )


@router.get("", response_model=list[schemas.TeamOut])
def list_teams(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.TeamOut]:
    """Equipos a los que pertenezco (propios y de otros), con mi rol."""
    out: list[schemas.TeamOut] = []
    for team, role in teams_svc.my_teams(db, user):
        count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
        out.append(
            schemas.TeamOut(
                id=team.id, name=team.name, owner_id=team.owner_id, role=role, member_count=count
            )
        )
    return out


@router.post("", response_model=schemas.TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    data: schemas.TeamCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.TeamOut:
    """Crea un equipo; el creador queda como owner y primer miembro."""
    team = Team(name=data.name.strip()[:120], owner_id=user.id)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(team)
    return schemas.TeamOut(
        id=team.id, name=team.name, owner_id=team.owner_id, role="owner", member_count=1
    )


@router.get("/{team_id}", response_model=schemas.TeamDetailOut)
def team_detail(
    team_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Detalle del equipo: sus miembros con su rol (requiere pertenecer)."""
    team = _team_or_404(db, team_id)
    role = teams_svc.is_in_team(db, team, user)
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No perteneces a este equipo")
    members = teams_svc.team_members(db, team)
    roles = {
        m.user_id: m.role for m in db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    }
    return {
        "id": team.id,
        "name": team.name,
        "owner_id": team.owner_id,
        "role": role,
        "members": [
            schemas.TeamMemberOut(
                user_id=m.id,
                email=m.email,
                name=m.name,
                role=roles.get(m.id, "member"),
                is_active=m.is_active,
            )
            for m in members
        ],
    }


@router.post("/{team_id}/members", response_model=schemas.TeamMemberOut)
def add_member(
    team_id: int,
    data: schemas.TeamAddMember,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Invita a un usuario REGISTRADO por su correo."""
    team = _team_or_404(db, team_id)
    _owner_of(team, user)
    target = db.query(User).filter(User.email == data.email).first()
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Ese correo no está registrado todavía (regístralo primero)",
        )
    already = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == target.id)
        .first()
    )
    if already:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Ya es miembro del equipo")

    db.add(TeamMember(team_id=team.id, user_id=target.id, role="member"))
    db.commit()
    return schemas.TeamMemberOut(
        user_id=target.id,
        email=target.email,
        name=target.name,
        role="member",
        is_active=target.is_active,
    )


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    team_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Quita a un miembro (owner/admin). El owner solo sale eliminando el equipo."""
    team = _team_or_404(db, team_id)
    _owner_of(team, user)
    if user_id == team.owner_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="El owner no se quita del equipo; disuélvelo si quieres cerrar la lista",
        )
    row = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No es miembro del equipo")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{team_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_team(
    team_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Salgo del equipo (que no sea el owner: ese lo disuelve)."""
    team = _team_or_404(db, team_id)
    if team.owner_id == user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Eres el dueño: usa DELETE /teams/{id} para disolver el equipo",
        )
    row = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No eres miembro del equipo")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Disuelve el equipo (solo owner o admin). Los recursos NO se borran."""
    team = _team_or_404(db, team_id)
    _owner_of(team, user)
    db.query(TeamMember).filter(TeamMember.team_id == team.id).delete()
    db.delete(team)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
