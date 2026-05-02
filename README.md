# CAIC Source Discovery

This is a research tool built for people from underserved backgrounds looking to understand the impact of climate change in their communities. When a climate disaster happens there's often a strong desire to understand who is being held accountable, what commitments have been made, what do local organizations say, and what is still missing.

The tool lets you describe a climate event and automatically:
- Searches the web for relevant sources from multiple angles (official response, community voice, accountability, science, NGO, legal, international)
- Uses AI to score each source on five dimensions that matter for climate justice work
- Ranks and presents sources so the most useful ones surface first
- Generates a structured report synthesizing what the sources say
- Lets you chat with the sources to dig into specifics

**No technical knowledge is needed to use it.** Fill in the form, wait a few minutes, and browse the results.

**Live demo:** https://caic-sourcing-frontend.onrender.com

---

## Background: what the scoring is optimizing for

Most search tools optimize for relevance or popularity. This tool optimizes for accountability and community impact, which often surfaces very different sources.

Each source is scored on five dimensions (0–10):

| Dimension | What it means in practice |
|---|---|
| **Event specificity** | Is this about *this specific event* or just climate change in general? |
| **Actionability** | Does this give community leaders or NGOs something concrete to act on? |
| **Accountability signal** | Does it name officials, track promises, or assign responsibility? |
| **Community proximity** | Is it produced by or close to the people actually affected? |
| **Independence** | Is it independent from government or corporate interests? |

A wire service story quoting a government minister scores high on event specificity but lower on accountability signal and community proximity. A local NGO situation report might score the opposite. Instead of deciding which is better, this tool lets you adjust the weights to match what your work needs.

---

## How the pipeline works

When you submit a search, the backend runs seven steps in sequence:

1. **Query generation** — Claude generates 12 search queries covering different angles (official response, community impact, accountability, scientific context, NGO coverage, legal/policy, etc.)
2. **Web search** — Each query hits the Gensee search API. Results are deduplicated by URL so you don't see the same source twice.
3. **Content extraction** — The full text of each page is fetched from its URL. The system tries three methods in order: trafilatura (best for news sites), PyPDF2 (for PDFs), and BeautifulSoup as a fallback.
4. **Cache lookup** — Before calling Claude, the system checks whether this source has already been characterized for this same event. If so, it reuses the stored scores instead of making another API call. This makes repeated searches on the same event much faster.
5. **Characterization** — For each source not in the cache, Claude reads the full text and returns scores on 13 dimensions plus a one-sentence summary. Each result is saved to the database immediately so progress isn't lost if something fails.
6. **Scoring** — The five core dimension scores are combined into a single composite score using the weights you selected. Sources are ranked highest to lowest.
7. **Save** — The ranked list is written to the database and the frontend picks it up.

The backend writes progress updates after each step so the UI can show you what's happening while you wait.

---

## Getting started (local development)

You need four things before you can run this locally:

- **Python 3.9+** and [uv](https://docs.astral.sh/uv/) (a faster alternative to pip — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Node.js 18+** and [pnpm](https://pnpm.io/) (install with `npm install -g pnpm`)
- **PostgreSQL** (on Mac: `brew install postgresql@14 && brew services start postgresql@14`)
- **API keys** for Anthropic and Gensee (see [Environment variables](#environment-variables))

Once you have those, see [DEVELOPMENT.md](DEVELOPMENT.md) for step-by-step setup. The short version:

```bash
# Clone the repo
git clone <repo-url>
cd caic-sourcing

# Set up the backend
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # fill in your API keys

# Set up the frontend
cd ../frontend/src
pnpm install

# Start everything
cd ../..
./dev.sh
```

This starts the backend at `http://localhost:8000` and the frontend at `http://localhost:5173`. The first time, also run:

```bash
curl -X POST http://localhost:8000/init-db
```

This creates the database tables. You only need to do it once.

---

## Environment variables

Create `backend/.env` by copying `backend/.env.example` and filling in values.

| Variable | Required | What it's for |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API — used for query generation, source characterization, the report, and chat |
| `GENSEE_API_KEY` | Yes | Gensee web search API |
| `JWT_SECRET_KEY` | Yes | Signs authentication tokens — generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | No | PostgreSQL connection string; defaults to `postgresql://localhost/caic_sourcing` |
| `CORS_ORIGINS` | No | Comma-separated list of allowed frontend origins; defaults to `*` (allow all) |

---

## Project structure

```
caic-sourcing/
├── backend/
│   ├── app.py                        # FastAPI entry point — wires together routes, CORS, rate limiting
│   ├── requirements.txt
│   ├── .env.example                  # Copy this to .env and fill in your keys
│   └── src/
│       ├── source_discovery/
│       │   ├── pipeline.py           # The core logic: query generation, content extraction, characterization, scoring
│       │   ├── tasks.py              # Runs the pipeline as a background job; writes progress to DB
│       │   ├── router.py             # HTTP endpoints for the pipeline
│       │   ├── config.py             # Scoring profiles and dimension weights
│       │   ├── schemas.py            # Data shapes for API requests and responses
│       │   └── models.py             # Database tables for pipeline runs, cached characterizations, and ratings
│       ├── core/
│       │   ├── auth.py               # JWT token logic (used for API integrations)
│       │   └── limiter.py            # Rate limiting: 2 pipeline runs/minute per IP
│       └── auth_jwt.py               # Auth API endpoints (/register, /login, /refresh)
├── frontend/src/
│   ├── app/
│   │   ├── pages/
│   │   │   ├── Home.tsx              # The search form
│   │   │   ├── Results.tsx           # Ranked sources, weight sliders, score breakdown
│   │   │   └── Report.tsx            # AI-generated report and chat panel
│   │   └── lib/api.ts                # All API calls in one place
│   └── vite.config.ts                # Routes /api calls to the backend in local dev
├── dev.sh                            # Starts backend + frontend together
├── render.yaml                       # Deployment config for Render.com
├── DEVELOPMENT.md                    # Full setup and deployment instructions
└── INTEGRATION_SPEC.md               # How to embed this module into a different codebase
```

---
## Systems Design Diagram

<img width="7837" height="8192" alt="Task Pipeline for Query-2026-04-29-122154" src="https://github.com/user-attachments/assets/107cfaf3-d980-4892-b2a7-ec2a89ec3975" />

--

## Roadmap

These are the most important things to work on next.

### 1. Speed — parallelize source characterization

Right now the pipeline characterizes sources one at a time. Each call to Claude takes 2–3 seconds, and with 20 sources that's nearly a minute just for step 5. The fix is to run characterizations in parallel using a thread pool:

```python
# in tasks.py, replace the sequential loop with:
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as pool:
    futures = {pool.submit(characterize_source, event, result, client): result for result in uncached}
    for future in as_completed(futures):
        char = future.result()
        # persist to DB and accumulate
```

Keep `max_workers` at 5–8 to avoid hitting Anthropic's rate limits. The characterization cache (step 4) already handles repeated events, so this change mainly helps the first time a new event is searched.

### 2. Concurrency — add a proper task queue

The current setup runs pipeline jobs directly inside the web server process using FastAPI's `BackgroundTasks`. If multiple users start pipelines at the same time, they all run in the same process and compete for resources.

The fix is to move jobs into a dedicated worker using [ARQ](https://arq-docs.helpmanual.io/), an async Redis-backed task queue. The task_id + database polling pattern already in place doesn't need to change — only the dispatch mechanism does:

1. Add Redis and ARQ to `requirements.txt` and `render.yaml`
2. Create a worker file that imports and registers `run_pipeline_task` from `tasks.py`
3. In `router.py`, replace `background_tasks.add_task(run_pipeline_task, ...)` with `await redis.enqueue_job("run_pipeline_task", ...)`

Celery is a more common alternative but ARQ is simpler to set up for this use case.

### 3. Finetuning — use activist feedback to improve scoring

Every time a user rates a source (thumbs up/down), the database stores the rating alongside the dimension scores and weights that were active at the time. This is in the `sd_source_ratings` table. Over time this becomes a dataset for improving the tool.

**Short-term — adjust the default scoring weights:**

Run this query against the database to see which dimensions activists actually value:

```sql
SELECT
  avg((dimension_scores->>'accountability_signal')::float) filter (where rating >= 4) as accountability_in_good_sources,
  avg((dimension_scores->>'community_proximity')::float)   filter (where rating >= 4) as proximity_in_good_sources,
  avg((dimension_scores->>'event_specificity')::float)     filter (where rating >= 4) as specificity_in_good_sources,
  avg((dimension_scores->>'accountability_signal')::float) filter (where rating <= 2) as accountability_in_bad_sources,
  avg((dimension_scores->>'community_proximity')::float)   filter (where rating <= 2) as proximity_in_bad_sources
FROM sd_source_ratings;
```

Use those numbers to update the default weights in `DEFAULT_PROFILES` in `config.py`. No code changes required — just the numbers in that dict.

**Medium-term — improve the characterization prompt:**

The prompt Claude uses to score sources is `_CHARACTERIZATION_PROMPT` at the top of `pipeline.py`. Look for sources that activists consistently rate highly but the pipeline scores low (or vice versa). Add 2–3 of these as concrete examples in the prompt — Claude responds well to few-shot examples and this is the fastest way to shift scoring behavior.

Focus first on `accountability_signal` and `community_proximity`, since those are the dimensions most specific to this project's mission and most different from what a generic search tool would optimize for.

**Long-term — build a fine-tuning dataset:**

Once you have several hundred ratings, the rows in `sd_source_ratings` combined with the full source text in `sd_characterizations` give you a supervised dataset: (source content, event context) → (dimension scores, user rating). This could be used to fine-tune a smaller, faster model to replace Claude for the characterization step, reducing both cost and latency.

---

## Tuning the pipeline (without changing the architecture)

### Change the scoring profiles

Edit `DEFAULT_PROFILES` in `backend/src/source_discovery/config.py`. Each profile is a dictionary of dimension name → weight. They don't need to sum to 1 — the code normalizes them automatically.

```python
DEFAULT_PROFILES = {
    "my_new_profile": {
        "accountability_signal": 0.5,
        "community_proximity": 0.3,
        "independence": 0.2,
        "event_specificity": 0.0,
        "actionability": 0.0,
    },
}
```

The new profile will appear in the frontend dropdown automatically.

### Change how sources are characterized

Edit `_CHARACTERIZATION_PROMPT` in `backend/src/source_discovery/pipeline.py`. This is the instruction Claude receives when reading each source. Changes only affect new characterizations — cached results are not re-scored. To force re-characterization, delete rows from the `sd_characterizations` table.

### Add a new scoring dimension

1. Add the dimension name to `SCORING_DIMENSIONS` in `config.py`
2. Add a definition for it (0–10 scale) in the characterization prompt in `pipeline.py`
3. Add the field to `ScoredSource` in `schemas.py`
4. Add the field to the `ScoredSource` TypeScript interface in `frontend/src/app/lib/api.ts`
5. Add a score bar for it in `frontend/src/app/pages/Results.tsx`
6. Clear the `sd_characterizations` table (old cached scores won't have the new field)

---

## Authentication

The pipeline endpoints are open — no login is needed to use the website. The JWT auth system (`/api/auth/jwt/register`, `/login`, `/refresh`) exists for programmatic integrations that want to associate runs with a specific user account. See [INTEGRATION_SPEC.md](INTEGRATION_SPEC.md) for details on embedding this module into another codebase.

---

## Deploying to Render

See [DEVELOPMENT.md](DEVELOPMENT.md) for full deployment instructions. The `render.yaml` file at the repo root defines the entire infrastructure as a single Blueprint: a PostgreSQL database, the Python backend, and the frontend static site. Connecting the repo to Render and setting four environment variables is all it takes.
