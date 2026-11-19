import os
import sys
import uuid
import sqlite3
import logging
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from config import settings

logger = logging.getLogger("feedpulse.backup")
logging.basicConfig(level=logging.INFO)

# Default core tables expected in a valid FeedPulse database
DEFAULT_REQUIRED_TABLES: Set[str] = {"reviews"}


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


def validate_sqlite_database(file_path: str, required_tables: Optional[Set[str]] = None) -> None:
    """
    Validates a SQLite database file:
    1. Runs PRAGMA integrity_check and PRAGMA quick_check.
    2. Verifies presence of expected schema tables.
    Raises ValueError or RuntimeError on any failure.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Database file not found: {file_path}")

    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a regular file: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise ValueError(f"Database file is empty: {file_path}")

    try:
        conn = sqlite3.connect(file_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            check_result = cursor.fetchone()
            if not check_result or check_result[0] != "ok":
                raise ValueError(f"Database failed SQLite integrity check: {check_result}")

            cursor.execute("PRAGMA quick_check;")
            quick_result = cursor.fetchone()
            if not quick_result or quick_result[0] != "ok":
                raise ValueError(f"Database failed SQLite quick check: {quick_result}")

            if required_tables:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                existing_tables = {row[0] for row in cursor.fetchall()}
                missing = required_tables - existing_tables
                if missing:
                    raise ValueError(f"Database is missing required schema tables: {sorted(missing)}")
        finally:
            conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as err:
        raise ValueError(f"Backup file failed SQLite integrity check: {err}")


def restore_sqlite_backup(
    backup_file_path: str,
    target_db_url: Optional[str] = None,
    required_tables: Optional[Set[str]] = None,
) -> bool:
    """
    Restores SQLite database from a specified backup file using an atomic,
    failure-resistant, temporary-staging process.

    Safety Guarantees:
    1. Validates backup file integrity and schema before touching any destination.
    2. Prevents restoring a database file onto itself.
    3. Restores into a temporary staging file first (never touches live DB directly).
    4. Validates the restored staging file with PRAGMA integrity_check and schema verification.
    5. Disposes active application database connections prior to replacement.
    6. Creates a rollback safety backup of the original database and WAL sidecars.
    7. Atomically replaces destination; automatically rolls back if replacement fails.
    8. Preserves the original database if restoration fails at any stage.
    """
    if not os.path.exists(backup_file_path):
        raise FileNotFoundError(f"Backup file not found at {backup_file_path}")

    if not os.path.isfile(backup_file_path):
        raise ValueError(f"Backup path is not a regular file: {backup_file_path}")

    tables_to_check = required_tables if required_tables is not None else DEFAULT_REQUIRED_TABLES

    # 1. Pre-validate backup file integrity and required schema
    validate_sqlite_database(backup_file_path, required_tables=tables_to_check)

    # 2. Resolve destination database path
    url = target_db_url or settings.DATABASE_URL
    if not url.startswith("sqlite:///"):
        raise ValueError(f"Restore is only supported for SQLite databases. URL: {url}")

    db_path = url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_path))

    # 3. Prevent self-restoration
    if os.path.exists(db_path):
        try:
            if os.path.samefile(backup_file_path, db_path):
                raise ValueError(
                    f"Cannot restore database onto itself: source backup and target database are the same file ({db_path})"
                )
        except OSError as oe:
            if "samefile" in str(oe).lower():
                raise

    target_dir = os.path.dirname(db_path)
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as err:
        raise OSError(f"Failed to create target directory '{target_dir}': {err}")

    # 4. Stage restoration into an isolated temporary database file
    restore_uuid = uuid.uuid4().hex[:8]
    tmp_staging_path = os.path.join(target_dir, f".restore_{restore_uuid}.tmp")
    orig_safety_backup = os.path.join(target_dir, f".pre_restore_{restore_uuid}.bak")

    try:
        source_conn = sqlite3.connect(backup_file_path)
        stage_conn = sqlite3.connect(tmp_staging_path)
        try:
            source_conn.backup(stage_conn, pages=250, sleep=0.01)
        finally:
            stage_conn.close()
            source_conn.close()

        # 5. Verify the staged temporary database integrity and schema
        validate_sqlite_database(tmp_staging_path, required_tables=tables_to_check)

        # 6. Dispose existing database connection pool to release file locks
        try:
            import database
            if hasattr(database, "engine") and database.engine is not None:
                database.engine.dispose()
        except Exception as e:
            logger.debug(f"Database engine dispose: {e}")

        # 7. Safe replacement with atomic rollback capability
        dest_existed = os.path.exists(db_path)
        wal_existed = os.path.exists(f"{db_path}-wal")
        shm_existed = os.path.exists(f"{db_path}-shm")

        if dest_existed:
            # Stash original database and sidecars
            os.replace(db_path, orig_safety_backup)
            if wal_existed:
                try:
                    os.replace(f"{db_path}-wal", f"{orig_safety_backup}-wal")
                except OSError:
                    pass
            if shm_existed:
                try:
                    os.replace(f"{db_path}-shm", f"{orig_safety_backup}-shm")
                except OSError:
                    pass

        try:
            # Atomically move verified staging database to target path
            os.replace(tmp_staging_path, db_path)
            # Remove staging sidecars if any
            for sidecar in [f"{tmp_staging_path}-wal", f"{tmp_staging_path}-shm"]:
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except OSError:
                        pass
        except Exception as swap_err:
            # Rollback: restore the original database if destination replacement failed
            logger.error(f"Failed to replace target database with staging file: {swap_err}. Rolling back...")
            if dest_existed and os.path.exists(orig_safety_backup):
                os.replace(orig_safety_backup, db_path)
                if wal_existed and os.path.exists(f"{orig_safety_backup}-wal"):
                    os.replace(f"{orig_safety_backup}-wal", f"{db_path}-wal")
                if shm_existed and os.path.exists(f"{orig_safety_backup}-shm"):
                    os.replace(f"{orig_safety_backup}-shm", f"{db_path}-shm")
            raise RuntimeError(f"Database replacement failed and was rolled back: {swap_err}")

        # Replacement succeeded; clean up safety backup
        if dest_existed and os.path.exists(orig_safety_backup):
            try:
                os.remove(orig_safety_backup)
            except OSError:
                pass
            for sidecar in [f"{orig_safety_backup}-wal", f"{orig_safety_backup}-shm"]:
                if os.path.exists(sidecar):
                    try:
                        os.remove(sidecar)
                    except OSError:
                        pass

        logger.info(f"Database successfully restored and verified from {backup_file_path} to {db_path}")
        return True

    finally:
        # Cleanup any leftover temporary staging files
        for leftover in [tmp_staging_path, f"{tmp_staging_path}-wal", f"{tmp_staging_path}-shm"]:
            if os.path.exists(leftover):
                try:
                    os.remove(leftover)
                except OSError:
                    pass


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
