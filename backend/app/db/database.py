"""
backend/app/db/database.py

SQLAlchemy session/engine setup. Defaults to SQLite for local dev/demo (per
spec section 24). Set DATABASE_URL to a postgresql:// DSN for production --
nothing in the persistence layer is SQLite-specific.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./riskreplay.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import orm_models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=engine)
