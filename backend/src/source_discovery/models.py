"""
SQLAlchemy models for the source discovery module.
All table names are prefixed with sd_ to avoid collision with host-app tables.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from ..models.base import Base


def compute_event_hash(event: dict) -> str:
    """SHA-256 of a canonically serialised event dict, truncated to 64 chars."""
    serialised = json.dumps(event, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode()).hexdigest()[:64]


class SDCharacterization(Base):
    """Cache of Claude characterizations keyed by (url, event_hash)."""

    __tablename__ = "sd_characterizations"
    __table_args__ = (
        UniqueConstraint("url", "event_hash", name="uq_sd_char_url_event"),
        Index("ix_sd_char_url", "url"),
        Index("ix_sd_char_event_hash", "event_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    characterization: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SDPipelineRun(Base):
    """Tracks a single pipeline execution including status, progress, and result."""

    __tablename__ = "sd_pipeline_runs"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event: Mapped[dict] = mapped_column(JSONB, nullable=False)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    profile_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    progress: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class SDSourceRating(Base):
    """User rating for a specific source within a pipeline run."""

    __tablename__ = "sd_source_ratings"
    __table_args__ = (Index("ix_sd_rating_task_id", "task_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    weights_used: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dimension_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
