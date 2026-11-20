import io
import pytest
from datetime import datetime
from models import Review, SUPPORTED_SOURCES


def test_import_with_explicitly_selected_source(client, auth_headers):
    """Verifies that selecting a source during CSV import tags all imported reviews with that source."""
    csv_content = (
        "author,rating,content\n"
        "Alice,1,Cannot access account due to crash\n"
        "Bob,5,Great features and fast performance\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("feedback.csv", file, "text/csv")},
        data={"source": "Reddit"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 2

    # Verify all reviews have the selected source
    rev_res = client.get("/api/reviews?source=Reddit")
    reviews = rev_res.json()
    assert len(reviews) == 2
    for r in reviews:
        assert r["source"] == "Reddit"


def test_import_with_default_source(client, auth_headers):
    """Verifies that CSVs without a source column or form source receive the default 'CSV / Other'."""
    csv_content = (
        "author,rating,content\n"
        "Anonymous,3,Average experience with the app\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("no_source.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 1

    rev_res = client.get("/api/reviews?source=CSV / Other")
    reviews = rev_res.json()
    assert len(reviews) == 1
    assert reviews[0]["source"] == "CSV / Other"


def test_existing_csv_compatibility(client, auth_headers):
    """Verifies backward compatibility with legacy CSV formats including 'App Store'."""
    csv_content = (
        "source,author,rating,content\n"
        "App Store,LegacyUser,1,Crash on login\n"
        "Google Play,PlayUser,4,Nice update\n"
        "Discord,DiscordUser,2,Subscription failed\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("legacy.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 3
    assert data["skipped_rows"] == 0


def test_invalid_source_form_handling(client, auth_headers):
    """Verifies that an invalid source in the upload form returns 400 with supported sources."""
    csv_content = "author,rating,content\nUser1,5,Good app\n"
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("test.csv", file, "text/csv")},
        data={"source": "InvalidPlatform"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "Invalid source 'InvalidPlatform'" in res.json()["detail"]


def test_invalid_source_row_handling(client, auth_headers):
    """Verifies that an invalid source in a CSV row is skipped with a row-specific reason."""
    csv_content = (
        "source,author,rating,content\n"
        "FakeChannel,User1,1,Some feedback\n"
        "Google Play,User2,5,Valid review\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("test.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 1
    assert data["skipped_rows"] == 1
    assert any("Skipped invalid source 'FakeChannel'" in r for r in data["reasons"])


def test_source_filter_correctness(client, auth_headers, db_session):
    """Verifies source filtering works accurately alongside sentiment and themes."""
    reviews_to_add = [
        Review(
            source="Google Play",
            author="UserGP",
            rating=5,
            content="Great Google Play experience",
            sentiment_score=0.8,
            sentiment_label="Positive",
            category_theme="General",
            status="New",
        ),
        Review(
            source="Apple App Store",
            author="UserApple",
            rating=1,
            content="App crashes on iOS",
            sentiment_score=-0.7,
            sentiment_label="Negative",
            category_theme="Login Crash",
            status="New",
        ),
        Review(
            source="Reddit",
            author="UserReddit",
            rating=2,
            content="Laggy on Reddit thread",
            sentiment_score=-0.5,
            sentiment_label="Negative",
            category_theme="Performance & Lag",
            status="New",
        ),
        Review(
            source="X (Twitter)",
            author="UserX",
            rating=4,
            content="Tweeting praise",
            sentiment_score=0.6,
            sentiment_label="Positive",
            category_theme="UI/UX",
            status="New",
        ),
    ]
    for r in reviews_to_add:
        db_session.add(r)
    db_session.commit()

    # 1. Filter by Google Play
    res_gp = client.get("/api/reviews?source=Google Play")
    assert res_gp.status_code == 200
    assert len(res_gp.json()) == 1
    assert res_gp.json()[0]["author"] == "UserGP"

    # 2. Filter by Apple App Store (also matches legacy 'App Store')
    res_apple = client.get("/api/reviews?source=Apple App Store")
    assert res_apple.status_code == 200
    assert len(res_apple.json()) == 1
    assert res_apple.json()[0]["author"] == "UserApple"

    # 3. Filter by X (Twitter)
    res_x = client.get("/api/reviews?source=X (Twitter)")
    assert res_x.status_code == 200
    assert len(res_x.json()) == 1
    assert res_x.json()[0]["author"] == "UserX"

    # 4. Multi-filter: source + sentiment
    res_multi = client.get("/api/reviews?source=Reddit&sentiment=Negative")
    assert res_multi.status_code == 200
    assert len(res_multi.json()) == 1
    assert res_multi.json()[0]["author"] == "UserReddit"

    # 5. Multi-filter: source + non-matching sentiment
    res_none = client.get("/api/reviews?source=Reddit&sentiment=Positive")
    assert res_none.status_code == 200
    assert len(res_none.json()) == 0


def test_source_breakdown_in_analytics(client, db_session):
    """Verifies that analytics summary contains breakdowns for all supported channels."""
    reviews_data = [
        Review(
            source="Google Play",
            author="A",
            rating=5,
            content="Good",
            sentiment_score=0.5,
            sentiment_label="Positive",
            category_theme="General",
            status="New",
        ),
        Review(
            source="Apple App Store",
            author="B",
            rating=1,
            content="Crash",
            sentiment_score=-0.7,
            sentiment_label="Negative",
            category_theme="Login Crash",
            status="New",
        ),
        Review(
            source="X (Twitter)",
            author="C",
            rating=3,
            content="Average",
            sentiment_score=0.0,
            sentiment_label="Neutral",
            category_theme="UI/UX",
            status="New",
        ),
    ]
    for r in reviews_data:
        db_session.add(r)
    db_session.commit()

    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    counts = data["channel_counts"]
    assert "Google Play" in counts
    assert "Apple App Store" in counts
    assert "X (Twitter)" in counts
    assert "Reddit" in counts
    assert "Discord" in counts
    assert "CSV / Other" in counts
    assert counts["Google Play"] == 1
    assert counts["Apple App Store"] == 1
    assert counts["X (Twitter)"] == 1


def test_upload_csv_with_explicit_timestamp_preserves_created_at(client, auth_headers):
    """Verifies limitation 2 resolution: explicit created_at timestamps in CSV are parsed and preserved."""
    csv_content = (
        "source,author,rating,content,created_at\n"
        "Reddit,UserPast,4,Good app earlier,2026-01-15T08:30:00Z\n"
        "Discord,UserRecent,1,Crashing today,2026-03-30T10:15:00Z\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("dated_reviews.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["successful_imports"] == 2

    reviews_res = client.get("/api/reviews?limit=10")
    items = reviews_res.json()
    past_review = next(r for r in items if r["author"] == "UserPast")
    recent_review = next(r for r in items if r["author"] == "UserRecent")

    assert "2026-01-15" in past_review["created_at"]
    assert "2026-03-30" in recent_review["created_at"]
