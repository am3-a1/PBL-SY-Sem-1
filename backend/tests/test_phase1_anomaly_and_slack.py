import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import httpx
import pytest

from models import Review, AlertConfig
import anomaly
import nlp
from anomaly import (
    calculate_z_score,
    detect_negative_review_anomalies,
    reset_dispatched_alerts,
)


@pytest.fixture(autouse=True)
def clean_anomaly_alert_cache():
    reset_dispatched_alerts()
    yield
    reset_dispatched_alerts()


def test_normal_review_volume():
    """Verifies that steady, low-negative volume produces Z < threshold and is not an anomaly."""
    # Historical counts of 1 negative review per hour across 10 hours
    historical = [1, 1, 2, 1, 0, 1, 2, 1, 1, 0]
    # Current hour has 1 negative review
    is_anomaly, z, mean, std, severity, reason = calculate_z_score(
        current_count=1,
        historical_counts=historical,
        threshold=2.5,
    )
    assert is_anomaly is False
    assert severity == "NORMAL"
    assert z is not None
    assert z < 2.5


def test_negative_review_spike():
    """Verifies that a sudden surge in negative reviews exceeds the Z-score threshold."""
    # Historical baseline: mean ~ 1.0, std > 0
    historical = [1, 0, 1, 1, 0, 1, 2, 0, 1, 1]
    # Sudden surge of 9 negative reviews
    is_anomaly, z, mean, std, severity, reason = calculate_z_score(
        current_count=9,
        historical_counts=historical,
        threshold=2.5,
    )
    assert is_anomaly is True
    assert severity in ("HIGH", "CRITICAL")
    assert z is not None
    assert z >= 2.5


def test_insufficient_historical_data():
    """Verifies that fewer than 3 historical windows reports insufficient baseline data."""
    historical = [1, 2]  # Only 2 windows
    is_anomaly, z, mean, std, severity, reason = calculate_z_score(
        current_count=5,
        historical_counts=historical,
        threshold=2.5,
    )
    assert is_anomaly is False
    assert z is None
    assert "Insufficient historical data" in reason


def test_zero_variance_scenarios():
    """Verifies graceful handling of flat baselines with zero standard deviation."""
    # Case A: Exactly flat baseline, current count equals historical mean
    historical_flat = [0, 0, 0, 0, 0]
    is_anomaly_a, z_a, mean_a, std_a, sev_a, _ = calculate_z_score(
        current_count=0,
        historical_counts=historical_flat,
        threshold=2.5,
    )
    assert is_anomaly_a is False
    assert std_a == 0.0

    # Case B: Significant spike (>= 3) above zero baseline
    is_anomaly_b, z_b, mean_b, std_b, sev_b, _ = calculate_z_score(
        current_count=5,
        historical_counts=historical_flat,
        threshold=2.5,
    )
    assert is_anomaly_b is True
    assert sev_b == "CRITICAL"

    # Case C: Minor volume increment (+1) on zero baseline is statistically inconclusive
    is_anomaly_c, z_c, mean_c, std_c, sev_c, _ = calculate_z_score(
        current_count=1,
        historical_counts=historical_flat,
        threshold=2.5,
    )
    assert is_anomaly_c is False


def test_empty_windows():
    """Verifies detection evaluates gracefully when no reviews exist in recent windows."""
    report = detect_negative_review_anomalies([])
    assert report.is_anomaly is False
    assert report.has_sufficient_data is False
    assert report.current_negative_count == 0


def test_invalid_and_timezone_timestamps():
    """Verifies that invalid or timezone-aware timestamps are handled without crashing."""
    now = datetime.utcnow()
    reviews = [
        Review(
            id=1,
            source="Reddit",
            author="A",
            content="Crash",
            sentiment_score=-0.8,
            sentiment_label="Negative",
            category_theme="Login Crash",
            status="New",
            created_at=None,  # Missing timestamp
        ),
        Review(
            id=2,
            source="Reddit",
            author="B",
            content="Works",
            sentiment_score=0.7,
            sentiment_label="Positive",
            category_theme="General",
            status="New",
            created_at=now,
        ),
        Review(
            id=3,
            source="Discord",
            author="C",
            content="Bad",
            sentiment_score=-0.5,
            sentiment_label="Negative",
            category_theme="UI/UX",
            status="New",
            created_at=now - timedelta(hours=2),
        ),
        Review(
            id=4,
            source="Discord",
            author="D",
            content="Broken",
            sentiment_score=-0.6,
            sentiment_label="Negative",
            category_theme="Login Crash",
            status="New",
            created_at=now - timedelta(hours=3),
        ),
    ]
    report = detect_negative_review_anomalies(reviews=reviews, eval_time=now)
    assert report is not None
    assert report.current_total_count >= 1


def test_duplicate_alert_prevention():
    """Verifies that an alert is not dispatched twice for the exact same anomaly window."""
    now = datetime.utcnow()
    # Create an anomalous batch of reviews
    reviews = []
    # 5 historical reviews (1 per hour)
    for h in range(1, 6):
        reviews.append(
            Review(
                id=h,
                source="Google Play",
                author=f"User{h}",
                content=f"Historical review {h}",
                sentiment_score=-0.2,
                sentiment_label="Negative",
                category_theme="General",
                status="New",
                created_at=now - timedelta(hours=h + 1),
            )
        )
    # Current window: 10 negative reviews in Login Crash
    for c in range(10):
        reviews.append(
            Review(
                id=100 + c,
                source="Google Play",
                author=f"CrashUser{c}",
                content=f"Crash on login {c}",
                sentiment_score=-0.8,
                sentiment_label="Negative",
                category_theme="Login Crash",
                status="New",
                created_at=now - timedelta(minutes=10),
            )
        )

    mock_alert_config = AlertConfig(
        id=1,
        slack_webhook_url=None,  # Sandbox mode
        negative_threshold_pct=30.0,
        is_enabled=True,
    )

    # First detection -> should trigger alert
    rep1 = detect_negative_review_anomalies(
        reviews=reviews,
        eval_time=now,
        threshold=2.0,
        alert_config=mock_alert_config,
        dispatch_slack=True,
    )
    assert rep1.is_anomaly is True
    assert rep1.alert_triggered is True

    # Second detection for same window -> should NOT dispatch duplicate alert
    rep2 = detect_negative_review_anomalies(
        reviews=reviews,
        eval_time=now,
        threshold=2.0,
        alert_config=mock_alert_config,
        dispatch_slack=True,
    )
    assert rep2.is_anomaly is True
    assert rep2.alert_triggered is False
    assert "already dispatched" in rep2.reason


def test_representative_negative_review_selection():
    """Verifies that the detector selects an actual negative review from the spike theme."""
    now = datetime.utcnow()
    reviews = [
        # Historical baseline
        Review(id=1, source="App Store", author="H1", content="ok", sentiment_score=0.1, sentiment_label="Neutral", category_theme="General", status="New", created_at=now - timedelta(hours=2)),
        Review(id=2, source="App Store", author="H2", content="fine", sentiment_score=0.2, sentiment_label="Positive", category_theme="General", status="New", created_at=now - timedelta(hours=3)),
        Review(id=3, source="App Store", author="H3", content="minor", sentiment_score=-0.1, sentiment_label="Negative", category_theme="General", status="New", created_at=now - timedelta(hours=4)),
        # Current window: mix of reviews, but worst is crash
        Review(id=10, source="App Store", author="Happy", content="I love this app so much!", sentiment_score=0.9, sentiment_label="Positive", category_theme="General", status="New", created_at=now - timedelta(minutes=15)),
        Review(id=11, source="App Store", author="Victim", content="The app crashes on startup after iOS update!", sentiment_score=-0.85, sentiment_label="Negative", category_theme="Login Crash", status="New", created_at=now - timedelta(minutes=10)),
        Review(id=12, source="App Store", author="Victim2", content="Login failed with error 500", sentiment_score=-0.75, sentiment_label="Negative", category_theme="Login Crash", status="New", created_at=now - timedelta(minutes=5)),
    ]
    report = detect_negative_review_anomalies(reviews=reviews, eval_time=now, threshold=1.0)
    assert report.triggering_theme == "Login Crash"
    assert "crashes on startup" in report.representative_review


def test_valid_slack_payload_generation():
    """Verifies enriched Slack Block Kit payload structure with all contextual fields."""
    payload = nlp.build_slack_blocks(
        title="Spike in Login Crash",
        message="Critical spike detected in past hour.",
        sample_review="Cannot log into my account, app shuts down.",
        alert_type="Time-Series Anomaly (Z-Score)",
        severity="CRITICAL",
        theme="Login Crash",
        affected_reviews=8,
        negative_pct=80.0,
        time_window="14:00 - 15:00 UTC",
    )
    assert "blocks" in payload
    blocks = payload["blocks"]
    assert len(blocks) >= 4

    # Header block check
    header = blocks[0]
    assert header["type"] == "header"
    assert "CRITICAL" in header["text"]["text"]

    # Fields block check
    fields_section = next(b for b in blocks if "fields" in b)
    field_texts = [f["text"] for f in fields_section["fields"]]
    assert any("Alert Type" in t for t in field_texts)
    assert any("Severity" in t for t in field_texts)
    assert any("Triggering Theme" in t for t in field_texts)
    assert any("Affected Reviews" in t for t in field_texts)
    assert any("Time Window" in t for t in field_texts)


def test_slack_http_failure_handling():
    """Verifies that HTTP non-200 responses are handled gracefully without raising unhandled errors."""
    fake_url = "https://hooks.slack.com/services/T00/B00/MOCKTOKEN"
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        res = asyncio.run(
            nlp.dispatch_slack_alert(
                webhook_url=fake_url,
                title="Test",
                message="Test message",
            )
        )
        assert res["status"] == "error"
        assert "500" in res["message"]


def test_slack_timeout_handling():
    """Verifies that webhook timeouts (10s) are caught without crashing."""
    fake_url = "https://hooks.slack.com/services/T00/B00/MOCKTOKEN"
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
        res = asyncio.run(
            nlp.dispatch_slack_alert(
                webhook_url=fake_url,
                title="Test",
                message="Test message",
            )
        )
        assert res["status"] == "error"
        assert "timed out" in res["message"].lower()


def test_sensitive_configuration_not_exposed(client, auth_headers):
    """Verifies that webhook secrets are never exposed in plaintext in alert config responses."""
    good_url = "https://hooks.slack.com/services/T00/B00/MOCKTOKEN"
    res = client.put(
        "/api/alerts/config",
        json={"slack_webhook_url": good_url, "z_score_threshold": 3.0},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "MOCKTOKEN" not in data["slack_webhook_url"]
    assert "******" in data["slack_webhook_url"]
    assert data["z_score_threshold"] == 3.0
