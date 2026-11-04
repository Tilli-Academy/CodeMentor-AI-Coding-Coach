
# CodeMentor — Project Plan

Phased roadmap for CodeMentor, an AI-powered coding tutor for beginners.
Status legend: ✅ done · 🔄 in progress · ⬜ not started.

Keep this file in sync with the **Project Status** section of `CLAUDE.md`.

---

## Phase 0 — Foundation ✅

Project scaffolding and tooling.

- ✅ Repo structure: `frontend/` (vanilla HTML/CSS/JS) + `backend/` (FastAPI).
- ✅ Git initialized (`master` branch).
- ✅ Backend virtualenv (`.venv`) and dependencies installed.
- ✅ CLAUDE.md / README.md documenting architecture and commands.

## Phase 1 — Backend core ✅

Thin, well-layered FastAPI app.

- ✅ FastAPI app (`main.py`) with CORS and `/health`.
- ✅ Layering: `routes/` (thin) → `services/` (logic) → `schemas/` (Pydantic).
- ✅ Service-error → HTTP convention: `LLMConfigError`→503, `LLMError`→502,
  validation→422.

## Phase 2 — Local AI integration ✅

Replaced the earlier cloud (Gemini) path with a fully local model.

- ✅ `services/llm.py` is the only module that talks to Ollama
  (`/api/generate`, `http://127.0.0.1:11434`, model `qwen2.5-coder:3b`).
- ✅ Timeout + connection/model-missing error handling.
- ✅ No API keys anywhere (runs locally).

## Phase 3 — AI features (Explain + Hints) ✅

- ✅ `POST /api/ai/explain` — beginner-friendly explanation; switches to a focused
  debugging diagnosis when an error message is supplied.
- ✅ Tutor system prompt: persona + teaching guidelines + structured Markdown output.
- ✅ `POST /api/ai/hints` — one progressive hint per request at level 1–3
  (gentle → approach → strong), never the full solution.
- ✅ Frontend wired to both: Explain form, plus "Get Hint" → "Next Hint" flow
  (one request at a time, button disabled while loading, resets on code/question change).

## Phase 3.5 — Learning Mode ✅

Interactive quizzing: ask the learner a question, then grade their answer.

- ✅ `POST /api/ai/learn/question` — generates ONE beginner question from the
  learner's code and/or a chosen topic (concept, behaviour, output prediction, logic).
- ✅ `POST /api/ai/learn/evaluate` — grades the answer and returns structured JSON
  `{ verdict, feedback, follow_up }` via Ollama's `format` constraint
  (verdict ∈ correct / partially_correct / incorrect), with an optional follow-up question.
- ✅ Schemas (`LearnQuestionRequest/Response`, `LearnEvaluateRequest/Response`);
  code-or-topic requirement enforced; same 503/502/422 error mapping as Explain/Hints.
- ✅ Frontend UI wired: "Get a Question" → answer → "Submit Answer" → color-coded
  verdict + feedback; "Answer this follow-up" / "New Question"; resets on code/topic change.

## Phase 4 — Persistence (SQLite) ✅

Learning activities are saved to a local SQLite file (`backend/codementor.db`)
using the stdlib `sqlite3` module — no ORM, no new dependency.

- ✅ `database/database.py`: connection + transactional `connection()` context
  manager (commit/rollback/close); `init_db()` creates the schema on startup (lifespan).
- ✅ `history` table (code, question, ai_response, activity_type, hint_level, created_at).
- ✅ Each successful Explain / Hints / Learning-Mode question / answer-evaluation is
  auto-saved (`routes/ai.py` `_record()`), failure-safe so a DB error never breaks
  the AI response; only successful activities are stored (no duplicate writes).
- ✅ History API: `GET /api/history` (recent, `?limit`), `GET /api/history/{id}`,
  `DELETE /api/history/{id}` — `routes/history.py` + `database/history.py` repo.
- ✅ Frontend History UI: a History section lists recent activities (type, local-time
  timestamp, preview), opens full details, and deletes individually; loading/empty/error
  states; auto-refreshes after each new activity. Rendered via `textContent` (no innerHTML).

## Phase 5 — Frontend editor & UX ✅

- ✅ History UI (view/delete previous activities) — built in Phase 4.
- ✅ Render AI Markdown responses as formatted HTML — self-contained safe renderer
  (`renderMarkdown` in `app.js`): escapes first, emits only known tags, no link/image
  parsing (no injection surface). Applied to Explain, Hints, Learning Mode, and the
  History AI-response field.
- ✅ UI/UX redesign: sticky top nav (Explain / Hints / Learning Mode / History) with
  active states + hash deep-linking; tabbed panels switch without reload; persistent
  shared code workspace (left) + active feature panel (right); consistent card/button/
  spacing design system; responsive (two-column → stacked below 860px). All existing
  JS/IDs/handlers preserved; tab controller is additive.
- ✅ Monaco editor for the code input (syntax highlighting, line numbers), vendored
  locally (`frontend/vendor/monaco`, v0.52.2 classic AMD build, git-ignored — fetch via
  its README). Progressive enhancement in `js/editor.js`: Monaco mounts over the `#code`
  textarea and mirrors its value back, so `app.js` is untouched and the textarea is the
  fallback if Monaco fails to load.
- ✅ Accessibility polish: full WAI-ARIA tabs pattern (tabs linked to panels via
  `aria-controls`/`aria-labelledby`, roving `tabindex`, Arrow/Home/End keyboard
  navigation in `app.js`); the four status regions are `role="status"
  aria-live="polite"` so loading/errors are announced; a "Skip to content" link
  lets keyboard users bypass the nav.

## Phase 6 — Quality & hardening ✅

- ✅ Automated tests: `pytest` + FastAPI `TestClient` (34 tests) covering `/health`,
  input validation (422), the AI success paths with `app.services.llm` monkeypatched
  (no Ollama needed), the `LLMConfigError`→503 / `LLMError`→502 mapping, and the
  history read/delete round-trip. Tests run offline against a temp SQLite DB (never
  `codementor.db`). Layout: `backend/conftest.py` (shared `client` fixture),
  `backend/tests/`, `backend/pytest.ini`, `backend/requirements-dev.txt` (`pytest`).
  Run with `pytest` from `backend/`.
- ✅ Input-size guards: every AI request field is length-capped in the Pydantic
  schemas (`code` ≤ 20000; `question`/`error`/`answer` ≤ 5000; `topic` ≤ 500) →
  over-length input returns 422.
- ✅ Rate limiting: a lightweight in-memory, per-client sliding-window limiter
  (`services/rate_limit.py`, no new dependency) applied router-wide to `/api/ai/*`;
  returns 429 + `Retry-After` when exceeded. Configurable via
  `RATE_LIMIT_MAX_REQUESTS` (default 30) / `RATE_LIMIT_WINDOW_SECONDS` (default 60);
  set max to 0 to disable. History/health are unaffected.
- ✅ First Git commit made and pushed to `origin/main`
  (github.com/SaiManish3/CodeMentor-AI-Coding-Coach); local run/setup flow documented
  in `CLAUDE.md` (backend, Ollama, frontend, and tests).

## Backlog / ideas ⬜

- ⬜ Support multiple models (e.g. `qwen2.5-coder:7b`) selectable via config.
- ⬜ Language/topic tagging of sessions.
- ⬜ User accounts (if the project grows beyond single-user local use).
