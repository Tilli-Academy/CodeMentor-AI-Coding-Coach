"""
Database layer — SQLite connection and schema setup.

Responsibility:
- Provide a single place to open SQLite connections and manage transactions.
- Create the schema (the `history` table) on startup.

Uses Python's built-in `sqlite3` module (no extra dependency) to stay minimal.
If the data model grows, we can introduce an ORM such as SQLAlchemy — but that
is a deliberate architectural decision to discuss first.

Concurrency note: a fresh connection is opened per operation. FastAPI runs the
sync route handlers in a threadpool, and a SQLite connection must not be shared
across threads; opening/closing per operation keeps each call self-contained.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# The SQLite file lives next to the backend (backend/codementor.db). This module
# is at app/database/, so parents[2] is the backend/ directory.
DB_PATH = Path(__file__).resolve().parents[2] / "codementor.db"


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection whose rows are accessible by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection, committing on success and always closing.

    Rolls back and re-raises on error so a failed write never leaves a partial
    transaction behind.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the history table if it does not exist (idempotent, safe to re-run)."""
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT    NOT NULL,
                code          TEXT,
                question      TEXT,
                ai_response   TEXT    NOT NULL,
                hint_level    INTEGER,
                created_at    TEXT    NOT NULL
            )
            """
        )
