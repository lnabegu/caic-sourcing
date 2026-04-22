"""
Database session management and table creation helpers.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from .models.base import Base, SessionLocal, engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all registered tables. Import models first to register them."""
    from .models import User  # noqa: F401 — registers User with Base
    from .source_discovery.models import (  # noqa: F401 — registers SD tables
        SDCharacterization,
        SDPipelineRun,
        SDSourceRating,
    )

    Base.metadata.create_all(bind=engine)
