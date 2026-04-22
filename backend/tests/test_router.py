"""
Integration tests for source_discovery router.
Uses FastAPI TestClient with a mock DB session and mocked pipeline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Minimal app fixture
# ---------------------------------------------------------------------------

def _make_app():
    """Build a minimal FastAPI app with the source_discovery router mounted."""
    from src.source_discovery.router import router
    from src.database import get_db
    from src.core.auth import get_current_active_user

    app = FastAPI()

    # Override auth — always return a mock user
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.is_active = True
    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    app.include_router(router, prefix="/api/source-discovery")
    return app


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------

def _mock_db_session():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    """TestClient with mocked DB and background task runner."""
    import sys
    # Force the submodule to load, then retrieve it from sys.modules to avoid
    # the naming collision with the `router` APIRouter attribute on the package.
    from src.source_discovery import router as _  # noqa: F401 — triggers submodule load
    router_module = sys.modules["src.source_discovery.router"]

    db = _mock_db_session()

    # Stub out background task execution so it doesn't actually run the pipeline
    monkeypatch.setattr(router_module, "run_pipeline_task", lambda **kwargs: None)

    app = _make_app()

    # Override get_db
    from src.database import get_db

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    return TestClient(app), db


def test_run_pipeline_returns_202_and_task_id(client):
    tc, db = client
    payload = {
        "event": {
            "location": "Mumbai",
            "event_type": "flood",
            "event_date": "2026-04-01",
            "description": "Heavy flooding in Mumbai",
        },
        "scoring": {"profile": "default"},
        "max_sources": 20,
    }
    response = tc.post("/api/source-discovery/pipeline/run", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert len(data["task_id"]) == 36  # UUID4


def test_get_status_returns_pending(client):
    tc, db = client
    from src.source_discovery.models import SDPipelineRun

    mock_run = MagicMock(spec=SDPipelineRun)
    mock_run.task_id = "test-task-123"
    mock_run.status = "pending"
    mock_run.progress = None
    mock_run.error = None

    db.query.return_value.filter.return_value.first.return_value = mock_run

    response = tc.get("/api/source-discovery/pipeline/test-task-123/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["task_id"] == "test-task-123"


def test_get_results_returns_409_when_pending(client):
    tc, db = client
    from src.source_discovery.models import SDPipelineRun

    mock_run = MagicMock(spec=SDPipelineRun)
    mock_run.task_id = "test-task-123"
    mock_run.status = "pending"

    db.query.return_value.filter.return_value.first.return_value = mock_run

    response = tc.get("/api/source-discovery/pipeline/test-task-123/results")
    assert response.status_code == 409


def test_get_results_returns_sources_when_completed(client):
    tc, db = client
    from src.source_discovery.models import SDPipelineRun

    mock_run = MagicMock(spec=SDPipelineRun)
    mock_run.task_id = "test-task-123"
    mock_run.status = "completed"
    mock_run.weights = {
        "event_specificity": 0.25,
        "actionability": 0.20,
        "accountability_signal": 0.20,
        "community_proximity": 0.20,
        "independence": 0.15,
    }
    mock_run.result = [
        {
            "url": "http://example.com/1",
            "title": "Source 1",
            "angle": "official",
            "source_type": "news",
            "composite_score": 7.5,
            "event_specificity": 8.0,
            "actionability": 7.0,
            "accountability_signal": 8.0,
            "community_proximity": 7.0,
            "independence": 6.0,
        }
    ]

    db.query.return_value.filter.return_value.first.return_value = mock_run

    response = tc.get("/api/source-discovery/pipeline/test-task-123/results")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["url"] == "http://example.com/1"


def test_rate_source_stores_rating(client):
    tc, db = client
    from src.source_discovery.models import SDPipelineRun, SDSourceRating

    mock_run = MagicMock(spec=SDPipelineRun)
    mock_run.task_id = "test-task-123"
    mock_run.status = "completed"
    mock_run.weights = {"event_specificity": 0.25, "actionability": 0.20,
                        "accountability_signal": 0.20, "community_proximity": 0.20,
                        "independence": 0.15}
    mock_run.result = [{"url": "http://example.com/1", "event_specificity": 8.0,
                        "actionability": 7.0, "accountability_signal": 7.0,
                        "community_proximity": 6.0, "independence": 5.0}]

    mock_rating = MagicMock(spec=SDSourceRating)
    mock_rating.id = 42
    mock_rating.task_id = "test-task-123"
    mock_rating.url = "http://example.com/1"
    mock_rating.rating = 4

    db.query.return_value.filter.return_value.first.return_value = mock_run
    db.refresh.side_effect = lambda obj: setattr(obj, 'id', 42) or None

    # Replace the rating row that gets added and committed
    added_objects = []
    def _add(obj):
        if isinstance(obj, SDSourceRating):
            obj.id = 42
            obj.task_id = "test-task-123"
            obj.url = "http://example.com/1"
            obj.rating = 4
            added_objects.append(obj)
    db.add.side_effect = _add

    response = tc.post(
        "/api/source-discovery/pipeline/test-task-123/rate",
        json={"url": "http://example.com/1", "rating": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rating"] == 4
    assert data["url"] == "http://example.com/1"


def test_rescore_returns_reranked_sources(client):
    tc, db = client
    from src.source_discovery.models import SDPipelineRun

    mock_run = MagicMock(spec=SDPipelineRun)
    mock_run.task_id = "test-task-123"
    mock_run.status = "completed"
    mock_run.result = [
        {
            "url": "http://example.com/1",
            "composite_score": 5.0,
            "event_specificity": 9.0,
            "actionability": 2.0,
            "accountability_signal": 5.0,
            "community_proximity": 5.0,
            "independence": 5.0,
        },
        {
            "url": "http://example.com/2",
            "composite_score": 5.0,
            "event_specificity": 2.0,
            "actionability": 9.0,
            "accountability_signal": 5.0,
            "community_proximity": 5.0,
            "independence": 5.0,
        },
    ]

    db.query.return_value.filter.return_value.first.return_value = mock_run

    # Use "actionable" profile which heavily weights actionability
    response = tc.post(
        "/api/source-discovery/pipeline/test-task-123/rescore",
        json={"scoring": {"profile": "actionable"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 2
    # With actionable profile, url/2 (high actionability) should rank first
    assert data["sources"][0]["url"] == "http://example.com/2"


def test_list_scoring_profiles_returns_5_profiles(client):
    tc, _ = client
    response = tc.get("/api/source-discovery/scoring/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "profiles" in data
    assert len(data["profiles"]) >= 5
    assert "default" in data["profiles"]
