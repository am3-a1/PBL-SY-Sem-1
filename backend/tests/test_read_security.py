import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import main
from main import app


def test_read_endpoints_require_auth_when_require_read_auth_enabled(client, auth_headers):
    """
    Verifies that when REQUIRE_READ_AUTH is enabled (production mode),
    all read endpoints strictly reject unauthenticated requests with HTTP 401,
    and succeed with HTTP 200 when valid API key credentials are provided.
    """
    with patch.object(main.settings, "REQUIRE_READ_AUTH", True):
        # 1. GET /api/reviews
        res_reviews_unauth = client.get("/api/reviews")
        assert res_reviews_unauth.status_code == 401
        res_reviews_auth = client.get("/api/reviews", headers=auth_headers)
        assert res_reviews_auth.status_code == 200

        # 2. GET /api/themes
        res_themes_unauth = client.get("/api/themes")
        assert res_themes_unauth.status_code == 401
        res_themes_auth = client.get("/api/themes", headers=auth_headers)
        assert res_themes_auth.status_code == 200

        # 3. GET /api/analytics/summary
        res_analytics_unauth = client.get("/api/analytics/summary")
        assert res_analytics_unauth.status_code == 401
        res_analytics_auth = client.get("/api/analytics/summary", headers=auth_headers)
        assert res_analytics_auth.status_code == 200

        # 4. GET /api/alerts/config
        res_alerts_unauth = client.get("/api/alerts/config")
        assert res_alerts_unauth.status_code == 401
        res_alerts_auth = client.get("/api/alerts/config", headers=auth_headers)
        assert res_alerts_auth.status_code == 200


def test_health_endpoints_remain_public_when_read_auth_enabled(client):
    """
    Verifies that health check endpoints (/health, /api/health) remain public
    and operational without requiring authentication headers even when REQUIRE_READ_AUTH=True.
    """
    with patch.object(main.settings, "REQUIRE_READ_AUTH", True):
        res_root = client.get("/health")
        assert res_root.status_code == 200
        assert res_root.json()["status"] == "healthy"

        res_api = client.get("/api/health")
        assert res_api.status_code == 200
        assert res_api.json()["status"] == "healthy"


def test_read_endpoints_accessible_without_auth_in_dev_mode(client):
    """
    Verifies that in development mode (REQUIRE_READ_AUTH=False),
    read endpoints allow unauthenticated read-only access for zero-friction local exploration.
    """
    with patch.object(main.settings, "REQUIRE_READ_AUTH", False):
        res_reviews = client.get("/api/reviews")
        assert res_reviews.status_code == 200

        res_themes = client.get("/api/themes")
        assert res_themes.status_code == 200

        res_analytics = client.get("/api/analytics/summary")
        assert res_analytics.status_code == 200
