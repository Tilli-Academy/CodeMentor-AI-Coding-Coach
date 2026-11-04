"""
Rate limiting on the AI endpoints (HTTP 429).

The limiter is a shared singleton; the autouse `_reset_rate_limiter` fixture in
conftest.py clears it around every test. Here we also shrink the per-window
limit via monkeypatch so the threshold is reached in a few deterministic calls
(monkeypatch restores the real value afterwards). The AI service is patched so
allowed requests succeed without touching Ollama.
"""
from app.services import llm
from app.services.rate_limit import rate_limiter


def test_exceeding_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(rate_limiter, "max_requests", 2)
    monkeypatch.setattr(llm, "generate_explanation", lambda *a, **k: "ok")

    body = {"code": "print(1)"}

    # The first two requests are within the limit.
    assert client.post("/api/ai/explain", json=body).status_code == 200
    assert client.post("/api/ai/explain", json=body).status_code == 200

    # The third trips the limiter.
    resp = client.post("/api/ai/explain", json=body)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_limit_is_shared_across_ai_endpoints(client, monkeypatch):
    # The limiter is router-wide, so mixed AI calls count against one budget.
    monkeypatch.setattr(rate_limiter, "max_requests", 1)
    monkeypatch.setattr(llm, "generate_explanation", lambda *a, **k: "ok")
    monkeypatch.setattr(llm, "generate_hint", lambda *a, **k: "ok")

    assert client.post("/api/ai/explain", json={"code": "print(1)"}).status_code == 200
    resp = client.post(
        "/api/ai/hints",
        json={"code": "print(1)", "question": "why?", "level": 1},
    )
    assert resp.status_code == 429


def test_limit_does_not_apply_to_health_or_history(client, monkeypatch):
    # Non-AI endpoints are unaffected even when the AI budget is exhausted.
    monkeypatch.setattr(rate_limiter, "max_requests", 1)
    monkeypatch.setattr(llm, "generate_explanation", lambda *a, **k: "ok")

    client.post("/api/ai/explain", json={"code": "print(1)"})  # uses the single slot
    assert client.post("/api/ai/explain", json={"code": "print(1)"}).status_code == 429

    # /health and /api/history still respond normally.
    assert client.get("/health").status_code == 200
    assert client.get("/api/history").status_code == 200
