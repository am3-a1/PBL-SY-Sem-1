import io
import pytest
from models import Review


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

    # Verify reviews were created
    rev_res = client.get("/api/reviews")
    assert len(rev_res.json()) == 3


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
    assert "Skipped invalid source 'UnknownChannel'" in data["reasons"][0]
