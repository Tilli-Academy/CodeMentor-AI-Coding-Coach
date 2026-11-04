"""
History persistence and the read/delete endpoints.

These run against the per-test temporary SQLite database from the `client`
fixture, so they exercise real SQL without touching codementor.db. Rows are
seeded directly through the repository (the same path the AI routes use on
success) to keep the tests independent of the AI layer.
"""
from app.database import history as history_repo


def _seed(activity_type="explain", ai_response="an explanation", **kw):
    """Insert one activity row and return its id."""
    return history_repo.save_activity(activity_type, ai_response, **kw)


def test_list_empty_initially(client):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_newest_first(client):
    first = _seed(ai_response="first")
    second = _seed(ai_response="second")

    resp = client.get("/api/history")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert ids == [second, first]  # newest (highest id) first


def test_list_respects_limit(client):
    for _ in range(3):
        _seed()
    resp = client.get("/api/history", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_by_id_roundtrip(client):
    row_id = _seed(
        activity_type="hints",
        ai_response="a hint",
        code="print(1)",
        question="help",
        hint_level=2,
    )
    resp = client.get(f"/api/history/{row_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == row_id
    assert body["activity_type"] == "hints"
    assert body["ai_response"] == "a hint"
    assert body["hint_level"] == 2


def test_get_missing_returns_404(client):
    resp = client.get("/api/history/999999")
    assert resp.status_code == 404


def test_delete_then_gone(client):
    row_id = _seed()

    resp = client.delete(f"/api/history/{row_id}")
    assert resp.status_code == 204

    # A second delete finds nothing -> 404.
    assert client.delete(f"/api/history/{row_id}").status_code == 404
    # And it is no longer fetchable.
    assert client.get(f"/api/history/{row_id}").status_code == 404


def test_delete_missing_returns_404(client):
    resp = client.delete("/api/history/999999")
    assert resp.status_code == 404
