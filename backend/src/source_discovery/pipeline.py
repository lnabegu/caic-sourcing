"""
Pure pipeline functions — no DB interactions, no FastAPI dependencies.
All functions are independently testable.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from .config import SCORING_DIMENSIONS

logger = logging.getLogger(__name__)

_CHARACTERIZATION_PROMPT = """You are an expert source analyst for climate disaster events.

Given the event context and source content below, characterize this source by returning a JSON object
with exactly these 13 fields (all required):

1. event_specificity (0-10): How specifically does this source address this particular event?
2. actionability (0-10): How actionable is this for community leaders and NGOs?
3. accountability_signal (0-10): Does this source assign responsibility or track promises?
4. community_proximity (0-10): How close is this to frontline / affected communities?
5. independence (0-10): How independent is this from government / corporate interests?
6. credibility (0-10): How credible/trustworthy is this source?
7. recency (0-10): How recent and timely is this content?
8. depth (0-10): How deeply does it cover the topic?
9. geographic_relevance (0-10): How geographically relevant is it to the affected area?
10. language_accessibility (0-10): How accessible is it to local communities?
11. source_type_quality (0-10): Quality given its source type (news/NGO/govt/social etc)?
12. unique_angle (0-10): Does it offer a unique perspective not found elsewhere?
13. summary (string): 1-2 sentence summary of what this source contributes.

Event context:
{event_json}

Source URL: {url}
Source title: {title}
Source angle/query: {angle}
Content (first {max_chars} chars):
{content}

Return ONLY a valid JSON object. No markdown, no explanation."""


def generate_queries(event: Dict[str, Any], client: Any) -> List[Dict[str, str]]:
    """
    Use Claude to generate 12 diverse search queries covering different angles.

    Args:
        event: Event metadata dict
        client: anthropic.Anthropic client instance

    Returns:
        List of dicts with keys: angle, source_type, query
    """
    prompt = f"""You are a research strategist for climate disaster response.

Generate 12 diverse search queries to find the best sources for this climate event.
Cover different angles: official response, community impact, accountability, scientific context,
aid/resources, historical patterns, legal/policy, media coverage, NGO response, social media,
technical analysis, and international perspective.

Event: {json.dumps(event, indent=2)}

Return a JSON array of 12 objects, each with:
- "angle": the investigative angle (e.g. "official response", "community impact")
- "source_type": expected source type (e.g. "government", "NGO", "news", "academic", "social")
- "query": the actual search query string

Return ONLY a valid JSON array. No markdown, no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    queries = json.loads(raw.strip())
    if not isinstance(queries, list):
        raise ValueError("generate_queries: Claude did not return a JSON array")
    return queries


def _search_gensee(
    query_obj: Dict[str, str],
    api_key: str,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Call the Gensee search API for a single query object.

    Returns results annotated with angle, source_type, original_query.
    """
    response = requests.post(
        "https://app.gensee.ai/api/search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"query": query_obj["query"], "max_results": max_results},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("search_response", data.get("results", data)) if isinstance(data, dict) else data
    for r in results:
        r.setdefault("angle", query_obj.get("angle", ""))
        r.setdefault("source_type", query_obj.get("source_type", ""))
        r.setdefault("original_query", query_obj.get("query", ""))
    return results


def search_queries(
    queries: List[Dict[str, str]],
    api_key: str,
    max_results_per_query: int = 5,
) -> List[Dict[str, Any]]:
    """
    Run all queries against Gensee, deduplicate by URL, return all unique results.
    """
    seen_urls: set = set()
    unique_results: List[Dict[str, Any]] = []

    for q in queries:
        try:
            results = _search_gensee(q, api_key, max_results=max_results_per_query)
        except Exception as exc:
            logger.warning("Gensee search failed for query '%s': %s", q.get("query"), exc)
            continue

        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

    return unique_results


def extract_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fetch and extract full text for each result.
    Adds full_text and scrape_status fields in-place.
    """
    for r in results:
        url = r.get("url", "")
        if not url:
            r["full_text"] = ""
            r["scrape_status"] = "no_url"
            continue

        try:
            if url.lower().endswith(".pdf"):
                # PDF extraction via PyPDF2
                import io
                import PyPDF2

                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
                pages_text = []
                for page in reader.pages:
                    pages_text.append(page.extract_text() or "")
                r["full_text"] = "\n".join(pages_text)
                r["scrape_status"] = "pdf_extracted"
            else:
                # HTML extraction via trafilatura
                try:
                    import trafilatura

                    downloaded = trafilatura.fetch_url(url)
                    text = trafilatura.extract(downloaded) if downloaded else None
                    if text:
                        r["full_text"] = text
                        r["scrape_status"] = "extracted"
                    else:
                        raise ValueError("trafilatura returned empty")
                except Exception:
                    # Fallback to raw requests + BeautifulSoup
                    from bs4 import BeautifulSoup

                    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer"]):
                        tag.decompose()
                    r["full_text"] = soup.get_text(separator=" ", strip=True)
                    r["scrape_status"] = "fallback_bs4"

        except Exception as exc:
            logger.warning("extract_results: failed for %s: %s", url, exc)
            r["full_text"] = ""
            r["scrape_status"] = f"failed:{exc}"

    return results


def characterize_source(
    event: Dict[str, Any],
    result: Dict[str, Any],
    client: Any,
    max_chars: int = 15000,
) -> Optional[Dict[str, Any]]:
    """
    Call Claude to characterize a single source.

    Returns the 13-field characterization merged with source metadata,
    or None if characterization fails.
    """
    content = (result.get("full_text") or "")[:max_chars]
    prompt = _CHARACTERIZATION_PROMPT.format(
        event_json=json.dumps(event, indent=2),
        url=result.get("url", ""),
        title=result.get("title", ""),
        angle=result.get("angle", ""),
        max_chars=max_chars,
        content=content,
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        char = json.loads(raw.strip())
    except Exception as exc:
        logger.warning("characterize_source failed for %s: %s", result.get("url"), exc)
        return None

    # Merge source metadata into characterization
    char.update(
        {
            "url": result.get("url", ""),
            "title": result.get("title", ""),
            "angle": result.get("angle", ""),
            "source_type": result.get("source_type", ""),
            "original_query": result.get("original_query", ""),
            "scrape_status": result.get("scrape_status", ""),
        }
    )
    return char


def characterize_all(
    event: Dict[str, Any],
    results: List[Dict[str, Any]],
    client: Any,
    cached_characterizations: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Characterize all results, skipping URLs already in the cache.

    Args:
        event: Event metadata
        results: List of extracted search results
        client: anthropic.Anthropic client
        cached_characterizations: dict mapping url -> characterization dict

    Returns:
        List of characterization dicts (failures dropped)
    """
    cache = cached_characterizations or {}
    characterized: List[Dict[str, Any]] = []

    for r in results:
        url = r.get("url", "")
        if url and url in cache:
            characterized.append(cache[url])
            continue

        char = characterize_source(event, r, client)
        if char is not None:
            characterized.append(char)

    return characterized


def score_sources(
    characterized: List[Dict[str, Any]],
    weights: Dict[str, float],
) -> List[Dict[str, Any]]:
    """
    Compute composite scores for all sources and sort descending.

    Each item in the returned list gains a composite_score field (0–10 scale).
    """
    scored: List[Dict[str, Any]] = []
    for char in characterized:
        composite = sum(
            float(char.get(dim, 0)) * weights.get(dim, 0)
            for dim in SCORING_DIMENSIONS
        )
        item = dict(char)
        item["composite_score"] = round(composite, 4)
        scored.append(item)

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored
