"""
History repository — CRUD for learning activity records.

All SQL for the `history` table lives here so routes stay thin and never build
queries themselves. Each row records one successful AI interaction (explain,
hints, a learning question, or an answer evaluation).
"""
from datetime import datetime, timezone

from app.database.database import connection

# Activity types stored in the `activity_type` column (one per AI feature).
VALID_ACTIVITY_TYPES = {"explain", "hints", "learn_question", "learn_evaluate"}


def save_activity(
    activity_type: str,
    ai_response: str,
    code: str | None = None,
    question: str | None = None,
    hint_level: int | None = None,
) -> int:
    """Insert one activity row and return its new id."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO history "
            "(activity_type, code, question, ai_response, hint_level, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (activity_type, code, question, ai_response, hint_level, created_at),
        )
        return int(cur.lastrowid)


def list_activities(limit: int = 20) -> list[dict]:
    """Return the most recent activities (newest first), capped at `limit`."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_activity(activity_id: int) -> dict | None:
    """Return a single activity by id, or None if it does not exist."""
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM history WHERE id = ?", (activity_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_activity(activity_id: int) -> bool:
    """Delete an activity by id. Returns True if a row was removed."""
    with connection() as conn:
        cur = conn.execute("DELETE FROM history WHERE id = ?", (activity_id,))
        return cur.rowcount > 0
