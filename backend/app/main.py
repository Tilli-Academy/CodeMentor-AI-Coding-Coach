"""
CodeMentor backend — FastAPI application entry point.

Responsibility:
- Create the FastAPI application instance.
- Configure CORS so the browser frontend (a separate static site) may call this API.
- Register routers (e.g. the AI routes).
- Expose a /health endpoint for quick liveness checks.

Run (after installing requirements, from the backend/ directory):
    uvicorn app.main:app --reload --port 8000

Interactive API docs are then available at http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import init_db
from app.routes import ai, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the SQLite history table (if missing) before serving requests.
    init_db()
    yield


app = FastAPI(title="CodeMentor API", version="0.1.0", lifespan=lifespan)

# The frontend runs on a different origin (static files / a separate dev server),
# so the browser requires CORS permission to call this API.
# TODO: restrict allow_origins to the real frontend origin before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire up the feature routers.
app.include_router(ai.router)
app.include_router(history.router)


@app.get("/health")
def health():
    """Liveness check — returns JSON the frontend or tooling can poll."""
    return {"status": "ok"}
