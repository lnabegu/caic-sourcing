"""
Background task: run_pipeline_task()

Runs the full source-discovery pipeline outside of the request lifecycle.
Opens its own DB session via db_factory so FastAPI's request-scoped session
has already been closed.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict

import anthropic

from .models import SDCharacterization, SDPipelineRun, compute_event_hash
from .pipeline import (
    characterize_all,
    extract_results,
    generate_queries,
    score_sources,
    search_queries,
)

logger = logging.getLogger(__name__)


def run_pipeline_task(
    task_id: str,
    event: Dict[str, Any],
    weights: Dict[str, float],
    db_factory: Callable,
) -> None:
    """
    Full pipeline execution called by FastAPI BackgroundTasks.

    Progress updates are persisted after each major step.
    Characterizations are committed one-at-a-time for partial recovery.
    """
    db = db_factory()

    def _update(status: str, progress: Dict | None = None, error: str | None = None):
        run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
        if run:
            run.status = status
            if progress is not None:
                run.progress = progress
            if error is not None:
                run.error = error
            db.commit()

    try:
        _update("running", {"step": "generating_queries", "done": 0, "total": 0})

        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        gensee_key = os.getenv("GENSEE_API_KEY", "")
        client = anthropic.Anthropic(api_key=anthropic_key)

        # Step 1: Generate queries
        queries = generate_queries(event, client)
        _update("running", {"step": "searching", "done": 0, "total": len(queries)})

        # Step 2: Search
        results = search_queries(queries, gensee_key)
        _update("running", {"step": "extracting", "done": 0, "total": len(results)})

        # Step 3: Extract full text
        results = extract_results(results)
        _update(
            "running",
            {"step": "characterizing", "done": 0, "total": len(results)},
        )

        # Step 4: Load characterization cache from DB
        event_hash = compute_event_hash(event)
        cached_rows = (
            db.query(SDCharacterization)
            .filter(SDCharacterization.event_hash == event_hash)
            .all()
        )
        cached_chars = {row.url: row.characterization for row in cached_rows}
        urls_needing_char = [
            r for r in results if r.get("url") not in cached_chars
        ]

        # Step 5: Characterize uncached sources and persist each immediately
        import anthropic as _anthropic
        from .pipeline import characterize_source

        done_count = len(cached_chars)
        for i, r in enumerate(urls_needing_char):
            url = r.get("url", "")
            char = characterize_source(event, r, client)
            if char is None:
                continue

            # Persist to cache
            try:
                row = SDCharacterization(
                    url=url,
                    event_hash=event_hash,
                    characterization=char,
                )
                db.add(row)
                db.commit()
                cached_chars[url] = char
            except Exception as exc:
                db.rollback()
                logger.warning("Could not cache characterization for %s: %s", url, exc)

            done_count += 1
            _update(
                "running",
                {
                    "step": "characterizing",
                    "done": done_count,
                    "total": len(results),
                },
            )

        # Step 6: Score
        all_characterized = list(cached_chars.values())
        scored = score_sources(all_characterized, weights)

        # Step 7: Save result
        run = db.query(SDPipelineRun).filter(SDPipelineRun.task_id == task_id).first()
        if run:
            run.status = "completed"
            run.progress = {"step": "done", "done": len(scored), "total": len(scored)}
            run.result = scored
            db.commit()

    except Exception as exc:
        logger.exception("Pipeline task %s failed: %s", task_id, exc)
        try:
            _update("failed", error=str(exc))
        except Exception:
            pass
    finally:
        db.close()
