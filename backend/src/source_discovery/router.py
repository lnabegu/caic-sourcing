"""
FastAPI router for source discovery endpoints.
Mount at /api/source-discovery via:
    app.include_router(source_discovery_router, prefix="/api/source-discovery")
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.auth import get_current_active_user
from ..database import get_db
from ..models.base import SessionLocal
from .config import default_scoring_config
from .models import SDPipelineRun, SDSourceRating
from .schemas import (
    ChatRequest,
    ChatResponse,
    PipelineResultsResponse,
    PipelineRunRequest,
    PipelineStatusResponse,
    ProfilesResponse,
    RatingResponse,
    RescoreRequest,
    RescoreResponse,
    ReportResponse,
    ScoredSource,
    SourceRatingRequest,
    TaskCreatedResponse,
)
from .tasks import run_pipeline_task

logger = logging.getLogger(__name__)

router = APIRouter(tags=["source-discovery"])


def _resolve_weights(scoring) -> Dict[str, float]:
    """Resolve ScoringOptions to a weights dict."""
    if scoring.custom_weights:
        default_scoring_config._validate_weights(scoring.custom_weights)
        total = sum(scoring.custom_weights.values())
        return {k: v / total for k, v in scoring.custom_weights.items()}
    return default_scoring_config.resolve(
        profile=scoring.profile, overrides=scoring.overrides
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/pipeline/run",
    response_model=TaskCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_pipeline(
    body: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a pipeline run and kick it off in the background."""
    try:
        weights = _resolve_weights(body.scoring)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task_id = str(uuid.uuid4())
    event_dict = body.event.model_dump()

    run = SDPipelineRun(
        task_id=task_id,
        event=event_dict,
        weights=weights,
        profile_name=body.scoring.profile if not body.scoring.custom_weights else None,
        status="pending",
    )
    db.add(run)
    db.commit()

    background_tasks.add_task(
        run_pipeline_task,
        task_id=task_id,
        event=event_dict,
        weights=weights,
        db_factory=SessionLocal,
    )

    return TaskCreatedResponse(task_id=task_id)


@router.get("/pipeline/{task_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Return current status and progress of a pipeline run."""
    run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return PipelineStatusResponse(
        task_id=run.task_id,
        status=run.status,
        progress=run.progress,
        error=run.error,
    )


@router.get("/pipeline/{task_id}/results", response_model=PipelineResultsResponse)
async def get_pipeline_results(
    task_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Return scored sources for a completed pipeline run (409 if not complete)."""
    run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline is not completed yet (status: {run.status})",
        )
    sources = [ScoredSource(**s) for s in (run.result or [])]
    return PipelineResultsResponse(
        task_id=run.task_id,
        status=run.status,
        weights_used=run.weights,
        sources=sources,
    )


@router.post("/pipeline/{task_id}/rate", response_model=RatingResponse)
async def rate_source(
    task_id: str,
    body: SourceRatingRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Store a user rating for a source with a snapshot of weights and scores."""
    run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    # Find dimension scores snapshot for this URL from the result
    dimension_scores: Dict[str, Any] = {}
    if run.result:
        for src in run.result:
            if src.get("url") == body.url:
                from .config import SCORING_DIMENSIONS
                dimension_scores = {d: src.get(d, 0) for d in SCORING_DIMENSIONS}
                break

    rating_row = SDSourceRating(
        task_id=task_id,
        url=body.url,
        rating=body.rating,
        weights_used=run.weights,
        dimension_scores=dimension_scores,
    )
    db.add(rating_row)
    db.commit()
    db.refresh(rating_row)

    return RatingResponse(
        id=rating_row.id,
        task_id=rating_row.task_id,
        url=rating_row.url,
        rating=rating_row.rating,
    )


_REPORT_PROMPT = """You are generating a structured climate event report for community leaders and decision-makers. This report should be actionable, specific, and grounded in the sources provided.

Event context:
{event}

You have {num_sources} characterized sources. For each source, you have structured metadata including named officials, commitments with dollar amounts and timelines, unmet needs, and coverage topics.

Here are the characterized sources (without full text):
{sources_summary}

Generate a report with these sections:

1. EVENT OVERVIEW
Synthesize what happened, when, where, who was affected, and the scale of impact. Include specific numbers.

2. CAUSES AND CLIMATE CONTEXT
What caused this event? What role did climate change play? Cite specific scientific findings.

3. KEY DECISION MAKERS AND RESPONSE
Who led the response? Name specific officials, organizations, and their roles. What actions did they take?

4. COMMITMENTS AND FUNDING
List every specific commitment with: who committed, what they committed, how much, and by when. Flag commitments without timelines or amounts.

5. ACTIONS AND PREPAREDNESS
What preparedness systems existed? Where did they succeed or fail? What actions are recommended going forward?

6. GAPS AND UNMET NEEDS
What is still missing? Who is being left out? Where do sources disagree or where is information absent? Be specific about populations, sectors, and geographic areas.

7. SOURCE LANDSCAPE
Briefly characterize the sources used: how many are institutional vs independent vs community-produced? What perspectives are missing? What languages are underrepresented?

Rules:
- Be specific. Use names, numbers, dates, and dollar amounts from the source characterizations.
- When sources disagree on figures (e.g. death tolls), note the range and which sources report which numbers.
- Flag where claims lack independent verification.
- The report should be useful to someone who has never read any of these sources.
- When citing specific facts, name the source (e.g., "according to the UNOCHA Situation Report No. 10" or "per the Red Cross Situation Report No. 8").
- Include a numbered REFERENCES section at the end listing all sources used, with title and URL.

- Be concise. Each section should be 2-3 paragraphs maximum.

Return the report as plain text with section headers."""


@router.post("/pipeline/{task_id}/report", response_model=ReportResponse)
def generate_report(
    task_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Generate an AI report synthesizing all sources for a completed pipeline run."""
    import os
    import json
    import anthropic

    run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline is not completed yet (status: {run.status})",
        )

    sources = run.result or []

    sources_summary = "\n\n".join(
        f"Source {i + 1}: {s.get('title', 'Untitled')}\n"
        f"URL: {s.get('url', '')}\n"
        f"Type: {s.get('source_type', '')} | Angle: {s.get('angle', '')}\n"
        f"Scores (0-10): event_specificity={s.get('event_specificity', 0)}, "
        f"actionability={s.get('actionability', 0)}, "
        f"accountability_signal={s.get('accountability_signal', 0)}, "
        f"community_proximity={s.get('community_proximity', 0)}, "
        f"independence={s.get('independence', 0)}\n"
        f"Summary: {s.get('summary', 'No summary available.')}"
        for i, s in enumerate(sources)
    )

    prompt = _REPORT_PROMPT.format(
        event=json.dumps(run.event, indent=2),
        num_sources=len(sources),
        sources_summary=sources_summary,
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    report_text = message.content[0].text.strip()

    return ReportResponse(task_id=task_id, report_text=report_text)


_CHAT_SYSTEM = """You are an expert analyst assistant helping users explore a climate event report.

Event context:
{event}

The following sources were analyzed (with summaries):
{sources_summary}

Answer questions about this event using only the information in these sources. Be specific — cite source titles when making claims. If something isn't covered by the sources, say so clearly. Keep answers concise (2-4 paragraphs max)."""


@router.post("/pipeline/{task_id}/chat", response_model=ChatResponse)
def chat(
    task_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Answer a question about a completed pipeline run using Claude."""
    import os
    import json
    import anthropic

    run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "completed":
        raise HTTPException(status_code=409, detail="Pipeline not completed")

    sources = run.result or []
    sources_summary = "\n\n".join(
        f"Source {i + 1}: {s.get('title', 'Untitled')}\n"
        f"URL: {s.get('url', '')}\n"
        f"Type: {s.get('source_type', '')} | Angle: {s.get('angle', '')}\n"
        f"Summary: {s.get('summary', 'No summary available.')}"
        for i, s in enumerate(sources)
    )

    system = _CHAT_SYSTEM.format(
        event=json.dumps(run.event, indent=2),
        sources_summary=sources_summary,
    )

    messages = [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    return ChatResponse(reply=response.content[0].text.strip())


@router.get("/scoring/profiles", response_model=ProfilesResponse)
async def list_scoring_profiles(
    current_user=Depends(get_current_active_user),
):
    """Return all available scoring profiles."""
    return ProfilesResponse(profiles=default_scoring_config.list_profiles())


@router.post("/pipeline/{task_id}/rescore", response_model=RescoreResponse)
async def rescore_pipeline(
    task_id: str,
    body: RescoreRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Re-rank completed pipeline results with new weights (no re-run)."""
    run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot rescore: pipeline status is '{run.status}'",
        )

    try:
        weights = _resolve_weights(body.scoring)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from .pipeline import score_sources

    rescored = score_sources(run.result or [], weights)
    sources = [ScoredSource(**s) for s in rescored]

    return RescoreResponse(
        task_id=task_id,
        sources=sources,
        weights_used=weights,
    )
