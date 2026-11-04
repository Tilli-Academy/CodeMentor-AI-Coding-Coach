"""
Shared pytest fixtures.

This file lives at the backend/ root so pytest adds backend/ to sys.path,
making `import app...` work from the test modules in tests/.

The `client` fixture is the backbone of the suite: it isolates every test from
the real SQLite database (`codementor.db`) by redirecting DB_PATH to a throwaway
file, then starts the app so FastAPI's lifespan creates a fresh `history` table.
No test touches real data, and (because the AI layer is monkeypatched in the
route tests) no test calls the real Ollama server.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient backed by a temporary, per-test SQLite database."""
    # Redirect the DB file BEFORE the app starts so init_db() (run in the app's
    # lifespan) creates the schema in the temp file, not backend/codementor.db.
    from app.database import database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    from app.main import app

    # The `with` block triggers startup/shutdown, so lifespan -> init_db() runs
    # against the patched DB_PATH.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the shared rate limiter around every test so counts never leak."""
    from app.services.rate_limit import rate_limiter

    rate_limiter.reset()
    yield
    rate_limiter.reset()
