"""
AI routes — HTTP endpoints for AI-assisted features.

Responsibility:
- Define the REST endpoints the frontend calls (e.g. "explain this error").
- Validate incoming JSON using the Pydantic models in app.schemas.ai.
- Delegate the actual AI work to app.services.llm (routes stay thin).
- Translate service errors into appropriate HTTP responses.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.database import history as history_repo
from app.services.rate_limit import rate_limit
from app.schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    HintsRequest,
    HintsResponse,
    LearnEvaluateRequest,
    LearnEvaluateResponse,
    LearnQuestionRequest,
    LearnQuestionResponse,
)
from app.services import llm

# Every AI endpoint is rate-limited (the model calls are expensive); the limiter
# runs as a router-wide dependency before any handler body.
router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(rate_limit)])

logger = logging.getLogger("codementor.history")


def _record(
    activity_type: str,
    ai_response: str,
    code: str | None = None,
    question: str | None = None,
    hint_level: int | None = None,
) -> None:
    """Save a successful activity to history, never breaking the AI response.

    History persistence is best-effort: a DB failure here must not turn a good
    AI result into an error, so everything is caught and logged.
    """
    try:
        history_repo.save_activity(
            activity_type,
            ai_response,
            code=code,
            question=question,
            hint_level=hint_level,
        )
    except Exception:  # pragma: no cover - defensive, logged not raised
        logger.exception("Failed to save %s activity to history", activity_type)


@router.post("/explain", response_model=ExplainResponse)
def explain(payload: ExplainRequest) -> ExplainResponse:
    """Explain submitted code (and an optional error) in beginner-friendly terms."""
    try:
        explanation = llm.generate_explanation(payload.code, payload.error_message)
    except llm.LLMConfigError as exc:
        # Ollama is not running or the model is not pulled — a server setup issue.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except llm.LLMError as exc:
        # The local model call failed or returned nothing usable.
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    _record("explain", explanation, code=payload.code, question=payload.error_message)
    return ExplainResponse(explanation=explanation)


@router.post("/hints", response_model=HintsResponse)
def hints(payload: HintsRequest) -> HintsResponse:
    """Return ONE progressive hint at the requested level (1-3) without giving the answer."""
    try:
        hint = llm.generate_hint(payload.code, payload.question, payload.level)
    except llm.LLMConfigError as exc:
        # Ollama is not running or the model is not pulled — a server setup issue.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except llm.LLMError as exc:
        # The local model call failed or returned nothing usable.
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    _record(
        "hints",
        hint,
        code=payload.code,
        question=payload.question,
        hint_level=payload.level,
    )
    return HintsResponse(hint=hint, level=payload.level)


@router.post("/learn/question", response_model=LearnQuestionResponse)
def learn_question(payload: LearnQuestionRequest) -> LearnQuestionResponse:
    """Generate ONE beginner learning question about the given code and/or topic."""
    try:
        question = llm.generate_learning_question(payload.code, payload.topic)
    except llm.LLMConfigError as exc:
        # Ollama is not running or the model is not pulled — a server setup issue.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except llm.LLMError as exc:
        # The local model call failed or returned nothing usable.
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    # `question` here is the AI-generated question; `topic` is the user's prompt.
    _record("learn_question", question, code=payload.code, question=payload.topic)
    return LearnQuestionResponse(question=question)


@router.post("/learn/evaluate", response_model=LearnEvaluateResponse)
def learn_evaluate(payload: LearnEvaluateRequest) -> LearnEvaluateResponse:
    """Evaluate the learner's answer and return a verdict, feedback and follow-up."""
    try:
        result = llm.evaluate_answer(
            payload.question, payload.answer, payload.code, payload.topic
        )
    except llm.LLMConfigError as exc:
        # Ollama is not running or the model is not pulled — a server setup issue.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except llm.LLMError as exc:
        # The local model call failed or returned nothing usable.
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    # Store the question that was answered plus the feedback the learner received.
    _record("learn_evaluate", result["feedback"], code=payload.code, question=payload.question)
    return LearnEvaluateResponse(**result)
