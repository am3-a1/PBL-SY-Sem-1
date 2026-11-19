#!/usr/bin/env bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting FeedPulse MVP ===${NC}"

# Navigate to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration from environment or defaults
BACKEND_HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_PORT="${VITE_PORT:-5173}"

# 1. Setup Backend
echo -e "${GREEN}[1/4] Checking Python environment...${NC}"
cd "$PROJECT_ROOT/backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "Applying database migrations..."
./venv/bin/alembic upgrade head

# 2. Setup Frontend
echo -e "${GREEN}[2/4] Checking Frontend dependencies...${NC}"
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    npm install
fi

# 3. Start Backend
echo -e "${GREEN}[3/4] Launching FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT} ...${NC}"
cd "$PROJECT_ROOT/backend"
./venv/bin/uvicorn main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" &
BACKEND_PID=$!

# Trap Ctrl+C to gracefully stop backend when frontend stops
cleanup() {
    echo -e "\n${BLUE}Stopping servers...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 4. Start Frontend
echo -e "${GREEN}[4/4] Launching Vite frontend on http://localhost:${FRONTEND_PORT} ...${NC}"
cd "$PROJECT_ROOT/frontend"
npm run dev
