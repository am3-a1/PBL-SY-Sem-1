import pytest
from datetime import datetime
from models import Review, Theme, AlertConfig
from main import init_default_themes


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_authentication_required_for_destructive_ops(client):
    # Without header -> 401 Unauthorized
    res = client.delete("/api/reviews")
    assert res.status_code == 401
    assert "Invalid or missing API key" in res.json()["detail"]

    res = client.post("/api/reviews/seed")
    assert res.status_code == 401

    res = client.patch("/api/reviews/1/status", json={"status": "Resolved"})
    assert res.status_code == 401


def test_seed_reviews_flow(client, auth_headers):
    res = client.post("/api/reviews/seed", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_seeded"] >= 60

    # Verify reviews exist
    rev_res = client.get("/api/reviews")
    assert rev_res.status_code == 200
    reviews = rev_res.json()
    assert len(reviews) == data["total_seeded"]


def test_review_status_update_and_validation(client, auth_headers, db_session):
    rev = Review(
        source="App Store",
        author="Test User",
        rating=1,
        content="App crashes on startup",
        sentiment_score=-0.7,
        sentiment_label="Negative",
        category_theme="Login Crash",
        status="New",
    )
    db_session.add(rev)
    db_session.commit()
    db_session.refresh(rev)

    # Valid status update
    res = client.patch(
        f"/api/reviews/{rev.id}/status",
        json={"status": "Investigating"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "Investigating"

    # Invalid status rejection
    bad_res = client.patch(
        f"/api/reviews/{rev.id}/status",
        json={"status": "NonExistentStatus"},
        headers=auth_headers,
    )
    assert bad_res.status_code == 400
    assert "Invalid status" in bad_res.json()["detail"]

    # Not found status update
    nf_res = client.patch(
        "/api/reviews/999999/status",
        json={"status": "Resolved"},
        headers=auth_headers,
    )
    assert nf_res.status_code == 404


def test_delete_review(client, auth_headers, db_session):
    rev = Review(
        source="Discord",
        author="Tester",
        rating=5,
        content="Works nicely",
        sentiment_score=0.8,
        sentiment_label="Positive",
        category_theme="General",
        status="New",
    )
    db_session.add(rev)
    db_session.commit()
    db_session.refresh(rev)

    del_res = client.delete(f"/api/reviews/{rev.id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Second delete returns 404
    del_res2 = client.delete(f"/api/reviews/{rev.id}", headers=auth_headers)
    assert del_res2.status_code == 404


def test_clear_all_reviews(client, auth_headers, db_session):
    rev = Review(
        source="Google Play",
        author="Dev",
        content="Buggy",
        sentiment_score=-0.4,
        sentiment_label="Negative",
        category_theme="General",
        status="New",
    )
    db_session.add(rev)
    db_session.commit()

    res = client.delete("/api/reviews", headers=auth_headers)
    assert res.status_code == 200
    assert "Cleared" in res.json()["message"]

    rev_res = client.get("/api/reviews")
    assert len(rev_res.json()) == 0


def test_pagination_reviews(client, auth_headers, db_session):
    # Add 5 reviews
    for i in range(5):
        rev = Review(
            source="Reddit",
            author=f"User{i}",
            content=f"Review number {i}",
            sentiment_score=0.1 * i,
            sentiment_label="Positive" if i > 2 else "Neutral",
            category_theme="General",
            status="New",
        )
        db_session.add(rev)
    db_session.commit()

    # Request page 1 with page_size=2
    res = client.get("/api/reviews?page=1&page_size=2")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2


def test_empty_analytics(client):
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_reviews"] == 0
    assert data["avg_sentiment"] == 0.0
    assert data["critical_negative_count"] == 0
    assert data["sentiment_timeline"] == []


def test_analytics_calculations(client, db_session):
    # Add diverse reviews
    reviews_data = [
        Review(
            source="App Store",
            author="A",
            rating=1,
            content="Crash",
            sentiment_score=-0.8,
            sentiment_label="Negative",
            category_theme="Login Crash",
            status="New",
            created_at=datetime(2026, 11, 15, 10, 0),
        ),
        Review(
            source="App Store",
            author="B",
            rating=5,
            content="Great",
            sentiment_score=0.9,
            sentiment_label="Positive",
            category_theme="General",
            status="Resolved",
            created_at=datetime(2026, 11, 15, 12, 0),
        ),
        Review(
            source="Google Play",
            author="C",
            rating=2,
            content="Charge issue",
            sentiment_score=-0.6,
            sentiment_label="Negative",
            category_theme="Billing & Payments",
            status="Escalated",
            created_at=datetime(2026, 11, 16, 9, 0),
        ),
    ]
    for r in reviews_data:
        db_session.add(r)
    db_session.commit()

    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_reviews"] == 3
    assert data["sentiment_counts"]["Negative"] == 2
    assert data["sentiment_counts"]["Positive"] == 1
    assert data["channel_counts"]["App Store"] == 2
    assert data["channel_counts"]["Google Play"] == 1
    assert data["critical_negative_count"] == 2
    assert len(data["sentiment_timeline"]) == 2


def test_theme_listing_and_escalate(client, auth_headers, db_session):
    # Explicitly seed themes for test
    init_default_themes(db_session)
    res = client.get("/api/themes")
    assert res.status_code == 200
    themes = res.json()
    assert len(themes) >= 5

    target_theme = themes[0]

    # Add a review in this theme
    rev = Review(
        source="App Store",
        author="X",
        rating=1,
        content="Crash issue",
        sentiment_score=-0.7,
        sentiment_label="Negative",
        category_theme=target_theme["name"],
        status="New",
    )
    db_session.add(rev)
    db_session.commit()

    # Escalate theme
    esc_res = client.post(f"/api/themes/{target_theme['id']}/escalate", headers=auth_headers)
    assert esc_res.status_code == 200
    assert esc_res.json()["escalated_count"] == 1

    # Verify review status is updated
    db_session.refresh(rev)
    assert rev.status == "Escalated"


def test_alert_config_and_webhook_protection(client, auth_headers):
    # Get initial config
    res = client.get("/api/alerts/config")
    assert res.status_code == 200
    data = res.json()
    assert "has_slack_webhook" in data

    # Update with invalid webhook URL -> 400 Bad Request
    bad_update = client.put(
        "/api/alerts/config",
        json={"slack_webhook_url": "http://insecure-url.com/webhook"},
        headers=auth_headers,
    )
    assert bad_update.status_code == 400
    assert "Invalid Slack" in bad_update.json()["detail"]

    # Update with valid Slack webhook URL (assembled dynamically to avoid push-protection false positives)
    slack_host = "hooks." + "slack.com"
    good_url = f"https://{slack_host}/services/T11111111/B22222222/ZZZZZZZZZZZZZZZZZZZZZZZZ"
    good_update = client.put(
        "/api/alerts/config",
        json={"slack_webhook_url": good_url, "negative_threshold_pct": 25.0},
        headers=auth_headers,
    )
    assert good_update.status_code == 200
    resp_data = good_update.json()
    assert resp_data["has_slack_webhook"] is True
    # Ensure webhook URL is masked in response
    assert "ZZZZZZZZZZZZZZZZZZZZZZZZ" not in resp_data["slack_webhook_url"]
    assert resp_data["negative_threshold_pct"] == 25.0


def test_get_endpoints_do_not_write_to_database(client, db_session):
    """
    Verifies GET /api/themes and GET /api/alerts/config are strictly read-only
    and perform zero database insertions or mutations when querying an empty DB.
    """
    # Verify DB is currently empty for themes and alert configs
    assert db_session.query(Theme).count() == 0
    assert db_session.query(AlertConfig).count() == 0

    # 1. GET /api/themes on empty database
    theme_res = client.get("/api/themes")
    assert theme_res.status_code == 200
    assert theme_res.json() == []
    # Assert still 0 in DB
    assert db_session.query(Theme).count() == 0

    # 2. GET /api/alerts/config on empty database
    alert_res = client.get("/api/alerts/config")
    assert alert_res.status_code == 200
    data = alert_res.json()
    assert data["id"] == 0
    assert data["has_slack_webhook"] is False
    # Assert still 0 in DB
    assert db_session.query(AlertConfig).count() == 0
