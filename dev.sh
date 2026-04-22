#!/usr/bin/env bash
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"

# Colors
CYAN='\033[0;36m' YELLOW='\033[0;33m' GREEN='\033[0;32m' RESET='\033[0m'

log() { echo -e "${GREEN}[dev]${RESET} $*"; }

# ── PostgreSQL ────────────────────────────────────────────────────────────────
log "Starting PostgreSQL..."
brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || true

# ── Backend ───────────────────────────────────────────────────────────────────
log "Starting backend..."
(
  cd "$REPO/backend"
  # Load .env if present
  [ -f .env ] && set -a && source .env && set +a
  # Prefer venv python if available
  PYTHON=python3
  [ -f .venv/bin/python ] && PYTHON=".venv/bin/python"
  UVICORN=uvicorn
  [ -f .venv/bin/uvicorn ] && UVICORN=".venv/bin/uvicorn"
  echo -e "${CYAN}[backend]${RESET} http://localhost:8000"
  $UVICORN app:app --reload 2>&1 | sed "s/^/$(echo -e "${CYAN}[backend]${RESET}") /"
) &
BACKEND_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
log "Starting frontend..."
(
  cd "$REPO/frontend/src"
  echo -e "${YELLOW}[frontend]${RESET} http://localhost:5173"
  pnpm vite 2>&1 | sed "s/^/$(echo -e "${YELLOW}[frontend]${RESET}") /"
) &
FRONTEND_PID=$!

# ── Cleanup on Ctrl+C ─────────────────────────────────────────────────────────
trap "log 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

log "All services started. Press Ctrl+C to stop."
wait
