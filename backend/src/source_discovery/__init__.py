"""
source_discovery — CAIC Source Discovery library for MMRAG.

Public surface:
    router          — FastAPI APIRouter to mount at /api/source-discovery
    ScoringConfig   — scoring profile management class
    default_scoring_config — module-level singleton
"""
from .config import ScoringConfig, default_scoring_config
from .router import router

__all__ = ["router", "ScoringConfig", "default_scoring_config"]
