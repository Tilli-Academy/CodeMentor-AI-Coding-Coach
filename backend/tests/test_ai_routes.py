"""
AI route behaviour: success paths and the service-error -> HTTP-status mapping.

The real AI work (app.services.llm) talks to a local Ollama server, which is not
available under test. So every test here monkeypatches the relevant llm function
to either return a canned value or raise one of the typed service errors. The
routes under test (app/routes/ai.py) reference the functions via the `llm`
module object, so patching attributes on that module intercepts the calls.

Error-mapping convention (see CLAUDE.md):
  LLMConfigError -> 503   (Ollama down / model not pulled — a setup problem)
  LLMError       -> 502   (the model call failed or returned nothing usable)
"""
import pytest

from app.services import llm

VALID_CODE = "for i in range(3):\n    print(i)"


@pytest.fixture
def patch_llm(monkeypatch):
    """Return a helper that replaces an llm function with our own callable."""

    def _patch(name, func):
        monkeypatch.setattr(llm, name, func)

    return _patch


# Each entry: endpoint path, a valid JSON body, the llm function it calls, and
# a factory producing a success return value for that function.
ENDPOINTS = [
    (
        "/api/ai/explain",
        {"code": VALID_CODE},
        "generate_explanation",
        lambda *a, **k: "This loop prints 0, 1, 2.",
    ),
    (
        "/api/ai/hints",
        {"code": VALID_CODE, "question": "why does it stop at 2?", "level": 1},
        "generate_hint",
        lambda *a, **k: "Think about what range(3) produces.",
    ),
    (
        "/api/ai/learn/question",
        {"topic": "for loops"},
        "generate_learning_question",
        lambda *a, **k: "What does range(3) return?",
    ),
    (
        "/api/ai/learn/evaluate",
        {"question": "What is a loop?", "answer": "repeats code"},
        "evaluate_answer",
        lambda *a, **k: {
            "verdict": "correct",
            "feedback": "Right!",
            "follow_up": None,
        },
    ),
]


@pytest.mark.parametrize("path, body, fn_name, ok_factory", ENDPOINTS)
def test_endpoint_success(client, patch_llm, path, body, fn_name, ok_factory):
    patch_llm(fn_name, ok_factory)
    resp = client.post(path, json=body)
    assert resp.status_code == 200
    # Every AI response is a JSON object (not an error envelope).
    assert isinstance(resp.json(), dict)


def test_explain_success_echoes_explanation(client, patch_llm):
    patch_llm("generate_explanation", lambda *a, **k: "A tidy explanation.")
    resp = client.post("/api/ai/explain", json={"code": VALID_CODE})
    assert resp.status_code == 200
    assert resp.json() == {"explanation": "A tidy explanation."}


def test_hints_success_returns_level(client, patch_llm):
    patch_llm("generate_hint", lambda *a, **k: "A gentle nudge.")
    resp = client.post(
        "/api/ai/hints",
        json={"code": VALID_CODE, "question": "stuck", "level": 2},
    )
    assert resp.status_code == 200
    assert resp.json() == {"hint": "A gentle nudge.", "level": 2}


@pytest.mark.parametrize("path, body, fn_name, _ok", ENDPOINTS)
def test_config_error_maps_to_503(client, patch_llm, path, body, fn_name, _ok):
    def boom(*a, **k):
        raise llm.LLMConfigError("Ollama is not running.")

    patch_llm(fn_name, boom)
    resp = client.post(path, json=body)
    assert resp.status_code == 503


@pytest.mark.parametrize("path, body, fn_name, _ok", ENDPOINTS)
def test_llm_error_maps_to_502(client, patch_llm, path, body, fn_name, _ok):
    def boom(*a, **k):
        raise llm.LLMError("model returned nothing")

    patch_llm(fn_name, boom)
    resp = client.post(path, json=body)
    assert resp.status_code == 502
