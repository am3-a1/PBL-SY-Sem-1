import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sqlalchemy as sa

import main
from main import app, lifespan, health_check
from config import settings


def test_successful_startup_lifespan(tmp_path):
    """Verifies that lifespan startup succeeds when database is initialized."""
    test_app = FastAPI(lifespan=lifespan)
    test_app.get("/health")(health_check)
    test_app.state.skip_schema_check = True

    # Use in-memory DB session with all tables created
    from sqlalchemy.pool import StaticPool
    engine = sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    main.database.Base.metadata.create_all(bind=engine)
    session_factory = sa.orm.sessionmaker(bind=engine)
    test_app.state.db_session_factory = session_factory

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[main.get_db] = override_db

    with TestClient(test_app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"


def test_database_connection_failure_aborts_startup():
    """Verifies that failure to connect to database raises RuntimeError and aborts startup."""
    test_app = FastAPI(lifespan=lifespan)

    def broken_session():
        raise sa.exc.OperationalError("Unable to open database file", {}, None)

    test_app.state.db_session_factory = broken_session
    test_app.state.allow_db_init_failure = False

    with patch.object(main.settings, "ENVIRONMENT", "production"):
        with pytest.raises(RuntimeError, match="Critical startup failure during database initialization"):
            with TestClient(test_app):
                pass


def test_missing_required_tables_aborts_startup(tmp_path):
    """Verifies that missing required schema tables aborts startup with clear migration hint."""
    import sqlite3
    empty_db = tmp_path / "empty_schema.db"
    conn = sqlite3.connect(str(empty_db))
    conn.execute("CREATE TABLE unrelated (id INT);")
    conn.commit()
    conn.close()

    engine = sa.create_engine(f"sqlite:///{empty_db}")
    session_factory = sa.orm.sessionmaker(bind=engine)

    test_app = FastAPI(lifespan=lifespan)
    test_app.state.db_session_factory = session_factory
    test_app.state.skip_schema_check = False
    test_app.state.allow_db_init_failure = False

    with patch.object(main.settings, "ENVIRONMENT", "production"):
        with pytest.raises(RuntimeError, match="Critical startup failure: Database is missing required tables"):
            with TestClient(test_app):
                pass


def test_optional_service_failure_does_not_abort_startup():
    """Verifies that optional service degradation (e.g. invalid Slack webhook URL) allows startup."""
    test_app = FastAPI(lifespan=lifespan)
    test_app.state.skip_schema_check = True

    with patch.object(main.settings, "DEFAULT_SLACK_WEBHOOK_URL", "https://invalid-non-slack.com/webhook"):
        with TestClient(test_app):
            assert test_app.state.optional_services.get("slack") == "degraded: invalid url"


def test_health_check_returns_503_when_database_is_degraded(client):
    """Verifies health check returns HTTP 503 when database connectivity fails or schema is missing."""
    def broken_db():
        session = MagicMock()
        session.execute.side_effect = sa.exc.OperationalError("Database disk image is malformed", {}, None)
        yield session

    app.dependency_overrides[main.get_db] = broken_db
    try:
        res = client.get("/health")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "unhealthy"
        assert "OperationalError" in data["database"]
    finally:
        app.dependency_overrides.pop(main.get_db, None)


def test_health_check_returns_503_when_tables_are_missing(client):
    """Verifies health check returns HTTP 503 when core tables are missing."""
    with patch("sqlalchemy.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["only_one_table"]
        mock_inspect.return_value = mock_inspector

        res = client.get("/health")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "degraded"
        assert "missing tables" in data["database"]
