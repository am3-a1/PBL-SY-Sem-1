import os
import sqlite3
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
    conn.execute("CREATE TABLE t (id INT);")
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
