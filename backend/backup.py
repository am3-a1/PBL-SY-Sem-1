import os
import sys
import uuid
import sqlite3
import logging
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any
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
    
    Collision-resistant: uses microsecond timestamp and unique suffix.
    Atomic: writes to temporary file and atomically moves upon verified integrity.
    Retention: keep_count=0 disables pruning; positive N retains newest N backups.
    The newly created backup is never pruned during its own creation operation.
    """
    url = db_url or settings.DATABASE_URL
    target_dir = backup_dir or settings.BACKUP_DIR

    # Explicit check for None; 0 disables pruning, positive retains N
    if retention is not None:
        try:
            retention_count = int(retention)
            if retention_count < 0:
                logger.warning(f"Negative retention '{retention}' provided; defaulting to 0 (no pruning).")
                retention_count = 0
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid retention value '{retention}'; defaulting to settings.BACKUP_RETENTION_COUNT ({settings.BACKUP_RETENTION_COUNT})."
            )
            retention_count = settings.BACKUP_RETENTION_COUNT
    else:
        retention_count = settings.BACKUP_RETENTION_COUNT

    if not url.startswith("sqlite:///"):
        raise ValueError(f"Online backup is currently implemented for SQLite databases. URL: {url}")

    # Extract file path from sqlite:///./path
    db_path = url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_path))

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Source database file not found at {db_path}")

    os.makedirs(target_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    unique_suffix = uuid.uuid4().hex[:6]
    backup_filename = f"feedpulse_backup_{timestamp}_{unique_suffix}.sqlite3"
    tmp_path = os.path.join(target_dir, f"{backup_filename}.tmp")
    backup_path = os.path.join(target_dir, backup_filename)

    logger.info(f"Starting online SQLite backup from {db_path} to {backup_path}...")

    # Write to temporary file first using SQLite's online backup API
    source_conn = sqlite3.connect(db_path)
    dest_conn = sqlite3.connect(tmp_path)
    try:
        source_conn.backup(dest_conn, pages=250, sleep=0.01)
        # Verify backup integrity before moving into place
        dest_cursor = dest_conn.cursor()
        dest_cursor.execute("PRAGMA integrity_check;")
        check_res = dest_cursor.fetchone()
        if not check_res or check_res[0] != "ok":
            raise RuntimeError(f"Backup failed SQLite integrity check: {check_res}")
    except Exception:
        # Clean up incomplete temporary file on failure
        dest_conn.close()
        source_conn.close()
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    finally:
        dest_conn.close()
        source_conn.close()

    # Atomically move verified backup into place
    os.replace(tmp_path, backup_path)
    logger.info(f"Backup created and verified successfully: {backup_path}")

    # Retention policy: keep the newest N backups (0 = disable pruning)
    cleanup_old_backups(target_dir, retention_count, exclude_path=backup_path)

    return backup_path


def restore_sqlite_backup(
    backup_file_path: str,
    target_db_url: Optional[str] = None,
) -> bool:
    """
    Restores SQLite database from a specified backup file as an offline maintenance operation.
    Validates backup integrity before and after restoration.
    """
    if not os.path.exists(backup_file_path):
        raise FileNotFoundError(f"Backup file not found at {backup_file_path}")

    # Validate backup file integrity first
    try:
        backup_conn = sqlite3.connect(backup_file_path)
        try:
            cursor = backup_conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            check_result = cursor.fetchone()
            if not check_result or check_result[0] != "ok":
                raise ValueError(f"Backup file failed SQLite integrity check: {check_result}")
        finally:
            backup_conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as err:
        raise ValueError(f"Backup file failed SQLite integrity check: {err}")

    url = target_db_url or settings.DATABASE_URL
    if not url.startswith("sqlite:///"):
        raise ValueError(f"Restore is only supported for SQLite databases. URL: {url}")

    db_path = url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_path))

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Perform restoration to the target database
    source_conn = sqlite3.connect(backup_file_path)
    dest_conn = sqlite3.connect(db_path)
    try:
        source_conn.backup(dest_conn, pages=250, sleep=0.01)
        # Verify restored database integrity
        dest_cursor = dest_conn.cursor()
        dest_cursor.execute("PRAGMA integrity_check;")
        res = dest_cursor.fetchone()
        if not res or res[0] != "ok":
            raise RuntimeError(f"Restored database failed integrity check: {res}")
        logger.info(f"Database successfully restored from {backup_file_path} to {db_path}")
        return True
    finally:
        dest_conn.close()
        source_conn.close()


def cleanup_old_backups(
    backup_dir: str,
    keep_count: int,
    exclude_path: Optional[str] = None,
) -> List[str]:
    """
    Cleans up old backups exceeding the retention count.
    - If keep_count <= 0: pruning is disabled; retains all backups.
    - If keep_count > 0: retains the newest keep_count backups.
    - The file at exclude_path is never deleted.
    """
    if keep_count <= 0 or not os.path.exists(backup_dir):
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
            if exclude_path and os.path.abspath(old_file) == os.path.abspath(exclude_path):
                continue
            try:
                os.remove(old_file)
                pruned.append(old_file)
                logger.info(f"Pruned old backup per retention policy: {old_file}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {old_file}: {e}")

    return pruned


def list_backups(backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists available backup files with size and creation timestamp."""
    target_dir = backup_dir or settings.BACKUP_DIR
    if not os.path.exists(target_dir):
        return []

    files = [
        f for f in os.listdir(target_dir)
        if f.startswith("feedpulse_backup_") and f.endswith(".sqlite3")
    ]
    results = []
    for f in sorted(files, reverse=True):
        full_path = os.path.join(target_dir, f)
        results.append({
            "filename": f,
            "path": full_path,
            "size_bytes": os.path.getsize(full_path),
            "modified_at": datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
        })
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FeedPulse SQLite Backup & Restore Utility")
    parser.add_argument("--restore", type=str, help="Path to backup file to restore")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--retention", type=int, default=None, help="Backup retention count (0 to keep all)")
    args = parser.parse_args()

    if args.list:
        backups = list_backups()
        if not backups:
            print("No backup files found.")
        else:
            print(f"Found {len(backups)} backup(s):")
            for b in backups:
                print(f"  - {b['filename']} ({b['size_bytes']} bytes, {b['modified_at']})")
    elif args.restore:
        try:
            restore_sqlite_backup(args.restore)
            print(f"Success: Database restored from {args.restore}")
        except Exception as exc:
            print(f"Error: Restore failed: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            path = create_sqlite_backup(retention=args.retention)
            print(f"Success: Backup created at {path}")
        except Exception as exc:
            print(f"Error: Backup failed: {exc}", file=sys.stderr)
            sys.exit(1)
