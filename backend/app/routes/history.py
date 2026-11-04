"""
History routes — read and delete stored learning activities.

Responsibility:
- Expose the learning-history REST endpoints the frontend will later call.
- Delegate all persistence to app.database.history (routes stay thin).

Writes happen automatically from the AI routes; this router is read/delete only.
"""
from fastapi import APIRouter, HTTPException, Query

from app.database import history as history_repo
from app.schemas.history import HistoryItem

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[HistoryItem])
def list_history(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """Return the most recent learning activities (newest first)."""
    try:
        return history_repo.list_activities(limit)
    except Exception as exc:  # pragma: no cover - defensive DB guard
        raise HTTPException(status_code=500, detail=f"Failed to read history: {exc}")


@router.get("/{activity_id}", response_model=HistoryItem)
def get_history(activity_id: int) -> dict:
    """Return a single learning activity by id (404 if it does not exist)."""
    try:
        item = history_repo.get_activity(activity_id)
    except Exception as exc:  # pragma: no cover - defensive DB guard
        raise HTTPException(status_code=500, detail=f"Failed to read history: {exc}")
    if item is None:
        raise HTTPException(status_code=404, detail="History activity not found")
    return item


@router.delete("/{activity_id}", status_code=204)
def delete_history(activity_id: int) -> None:
    """Delete a learning activity by id (404 if it does not exist)."""
    try:
        deleted = history_repo.delete_activity(activity_id)
    except Exception as exc:  # pragma: no cover - defensive DB guard
        raise HTTPException(status_code=500, detail=f"Failed to delete history: {exc}")
    if not deleted:
        raise HTTPException(status_code=404, detail="History activity not found")
