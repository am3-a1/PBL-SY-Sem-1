import os
import uuid
import sqlite3
import pytest
from alembic.config import Config
from alembic import command


@pytest.fixture
def alembic_cfg():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    return cfg


def test_alembic_migration_on_fresh_empty_database(alembic_cfg, tmp_path):
    """
    Verifies that a brand-new empty SQLite database successfully upgrades
    to alembic head, creating all tables, indexes, and constraints.
    """
    db_file = tmp_path / f"fresh_{uuid.uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"

    # Database file is initially empty / doesn't exist
    assert not db_file.exists()

    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    assert db_file.exists()

    # Verify tables and columns
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "reviews" in tables
        assert "themes" in tables
        assert "alert_configs" in tables
        assert "alembic_version" in tables

        # Verify reviews columns include theme_confidence
        cursor.execute("PRAGMA table_info(reviews);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert "id" in columns
        assert "source" in columns
        assert "author" in columns
        assert "rating" in columns
        assert "content" in columns
        assert "theme_confidence" in columns
        assert "status" in columns

        # Verify insertion works
        cursor.execute(
            """
            INSERT INTO reviews (source, author, rating, content, sentiment_score, sentiment_label, category_theme, theme_confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("App Store", "Tester", 5, "Works great!", 0.9, "Positive", "General", 1.0, "New")
        )
        conn.commit()
        cursor.execute("SELECT count(*) FROM reviews;")
        assert cursor.fetchone()[0] == 1
    finally:
        conn.close()


def test_alembic_migration_on_legacy_database(alembic_cfg, tmp_path):
    """
    Verifies that an existing database created by the original pre-Alembic schema
    (without alembic_version and without theme_confidence) upgrades safely,
    adding theme_confidence and leaving existing records intact.
    """
    db_file = tmp_path / f"legacy_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.cursor()
        # Create legacy schema as defined in original FeedPulse
        cursor.execute("""
            CREATE TABLE alert_configs (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                slack_webhook_url VARCHAR(255),
                negative_threshold_pct FLOAT NOT NULL,
                is_enabled BOOLEAN NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE themes (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                owner_team VARCHAR(100),
                jira_component_id VARCHAR(100),
                created_at DATETIME
            );
        """)
        cursor.execute("""
            CREATE TABLE reviews (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                source VARCHAR(50) NOT NULL,
                author VARCHAR(100) NOT NULL,
                rating INTEGER,
                content TEXT NOT NULL,
                created_at DATETIME,
                sentiment_score FLOAT NOT NULL,
                sentiment_label VARCHAR(20) NOT NULL,
                category_theme VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL
            );
        """)
        # Insert legacy review records
        cursor.execute(
            """
            INSERT INTO reviews (source, author, rating, content, sentiment_score, sentiment_label, category_theme, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Google Play", "Legacy User 1", 1, "App crashed on launch", -0.8, "Negative", "Login Crash", "New")
        )
        cursor.execute(
            """
            INSERT INTO reviews (source, author, rating, content, sentiment_score, sentiment_label, category_theme, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Discord", "Legacy User 2", 4, "Pretty good overall", 0.5, "Positive", "General", "Resolved")
        )
        conn.commit()
    finally:
        conn.close()

    # Run Alembic upgrade head on this legacy database
    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    # Verify existing records are intact and theme_confidence column was added
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reviews);")
        columns = {row[1] for row in cursor.fetchall()}
        assert "theme_confidence" in columns

        cursor.execute("SELECT author, rating, content, status FROM reviews ORDER BY id;")
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0] == ("Legacy User 1", 1, "App crashed on launch", "New")
        assert rows[1] == ("Legacy User 2", 4, "Pretty good overall", "Resolved")

        # Verify alembic_version was stamped
        cursor.execute("SELECT version_num FROM alembic_version;")
        assert cursor.fetchone()[0] == "7051498a93a1"
    finally:
        conn.close()
