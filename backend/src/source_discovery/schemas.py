"""
Pydantic v2 request / response schemas for the source discovery module.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EventMetadata(BaseModel):
    location: str
    coordinates: Optional[List[float]] = None  # [lat, lon]
    event_type: str
    event_date: str
    description: str


class ScoringOptions(BaseModel):
    profile: str = "default"
    overrides: Optional[Dict[str, float]] = None
    # custom_weights fully overrides profile + overrides when present
    custom_weights: Optional[Dict[str, float]] = None


class PipelineRunRequest(BaseModel):
    event: EventMetadata
    scoring: ScoringOptions = Field(default_factory=ScoringOptions)
    max_sources: int = Field(default=20, ge=1, le=50)


class RescoreRequest(BaseModel):
    scoring: ScoringOptions


class SourceRatingRequest(BaseModel):
    url: str
    rating: int = Field(..., ge=1, le=5)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TaskCreatedResponse(BaseModel):
    task_id: str


class PipelineStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ScoredSource(BaseModel):
    url: str
    title: Optional[str] = None
    angle: Optional[str] = None
    source_type: Optional[str] = None
    original_query: Optional[str] = None
    composite_score: float
    # Core scoring dimensions (0-10 scale)
    event_specificity: float = 0.0
    actionability: float = 0.0
    accountability_signal: float = 0.0
    community_proximity: float = 0.0
    independence: float = 0.0
    # Extended characterization fields (0-10 scale)
    credibility: float = 0.0
    recency: float = 0.0
    depth: float = 0.0
    geographic_relevance: float = 0.0
    language_accessibility: float = 0.0
    source_type_quality: float = 0.0
    unique_angle: float = 0.0
    # Qualitative summary from Claude
    summary: Optional[str] = None

    class Config:
        extra = "allow"


class PipelineResultsResponse(BaseModel):
    task_id: str
    status: str
    weights_used: Dict[str, float]
    sources: List[ScoredSource]


class ProfilesResponse(BaseModel):
    profiles: Dict[str, Dict[str, float]]


class ReportResponse(BaseModel):
    task_id: str
    report_text: str


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str


class RescoreResponse(BaseModel):
    task_id: str
    sources: List[ScoredSource]
    weights_used: Dict[str, float]


class RatingResponse(BaseModel):
    id: int
    task_id: str
    url: str
    rating: int
