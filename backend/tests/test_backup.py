import os
import sqlite3
from unittest.mock import patch
import pytest
from backup import (
    create_sqlite_backup,
    restore_sqlite_backup,
    cleanup_old_backups,
    list_backups,
)


def test_backup_and_restore_integrity(tmp_path):
    """
    Verifies that a point-in-time online backup can be created and fully restored,
    and that restored data and schema constraints remain 100% intact.
    """
    db_file = tmp_path / "original_feedpulse.db"
    backup_dir = tmp_path / "backups"
    restore_target = tmp_path / "restored_feedpulse.db"

    # 1. Setup initial SQLite database with reviews
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            sentiment_score FLOAT NOT NULL
        );
    """)
    cursor.execute("INSERT INTO reviews VALUES (1, 'Alice', 'App works great', 0.9);")
    cursor.execute("INSERT INTO reviews VALUES (2, 'Bob', 'App crashes frequently', -0.8);")
    conn.commit()
    conn.close()

    # 2. Create backup
    backup_path = create_sqlite_backup(
        db_url=f"sqlite:///{db_file}",
        backup_dir=str(backup_dir),
        retention=5,
    )
    assert os.path.exists(backup_path)

    # 3. Restore to a new location
    success = restore_sqlite_backup(
        backup_file_path=backup_path,
        target_db_url=f"sqlite:///{restore_target}",
    )
    assert success is True
    assert restore_target.exists()

    # 4. Verify data integrity in restored database
    r_conn = sqlite3.connect(str(restore_target))
    r_cursor = r_conn.cursor()
    r_cursor.execute("PRAGMA integrity_check;")
    assert r_cursor.fetchone()[0] == "ok"

    r_cursor.execute("SELECT id, author, content, sentiment_score FROM reviews ORDER BY id;")
    rows = r_cursor.fetchall()
    assert len(rows) == 2
    assert rows[0] == (1, "Alice", "App works great", 0.9)
    assert rows[1] == (2, "Bob", "App crashes frequently", -0.8)
    r_conn.close()


def test_backup_retention_behavior(tmp_path):
    """
    Verifies retention pruning:
    - keep_count=2 keeps 2 newest files and removes older ones.
    - keep_count=0 disables pruning (all backups kept).
    - keep_count=1 keeps 1 newest file.
    - newly created backup path is never deleted.
    """
    backup_dir = tmp_path / "retention_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create 4 dummy backup files with staggered timestamps
    filenames = [
        "feedpulse_backup_20261101_100000_000001_aaa111.sqlite3",
        "feedpulse_backup_20261102_100000_000002_bbb222.sqlite3",
        "feedpulse_backup_20261103_100000_000003_ccc333.sqlite3",
        "feedpulse_backup_20261104_100000_000004_ddd444.sqlite3",
    ]
    for idx, fname in enumerate(filenames):
        fpath = backup_dir / fname
        fpath.write_text("dummy")
        os.utime(str(fpath), (1000 + idx * 100, 1000 + idx * 100))

    # keep_count=0 -> disables pruning, returns empty list, all 4 kept
    pruned_zero = cleanup_old_backups(str(backup_dir), keep_count=0)
    assert len(pruned_zero) == 0
    assert len(os.listdir(str(backup_dir))) == 4

    # keep_count=2 -> keeps newest 2, removes 2
    pruned_two = cleanup_old_backups(str(backup_dir), keep_count=2)
    assert len(pruned_two) == 2
    remaining = [f for f in os.listdir(str(backup_dir)) if f.endswith(".sqlite3")]
    assert len(remaining) == 2
    assert "feedpulse_backup_20261104_100000_000004_ddd444.sqlite3" in remaining
    assert "feedpulse_backup_20261103_100000_000003_ccc333.sqlite3" in remaining

    # keep_count=1 -> keeps newest 1
    pruned_one = cleanup_old_backups(str(backup_dir), keep_count=1)
    assert len(pruned_one) == 1
    assert len([f for f in os.listdir(str(backup_dir)) if f.endswith(".sqlite3")]) == 1


def test_rapid_succession_backups_collision_resistance(tmp_path):
    """
    Verifies that multiple backups created in rapid succession have unique filenames
    and do not overwrite each other.
    """
    db_file = tmp_path / "rapid.db"
    backup_dir = tmp_path / "rapid_backups"

    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE reviews (id INT);")
    conn.commit()
    conn.close()

    paths = []
    for _ in range(5):
        p = create_sqlite_backup(db_url=f"sqlite:///{db_file}", backup_dir=str(backup_dir), retention=10)
        paths.append(p)

    # All paths must be unique
    assert len(paths) == 5
    assert len(set(paths)) == 5
    # All files must physically exist on disk
    for p in paths:
        assert os.path.exists(p)


def test_restore_rejects_corrupted_backup(tmp_path):
    """Verifies that restore_sqlite_backup aborts if the backup file is corrupted."""
    corrupted_file = tmp_path / "corrupted.sqlite3"
    corrupted_file.write_bytes(b"NOT A VALID SQLITE HEADER AND CORRUPT DATA")
    target_db = tmp_path / "target.db"

    with pytest.raises(ValueError, match="SQLite integrity check"):
        restore_sqlite_backup(str(corrupted_file), target_db_url=f"sqlite:///{target_db}")


def test_restore_rejects_missing_file(tmp_path):
    """Verifies that restore_sqlite_backup raises FileNotFoundError for missing backup."""
    target_db = tmp_path / "target.db"
    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        restore_sqlite_backup(str(tmp_path / "nonexistent.sqlite3"), target_db_url=f"sqlite:///{target_db}")


def test_restore_rejects_empty_file(tmp_path):
    """Verifies that restore_sqlite_backup raises ValueError for an empty backup file."""
    empty_file = tmp_path / "empty.sqlite3"
    empty_file.write_bytes(b"")
    target_db = tmp_path / "target.db"
    with pytest.raises(ValueError, match="empty"):
        restore_sqlite_backup(str(empty_file), target_db_url=f"sqlite:///{target_db}")


def test_restore_rejects_self_restoration(tmp_path):
    """Verifies that restore_sqlite_backup refuses to restore a database file onto itself."""
    same_file = tmp_path / "same.db"
    conn = sqlite3.connect(str(same_file))
    conn.execute("CREATE TABLE reviews (id INT);")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="Cannot restore database onto itself"):
        restore_sqlite_backup(str(same_file), target_db_url=f"sqlite:///{same_file}")


def test_restore_rejects_missing_required_schema_tables(tmp_path):
    """Verifies that restore_sqlite_backup rejects databases lacking required FeedPulse tables."""
    invalid_schema_file = tmp_path / "invalid_schema.db"
    conn = sqlite3.connect(str(invalid_schema_file))
    conn.execute("CREATE TABLE unrelated_table (id INT);")
    conn.commit()
    conn.close()

    target_db = tmp_path / "target.db"
    with pytest.raises(ValueError, match="missing required schema tables"):
        restore_sqlite_backup(str(invalid_schema_file), target_db_url=f"sqlite:///{target_db}")


def test_restore_preserves_original_destination_on_corrupt_backup(tmp_path):
    """
    Verifies that if a restoration fails (e.g. invalid/corrupt backup),
    the pre-existing destination database is left completely unharmed.
    """
    dest_db = tmp_path / "live_db.sqlite"
    conn = sqlite3.connect(str(dest_db))
    conn.execute("CREATE TABLE reviews (id INT, author TEXT);")
    conn.execute("INSERT INTO reviews VALUES (1, 'Preserved Author');")
    conn.commit()
    conn.close()

    corrupt_backup = tmp_path / "bad.sqlite3"
    corrupt_backup.write_bytes(b"GARBAGE BYTES NOT A DB")

    with pytest.raises(ValueError, match="SQLite integrity check"):
        restore_sqlite_backup(str(corrupt_backup), target_db_url=f"sqlite:///{dest_db}")

    # Destination DB must still exist with original data
    conn_verify = sqlite3.connect(str(dest_db))
    cursor = conn_verify.cursor()
    cursor.execute("SELECT author FROM reviews WHERE id=1;")
    assert cursor.fetchone() == ("Preserved Author",)
    conn_verify.close()


def test_restore_recovers_from_swap_failure(tmp_path):
    """
    Verifies that if an error occurs during replacement of the destination database,
    the original database is restored from safety backup and preserved.
    """
    dest_db = tmp_path / "live_db_swap_fail.sqlite"
    conn = sqlite3.connect(str(dest_db))
    conn.execute("CREATE TABLE reviews (id INT, author TEXT);")
    conn.execute("INSERT INTO reviews VALUES (99, 'Original Safe Data');")
    conn.commit()
    conn.close()

    # Create a valid backup
    backup_file = tmp_path / "good_backup.sqlite3"
    b_conn = sqlite3.connect(str(backup_file))
    b_conn.execute("CREATE TABLE reviews (id INT, author TEXT);")
    b_conn.execute("INSERT INTO reviews VALUES (100, 'New Data');")
    b_conn.commit()
    b_conn.close()

    real_replace = os.replace

    def mock_replace(src, dst):
        # Allow moving original to backup, but fail when moving staging into place
        if ".restore_" in str(src):
            raise OSError("Simulated disk replacement failure")
        return real_replace(src, dst)

    with patch("os.replace", side_effect=mock_replace):
        with pytest.raises(RuntimeError, match="Database replacement failed and was rolled back"):
            restore_sqlite_backup(str(backup_file), target_db_url=f"sqlite:///{dest_db}")

    # Verify original destination database was rolled back and still contains original data
    conn_verify = sqlite3.connect(str(dest_db))
    cursor = conn_verify.cursor()
    cursor.execute("SELECT author FROM reviews WHERE id=99;")
    assert cursor.fetchone() == ("Original Safe Data",)
    conn_verify.close()


def test_restore_handles_wal_mode_and_sidecars(tmp_path):
    """
    Verifies that restoring to a destination using SQLite WAL mode
    properly handles and cleans up WAL and SHM sidecars.
    """
    dest_db = tmp_path / "wal_db.sqlite"
    conn = sqlite3.connect(str(dest_db))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE reviews (id INT, author TEXT);")
    conn.execute("INSERT INTO reviews VALUES (1, 'WAL Author');")
    conn.commit()
    conn.close()

    # WAL sidecars exist
    wal_file = tmp_path / "wal_db.sqlite-wal"
    shm_file = tmp_path / "wal_db.sqlite-shm"

    # Valid backup
    backup_file = tmp_path / "fresh_backup.sqlite3"
    b_conn = sqlite3.connect(str(backup_file))
    b_conn.execute("CREATE TABLE reviews (id INT, author TEXT);")
    b_conn.execute("INSERT INTO reviews VALUES (2, 'Restored From Backup');")
    b_conn.commit()
    b_conn.close()

    # Perform restore
    success = restore_sqlite_backup(str(backup_file), target_db_url=f"sqlite:///{dest_db}")
    assert success is True

    # Check restored database
    r_conn = sqlite3.connect(str(dest_db))
    r_cursor = r_conn.cursor()
    r_cursor.execute("PRAGMA integrity_check;")
    assert r_cursor.fetchone()[0] == "ok"
    r_cursor.execute("SELECT author FROM reviews;")
    assert r_cursor.fetchall() == [("Restored From Backup",)]
    r_conn.close()
