"""
History schemas — the response contract for the learning-history endpoints.

A `HistoryItem` mirrors one row of the `history` table. Nullable columns
(`code`, `question`, `hint_level`) map to optional fields.
"""
from pydantic import BaseModel


class HistoryItem(BaseModel):
    """One stored learning activity."""

    id: int
    activity_type: str
    code: str | None = None
    question: str | None = None
    ai_response: str
    hint_level: int | None = None
    created_at: str
