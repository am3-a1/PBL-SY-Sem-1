#!/usr/bin/env bash
set -euo pipefail

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting FeedPulse (Production Launcher) ===${NC}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ENVIRONMENT="${ENVIRONMENT:-production}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

# 1. Environment & Configuration Security Checks
echo -e "${GREEN}[1/4] Validating production configuration...${NC}"

if [ "${ENVIRONMENT}" = "production" ]; then
    if [ -z "${FEEDPULSE_API_KEY:-}" ]; then
        echo -e "${RED}ERROR: FEEDPULSE_API_KEY environment variable is required in production mode.${NC}"
        echo -e "Generate a secure random key using:"
        echo -e "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        echo -e "Then export it before running:"
        echo -e "  export FEEDPULSE_API_KEY=\"<generated-key>\""
        exit 1
    fi

    # Check for known insecure default keys
    INSECURE_KEYS="feedpulse-dev-secret-key secret password admin 123456 12345678 changeme development test"
    for BAD in $INSECURE_KEYS; do
        if [ "${FEEDPULSE_API_KEY}" = "$BAD" ]; then
            echo -e "${RED}ERROR: Insecure default or weak FEEDPULSE_API_KEY detected in production environment.${NC}"
            echo -e "Generate a secure random key using:"
            echo -e "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            exit 1
        fi
    done

    if [ ${#FEEDPULSE_API_KEY} -lt 16 ]; then
        echo -e "${RED}ERROR: FEEDPULSE_API_KEY is too short (${#FEEDPULSE_API_KEY} chars). Must be at least 16 characters in production.${NC}"
        echo -e "Generate a secure random key using:"
        echo -e "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        exit 1
    fi
fi

# 2. Frontend Dependencies & Production Build
echo -e "${GREEN}[2/4] Checking frontend build...${NC}"
cd "$PROJECT_ROOT/frontend"

# Check if node_modules exists or package.json/package-lock.json is newer than stamp
if [ ! -d "node_modules" ] || [ ! -f "node_modules/.installed" ] || [ "package.json" -nt "node_modules/.installed" ] || [ "package-lock.json" -nt "node_modules/.installed" ]; then
    echo "Installing frontend dependencies with npm ci..."
    if ! npm ci; then
        echo -e "${RED}ERROR: 'npm ci' failed. Ensure package.json and package-lock.json are in sync.${NC}"
        echo -e "To resolve, run in the frontend directory:"
        echo -e "  cd frontend && npm install"
        exit 1
    fi
    touch "node_modules/.installed"
fi

echo "Building frontend bundle..."
npm run build

# 3. Backend Dependencies & Database Migrations
echo -e "${GREEN}[3/4] Preparing backend and database migrations...${NC}"
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

# Sync Python dependencies if requirements.txt is newer than stamp file
if [ ! -f "venv/.installed" ] || [ "requirements.txt" -nt "venv/.installed" ]; then
    echo "Syncing Python dependencies from requirements.txt..."
    ./venv/bin/pip install -r requirements.txt
    touch "venv/.installed"
fi

# Validate Python configuration settings
./venv/bin/python -c "from config import settings; settings.validate_production_configuration()"

# Run Alembic migrations
echo "Executing database migrations (alembic upgrade head)..."
./venv/bin/alembic upgrade head

# 4. Start Uvicorn Server (Single port, serving API and static frontend)
echo -e "${GREEN}[4/4] Starting FeedPulse production server on http://${HOST}:${PORT} ...${NC}"
exec ./venv/bin/uvicorn main:app --host "${HOST}" --port "${PORT}" --no-access-log
