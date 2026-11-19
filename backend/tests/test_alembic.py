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


def test_legacy_database_with_existing_metadata_table(alembic_cfg, tmp_path):
    """
    Scenario 4:
    Legacy database where _alembic_migration_metadata ALREADY existed before migration.
    Upgrade should preserve existing metadata rows and perform required schema upgrades.
    Downgrade must PRESERVE _alembic_migration_metadata and its original contents because
    this migration did not create the table!
    """
    db_file = tmp_path / f"legacy_meta_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE _alembic_migration_metadata (
            key VARCHAR(100) PRIMARY KEY,
            value VARCHAR(100) NOT NULL
        );
    """)
    cursor.execute(
        "INSERT INTO _alembic_migration_metadata (key, value) VALUES ('legacy_custom_key', 'custom_value_123');"
    )
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
        "VALUES ('Google Play', 'Legacy Meta User', 2, 'Needs update', -0.3, 'Negative', 'General', 'New');"
    )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # Check that pre-existing metadata key is intact
    cursor.execute("SELECT value FROM _alembic_migration_metadata WHERE key = 'legacy_custom_key';")
    assert cursor.fetchone() == ("custom_value_123",)
    # Check that theme_confidence was added
    cursor.execute("PRAGMA table_info(reviews);")
    cols = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" in cols
    conn.close()

    # 2. Downgrade
    command.downgrade(alembic_cfg, "base")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # _alembic_migration_metadata MUST still exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables_after = {row[0] for row in cursor.fetchall()}
    assert "_alembic_migration_metadata" in tables_after
    assert "reviews" in tables_after

    # Original metadata key/value MUST be preserved
    cursor.execute("SELECT value FROM _alembic_migration_metadata WHERE key = 'legacy_custom_key';")
    assert cursor.fetchone() == ("custom_value_123",)

    # Original user review MUST be preserved
    cursor.execute("SELECT author, content FROM reviews;")
    assert cursor.fetchone() == ("Legacy Meta User", "Needs update")
    conn.close()


def test_legacy_database_with_all_colliding_metadata_keys(alembic_cfg, tmp_path):
    """
    Scenario 5:
    Legacy database containing pre-existing metadata rows for EVERY generic key
    AND every revision-scoped key.
    Verifies:
    1. Upgrade succeeds without primary key violation or crashing on collisions.
    2. Pre-existing user review records and table schemas are preserved.
    3. Downgrade restores EVERY pre-existing metadata key to its exact original value.
    4. Downgrade does not drop pre-existing tables or metadata table.
    5. Re-upgrade after downgrade succeeds cleanly.
    """
    db_file = tmp_path / f"legacy_colliding_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE _alembic_migration_metadata (
            key VARCHAR(100) PRIMARY KEY,
            value VARCHAR(100) NOT NULL
        );
    """)

    preexisting_metadata = {
        "created_reviews": "preexisting_generic_reviews_value",
        "created_themes": "preexisting_generic_themes_value",
        "created_alert_configs": "preexisting_generic_alerts_value",
        "added_theme_confidence": "preexisting_generic_conf_value",
        "created_metadata_table": "preexisting_generic_meta_value",
        "rev_7051498a93a1:created_reviews": "preexisting_scoped_reviews_value",
        "rev_7051498a93a1:created_themes": "preexisting_scoped_themes_value",
        "rev_7051498a93a1:created_alert_configs": "preexisting_scoped_alerts_value",
        "rev_7051498a93a1:added_theme_confidence": "preexisting_scoped_conf_value",
        "rev_7051498a93a1:created_metadata_table": "preexisting_scoped_meta_value",
        "unrelated_app_setting": "unrelated_app_value_999",
    }

    for k, v in preexisting_metadata.items():
        cursor.execute(
            "INSERT INTO _alembic_migration_metadata (key, value) VALUES (?, ?);",
            (k, v),
        )

    # Legacy reviews table
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
        "VALUES ('Reddit', 'Collision User', 4, 'Great work', 0.6, 'Positive', 'General', 'New');"
    )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade against colliding database
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # reviews table must have theme_confidence added
    cursor.execute("PRAGMA table_info(reviews);")
    cols = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" in cols
    # legacy review row preserved
    cursor.execute("SELECT author, content FROM reviews;")
    assert cursor.fetchone() == ("Collision User", "Great work")
    # generic keys were never touched
    for k in ["created_reviews", "created_themes", "created_alert_configs", "added_theme_confidence", "created_metadata_table", "unrelated_app_setting"]:
        cursor.execute("SELECT value FROM _alembic_migration_metadata WHERE key = ?;", (k,))
        assert cursor.fetchone() == (preexisting_metadata[k],)
    conn.close()

    # 2. Downgrade
    command.downgrade(alembic_cfg, "base")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    # reviews table and metadata table must still exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "reviews" in tables
    assert "_alembic_migration_metadata" in tables

    # theme_confidence should be removed (as it was added by this migration)
    cursor.execute("PRAGMA table_info(reviews);")
    cols_after = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" not in cols_after

    # Legacy review row preserved
    cursor.execute("SELECT author, content FROM reviews;")
    assert cursor.fetchone() == ("Collision User", "Great work")

    # Verify EVERY pre-existing metadata entry has been restored to its EXACT original value
    for k, v in preexisting_metadata.items():
        cursor.execute("SELECT value FROM _alembic_migration_metadata WHERE key = ?;", (k,))
        row = cursor.fetchone()
        assert row is not None, f"Metadata key '{k}' was lost during downgrade!"
        assert row[0] == v, f"Metadata key '{k}' value mismatch: expected '{v}', got '{row[0]}'"

    # No __orig__ temporary keys left behind
    cursor.execute("SELECT key FROM _alembic_migration_metadata WHERE key LIKE '%__orig__';")
    orig_keys = cursor.fetchall()
    assert len(orig_keys) == 0, f"Dangling backup keys found: {orig_keys}"
    conn.close()

    # 3. Re-upgrade after downgrade succeeds
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(reviews);")
    cols_reupgrade = {row[1] for row in cursor.fetchall()}
    assert "theme_confidence" in cols_reupgrade
    cursor.execute("SELECT author, content FROM reviews;")
    assert cursor.fetchone() == ("Collision User", "Great work")
    conn.close()


def test_alembic_cli_upgrade_uses_settings_database_url(tmp_path):
    """
    Scenario 6:
    CLI execution of 'alembic upgrade head' without explicit programmatic override.
    Verifies that Alembic env.py properly resolves DATABASE_URL and executes
    without NoSuchModuleError (driver:// placeholder issue).
    """
    import subprocess
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_bin = os.path.join(backend_dir, "venv", "bin", "alembic")
    db_file = tmp_path / f"cli_test_{uuid.uuid4().hex}.db"
    db_url = f"sqlite:///{db_file}"

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url

    # 1. Run upgrade head via CLI
    res_upgrade = subprocess.run(
        [alembic_bin, "upgrade", "head"],
        env=env,
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    assert res_upgrade.returncode == 0, f"CLI upgrade failed: {res_upgrade.stderr}\n{res_upgrade.stdout}"
    assert "NoSuchModuleError" not in res_upgrade.stderr

    # Verify tables created
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    assert "reviews" in tables
    assert "themes" in tables
    assert "alert_configs" in tables
    conn.close()

    # 2. Run current via CLI
    res_curr = subprocess.run(
        [alembic_bin, "current"],
        env=env,
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    assert res_curr.returncode == 0
    assert "7051498a93a1" in res_curr.stdout

    # 3. Run downgrade base via CLI
    res_down = subprocess.run(
        [alembic_bin, "downgrade", "base"],
        env=env,
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    assert res_down.returncode == 0, f"CLI downgrade failed: {res_down.stderr}\n{res_down.stdout}"


def test_legacy_database_with_simultaneous_backup_keys_and_repeated_cycles(alembic_cfg, tmp_path):
    """
    Scenario 7:
    Verifies that pre-existing suffix-based keys (such as :__orig__) and primary keys
    existing simultaneously in legacy databases are never modified, clobbered, or deleted,
    and that repeated upgrade -> downgrade -> upgrade cycles are 100% deterministic.
    """
    db_file = tmp_path / f"legacy_simultaneous_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE _alembic_migration_metadata (
            key VARCHAR(100) PRIMARY KEY,
            value VARCHAR(100) NOT NULL
        );
    """)

    preexisting_simultaneous = {
        "created_reviews": "primary_value",
        "created_reviews:__orig__": "legacy_backup_value",
        "rev_7051498a93a1:created_reviews": "scoped_primary",
        "rev_7051498a93a1:created_reviews:__orig__": "scoped_backup",
        "unrelated_setting": "preserve_me",
    }

    for k, v in preexisting_simultaneous.items():
        cursor.execute(
            "INSERT INTO _alembic_migration_metadata (key, value) VALUES (?, ?);",
            (k, v),
        )

    cursor.execute("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        "VALUES ('Test', 'Cycle User', 5, 'Great app', 0.8, 'Positive', 'General', 'New');"
    )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Run 3 consecutive upgrade -> downgrade cycles
    for cycle in range(3):
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reviews);")
        cols = {row[1] for row in cursor.fetchall()}
        assert "theme_confidence" in cols

        # Metadata table was never clobbered
        for k, v in preexisting_simultaneous.items():
            cursor.execute("SELECT value FROM _alembic_migration_metadata WHERE key = ?;", (k,))
            assert cursor.fetchone() == (v,), f"Cycle {cycle}: Key {k} was corrupted during upgrade!"
        conn.close()

        command.downgrade(alembic_cfg, "base")

        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reviews);")
        cols_down = {row[1] for row in cursor.fetchall()}
        assert "theme_confidence" not in cols_down

        # Every key perfectly preserved
        for k, v in preexisting_simultaneous.items():
            cursor.execute("SELECT value FROM _alembic_migration_metadata WHERE key = ?;", (k,))
            assert cursor.fetchone() == (v,), f"Cycle {cycle}: Key {k} was corrupted during downgrade!"

        # Reviews data preserved
        cursor.execute("SELECT author FROM reviews;")
        assert cursor.fetchone() == ("Cycle User",)
        conn.close()
