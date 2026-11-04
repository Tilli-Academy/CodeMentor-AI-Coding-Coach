"""
LLM service — the ONLY module that talks to the local Ollama server.

Responsibility:
- Encapsulate all AI calls behind simple Python functions, so routes stay thin
  and the AI backend (currently local Ollama) could be swapped without touching
  the HTTP layer.

Runs fully locally: there is NO API key and NO cloud call. Prerequisites:
- the Ollama server is running:  ollama serve   (listens on 127.0.0.1:11434)
- the model has been pulled:     ollama pull qwen2.5-coder:3b

Host/model are overridable via backend/.env (OLLAMA_HOST, OLLAMA_MODEL); the
defaults below make the app work out of the box once Ollama is running.
"""
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables from backend/.env (this file is at app/services/).
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")

# CPU inference can be slow for longer generations; allow generous headroom.
REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

# Max tokens Ollama may generate for an evaluation. The default (~128) truncated
# some feedback mid-sentence; a higher cap lets the explanation finish.
EVALUATE_NUM_PREDICT = int(os.getenv("OLLAMA_EVALUATE_NUM_PREDICT", "512"))

# Tutor persona + teaching rules, sent as Ollama's `system` message for the
# explanation endpoint. The user prompt supplies only the code/error to explain.
EXPLAIN_SYSTEM_PROMPT = """\
You are CodeMentor, a patient, friendly programming tutor for complete beginners. \
Help the learner genuinely understand their code and any error — not just get an answer.

Teaching guidelines:
1. Use simple, plain language and assume the learner is a beginner; if a technical term is unavoidable, define it briefly.
2. First say what the code does overall, then go into technical details.
3. Break complex code into logical, ordered steps.
4. Explain the important variables, functions, parameters, and concepts involved.
5. Include the expected output when it can be determined from the code.
6. Use a small example only when it genuinely improves understanding.
7. Explain WHY something happens, not just WHAT happens.
8. Be concise: no filler introductions, no repetition, no padding.
9. Never invent or guess code behavior, and never claim you ran the code — you are reading it, not executing it.
10. If the code is incomplete, ambiguous, or depends on missing context, say so clearly.

Format your answer in Markdown using only the sections that are relevant (omit any that do not apply):
- **Overview** — what the code does.
- **Step-by-step explanation** — how it works.
- **Important concepts** — what a beginner should learn here.
- **Expected output** — what it will produce (only if it can be determined).
- **Learning takeaway** — the one key thing to remember.

Adapt depth to complexity: a one-liner deserves a sentence or two, not five sections."""

# Extra instructions injected into the USER message only when the learner supplies
# an error message, steering the explanation toward a focused debugging diagnosis.
# The system prompt (persona + rules) is unchanged; this just reshapes the sections
# for the error case.
_DEBUG_INSTRUCTIONS = """\
An error message is provided, so focus on diagnosing and fixing it. Base your \
diagnosis ONLY on the code and the error text shown — do not assume the code was \
run beyond this error, and do not invent other errors. Respond in Markdown using \
these sections:
- **Error** — name the exact error and what it means in plain words.
- **Root cause** — why it happens in this specific code, explained for a beginner.
- **Problem spot** — the exact line or expression responsible, when it can be identified.
- **Fix** — the corrected code. If more than one fix is possible, show the simplest appropriate one first.
- **Why the fix works** — why the correction resolves the error.
- **Expected output** — what the corrected code will produce, when it can be determined.
Keep it concise and educational; a one-line overview first is fine, but the diagnosis is the point."""


class LLMConfigError(RuntimeError):
    """Raised when Ollama is unreachable or the model is missing (a setup problem)."""


class LLMError(RuntimeError):
    """Raised when the Ollama call fails or returns nothing usable."""


def _generate(
    prompt: str,
    fmt: object | None = None,
    system: str | None = None,
    options: dict[str, object] | None = None,
) -> str:
    """POST a prompt to Ollama's /api/generate and return the response text.

    `system` sets Ollama's `system` field (the tutor persona / instructions).
    `fmt` maps to Ollama's `format` field: pass a JSON schema (or the string
    "json") to constrain the output to valid JSON.
    `options` maps to Ollama's `options` field (runtime params such as
    `num_predict`, the max tokens to generate).
    """
    payload: dict[str, object] = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system is not None:
        payload["system"] = system
    if fmt is not None:
        payload["format"] = fmt
    if options is not None:
        payload["options"] = options

    try:
        resp = httpx.post(
            f"{OLLAMA_HOST}/api/generate", json=payload, timeout=REQUEST_TIMEOUT
        )
    except httpx.ConnectError as exc:
        raise LLMConfigError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Is `ollama serve` running?"
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMError(f"Ollama request timed out after {REQUEST_TIMEOUT}s.") from exc
    except httpx.HTTPError as exc:  # other transport-level failures
        raise LLMError(f"Ollama request failed: {exc}") from exc

    if resp.status_code == 404:
        # Ollama is up, but the requested model has not been pulled.
        raise LLMConfigError(
            f"Model '{OLLAMA_MODEL}' is not available in Ollama. "
            f"Run: ollama pull {OLLAMA_MODEL}"
        )
    if resp.status_code != 200:
        raise LLMError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        text = (resp.json().get("response") or "").strip()
    except ValueError as exc:  # malformed envelope
        raise LLMError("Ollama returned a non-JSON response envelope.") from exc
    if not text:
        raise LLMError("Ollama returned an empty response.")
    return text


def _build_prompt(code: str, error_message: str | None) -> str:
    """Build the user message for the given code (plus any error the learner saw).

    The teaching rules and response format live in EXPLAIN_SYSTEM_PROMPT, so this
    only presents the task-specific input. When an error message is present, the
    request switches to a focused debugging diagnosis (_DEBUG_INSTRUCTIONS);
    otherwise it is a plain beginner explanation with no invented runtime errors.
    """
    code_block = "\nCode:\n```\n" + code + "\n```"
    if error_message:
        return (
            _DEBUG_INSTRUCTIONS
            + "\n\nError message:\n"
            + error_message
            + "\n"
            + code_block
        )
    return "Explain the following code for a beginner." + code_block


def generate_explanation(code: str, error_message: str | None = None) -> str:
    """Send the code (and optional error) to Ollama and return its explanation."""
    return _generate(_build_prompt(code, error_message), system=EXPLAIN_SYSTEM_PROMPT)


# Persona/rules for the hints endpoint, sent as Ollama's `system` message. One
# hint per request, never the full solution — the per-level specificity is set by
# _HINT_LEVELS in the user prompt.
_HINT_SYSTEM_PROMPT = """\
You are CodeMentor, a patient programming tutor. The learner wants ONE hint to help \
them make progress on their own — NOT a full explanation or the finished solution.

Rules:
- Give exactly one hint: a few sentences at most. Be concise and encouraging.
- Keep the hint specific to the learner's code and their question.
- Guide their thinking. Never hand over the complete solution or the full corrected \
code, even at the strongest hint level.
- Use plain, beginner-friendly language. A tiny snippet or pseudocode is acceptable \
only if it does not amount to the whole answer.
- Do not invent code behavior or claim you ran the code; you are only reading it.
- Reply with just the hint text (no headings, no "Hint:" prefix)."""

# How specific the single hint should be at each level.
_HINT_LEVELS = {
    1: "Give a LEVEL 1 (gentle) hint: nudge the learner toward the general concept "
    "or area to think about. Do not reveal the approach or the solution.",
    2: "Give a LEVEL 2 (approach) hint: point more specifically at the approach, "
    "method, or part of the code to focus on. Still do not give the full solution.",
    3: "Give a LEVEL 3 (strong) hint: give concrete, near-complete guidance on what "
    "to change or try — but stop short of writing out the entire solution for them.",
}


def _build_hint_prompt(code: str, question: str, level: int) -> str:
    """Build the user message for a single hint at the given level (1-3)."""
    return (
        _HINT_LEVELS[level]
        + "\n\nLearner's question/problem:\n"
        + question
        + "\n\nCode:\n```\n"
        + code
        + "\n```"
    )


def generate_hint(code: str, question: str, level: int) -> str:
    """Send the code + question to Ollama and return ONE hint at the given level."""
    if level not in _HINT_LEVELS:
        # Defensive: the request schema already constrains level to 1-3.
        raise LLMError(f"Unsupported hint level: {level!r} (expected 1, 2, or 3).")
    return _generate(
        _build_hint_prompt(code, question, level), system=_HINT_SYSTEM_PROMPT
    )


# ---- Learning Mode ----
# Two complementary calls: ASK a question about the learner's code/topic, then
# EVALUATE the answer they give back. The question is free text; the evaluation is
# constrained to JSON (via Ollama's `format` field) so the verdict is machine-usable.

_LEARN_QUESTION_SYSTEM_PROMPT = """\
You are CodeMentor, a patient programming tutor for complete beginners. Here your \
job is to ASK the learner ONE question that checks and deepens their understanding \
— you are quizzing them, not explaining.

Rules:
- Ask exactly ONE clear, beginner-friendly question (a few sentences at most).
- Base it on the provided code or topic, and keep it relevant to what was given.
- Choose ONE angle that fits: the meaning of a concept, what the code does, \
predicting the output, or reasoning about the logic.
- Keep it answerable by a beginner reasoning about the material; do not require \
them to actually run anything.
- Do not reveal the answer. Only offer multiple-choice options if the question \
genuinely needs them.
- Reply with just the question text (no headings, no "Question:" prefix)."""

# Grading persona for the evaluation call. Paired with _EVALUATE_FORMAT so the
# model must return JSON with exactly these fields.
_EVALUATE_SYSTEM_PROMPT = """\
You are CodeMentor, a patient programming tutor for complete beginners. You are \
grading a learner's answer to a question you asked, and teaching them along the way.

Guidelines:
- Judge the answer honestly against the question and any provided code/topic.
- "verdict" must be exactly one of: "correct", "partially_correct", "incorrect".
- In "feedback": in plain, encouraging language, say what was right or wrong, then \
explain the correct concept simply. Never shame the learner.
- Base your judgement only on the material shown; never claim you ran any code.
- "follow_up": a short follow-up question ONLY when it would help them go deeper; \
otherwise use an empty string.
- Keep it concise and beginner-friendly."""

# JSON schema handed to Ollama's `format` field so the evaluation comes back
# structured. follow_up is required but may be an empty string (see prompt).
_EVALUATE_FORMAT: dict[str, object] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["correct", "partially_correct", "incorrect"],
        },
        "feedback": {"type": "string"},
        "follow_up": {"type": "string"},
    },
    "required": ["verdict", "feedback", "follow_up"],
}

_VALID_VERDICTS = {"correct", "partially_correct", "incorrect"}


def _build_learn_context(code: str | None, topic: str | None) -> str:
    """Render the supplied code and/or topic as a prompt context block."""
    parts: list[str] = []
    if topic:
        parts.append("Topic: " + topic)
    if code:
        parts.append("Code:\n```\n" + code + "\n```")
    return "\n\n".join(parts)


def generate_learning_question(code: str | None, topic: str | None) -> str:
    """Ask Ollama for ONE beginner question about the given code and/or topic."""
    if not code and not topic:
        # Defensive: the request schema already requires code or topic.
        raise LLMError("A code snippet or a topic is required to generate a question.")
    prompt = (
        "Ask the learner one question based on the following.\n\n"
        + _build_learn_context(code, topic)
    )
    return _generate(prompt, system=_LEARN_QUESTION_SYSTEM_PROMPT)


def evaluate_answer(
    question: str,
    answer: str,
    code: str | None = None,
    topic: str | None = None,
) -> dict[str, object]:
    """Evaluate the learner's answer; return {verdict, feedback, follow_up}."""
    context = _build_learn_context(code, topic)
    prompt = (
        "Question asked:\n"
        + question
        + "\n\nLearner's answer:\n"
        + answer
        + (("\n\n" + context) if context else "")
    )
    raw = _generate(
        prompt,
        fmt=_EVALUATE_FORMAT,
        system=_EVALUATE_SYSTEM_PROMPT,
        options={"num_predict": EVALUATE_NUM_PREDICT},
    )

    try:
        data = json.loads(raw)
    except ValueError as exc:  # model ignored the format constraint
        raise LLMError("Ollama returned malformed JSON for the evaluation.") from exc
    if not isinstance(data, dict):
        raise LLMError("Ollama returned an unexpected evaluation shape.")

    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in _VALID_VERDICTS:
        # Keep the contract intact even if the model drifts off the enum.
        verdict = "partially_correct"
    feedback = str(data.get("feedback", "")).strip()
    if not feedback:
        raise LLMError("Ollama returned an empty evaluation.")
    follow_up = str(data.get("follow_up", "")).strip() or None

    return {"verdict": verdict, "feedback": feedback, "follow_up": follow_up}
