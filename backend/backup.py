import os
import sys
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List
from config import settings

logger = logging.getLogger("feedpulse.backup")
logging.basicConfig(level=logging.INFO)


def create_sqlite_backup(
    db_url: Optional[str] = None,
    backup_dir: Optional[str] = None,
    retention: Optional[int] = None,
) -> str:
    """
    Creates an online, safe point-in-time backup of SQLite database using
    sqlite3's built-in backup API. Does not corrupt open transactions.
    """
    url = db_url or settings.DATABASE_URL
    target_dir = backup_dir or settings.BACKUP_DIR
    retention_count = retention or settings.BACKUP_RETENTION_COUNT

    if not url.startswith("sqlite:///"):
        raise ValueError(f"Online backup is currently implemented for SQLite databases. URL: {url}")

    # Extract file path from sqlite:///./path
    db_path = url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_path))

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Source database file not found at {db_path}")

    os.makedirs(target_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"feedpulse_backup_{timestamp}.sqlite3"
    backup_path = os.path.join(target_dir, backup_filename)

    logger.info(f"Starting online SQLite backup from {db_path} to {backup_path}...")

    # Use SQLite's online backup API
    source_conn = sqlite3.connect(db_path)
    dest_conn = sqlite3.connect(backup_path)
    try:
        source_conn.backup(dest_conn, pages=250, sleep=0.01)
        logger.info(f"Backup created successfully: {backup_path}")
    finally:
        dest_conn.close()
        source_conn.close()

    # Retention policy: keep the newest N backups
    cleanup_old_backups(target_dir, retention_count)

    return backup_path


def cleanup_old_backups(backup_dir: str, keep_count: int) -> List[str]:
    """
    Cleans up old backups exceeding the retention count.
    """
    if not os.path.exists(backup_dir):
        return []

    files = [
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.startswith("feedpulse_backup_") and f.endswith(".sqlite3")
    ]
    files.sort(key=os.path.getmtime, reverse=True)

    pruned = []
    if len(files) > keep_count:
        for old_file in files[keep_count:]:
            try:
                os.remove(old_file)
                pruned.append(old_file)
                logger.info(f"Pruned old backup per retention policy: {old_file}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {old_file}: {e}")

    return pruned


if __name__ == "__main__":
    try:
        path = create_sqlite_backup()
        print(f"Success: Backup created at {path}")
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        sys.exit(1)
