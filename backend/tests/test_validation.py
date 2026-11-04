"""
Input validation (HTTP 422).

These exercise the Pydantic schemas in app/schemas. Validation happens before
the route body runs, so the AI layer is never reached — no Ollama needed, and
nothing is written to history.
"""
import pytest

VALID_CODE = "print('hi')"


# ----------------------------- /api/ai/explain -----------------------------


def test_explain_requires_code(client):
    # `code` is required.
    resp = client.post("/api/ai/explain", json={})
    assert resp.status_code == 422


def test_explain_rejects_blank_code(client):
    # Whitespace-only code is treated as empty by the custom validator.
    resp = client.post("/api/ai/explain", json={"code": "   "})
    assert resp.status_code == 422


def test_explain_rejects_oversized_code(client):
    resp = client.post("/api/ai/explain", json={"code": "x" * 20001})
    assert resp.status_code == 422


# ------------------------------ /api/ai/hints ------------------------------


@pytest.mark.parametrize("level", [0, 4, -1])
def test_hints_rejects_out_of_range_level(client, level):
    resp = client.post(
        "/api/ai/hints",
        json={"code": VALID_CODE, "question": "why?", "level": level},
    )
    assert resp.status_code == 422


def test_hints_requires_question(client):
    resp = client.post("/api/ai/hints", json={"code": VALID_CODE, "level": 1})
    assert resp.status_code == 422


# ------------------------- /api/ai/learn/question --------------------------


def test_learn_question_requires_code_or_topic(client):
    # Neither code nor topic -> model validator rejects it.
    resp = client.post("/api/ai/learn/question", json={})
    assert resp.status_code == 422


def test_learn_question_blank_fields_are_rejected(client):
    # Blank strings collapse to None, leaving nothing provided.
    resp = client.post(
        "/api/ai/learn/question", json={"code": "  ", "topic": ""}
    )
    assert resp.status_code == 422


# ------------------------- /api/ai/learn/evaluate --------------------------


def test_learn_evaluate_requires_answer(client):
    resp = client.post(
        "/api/ai/learn/evaluate", json={"question": "What is a loop?"}
    )
    assert resp.status_code == 422


# ------------------------------ /api/history -------------------------------


@pytest.mark.parametrize("limit", [0, 101])
def test_history_limit_out_of_range(client, limit):
    resp = client.get("/api/history", params={"limit": limit})
    assert resp.status_code == 422
