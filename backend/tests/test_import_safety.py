import os
import sqlite3
import subprocess
import sys
import tempfile


def test_import_main_does_not_create_database_tables():
    """
    Verifies that importing main does NOT automatically invoke create_all()
    or modify the database schema at module load time.
    Database creation must be governed strictly by Alembic migrations.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "import_test.db")
        db_url = f"sqlite:///{db_path}"

        test_code = """
import os
import sys

# Ensure clean import of main with target DATABASE_URL
from main import app
print("MAIN_IMPORTED_SUCCESSFULLY")
"""

        env = os.environ.copy()
        env["DATABASE_URL"] = db_url
        env["ENVIRONMENT"] = "development"
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        res = subprocess.run(
            [sys.executable, "-c", test_code],
            env=env,
            cwd=backend_dir,
            capture_output=True,
            text=True,
        )

        assert res.returncode == 0, f"Import script failed: {res.stderr}"
        assert "MAIN_IMPORTED_SUCCESSFULLY" in res.stdout

        # Verify that either the DB file was not created or no tables exist
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = cursor.fetchall()
            conn.close()
            assert len(tables) == 0, f"Tables were unexpectedly created at import time: {tables}"
