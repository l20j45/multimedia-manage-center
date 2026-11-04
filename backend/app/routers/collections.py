"""Router /collections: colecciones (álbumes/playlists) de la biblioteca.

Colecciones privadas del usuario con N:M hacia /media. En SQLite el borrado
en cascada no está garantizado sin PRAGMA foreign_keys=ON, así que los
endpoints limpian las filas hijas manualmente.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.deps import get_current_user
from app.models import Collection, CollectionItem, MediaItem, User
from app.routers.media import _owned_item

router = APIRouter(prefix="/collections", tags=["collections"])


def _owned_collection(db: Session, user: User, collection_id: int) -> Collection:
    col = (
        db.query(Collection)
        .filter(Collection.id == collection_id, Collection.owner_id == user.id)
        .first()
    )
    if col is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Colección no encontrada")
    return col


@router.get("", response_model=list[schemas.CollectionOut])
def list_collections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.CollectionOut]:
    """Colecciones propias con el conteo de recursos de cada una."""
    collections = (
        db.query(Collection).filter(Collection.owner_id == user.id).order_by(Collection.name).all()
    )
    counts: dict[int, int] = defaultdict(int)
    rows = (
        db.query(CollectionItem.collection_id)
        .join(Collection, CollectionItem.collection_id == Collection.id)
        .filter(Collection.owner_id == user.id)
        .all()
    )
    for (col_id,) in rows:
        counts[col_id] += 1
    return [
        schemas.CollectionOut(id=c.id, name=c.name, item_count=counts[c.id]) for c in collections
    ]


@router.post("", response_model=schemas.CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(
    data: schemas.CollectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.CollectionOut:
    """Crea una colección (el nombre es único por usuario)."""
    exists = (
        db.query(Collection)
        .filter(Collection.owner_id == user.id, Collection.name == data.name.strip())
        .first()
    )
    if exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Ya existe una colección llamada '{data.name.strip()}'",
        )
    col = Collection(owner_id=user.id, name=data.name.strip())
    db.add(col)
    db.commit()
    db.refresh(col)
    return schemas.CollectionOut(id=col.id, name=col.name, item_count=0)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Borra la colección (los recursos NO se borran, solo su pertenencia)."""
    col = _owned_collection(db, user, collection_id)
    db.query(CollectionItem).filter(CollectionItem.collection_id == col.id).delete()
    db.delete(col)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{collection_id}/items", response_model=list[schemas.MediaOut])
def collection_items(
    collection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schemas.MediaOut]:
    """Recursos de una colección, en orden de posición."""
    col = _owned_collection(db, user, collection_id)
    items = (
        db.query(MediaItem)
        .join(CollectionItem, CollectionItem.media_id == MediaItem.id)
        .filter(CollectionItem.collection_id == col.id)
        .order_by(CollectionItem.position, CollectionItem.id)
        .all()
    )
    return [schemas.MediaOut.from_item(i) for i in items]


@router.post("/{collection_id}/items", status_code=status.HTTP_201_CREATED)
def add_item(
    collection_id: int,
    data: schemas.CollectionAddItem,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.CollectionOut:
    """Agrega un recurso propio a la colección."""
    col = _owned_collection(db, user, collection_id)
    media = _owned_item(db, user, data.media_id)  # 404 si no es suyo
    dup = (
        db.query(CollectionItem)
        .filter(
            CollectionItem.collection_id == col.id,
            CollectionItem.media_id == media.id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="El recurso ya está en la colección")
    position = (
        max(
            (
                p
                for (p,) in db.query(CollectionItem.position)
                .filter(CollectionItem.collection_id == col.id)
                .all()
            ),
            default=0,
        )
        + 1
    )
    db.add(CollectionItem(collection_id=col.id, media_id=media.id, position=position))
    db.commit()
    total = db.query(CollectionItem).filter(CollectionItem.collection_id == col.id).count()
    return schemas.CollectionOut(id=col.id, name=col.name, item_count=total)


@router.delete("/{collection_id}/items/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    collection_id: int,
    media_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Quita un recurso de la colección (sin borrar el recurso)."""
    col = _owned_collection(db, user, collection_id)
    _owned_item(db, user, media_id)
    rows = db.query(CollectionItem).filter(
        CollectionItem.collection_id == col.id, CollectionItem.media_id == media_id
    )
    if rows.first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No está en la colección")
    rows.delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
