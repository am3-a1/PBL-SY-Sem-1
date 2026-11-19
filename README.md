# FeedPulse — Multi-Channel App Review & Feedback Triage Dashboard

FeedPulse is a centralized feedback triage and analytics dashboard designed to solve customer feedback fragmentation across app stores and developer communities. It ingests user reviews across the Apple App Store, Google Play Store, Reddit, and Discord, scores polarity using local rule-based NLP, clusters feedback themes, provides a Kanban triage workflow, and dispatches automated Slack notifications when negative feedback breaches an alert threshold.

FeedPulse operates completely offline without paid external cloud LLMs or third-party sentiment APIs.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Prerequisites & Requirements](#prerequisites--requirements)
5. [Local Development Quick Start](#local-development-quick-start)
6. [Manual Setup (Backend & Frontend)](#manual-setup)
7. [Environment Configuration Reference](#environment-configuration-reference)
8. [Automated Test Execution](#automated-test-execution)
9. [Production Build & Deployment](#production-build--deployment)
10. [Database Management & Backups](#database-management--backups)
11. [Authentication & API Security](#authentication--api-security)
12. [Slack Alerting & Sandbox Mode](#slack-alerting--sandbox-mode)
13. [CSV Ingestion Format & Limits](#csv-ingestion-format--limits)
14. [Known Limitations](#known-limitations)

---

## Project Overview

Modern software teams receive feedback fragmented across multiple channels. FeedPulse unifies review ingestion into an actionable dashboard with two core views:
- **Analytics Overview:** Stacked daily sentiment bar chart, ranked issue theme breakdown, channel breakdown table, and negative spike detection.
- **Triage Board:** Native HTML5 drag-and-drop Kanban board (`New`, `Investigating`, `Escalated`, `Resolved`) with review detail drawer and keyboard navigation.

All demo data included with this repository is completely fictional and generated for testing purposes.

---

## Key Features

- **Multi-channel ingestion:** Ingest feedback from the Apple App Store, Google Play, Reddit, and Discord via CSV upload or one-click mock data generation.
- **Offline NLP pipeline:** Hybrid VADER lexicon sentiment analysis augmented with star-rating weighting and TF-IDF cosine similarity theme classification with confidence scoring.
- **Negative spike sentinel:** Monitors batches and calendar days; triggers alerts when negative reviews meet or exceed the user's threshold percentage.
- **Slack webhook integration:** Dispatches rich Slack Block Kit notifications during negative feedback spikes, with a zero-config sandbox simulator mode for offline testing.
- **Secure API & destructive operation safeguards:** Protects data-mutating routes with API key verification and prevents accidental database clears in production.
- **Database reliability:** SQLAlchemy transactional rollbacks, Alembic schema migrations, and native point-in-time online SQLite backups.
- **Accessible design system:** High-contrast light and dark modes, semantic design tokens, WCAG AA compliance, focus traps, and keyboard navigation.

---

## Architecture

```
+---------------------------------------------------------------------------------+
|                                 BROWSER CLIENT                                  |
|         React 18 + Vite + Tailwind CSS + Recharts + Lucide Icons                |
|           [Analytics View]  <--->  [Kanban Triage]  <--->  [Import Modal]       |
+---------------------------------------------------------------------------------+
                                       │ (HTTP / JSON / Form-Data)
                                       ▼
+---------------------------------------------------------------------------------+
|                                FASTAPI BACKEND                                  |
|  - CORS & Header Security (X-API-Key / Bearer Authentication)                   |
|  - Health Checks (/health, /api/health)                                         |
|  - CSV Streaming Validator (5 MB limit, encoding fallback, row limits)          |
|  - Database-Side Analytics (SQL COUNT, AVG, GROUP BY, date aggregation)          |
+---------------------------------------------------------------------------------+
          │                                              │
          ▼                                              ▼
+-------------------------+                    +----------------------------------+
|    LOCAL NLP ENGINE     |                    |      DATABASE & STORAGE          |
| - VADER Polarity        |                    | - SQLite (feedpulse.db)          |
| - Star-Rating Hybrid    |                    | - Alembic Schema Migrations      |
| - TF-IDF Classification |                    | - Online Point-in-Time Backups   |
| - Confidence Scoring    |                    +----------------------------------+
+-------------------------+                              │
          │                                              ▼
          ▼                                    +----------------------------------+
+-------------------------+                    |      OUTBOUND INTEGRATIONS       |
|    SLACK SENTINEL       |                    | - Slack Incoming Webhooks        |
| - Strict URL Validation |------------------->| - Sandbox Offline Simulator      |
| - Masked Secret URLs    |                    +----------------------------------+
+-------------------------+
```

---

## Prerequisites & Requirements

- **Python:** Version 3.9 or higher
- **Node.js:** Version 18.0.0 or higher, with `npm`
- **Operating System:** macOS, Linux, or Windows (WSL recommended for Windows)

---

## Local Development Quick Start

Run both backend and frontend concurrently with the development launch script:

```bash
./run.sh
```

This script:
1. Creates a Python virtual environment in `backend/venv` and installs dependencies.
2. Installs frontend dependencies in `frontend/node_modules`.
3. Launches the FastAPI server at `http://127.0.0.1:8000`.
4. Starts the Vite dev server at `http://localhost:5173` with automatic API proxying.

---

## Manual Setup

### 1. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI Swagger documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 2. Frontend Setup

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the dashboard in your browser at [http://localhost:5173](http://localhost:5173).

---

## Environment Configuration Reference

To customize configuration, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Deployment environment mode (`development`, `production`, `test`). |
| `HOST` | `127.0.0.1` | Backend host bind address (`0.0.0.0` for production container/VM). |
| `PORT` | `8000` | Backend listening port. |
| `DATABASE_URL` | `sqlite:///./feedpulse.db` | SQLAlchemy database connection string (supports SQLite and PostgreSQL). |
| `FEEDPULSE_API_KEY` | `feedpulse-dev-secret-key` | Secret key protecting data-mutating routes via `X-API-Key` or `Authorization: Bearer`. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000` | Comma-separated list of allowed CORS client origins. |
| `ALLOW_DEMO_SEEDING` | `true` in dev, `false` in prod | Set to `false` in production to prevent test data from replacing live records. |
| `MAX_UPLOAD_SIZE_BYTES` | `5242880` (5 MB) | Maximum permitted CSV upload file size. |
| `MAX_UPLOAD_ROWS` | `5000` | Maximum rows processed per CSV upload. |
| `MAX_CONTENT_LENGTH` | `2000` | Maximum character length per individual review. |
| `SLACK_WEBHOOK_URL` | `""` | Slack Incoming Webhook URL (leave empty to use built-in offline Sandbox mode). |
| `NEGATIVE_THRESHOLD_PCT` | `30.0` | Percentage threshold of negative reviews in a batch triggering an alert. |
| `BACKUP_DIR` | `./backups` | Directory where online SQLite backups are saved. |
| `BACKUP_RETENTION_COUNT` | `10` | Maximum number of point-in-time backups to retain before pruning. |
| `VITE_PORT` | `5173` | Frontend dev server port. |
| `VITE_API_URL` | `http://127.0.0.1:8000` | Target backend URL for Vite development proxy. |
| `VITE_API_KEY` | `feedpulse-dev-secret-key` | API key supplied by the frontend client for protected requests. |

---

## Automated Test Execution

Both backend and frontend include automated test suites.

### Running Backend Tests (pytest)

```bash
cd backend
./venv/bin/pytest -v tests/
```

Test coverage includes:
- VADER sentiment analysis, empty/malformed text, and rating weighting.
- TF-IDF theme classification and confidence score generation.
- Empty analytics vs populated aggregate SQL calculations.
- Review CRUD, invalid IDs, invalid statuses, and pagination.
- CSV import validation (empty files, header-only, invalid format, missing columns, invalid sources).
- Authentication and authorization enforcement on destructive endpoints.
- Slack webhook validation, masking, and offline sandbox simulator.

### Running Frontend Tests (vitest)

```bash
cd frontend
npm run test
```

Test coverage includes:
- Centralized API client error handling, network error recovery, and auth header injection.
- Review card rendering, keyboard accessibility (Enter/Space), and screen reader labels.
- Filter bar dropdowns, keyword search input, and review counter calculations.
- Modal tab switching, asynchronous alert configuration synchronization, and database clear confirmation.
- Theme switcher state cycling and accessibility attributes.

---

## Production Build & Deployment

### Single-Command Production Run

FeedPulse supports self-contained single-server deployment. The FastAPI backend automatically serves the compiled frontend bundle from `frontend/dist` when available:

```bash
./run_production.sh
```

### Manual Production Deployment Steps

1. **Build the Frontend Bundle:**
   ```bash
   cd frontend
   npm ci
   npm run build
   ```
   This generates optimized, tree-shaken static assets in `frontend/dist/`.

2. **Run Database Migrations:**
   ```bash
   cd backend
   ./venv/bin/alembic upgrade head
   ```

3. **Start Production Backend:**
   ```bash
   ENVIRONMENT=production ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Both the API routes (`/api/...`) and the production web dashboard (`/`) are served from the same host and port.

---

## Database Management & Backups

FeedPulse uses SQLite by default with SQLAlchemy ORM and Alembic migrations.

### Creating an Online Database Backup

To create a safe, non-blocking point-in-time backup while the application is actively running:

```bash
cd backend
./venv/bin/python backup.py
```

- Backups are stored in `backend/backups/` named `feedpulse_backup_<timestamp>.sqlite3`.
- Backups use SQLite's native `sqlite3.Connection.backup()` API, avoiding file locks or partial reads.
- Pruning automatically enforces the `BACKUP_RETENTION_COUNT` retention policy.

### Running Database Migrations

```bash
cd backend
# Check current revision
./venv/bin/alembic current
# Apply pending migrations
./venv/bin/alembic upgrade head
```

---

## Authentication & API Security

To protect destructive operations without introducing unnecessary enterprise complexity:
- Destructive operations (`/api/reviews/seed`, `/api/reviews/upload`, review status updates, deletions, and alert configuration updates) require an API key.
- Provide the key via the `X-API-Key` header or `Authorization: Bearer <KEY>`.
- The default development key is `feedpulse-dev-secret-key`. For production deployments, set `FEEDPULSE_API_KEY` to a cryptographically random secret.
- Demo data seeding (`POST /api/reviews/seed`) can be disabled in production by setting `ALLOW_DEMO_SEEDING=false`.

---

## Slack Alerting & Sandbox Mode

FeedPulse integrates with Slack Incoming Webhooks to alert teams when negative reviews spike:
- **Sandbox Mode (Zero Config):** If no Slack webhook URL is configured or left blank, alerts execute in sandbox mode. Payloads are formatted, logged, and returned in the UI for inspection without network calls.
- **Strict Webhook Security:** Webhook URLs are validated using URL parsing. Only `https://hooks.slack.com/services/...` URLs are accepted.
- **Secret Protection:** Webhook tokens are never returned in plaintext by API endpoints; API responses return masked URLs (`https://hooks.slack.com/services/T***/B***/******`).

---

## CSV Ingestion Format & Limits

FeedPulse accepts standard comma-separated review files (`.csv` or `.txt`).

### File Constraints
- **Maximum File Size:** 5 MB (`MAX_UPLOAD_SIZE_BYTES=5242880`)
- **Maximum Batch Rows:** 5,000 rows (`MAX_UPLOAD_ROWS=5000`)
- **Maximum Review Length:** 2,000 characters per review (`MAX_CONTENT_LENGTH=2000`)

### Required & Optional Columns

| Column | Required? | Accepted Values | Description |
| :--- | :--- | :--- | :--- |
| `content` | **Yes** | Text string (1–2000 chars) | Full user review or comment text. |
| `source` | No | `App Store`, `Google Play`, `Reddit`, `Discord` | Channel source (defaults to `App Store`). Invalid sources are reported and skipped. |
| `author` | No | Text string | Author handle or username (defaults to `Anonymous User`). |
| `rating` | No | Integer `1` to `5`, or blank | Star rating (used in hybrid sentiment weighting). |

### Sample CSV Row Format
```csv
source,author,rating,content
App Store,Alex_G,1,"Continuous crash loop on startup. Cannot type password."
Google Play,Kenji_S,5,"Super fast search and clean typography."
Reddit,u/dev_dan,, "Memory leak climbs to 1.2GB after opening multiple tabs."
Discord,Zack#1234,, "Double charged for monthly subscription renewal."
```

---

## Known Limitations

1. **Local NLP Architecture:** Sentiment analysis is based on VADER's rule-based lexicon and TF-IDF similarity. It does not use deep transformer models. Nuanced sarcasm without low star ratings or mixed-sentiment paragraphs may have lower classification confidence.
2. **Single SQLite Process:** SQLite supports concurrent readers with single writers. For multi-replica horizontal clustering, set `DATABASE_URL` to a PostgreSQL instance (`postgresql://user:pass@host:5432/feedpulse`).
3. **Single API Key Authentication:** The lightweight API key model protects endpoints against unauthorized public access, but does not provide multi-tenant user accounts or role-based access control (RBAC).
