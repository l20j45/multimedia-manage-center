"""Conexión a la base de datos (SQLite por defecto)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa de los modelos."""


def get_db():
    """Sesión de BD por petición (Dependency de FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
