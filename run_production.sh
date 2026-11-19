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

# Safe .env file loader for key-value pairs (does not use unsafe shell source or execute code)
load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            line="$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            if [ -z "$line" ] || [[ "$line" == \#* ]] || [[ "$line" != *"="* ]]; then
                continue
            fi
            local key="${line%%=*}"
            local value="${line#*=}"
            key="$(echo "$key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            value="$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
                value="${value:1:${#value}-2}"
            fi
            if [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
                if [ -z "${!key+x}" ]; then
                    export "$key=$value"
                fi
            fi
        done < "$env_file"
    fi
}

# Load configuration from supported .env locations (backend/.env, then project root .env)
# Shell environment variables already present always take precedence
load_env_file "$PROJECT_ROOT/backend/.env"
load_env_file "$PROJECT_ROOT/.env"

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
        echo -e "Then export it before running or configure it in backend/.env or .env:"
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

    # Cross-validate configuration via centralized Python Settings validator
    PYTHON_CMD=""
    if [ -x "$PROJECT_ROOT/backend/venv/bin/python" ]; then
        PYTHON_CMD="$PROJECT_ROOT/backend/venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    fi

    if [ -n "$PYTHON_CMD" ]; then
        if ! "$PYTHON_CMD" "$PROJECT_ROOT/backend/config.py" --validate-production 2>/dev/null; then
            echo -e "${RED}ERROR: Production configuration validation failed via config.py.${NC}"
            exit 1
        fi
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
echo -e "${GREEN}[3/4] Preparing backend environment & migrations...${NC}"
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
elif [ "requirements.txt" -nt "venv" ]; then
    echo "Updating backend dependencies..."
    ./venv/bin/pip install -r requirements.txt
fi

echo "Applying database migrations (alembic upgrade head)..."
./venv/bin/alembic -c alembic.ini upgrade head

# 4. Start Production Server
echo -e "${GREEN}[4/4] Launching FeedPulse production server...${NC}"
echo -e "Host: ${HOST}, Port: ${PORT}, Environment: ${ENVIRONMENT}"
echo -e "Serving application at: http://${HOST}:${PORT}"

exec ./venv/bin/uvicorn main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers 1 \
    --log-level info
