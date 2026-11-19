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


def test_fresh_database_upgrade_downgrade_and_reupgrade(alembic_cfg, tmp_path):
    """
    Scenario 1 & 4:
    Fresh empty database -> upgrade -> downgrade -> re-upgrade.
    Verifies tables are created on upgrade, removed on downgrade, and recreated on re-upgrade.
    """
    db_file = tmp_path / f"fresh_{uuid.uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade fresh DB
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "reviews" in tables
    assert "themes" in tables
    assert "alert_configs" in tables
    conn.close()

    # 2. Downgrade fresh DB
    command.downgrade(alembic_cfg, "base")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables_after_downgrade = {row[0] for row in cursor.fetchall()}
    # Created tables should be cleanly removed
    assert "reviews" not in tables_after_downgrade
    assert "themes" not in tables_after_downgrade
    assert "alert_configs" not in tables_after_downgrade
    conn.close()

    # 3. Re-upgrade
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables_reupgrade = {row[0] for row in cursor.fetchall()}
    assert "reviews" in tables_reupgrade
    assert "themes" in tables_reupgrade
    assert "alert_configs" in tables_reupgrade
    conn.close()


def test_legacy_database_upgrade_preserves_records_and_downgrade_protects_data(alembic_cfg, tmp_path):
    """
    Scenario 2:
    Legacy database (without theme_confidence) with existing user data.
    Upgrade adds theme_confidence without modifying data.
    Downgrade removes ONLY theme_confidence, keeping reviews and user data 100% intact.
    """
    db_file = tmp_path / f"legacy_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
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
    cursor.execute(
        "INSERT INTO reviews (source, author, rating, content, sentiment_score, sentiment_label, category_theme, status) "
        "VALUES ('Google Play', 'Legacy User 1', 1, 'Critical crash', -0.8, 'Negative', 'Login Crash', 'New');"
    )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade legacy DB
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(reviews);")
    cols = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" in cols

    # Verify existing record intact
    cursor.execute("SELECT author, content FROM reviews;")
    assert cursor.fetchone() == ("Legacy User 1", "Critical crash")
    conn.close()

    # 2. Downgrade legacy DB
    command.downgrade(alembic_cfg, "base")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # reviews table must still exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "reviews" in tables
    assert "themes" in tables
    assert "alert_configs" in tables

    # theme_confidence should be removed
    cursor.execute("PRAGMA table_info(reviews);")
    cols_after = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" not in cols_after

    # User data MUST be completely preserved!
    cursor.execute("SELECT author, content FROM reviews;")
    assert cursor.fetchone() == ("Legacy User 1", "Critical crash")
    conn.close()


def test_legacy_database_with_existing_theme_confidence(alembic_cfg, tmp_path):
    """
    Scenario 3:
    Legacy database where theme_confidence ALREADY existed before migration.
    Upgrade shouldn't fail.
    Downgrade must PRESERVE theme_confidence because it wasn't added by this migration!
    """
    db_file = tmp_path / f"legacy_with_conf_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
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
            theme_confidence FLOAT DEFAULT 0.85,
            status VARCHAR(50) NOT NULL
        );
    """)
    cursor.execute(
        "INSERT INTO reviews (source, author, rating, content, sentiment_score, sentiment_label, category_theme, theme_confidence, status) "
        "VALUES ('App Store', 'Pre-existing User', 5, 'Great app', 0.9, 'Positive', 'General', 0.85, 'New');"
    )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT theme_confidence FROM reviews;")
    assert cursor.fetchone()[0] == 0.85
    conn.close()

    # 2. Downgrade -> must NOT drop theme_confidence because this migration didn't add it!
    command.downgrade(alembic_cfg, "base")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(reviews);")
    cols = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" in cols
    cursor.execute("SELECT author, theme_confidence FROM reviews;")
    assert cursor.fetchone() == ("Pre-existing User", 0.85)
    conn.close()
