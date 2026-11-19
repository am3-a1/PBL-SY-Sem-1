# FeedPulse — Multi-Channel App Review & Feedback Triage Dashboard

FeedPulse is a centralized feedback triage and analytics dashboard designed to solve customer feedback fragmentation across app stores and developer communities. It ingests user reviews across the Apple App Store, Google Play Store, Reddit, and Discord, scores polarity using local rule-based NLP, clusters feedback themes, provides a Kanban triage workflow, and dispatches automated Slack notifications when negative feedback breaches an alert threshold.

FeedPulse operates completely offline without paid external cloud LLMs or third-party sentiment APIs.

---

## Intended Deployment Model & Scope

FeedPulse is designed and proportioned as a **locally hosted or private single-user application** (e.g., local developer machine, private LAN, or private portfolio demonstration).

> [!IMPORTANT]
> **Authentication & Identity Scope:**
> The API key protection mechanism is a lightweight, shared secret key designed to safeguard destructive operations (such as data clearing, seeding, and CSV uploads) from unauthenticated tampering.
>
> - **Not Multi-User RBAC:** It does **NOT** provide multi-user accounts, user registration, role-based access controls (RBAC), browser sessions, or tenant isolation.
> - **Client-Side Key Storage:** When configured in the frontend UI, the key is securely stored in browser `localStorage` and attached to outgoing mutating requests. It is not bundled into static JavaScript code.
> - **Public Internet Exposure:** If deployed to the public internet, FeedPulse should be placed behind a reverse proxy with TLS and an authentication gateway (such as HTTP Basic Auth, VPN, Cloudflare Access, or OAuth proxy) rather than exposed directly as a public multi-tenant service.

---

## Table of Contents

1. [Key Features](#key-features)
2. [Architecture](#architecture)
3. [Prerequisites & Requirements](#prerequisites--requirements)
4. [Local Development Quick Start](#local-development-quick-start)
5. [Production Setup & Launcher](#production-setup--launcher)
6. [Frontend API Key Configuration](#frontend-api-key-configuration)
7. [Environment Configuration Reference](#environment-configuration-reference)
8. [Database Migrations (Alembic)](#database-migrations-alembic)
9. [Database Backup & Recovery](#database-backup--recovery)
10. [Safe Offline Database Restore Procedure](#safe-offline-database-restore-procedure)
11. [Authentication & API Security](#authentication--api-security)
12. [CSV Ingestion Format & Validation Limits](#csv-ingestion-format--validation-limits)
13. [Slack Alerting & Sandbox Simulator](#slack-alerting--sandbox-simulator)
14. [Automated Test Execution & CI](#automated-test-execution--ci)
15. [Deployment Readiness & Scope Suitability](#deployment-readiness--scope-suitability)
16. [Known Limitations](#known-limitations)

---

## Key Features

- **Multi-channel ingestion:** Ingest feedback from the Apple App Store, Google Play, Reddit, and Discord via CSV upload or one-click mock data generation.
- **Offline NLP pipeline:** Hybrid VADER lexicon sentiment analysis augmented with star-rating weighting and TF-IDF cosine similarity theme classification with confidence scoring.
- **Negative spike sentinel:** Monitors batches and calendar days; triggers alerts when negative reviews meet or exceed the user's threshold percentage.
- **Slack webhook integration:** Dispatches rich Slack Block Kit notifications during negative feedback spikes, with a zero-config sandbox simulator mode for offline testing.
- **Constant-time API security:** Protects data-mutating routes using constant-time key verification (`secrets.compare_digest`) via `X-API-Key` or `Authorization: Bearer <KEY>`.
- **Read-only GET endpoints:** Strictly idempotent HTTP GET queries without implicit database side-effects or connection locks.
- **Database reliability:** SQLAlchemy transactional rollbacks, Alembic schema migrations supporting fresh and legacy databases, and native point-in-time online SQLite backups and restores.
- **Accessible design system:** High-contrast light and dark modes, semantic design tokens, WCAG AA compliance, focus traps, and keyboard navigation.

---

## Architecture

```
+---------------------------------------------------------------------------------+
|                                 BROWSER CLIENT                                  |
|         React 18 + Vite + Tailwind CSS + Recharts + Lucide Icons                |
|    [Analytics View]  <--->  [Kanban Triage]  <--->  [Settings / API Key Modal]  |
+---------------------------------------------------------------------------------+
                                       │ (HTTP / JSON / Form-Data)
                                       ▼
+---------------------------------------------------------------------------------+
|                                FASTAPI BACKEND                                  |
|  - CORS & Header Security (X-API-Key / Bearer Authentication)                   |
|  - Constant-Time Key Verification (secrets.compare_digest)                      |
|  - Health Checks (/health, /api/health)                                         |
|  - Hardened CSV Streaming (5 MB limit, encoding fallback, row limits)           |
|  - Strictly Read-Only GET Endpoints (/api/themes, /api/alerts/config)          |
|  - Database-Side Analytics (SQL COUNT, AVG, GROUP BY, date aggregation)         |
+---------------------------------------------------------------------------------+
          │                                              │
          ▼                                              ▼
+-------------------------+                    +----------------------------------+
|    LOCAL NLP ENGINE     |                    |      DATABASE & STORAGE          |
| - VADER Polarity        |                    | - SQLite (feedpulse.db)          |
| - Star-Rating Hybrid    |                    | - Alembic Schema Migrations      |
| - TF-IDF Classification |                    | - Point-in-Time Online Backups   |
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

- Backend runs on `http://127.0.0.1:8000` with hot-reload enabled.
- Frontend runs on `http://localhost:5173` via Vite development server.
- Database migrations are automatically checked and applied on launch.
- In development mode (`ENVIRONMENT=development`), the default API key `feedpulse-dev-secret-key` is used if no custom key is configured.

---

## Production Setup & Launcher

FeedPulse supports self-contained single-server deployment. The FastAPI backend automatically serves the compiled frontend bundle from `frontend/dist/` at `/` when built.

### Generating a Secure API Key

Generate a cryptographically secure key using Python's standard library:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Launching via `run_production.sh`

The production launcher verifies environment configuration, compiles the frontend bundle using `npm ci`, runs database migrations, and launches Uvicorn:

```bash
export ENVIRONMENT=production
export FEEDPULSE_API_KEY="your-generated-random-secret-key-min-16-chars"
export ALLOWED_ORIGINS="http://127.0.0.1:8000,https://yourdomain.com"

./run_production.sh
```

The launcher enforces strict validation before executing:
1. `FEEDPULSE_API_KEY` must be set, non-empty, and at least 16 characters long.
2. Insecure default keys (e.g. `feedpulse-dev-secret-key`, `admin`, `password`) are strictly rejected.
3. Production CORS origins (`ALLOWED_ORIGINS`) must be explicit, valid URLs without wildcards or URL paths.
4. Dependencies are installed and verified via `npm ci` and requirements stamp tracking.
5. Database migrations (`alembic upgrade head`) are run before Uvicorn starts.
6. If any validation or migration step fails, the launcher aborts immediately.

---

## Frontend API Key Configuration

To interact with protected backend endpoints (such as uploading CSVs, updating review statuses, escalating themes, or configuring alerts), users configure the API key directly in the browser interface:

1. Click the **"Import & Settings"** button in the header bar.
2. Switch to the **"API Key"** tab.
3. Enter your configured `FEEDPULSE_API_KEY` into the password input field (toggle the eye icon to inspect).
4. Click **"Save API Key"**.

### Persistence and Feedback:
- **Client Storage:** The key is stored in browser `localStorage` and persists across page reloads.
- **Immediate Effect:** Saving or clearing the key immediately updates all subsequent outgoing requests without requiring a full page refresh.
- **Privacy:** The interface displays whether an API key is configured or not configured, without exposing the raw secret key.
- **Actionable 401 Handling:** If an unauthenticated or invalid mutating request is rejected by the backend with HTTP 401, a clear notification banner appears with an interactive **"Configure API Key"** button that directly opens the API Key settings modal.

---

## Environment Configuration Reference

### `.env` File Placement & Loading Order
The backend automatically searches for `.env` files in:
1. `backend/.env`
2. Project root (`.env`)

Any variables explicitly set in your shell environment take precedence over values in `.env` files.

| Variable | Default (Dev) | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Deployment mode: `development`, `production`, or `test`. |
| `HOST` | `127.0.0.1` (dev) / `0.0.0.0` (prod) | Backend network bind interface. |
| `PORT` | `8000` | Backend port. |
| `DATABASE_URL` | `sqlite:///./feedpulse.db` | SQLAlchemy connection string. |
| `FEEDPULSE_API_KEY` | `feedpulse-dev-secret-key` (dev only) | Secret key for mutating operations. In production, an explicit key $\ge 16$ chars is mandatory. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000` | Comma-separated CORS origins whitelist. In production, wildcard `*` and paths are rejected. |
| `ALLOW_DEMO_SEEDING` | `true` in dev, `false` in prod | Disables the `/api/reviews/seed` route in production to prevent accidental demo data overwrites. |
| `MAX_UPLOAD_SIZE_BYTES` | `5242880` (5 MB) | Maximum permitted CSV upload file size. |
| `MAX_UPLOAD_ROWS` | `5000` | Maximum rows parsed per CSV upload batch. |
| `MAX_CONTENT_LENGTH` | `2000` | Maximum character length per review text. Rows exceeding this are rejected. |
| `SLACK_WEBHOOK_URL` | `""` | Slack Incoming Webhook URL (leave empty for built-in Sandbox mode). |
| `NEGATIVE_THRESHOLD_PCT` | `30.0` | Negative review percentage in a batch required to trigger an alert. |
| `BACKUP_DIR` | `./backups` | Directory for point-in-time SQLite backups. |
| `BACKUP_RETENTION_COUNT` | `10` | Backups to retain before pruning older files (`0` disables pruning and retains all backups). |

---

## Database Migrations (Alembic)

FeedPulse uses Alembic for declarative database migrations. The migration strategy supports both:
1. **Fresh Installations:** Creates all tables (`reviews`, `themes`, `alert_configs`), check constraints, and performance indexes from scratch.
2. **Legacy Databases:** Detects existing pre-Alembic databases (created by previous versions), verifies tables, and safely adds `theme_confidence` without modifying existing rows.
3. **Safe Reversible Downgrades:** Tracks objects created during migration in `_alembic_migration_metadata` to guarantee that rolling back a migration never drops pre-existing legacy tables or user review data.

### Running Migrations Manually

```bash
cd backend

# View current migration state
./venv/bin/alembic current

# Upgrade database to latest revision
./venv/bin/alembic upgrade head

# Rollback latest migration
./venv/bin/alembic downgrade -1
```

---

## Database Backup & Recovery

FeedPulse includes an online backup utility (`backend/backup.py`) utilizing SQLite's native `sqlite3.Connection.backup()` API. Backups are non-blocking, collision-resistant, and verified with SQLite's internal integrity checks.

### Features:
- **Collision-Resistant Filenames:** Uses microsecond timestamps and random UUID suffixes (`feedpulse_backup_%Y%m%d_%H%M%S_%f_<uuid>.sqlite3`).
- **Atomic Writes:** Backups are written to a temporary `.tmp` file and renamed via atomic `os.replace` only upon passing `PRAGMA integrity_check`.
- **Retention Policy:**
  - `BACKUP_RETENTION_COUNT > 0`: Retains the newest $N$ backups.
  - `BACKUP_RETENTION_COUNT=0`: Disables pruning, retaining all backup files indefinitely.
  - The newly created backup is never pruned during creation.

### Creating a Backup

```bash
cd backend
./venv/bin/python backup.py
```

### Listing Available Backups

```bash
cd backend
./venv/bin/python backup.py --list
```

---

## Safe Offline Database Restore Procedure

When recovering from data corruption or restoring historical data, perform an **offline restore** using this standard maintenance workflow:

1. **Stop Application Processes:**
   Ensure no active writers or application servers are accessing the database:
   ```bash
   pkill -f uvicorn
   ```

2. **Create a Safety Backup of Current State:**
   Never overwrite the existing database without taking a safety snapshot first:
   ```bash
   cp backend/feedpulse.db backend/feedpulse.db.pre-restore-safety-copy
   ```

3. **Verify Target Backup Integrity:**
   Ensure the chosen backup file is valid and uncorrupted:
   ```bash
   sqlite3 backend/backups/feedpulse_backup_20261119_140000.sqlite3 "PRAGMA integrity_check;"
   # Expected output: ok
   ```

4. **Restore Database:**
   Use the built-in restore CLI or perform an atomic file copy:
   ```bash
   cd backend
   ./venv/bin/python backup.py --restore backups/feedpulse_backup_20261119_140000.sqlite3
   ```

5. **Execute Schema Migrations (if applicable):**
   If the restored snapshot originates from an earlier application version, bring the schema up to date:
   ```bash
   cd backend
   ./venv/bin/alembic upgrade head
   ```

6. **Verify Database Health:**
   Verify SQLite integrity on the restored database:
   ```bash
   sqlite3 backend/feedpulse.db "PRAGMA integrity_check;"
   # Expected output: ok
   ```

7. **Restart the Application:**
   ```bash
   ./run_production.sh
   ```

---

## Authentication & API Security

### Protected Endpoints
All operations that mutate data or configuration require authentication:
- `POST /api/reviews/seed`
- `POST /api/reviews/upload`
- `PATCH /api/reviews/{id}/status`
- `DELETE /api/reviews/{id}`
- `DELETE /api/reviews`
- `POST /api/themes/{id}/escalate`
- `PUT /api/alerts/config`
- `POST /api/alerts/test`

### Header Formats
Supply credentials using either standard format:
1. `X-API-Key: <YOUR_KEY>`
2. `Authorization: Bearer <YOUR_KEY>` (case-insensitive prefix)

Verification uses constant-time comparison via Python's `secrets.compare_digest` to prevent side-channel timing attacks.

---

## CSV Ingestion Format & Validation Limits

FeedPulse accepts standard comma-separated review files (`.csv` or `.txt`).

### Validation Rules
- **File Size:** Maximum 5 MB (`MAX_UPLOAD_SIZE_BYTES`).
- **Row Limit:** Maximum 5,000 data rows (`MAX_UPLOAD_ROWS`).
- **Encoding Resiliency:** Automatically decodes UTF-8, UTF-8 with BOM, and Latin-1.
- **Review Content Length:** Maximum 2,000 characters (`MAX_CONTENT_LENGTH`). Rows exceeding this limit are **rejected with an explicit row-specific error** (content is never silently truncated).
- **Rating Validation:** Must be an integer between `1` and `5`, or blank/null. Non-numeric ratings (e.g. `"five"`), decimal ratings (e.g. `"3.5"`), and out-of-range ratings (e.g. `0`, `6`, `10`) are **rejected with an explicit row-specific error**. Genuinely blank cells are accepted as `rating = None`.
- **Channel Sources:** Must be one of `App Store`, `Google Play`, `Reddit`, or `Discord` (case-insensitive). Unsupported sources are rejected with row-specific errors.
- **Atomic Transaction:** Valid rows are committed atomically. If database persistence encounters an error, the transaction rolls back cleanly.

### Sample CSV Structure
```csv
source,author,rating,content
App Store,Alex_G,1,"Continuous crash loop on startup. Cannot type password."
Google Play,Kenji_S,5,"Super fast search and clean typography."
Reddit,u/dev_dan,,"Memory leak climbs to 1.2GB after opening multiple tabs."
Discord,Zack#1234,,"Double charged for monthly subscription renewal."
```

---

## Slack Alerting & Sandbox Simulator

- **Sandbox Simulator Mode:** If `SLACK_WEBHOOK_URL` is empty or omitted, alerts run in offline sandbox mode. Payloads are rendered, logged, and returned in the UI for review without outbound HTTP traffic.
- **Strict Hostname & Path Validation:** Incoming webhook URLs must strictly match `https://hooks.slack.com/services/T.../B.../...`. Arbitrary outbound hostnames and insecure HTTP schemes are rejected with `400 Bad Request`.
- **Credential Masking:** Webhook URLs are never exposed in API responses or logs (`https://hooks.slack.com/services/T***/B***/******`).

---

## Automated Test Execution & CI

### GitHub Actions CI
The project includes a continuous integration pipeline (`.github/workflows/ci.yml`) that triggers on push and pull requests to `main` and `deployment-fixes`, running:
- **Backend Test Job:** Python 3.10 setup, pip cache, dependency installation, and complete `pytest` execution.
- **Frontend Test Job:** Node.js 20 setup, npm cache, clean install (`npm ci`), `vitest` unit tests, and production build (`npm run build`).

### Backend Tests (pytest)

```bash
cd backend
./venv/bin/pytest -v tests/
```

Coverage (47 tests) includes:
- **Alembic:** Fresh database migration, legacy migration with data preservation, pre-existing metadata and key collision safety, reversible downgrade safety, re-upgrade, and standalone CLI upgrade execution with environment URL resolution.
- **Security:** Production configuration validation, constant-time `secrets.compare_digest` comparison, authentication headers (`X-API-Key`, `Authorization: Bearer`), production CORS origin validation, and production launcher checks.
- **Import Safety:** Proves that importing the application module does not create database tables or schemas outside of Alembic.
- **Read-Only Endpoints:** Proves that `GET /api/themes` and `GET /api/alerts/config` execute zero database writes.
- **CSV:** Valid ratings, genuinely missing ratings, out-of-range ratings, non-numeric and decimal ratings, oversized text rejection without silent truncation, source validation, and atomic commits.
- **Backups:** Online backup creation, backup restoration, integrity verification, collision resistance under rapid execution, corrupted backup rejection, and retention pruning (`0`, positive integers).
- **NLP & Slack:** Sentiment polarity, star-rating weighting, TF-IDF theme classification, Slack webhook validation, masking, and sandbox mode.
- **End-to-End Workflow:** Full integration workflow across database migration, unauthenticated 401 rejection, authenticated seeding, review status updating, alert configuration, analytics calculations, and disk persistence.

### Frontend Tests (vitest)

```bash
cd frontend
npm run test
```

Coverage (22 tests across 5 suites) includes:
- API client authentication injection, explicit handling of missing keys without silent dev fallback, and network error extraction.
- Review card rendering, keyboard accessibility (Enter/Space), and screen reader attributes.
- Filter bar dropdowns, keyword search input, and counters.
- Modal tabs, API key configuration (saving, clearing, masking, tab navigation), seed reviews API workflow, asynchronous alert config synchronization, and database clear confirmations.
- Theme switcher state cycling.

---

## Deployment Readiness & Scope Suitability

| Deployment Scope | Status | Notes |
| :--- | :--- | :--- |
| **Local Single-User** | **Ready** | Fully supported out-of-the-box via `./run.sh`. Default configuration enables rapid local development and testing. |
| **Private LAN** | **Ready** | Supported via `./run_production.sh` with `HOST=0.0.0.0`. Set a custom `FEEDPULSE_API_KEY` to secure mutations. |
| **Portfolio Demonstration** | **Ready** | Single-port production server (`./run_production.sh`) serves both API and frontend bundle cleanly on a single port. |
| **Public Internet** | **Conditional** | Requires external TLS termination and an authentication proxy (e.g. Cloudflare Access, Basic Auth, or OAuth gateway). FeedPulse's single shared API key does not provide user accounts or multi-tenant isolation. |

---

## Known Limitations

1. **Rule-Based NLP:** Polarity classification uses rule-based VADER and TF-IDF similarity. Sarcasm without low star ratings or complex multi-sentence nuances may have lower classification confidence.
2. **Single-Writer SQLite:** SQLite supports high concurrency for readers with sequential writes. For high-volume multi-writer deployments, configure `DATABASE_URL` with a PostgreSQL server.
3. **Shared Secret Key:** The API key protects endpoints from unauthorized modifications but does not replace user accounts, sessions, or multi-tenant authorization.
