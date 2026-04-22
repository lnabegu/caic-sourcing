"""Unit tests for pure pipeline functions."""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.source_discovery.models import compute_event_hash
from src.source_discovery.pipeline import (
    characterize_all,
    generate_queries,
    score_sources,
)
from src.source_discovery.config import SCORING_DIMENSIONS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _equal_weights():
    w = len(SCORING_DIMENSIONS)
    return {dim: 1.0 / w for dim in SCORING_DIMENSIONS}


def _make_char(url: str, **scores) -> dict:
    base = {dim: 5.0 for dim in SCORING_DIMENSIONS}
    base.update(scores)
    base["url"] = url
    base["title"] = f"Title for {url}"
    base["angle"] = "test"
    base["source_type"] = "news"
    base["original_query"] = "test query"
    base["scrape_status"] = "extracted"
    base["summary"] = "A source."
    return base


# ---------------------------------------------------------------------------
# score_sources
# ---------------------------------------------------------------------------

def test_score_sources_sorts_descending():
    chars = [
        _make_char("http://low.example.com", event_specificity=2.0, actionability=2.0,
                   accountability_signal=2.0, community_proximity=2.0, independence=2.0),
        _make_char("http://high.example.com", event_specificity=9.0, actionability=9.0,
                   accountability_signal=9.0, community_proximity=9.0, independence=9.0),
        _make_char("http://mid.example.com", event_specificity=5.0, actionability=5.0,
                   accountability_signal=5.0, community_proximity=5.0, independence=5.0),
    ]
    result = score_sources(chars, _equal_weights())
    scores = [r["composite_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_score_sources_respects_max_sources():
    chars = [_make_char(f"http://example.com/{i}") for i in range(30)]
    result = score_sources(chars, _equal_weights(), max_sources=20)
    assert len(result) <= 20


def test_score_sources_default_max_is_20():
    chars = [_make_char(f"http://example.com/{i}") for i in range(25)]
    result = score_sources(chars, _equal_weights())
    assert len(result) <= 20


def test_score_sources_empty_input():
    result = score_sources([], _equal_weights())
    assert result == []


# ---------------------------------------------------------------------------
# compute_event_hash
# ---------------------------------------------------------------------------

def test_compute_event_hash_is_stable():
    event = {"location": "Mumbai", "event_type": "flood", "event_date": "2026-04-01"}
    h1 = compute_event_hash(event)
    h2 = compute_event_hash(event)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_event_hash_differs_for_different_events():
    e1 = {"location": "Mumbai"}
    e2 = {"location": "Delhi"}
    assert compute_event_hash(e1) != compute_event_hash(e2)


def test_compute_event_hash_key_order_independent():
    e1 = {"a": 1, "b": 2}
    e2 = {"b": 2, "a": 1}
    assert compute_event_hash(e1) == compute_event_hash(e2)


# ---------------------------------------------------------------------------
# characterize_all (caching)
# ---------------------------------------------------------------------------

def test_characterize_all_skips_cached_urls():
    """Client should never be called for URLs already in the cache."""
    mock_client = MagicMock()

    cached = {"http://cached.example.com": _make_char("http://cached.example.com")}
    results = [
        {"url": "http://cached.example.com", "full_text": "ignored"},
    ]

    chars = characterize_all({}, results, mock_client, cached_characterizations=cached)

    mock_client.messages.create.assert_not_called()
    assert len(chars) == 1
    assert chars[0]["url"] == "http://cached.example.com"


def test_characterize_all_calls_client_for_uncached():
    mock_client = MagicMock()
    char_data = _make_char("http://new.example.com")
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(char_data))]
    )

    results = [{"url": "http://new.example.com", "full_text": "some text",
                "title": "t", "angle": "a", "source_type": "news",
                "original_query": "q", "scrape_status": "ok"}]

    chars = characterize_all({}, results, mock_client, cached_characterizations={})

    mock_client.messages.create.assert_called_once()
    assert len(chars) == 1


# ---------------------------------------------------------------------------
# generate_queries
# ---------------------------------------------------------------------------

def test_generate_queries_parses_valid_json():
    mock_queries = [
        {"angle": "official response", "source_type": "government", "query": "flood Mumbai govt"}
        for _ in range(12)
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(mock_queries))]
    )

    event = {"location": "Mumbai", "event_type": "flood", "event_date": "2026-04-01",
             "description": "test"}
    result = generate_queries(event, mock_client)

    assert isinstance(result, list)
    assert len(result) == 12
    assert "angle" in result[0]
    assert "query" in result[0]


def test_generate_queries_strips_markdown_fences():
    mock_queries = [{"angle": "a", "source_type": "b", "query": "c"}]
    raw = "```json\n" + json.dumps(mock_queries) + "\n```"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=raw)]
    )
    result = generate_queries({}, mock_client)
    assert isinstance(result, list)
