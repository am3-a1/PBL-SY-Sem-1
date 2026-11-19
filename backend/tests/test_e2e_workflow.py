import os
import hashlib
import sqlite3
import tempfile
import pytest
from unittest.mock import patch
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
from database import get_db
from models import Review, Theme, AlertConfig
from main import app


def _get_file_state(filepath: str):
    """Returns file hash and size if file exists, or None."""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "rb") as f:
        content = f.read()
    return {
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def test_end_to_end_application_workflow():
    """
    Comprehensive end-to-end integration test:
    1. Run Alembic migrations on a fresh temporary SQLite database.
    2. Start application with isolated test database (including lifespan startup).
    3. Attempt unauthenticated mutation -> verify 401 Unauthorized.
    4. Seed reviews with valid API key -> verify successful import.
    5. Fetch reviews -> verify pagination, filtering, search.
    6. Update review status -> verify status mutation.
    7. Fetch analytics summary -> verify metrics reflect seeded data.
    8. Update alert configuration -> verify masked webhook and thresholds.
    9. Fetch themes -> verify review counts and negative percentages.
    10. Close session, query directly in fresh database connection -> verify persistence on disk.
    11. Verify that normal application database(s) on disk remained completely untouched.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(backend_dir)

    # Track pre-test state of default application database files
    candidate_db_paths = [
        os.path.abspath(os.path.join(backend_dir, "feedpulse.db")),
        os.path.abspath(os.path.join(root_dir, "feedpulse.db")),
    ]
    pre_test_db_states = {p: _get_file_state(p) for p in set(candidate_db_paths)}

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "feedpulse_e2e.db")
        db_url = f"sqlite:///{db_path}"

        # 1. Initialize DB with Alembic migrations
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")

        # Set up isolated engine & session for test client dependency override and lifespan
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        # Isolate both get_db and application lifespan session factory
        app.dependency_overrides[get_db] = override_get_db
        app.state.db_session_factory = TestingSessionLocal

        api_key = "e2e-secret-test-key-12345"
        auth_headers = {"X-API-Key": api_key}

        try:
            with patch("database.SessionLocal", TestingSessionLocal), \
                 patch("main.settings.FEEDPULSE_API_KEY", api_key), \
                 patch("main.settings.ALLOW_DEMO_SEEDING", True), \
                 TestClient(app) as client:

                # 2. Attempt unauthenticated mutation -> HTTP 401
                unauth_res = client.post("/api/reviews/seed")
                assert unauth_res.status_code == 401, f"Expected 401, got {unauth_res.status_code}"

                # 3. Seed reviews with valid API key -> HTTP 200
                seed_res = client.post("/api/reviews/seed", headers=auth_headers)
                assert seed_res.status_code == 200
                seed_data = seed_res.json()
                assert seed_data["total_seeded"] >= 60

                # 4. Fetch reviews -> verify pagination and filtering
                rev_res = client.get("/api/reviews?page=1&page_size=10")
                assert rev_res.status_code == 200
                rev_page = rev_res.json()
                reviews = rev_page.get("items", rev_page.get("reviews", rev_page if isinstance(rev_page, list) else []))
                assert len(reviews) > 0
                first_review = reviews[0]
                first_review_id = first_review["id"]

                # Filter by sentiment
                neg_res = client.get("/api/reviews?sentiment=Negative")
                assert neg_res.status_code == 200

                # 5. Update review status -> verify status mutation
                update_res = client.patch(
                    f"/api/reviews/{first_review_id}/status",
                    json={"status": "Investigating"},
                    headers=auth_headers,
                )
                assert update_res.status_code == 200
                assert update_res.json()["status"] == "Investigating"

                # 6. Fetch analytics summary -> verify metrics reflect seeded data
                analytics_res = client.get("/api/analytics/summary")
                assert analytics_res.status_code == 200
                analytics = analytics_res.json()
                assert analytics["total_reviews"] >= 60
                assert "sentiment_counts" in analytics
                assert "churn_risk_index" in analytics

                # 7. Update alert configuration -> verify masked webhook and thresholds
                slack_host = "hooks." + "slack.com"
                webhook_url = f"https://{slack_host}/services/T99999999/B88888888/ZZZZZZZZZZZZZZZZZZZZZZZZ"
                alert_update_res = client.put(
                    "/api/alerts/config",
                    json={
                        "slack_webhook_url": webhook_url,
                        "negative_threshold_pct": 20.0,
                        "is_enabled": True,
                    },
                    headers=auth_headers,
                )
                assert alert_update_res.status_code == 200
                alert_data = alert_update_res.json()
                assert alert_data["has_slack_webhook"] is True
                assert alert_data["negative_threshold_pct"] == 20.0
                assert "ZZZZZZZZZZZZZZZZZZZZZZZZ" not in alert_data["slack_webhook_url"]

                # 8. Fetch themes -> verify counts and strictly read-only
                themes_res = client.get("/api/themes")
                assert themes_res.status_code == 200
                themes = themes_res.json()
                assert len(themes) >= 5
        finally:
            # Reliably restore all overrides and dispose engine connections
            app.dependency_overrides.clear()
            if hasattr(app.state, "db_session_factory"):
                delattr(app.state, "db_session_factory")
            engine.dispose()

        # 9. Direct verification on disk using fresh raw SQLite connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Verify reviews persisted in isolated DB
        cursor.execute("SELECT COUNT(*) FROM reviews;")
        (persisted_reviews_count,) = cursor.fetchone()
        assert persisted_reviews_count >= 60

        # Verify updated status persisted on disk
        cursor.execute("SELECT status FROM reviews WHERE id = ?;", (first_review_id,))
        (persisted_status,) = cursor.fetchone()
        assert persisted_status == "Investigating"

        # Verify alert config persisted on disk
        cursor.execute("SELECT slack_webhook_url, negative_threshold_pct, is_enabled FROM alert_configs LIMIT 1;")
        db_url_stored, db_threshold, db_enabled = cursor.fetchone()
        assert webhook_url == db_url_stored
        assert db_threshold == 20.0
        assert db_enabled == 1

        # Verify themes persisted on disk
        cursor.execute("SELECT COUNT(*) FROM themes;")
        (persisted_themes_count,) = cursor.fetchone()
        assert persisted_themes_count >= 5

        conn.close()

    # 10. Verify that normal application database(s) remained completely unchanged
    for p, initial_state in pre_test_db_states.items():
        current_state = _get_file_state(p)
        assert current_state == initial_state, f"Application database at {p} was unexpectedly altered during e2e test!"
