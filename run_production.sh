#!/usr/bin/env bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting FeedPulse (Production Mode) ===${NC}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ENVIRONMENT="${ENVIRONMENT:-production}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

# 1. Build frontend for production if dist doesn't exist or forced
echo -e "${GREEN}[1/2] Building frontend for production...${NC}"
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    npm ci || npm install
fi
npm run build

# 2. Run backend migrations and start server
echo -e "${GREEN}[2/2] Running database migrations and starting server on http://${HOST}:${PORT} ...${NC}"
cd "$PROJECT_ROOT/backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

./venv/bin/alembic upgrade head
exec ./venv/bin/uvicorn main:app --host "${HOST}" --port "${PORT}"
