"""
Standalone FastAPI entry point for the CAIC Source Discovery backend.

Run locally:
    uvicorn app:app --reload

The source discovery routes are mounted at /api/source-discovery.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.source_discovery import router as source_discovery_router
from src.auth_jwt import router as auth_router

app = FastAPI(
    title="CAIC Source Discovery API",
    description="Standalone source discovery and ranking backend for climate events.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(source_discovery_router, prefix="/api/source-discovery")
app.include_router(auth_router, prefix="/api")


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("CAIC Source Discovery API starting up")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "caic-source-discovery"}


@app.post("/init-db")
def initialize_database():
    """Create all tables (run once after deploying)."""
    try:
        from src.database import create_tables
        create_tables()
        return {"status": "success", "message": "Database tables created"}
    except Exception as exc:
        logger.error("init-db failed: %s", exc)
        return {"status": "error", "message": str(exc)}
