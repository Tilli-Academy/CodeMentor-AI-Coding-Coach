"""Liveness check: /health returns a simple ok payload."""


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
