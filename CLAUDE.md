# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CodeMentor is an AI-powered coding tutor that helps beginner programmers understand
errors, debug code, and improve their programming skills.

## Technology Stack

**Frontend**
- HTML, CSS, JavaScript (vanilla — no framework)
- Monaco Editor (planned, not yet added)

**Backend**
- Python + FastAPI
- Uvicorn (ASGI server)

**Database**
- SQLite (via Python's built-in `sqlite3`)

**AI**
- Local Ollama (`qwen2.5-coder:3b`) over HTTP via `httpx` — runs locally, no API key

## Architecture

- `frontend/` — static browser app (HTML/CSS/JS). Handles UI and talks to the
  backend via HTTP `fetch()` + JSON.
- `backend/` — FastAPI app. Handles REST APIs, business logic, and the Ollama integration.
- `backend/app/` layering:
  - `main.py` — app entry point: creates the FastAPI instance, configures CORS,
    registers routers, exposes `/health`.
  - `routes/` — HTTP endpoints (thin; validate input, delegate to services).
  - `services/` — business logic and external integrations; `llm.py` is the
    only module that calls Ollama (`/api/generate` on `http://127.0.0.1:11434`).
  - `schemas/` — Pydantic request/response models (the JSON contract with the frontend).
  - `database/` — SQLite layer: `database.py` (connection + `connection()`
    transaction context manager + `init_db()`); `history.py` (repository CRUD for
    the `history` table, which stores each successful AI activity). The DB file is
    `backend/codementor.db` (gitignored); `init_db()` runs on startup via lifespan.

Data flow: frontend `fetch()` → FastAPI route → service (`llm.py` → Ollama), then
the route records the successful activity to SQLite (best-effort), with JSON in and
out. The frontend never talks to Ollama or the database directly. AI runs locally,
so there is no API key anywhere.

**Service-error → HTTP-status convention.** The `llm.py` service raises typed
errors that routes translate to HTTP codes (keep this mapping for new AI endpoints):
- `LLMConfigError` → **503** — Ollama is unreachable (server not running) or the
  configured model is not pulled. A setup problem, not the client's fault.
- `LLMError` → **502** — the local model call failed, timed out, or returned
  nothing usable.
- Pydantic validation failures surface as **422** automatically.

**Frontend → backend URL (dev proxy).** The static frontend is served on **:5500**
and the backend on **:8010**, both forwarded through a host proxy. So `app.js` sets
`API_BASE = window.location.origin + "/proxy/8010"` rather than a hardcoded
`localhost` URL — it must stay relative to the page origin to work behind the proxy.

## Commands

**Backend** (from `backend/`, inside a virtual environment):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010   # interactive docs at /docs
```

Run on **port 8010**, not 8000: port 8000 is already taken by another project on
this host, and the frontend's `API_BASE` is wired to 8010 (see below).

**AI (Ollama)** — the backend calls a local Ollama server; start it and pull the
model once before using `/api/ai/*`:

```bash
ollama serve                    # listens on http://127.0.0.1:11434
ollama pull qwen2.5-coder:3b    # the default model (override via OLLAMA_MODEL)
```

Ollama is installed user-space in `~/.local` on this machine (no root); the binary
is `~/.local/bin/ollama`. No API key is involved.

**Frontend** (from `frontend/`): open `index.html` directly, or serve it with a
static server, e.g. `python3 -m http.server 5500`.

No automated test suite is configured. To smoke-test the API without a running
server, drive the app in-process with FastAPI's `TestClient` (e.g.
`TestClient(app).post("/api/ai/hints", json={...})`) — useful for checking
validation (422). AI calls require Ollama running; if it is down, endpoints
return **503**.

## Environment Constraints

- Python 3.12.3 and `venv` are available on this machine.
- PostgreSQL on this host is shared with other projects — but CodeMentor now uses
  **SQLite** (a local file), so that is no longer a concern.
- The project uses Git (`master` branch, no commits yet). An earlier SvelteKit
  prototype was removed; the active frontend is the vanilla HTML/CSS/JS app in
  `frontend/`.

## Development Rules

- Use **Python type hints** in the backend; keep the frontend JavaScript clean and modular.
- Write reusable and maintainable components.
- Separate business logic from UI, and keep routes thin (logic lives in services).
- Keep frontend and backend responsibilities separate.
- Keep AI calls server-side only; the frontend never calls Ollama directly.
- Validate API inputs (use the Pydantic schemas).
- Never execute arbitrary submitted code directly on the server.
- Avoid unnecessary dependencies and overengineering.

## Learning Rules

The project owner is learning this technology stack while building the project. Therefore:

- Explain important technical decisions.
- Explain new files and dependencies.
- Don't generate large amounts of code without explaining them.
- Work on one feature at a time.
- Ask before introducing major architectural changes.
- Help the owner understand the code rather than simply implementing everything,
  including how the frontend communicates with FastAPI over HTTP/JSON.

## Token Efficiency Rules

- Minimize unnecessary token usage.
- Avoid repeating project context or explanations.
- Inspect existing files before modifying them.
- Never rewrite working code unnecessarily.
- Make focused changes rather than large unnecessary refactors.
- Avoid lengthy explanations and repeated summaries.
- Do not generate documentation unless requested.
- Implement features incrementally.
- Run targeted tests instead of repeatedly testing everything.
- Report only changed files, important decisions, test results and blockers.
- Ask questions only when essential information is missing.
- Prioritize a working MVP before optional features.

## Project Status

- ✅ Project structure (vanilla frontend + FastAPI backend) scaffolded.
- ✅ Documentation updated for the FastAPI/Python/SQLite architecture.
- ✅ Git repository initialized (`master` branch; first commit not yet made).
- ✅ Backend dependencies installed (`.venv` present; `httpx` for Ollama calls).
- ✅ Local Ollama integration implemented (`services/llm.py`, model `qwen2.5-coder:3b`).
- ✅ AI endpoints implemented: `POST /api/ai/explain`, `POST /api/ai/hints`
  (one progressive hint per request at level 1–3), `POST /api/ai/learn/question`
  and `POST /api/ai/learn/evaluate` (Learning Mode), plus `/health`.
- ✅ Frontend wired to all AI endpoints: Explain form, Progressive Hints
  ("Get Hint" → "Next Hint", levels 1→2→3), and Learning Mode (ask a question →
  grade the answer → optional follow-up); each resets when its inputs change.
- ✅ SQLite persistence implemented (`database/database.py` + `database/history.py`):
  a `history` table stores each successful AI activity; read/delete via
  `GET /api/history`, `GET /api/history/{id}`, `DELETE /api/history/{id}`.
- ✅ Frontend History UI: lists recent activities (type, timestamp, preview), opens
  full details, deletes individually, with loading/empty/error states; auto-refreshes
  after each new activity.
- ✅ Markdown rendering: AI responses render as formatted HTML via a self-contained
  safe renderer (`renderMarkdown` in `app.js`) — escapes input first, emits only known
  tags, no link/image parsing. `innerHTML` is used ONLY with this renderer's output;
  user code / questions / previews still use `textContent`.
- ✅ UI redesign: single-page app with a sticky top nav (Explain / Hints / Learning
  Mode / History) that toggles tabbed panels via a hash-synced controller (`activateTab`
  in `app.js`) — no reloads. Layout is a persistent shared `#code` workspace (left) plus
  the active feature panel (right); History is full-width. Responsive, consistent
  card/button design system.
- ✅ Monaco editor (vendored at `frontend/vendor/monaco`, v0.52.2 classic AMD build;
  `vs/` is git-ignored — fetch via `frontend/vendor/monaco/README.md`). `js/editor.js`
  mounts it over the `#code` textarea via progressive enhancement: Monaco mirrors its
  value into `#code` (which stays the source `app.js` reads), and the textarea is the
  fallback if Monaco fails to load. `app.js` is unchanged.
- ✅ Accessibility: the top nav implements the full WAI-ARIA tabs pattern — tabs are
  linked to their panels (`aria-controls`/`aria-labelledby`, `role="tabpanel"`), use a
  roving `tabindex`, and support Arrow/Home/End keyboard navigation (`focusTab` in
  `app.js`). Status regions are `role="status" aria-live="polite"` (loading/errors are
  announced), and a "Skip to content" link lets keyboard users bypass the nav.
- ⬜ No automated test suite configured.

See `plan.md` for the phased roadmap.

