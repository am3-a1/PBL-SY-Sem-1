import io
import pytest
from models import Review
from config import settings


def test_csv_upload_requires_auth(client):
    csv_bytes = b"source,author,rating,content\nApp Store,User1,1,Crashes constantly"
    file = io.BytesIO(csv_bytes)
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("test.csv", file, "text/csv")},
    )
    assert res.status_code == 401


def test_csv_upload_success(client, auth_headers):
    csv_content = (
        "source,author,rating,content\n"
        "App Store,Alice,1,Application crashes immediately when logging in\n"
        "Google Play,Bob,5,Love the smooth UI and clean typography\n"
        "Reddit,Charlie,,Laggy scrolling and slow loading times\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("feedback.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 3
    assert data["total_rows_processed"] == 3
    assert data["skipped_rows"] == 0

    # Verify reviews were created and missing rating is None
    rev_res = client.get("/api/reviews")
    reviews = rev_res.json()
    assert len(reviews) == 3
    charlie_rev = next(r for r in reviews if r["author"] == "Charlie")
    assert charlie_rev["rating"] is None


def test_csv_upload_missing_content_column(client, auth_headers):
    csv_content = "source,author,rating\nApp Store,Alice,5\n"
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("missing_col.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "must contain at least a 'content' column" in res.json()["detail"]


def test_csv_upload_empty_file(client, auth_headers):
    file = io.BytesIO(b"")
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("empty.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "Uploaded file is empty" in res.json()["detail"]


def test_csv_upload_header_only_file(client, auth_headers):
    file = io.BytesIO(b"content,source,author\n")
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("header_only.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "no data rows" in res.json()["detail"]


def test_csv_upload_invalid_file_extension(client, auth_headers):
    file = io.BytesIO(b"some content")
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("malicious.exe", file, "application/octet-stream")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "Invalid file format" in res.json()["detail"]


def test_csv_upload_skips_invalid_sources_with_reason(client, auth_headers):
    csv_content = (
        "source,author,rating,content\n"
        "UnknownChannel,Alice,1,This source is not supported\n"
        "Google Play,Bob,5,Valid source\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("sources.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 1
    assert data["skipped_rows"] == 1
    assert len(data["reasons"]) >= 1
    assert "Row 2: Skipped invalid source 'UnknownChannel'" in data["reasons"][0]


def test_csv_upload_rating_validation_out_of_range(client, auth_headers):
    """Verifies that out-of-range ratings (0, 6, 10, -1) are skipped with row-specific errors."""
    csv_content = (
        "source,author,rating,content\n"
        "App Store,UserZero,0,Rating is zero\n"
        "Google Play,UserSix,6,Rating is six\n"
        "Reddit,UserTen,10,Rating is ten\n"
        "Discord,UserNeg,-1,Rating is negative\n"
        "App Store,ValidUser,4,Valid rating\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("ratings_range.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 1
    assert data["skipped_rows"] == 4
    assert len(data["reasons"]) == 4
    assert "Row 2: Rating '0' is out of range" in data["reasons"][0]
    assert "Row 3: Rating '6' is out of range" in data["reasons"][1]
    assert "Row 4: Rating '10' is out of range" in data["reasons"][2]
    assert "Row 5: Rating '-1' is out of range" in data["reasons"][3]


def test_csv_upload_rating_validation_non_numeric_and_fractional(client, auth_headers):
    """Verifies that non-numeric and non-integer ratings are skipped with explicit errors."""
    csv_content = (
        "source,author,rating,content\n"
        "App Store,UserWords,five,Rating is text\n"
        "Google Play,UserFraction,3.5,Rating is decimal\n"
        "Discord,UserValid,5,Valid integer rating\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("ratings_types.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 1
    assert data["skipped_rows"] == 2
    assert "Row 2: Invalid non-numeric rating 'five'" in data["reasons"][0]
    assert "Row 3: Invalid non-integer rating '3.5'" in data["reasons"][1]


def test_csv_upload_oversized_text_rejection(client, auth_headers):
    """Verifies that review text exceeding MAX_CONTENT_LENGTH is rejected with clear row error."""
    max_len = settings.MAX_CONTENT_LENGTH
    exact_text = "A" * max_len
    oversized_text = "B" * (max_len + 50)

    csv_content = (
        "source,author,rating,content\n"
        f"App Store,ExactUser,5,{exact_text}\n"
        f"Google Play,OversizedUser,1,{oversized_text}\n"
    )
    file = io.BytesIO(csv_content.encode("utf-8"))
    res = client.post(
        "/api/reviews/upload",
        files={"file": ("length_test.csv", file, "text/csv")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_imports"] == 1
    assert data["skipped_rows"] == 1
    assert len(data["reasons"]) == 1
    assert f"Row 3: Review content exceeds maximum allowed length of {max_len}" in data["reasons"][0]

    # Confirm the exact length review was stored intact
    rev_res = client.get("/api/reviews")
    reviews = rev_res.json()
    exact_rev = next(r for r in reviews if r["author"] == "ExactUser")
    assert len(exact_rev["content"]) == max_len
