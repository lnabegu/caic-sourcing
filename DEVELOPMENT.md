# Local Development

## Prerequisites

- **Python 3.9+** with `pip3`
- **Node.js 18+** with `pnpm` (`npm install -g pnpm`)
- **PostgreSQL** (via Homebrew: `brew install postgresql@14`)

## First-time setup

### 1. Clone and enter the repo

```bash
git clone <repo-url>
cd caic-sourcing
```

### 2. Create the database

```bash
brew services start postgresql@14
createdb caic_sourcing
```

### 3. Set up the backend

Install [uv](https://docs.astral.sh/uv/) if you don't have it — it's dramatically faster than pip:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install dependencies:

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Copy the example env file and fill in your API keys:

```bash
cp .env.example .env
# edit .env — at minimum set ANTHROPIC_API_KEY and GENSEE_API_KEY
```

Create the database tables (run once):

```bash
curl -X POST http://localhost:8000/init-db
# or after starting the server below
```

### 4. Install frontend dependencies

```bash
cd ../frontend/src
pnpm install
```

## Running locally

From the repo root, run everything with one command:

```bash
./dev.sh
```

This starts:
- **PostgreSQL** (via `brew services`)
- **Backend** at `http://localhost:8000` (FastAPI + uvicorn, hot-reload)
- **Frontend** at `http://localhost:5173` (Vite dev server, proxies `/api` to backend)

Press `Ctrl+C` to stop all services.

### First run after starting

Initialize the DB tables if you haven't already:

```bash
curl -X POST http://localhost:8000/init-db
```

Then open `http://localhost:5173`, register an account, and you're in.

## API docs

Interactive Swagger UI is available at `http://localhost:8000/docs` while the backend is running.

## Project structure

```
caic-sourcing/
├── backend/
│   ├── app.py                  # FastAPI entry point
│   ├── requirements.txt
│   ├── .env                    # Local secrets (gitignored)
│   ├── .env.example            # Template — copy to .env
│   └── src/
│       ├── auth_jwt.py         # JWT auth router
│       ├── core/auth.py        # Token creation, password hashing
│       ├── database.py         # SQLAlchemy engine + session
│       ├── models/             # ORM models (User, pipeline runs, ratings)
│       └── source_discovery/
│           ├── router.py       # All /api/source-discovery endpoints
│           ├── pipeline.py     # Search → characterize → score logic
│           ├── tasks.py        # Background task runner
│           ├── schemas.py      # Pydantic request/response models
│           ├── config.py       # Scoring profiles and dimension weights
│           └── models.py       # DB models for pipeline runs and ratings
├── frontend/src/
│   ├── app/
│   │   ├── pages/              # Home, Results, Report
│   │   ├── lib/api.ts          # Typed API client
│   │   └── routes.ts           # React Router config
│   └── vite.config.ts          # Dev proxy to backend
├── dev.sh                      # One-command local startup
└── render.yaml                 # Render.com deployment blueprint
```

## Deploying to Render

See `render.yaml` at the repo root — it defines the PostgreSQL database, backend web service, and frontend static site as a single Blueprint.

1. Push to GitHub
2. In Render dashboard → **New** → **Blueprint** → connect your repo
3. Set the secret env vars when prompted:
   - `ANTHROPIC_API_KEY`
   - `GENSEE_API_KEY`
   - `JWT_SECRET_KEY`
   - `CORS_ORIGINS` (set to your frontend URL, e.g. `https://caic-frontend.onrender.com`)
4. After deploy, hit the `/init-db` endpoint once to create tables:
   ```bash
   curl -X POST https://caic-backend.onrender.com/init-db
   ```
