# FeedPulse

FeedPulse is a centralized dashboard for multi-channel app reviews with local sentiment scoring, theme clustering, Kanban triage, and automated Slack spike alerts. It helps product and engineering teams monitor user feedback across the Apple App Store, Google Play Store, Reddit, and Discord without requiring third-party cloud NLP services.

<!-- Screenshot Placeholder: Place dashboard preview image at docs/screenshots/dashboard.png -->
```
+---------------------------------------------------------------------------------------------+
| FeedPulse                                           [Analytics] [Triage board]  [Import & Alerts] |
|                                                                                             |
| 65 reviews · 32.3% negative · 14 open critical issues                                      |
| +-----------------------------------------------------------------------------------------+ |
| | Daily Sentiment & Negative Spike Sentinel Chart                                         | |
| +-----------------------------------------------------------------------------------------+ |
|                                                                                             |
| [New]                      [Investigating]            [Escalated]               [Resolved]  |
| +-----------------------+  +-----------------------+  +-----------------------+ +---------+ |
| | Crash on login screen |  | Double charge issue   |  | Memory leak on iOS    | | UI font | |
| +-----------------------+  +-----------------------+  +-----------------------+ +---------+ |
+---------------------------------------------------------------------------------------------+
```

## Features

- **Multi-channel ingestion:** Ingest feedback from the App Store, Google Play, Reddit, and Discord via CSV upload or built-in mock seeding.
- **Offline NLP analysis:** Uses VADER sentiment analysis and TF-IDF theme classification to score polarity and categorize issues locally with zero external API dependencies.
- **Automated spike sentinel:** Flags days where negative reviews breach a configurable threshold percentage.
- **Slack webhook integration:** Dispatches rich Slack Block Kit notifications during negative feedback spikes, with a built-in sandbox mode for offline testing.
- **Interactive triage board:** Drag-and-drop Kanban workflow (`New`, `Investigating`, `Escalated`, `Resolved`) with a slide-in review detail drawer.
- **Accessible design system:** Built with semantic design tokens supporting light and dark modes with WCAG AA compliance.

## Tech stack

- **Frontend:** React 18, Vite, Tailwind CSS, Recharts, Lucide Icons
- **Backend:** FastAPI, Python 3.9+, SQLAlchemy, SQLite, Uvicorn, Pydantic
- **NLP engine:** `vaderSentiment`, `scikit-learn` (TF-IDF vectorizer)

## Getting started

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Homebrew (macOS) for optional CLI tools

### Single-step launch

Run both the backend and frontend concurrently with the root launch script:

```bash
./run.sh
```

### Manual setup

#### 1. Backend setup

Navigate to the `backend/` directory, create a virtual environment, and install dependencies:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The FastAPI backend will start at `http://127.0.0.1:8000`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

#### 2. Frontend setup

In a separate terminal, navigate to the `frontend/` directory, install dependencies, and start the development server:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server will start at `http://localhost:5173` and automatically proxy `/api` requests to the backend.

### Environment variables

FeedPulse runs out of the box with zero configuration using SQLite and offline sandbox alert mode. To customize configuration, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HOST` | `127.0.0.1` | Backend host bind address |
| `PORT` | `8000` | Backend port number |
| `DATABASE_URL` | `sqlite:///./feedpulse.db` | SQLAlchemy database connection string |
| `SLACK_WEBHOOK_URL` | `""` | Slack Incoming Webhook URL (leave empty for built-in sandbox mode) |
| `NEGATIVE_THRESHOLD_PCT` | `30.0` | Percentage threshold of negative reviews in a batch to trigger an alert |
| `VITE_PORT` | `5173` | Frontend development server port |
| `VITE_API_URL` | `http://127.0.0.1:8000` | Target backend URL for Vite proxy |

## Loading demo data

All demo and sample reviews included with this project are completely fictional and generated for testing purposes.

1. Open the dashboard at `http://localhost:5173`.
2. Click **Import and alerts** in the top navigation bar.
3. Under the **Data** tab, click **Load demo reviews** to seed 65 mock reviews across all four channels.
4. Alternatively, upload your own CSV file or use the provided `sample_reviews.csv` or datasets in `test_datasets/`.

## Security and pre-commit hooks

To prevent committing sensitive data or secrets, this repository includes a pre-commit configuration (`.pre-commit-config.yaml`) using Gitleaks:

```bash
pip install pre-commit
pre-commit install
```

To run a scan manually:

```bash
pre-commit run --all-files
```
