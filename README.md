# CodeMentor

An AI-powered coding tutor that helps beginner programmers understand errors,
debug code, and improve their programming skills.

## Technology Stack

- **Frontend:** HTML, CSS, JavaScript (vanilla) + Monaco Editor (planned)
- **Backend:** Python + FastAPI
- **AI:** Local Ollama (`qwen2.5-coder:3b`) — runs locally, no API key
- **Database:** SQLite

## Project Structure

```
Ai-CodingMentor/
├── frontend/              # Static browser app (HTML/CSS/JS)
│   ├── index.html         # Page shell; loads the CSS and JS
│   ├── css/style.css      # Global styles
│   ├── js/app.js          # UI logic; calls the backend via fetch() + JSON
│   └── assets/            # Static assets (favicon, images)
│
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── main.py        # App entry point: creates FastAPI app, CORS, routers
│   │   ├── routes/ai.py   # HTTP endpoints for AI features
│   │   ├── services/llm.py  # Talks to local Ollama (only place that does)
│   │   ├── schemas/ai.py  # Pydantic request/response models (the JSON contract)
│   │   └── database/database.py  # SQLite connection/setup
│   ├── requirements.txt   # Python dependencies
│   └── .env.example       # Template for environment variables (copy to .env)
│
├── frontend-sveltekit-archive/  # Previous SvelteKit frontend (kept for reference)
├── .gitignore
└── README.md
```

## How the frontend talks to the backend

The frontend is a static site; the backend is a separate FastAPI server. They
communicate over HTTP with JSON bodies: the browser `fetch()`es a backend URL,
sends/receives JSON, and FastAPI validates it against the Pydantic schemas in
`backend/app/schemas/`. Because they run on different origins, the backend
enables CORS in `main.py`.

## Running

AI runs locally via [Ollama](https://ollama.com). Start it and pull the model once:

```bash
ollama serve                    # listens on http://127.0.0.1:11434
ollama pull qwen2.5-coder:3b    # the default model
```

Backend (from `backend/`, inside a virtual environment):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010   # docs at http://localhost:8010/docs
```

Frontend (from `frontend/`): open `index.html` in a browser, or serve it with any
static file server (e.g. `python3 -m http.server 5500`).

## Status

The AI endpoints — `POST /api/ai/explain` and `POST /api/ai/hints` — are implemented
and backed by local Ollama. The SQLite layer and Monaco editor are still to come;
see `CLAUDE.md` for the detailed status.
