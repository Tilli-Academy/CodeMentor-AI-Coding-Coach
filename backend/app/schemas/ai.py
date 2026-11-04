"""
AI schemas — the request/response data contracts for the AI endpoints.

Responsibility:
- Define Pydantic models describing the JSON the frontend sends and receives.
  FastAPI uses these models to validate input, serialize output, and
  auto-generate the interactive API docs at /docs.

These are the initial shapes (the "contract" between frontend and backend) and
will evolve as features are added. No behaviour lives here — only data shapes.
"""
from pydantic import BaseModel, Field, field_validator, model_validator


class ExplainRequest(BaseModel):
    """JSON the frontend POSTs when asking CodeMentor to explain code/an error."""

    code: str = Field(min_length=1, max_length=20000, description="The code to explain.")
    error_message: str | None = Field(default=None, max_length=5000)

    @field_validator("code")
    @classmethod
    def _code_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code must not be empty or whitespace only")
        return value


class ExplainResponse(BaseModel):
    """JSON returned to the frontend containing the AI explanation."""

    explanation: str


class HintsRequest(BaseModel):
    """JSON the frontend POSTs to request ONE progressive hint at a given level."""

    code: str = Field(
        min_length=1, max_length=20000, description="The code the learner is working on."
    )
    question: str = Field(
        min_length=1,
        max_length=5000,
        description="What the learner is trying to do or is stuck on.",
    )
    level: int = Field(
        ge=1, le=3, description="Hint level: 1 (gentle), 2 (approach), 3 (strong)."
    )

    @field_validator("code", "question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty or whitespace only")
        return value


class HintsResponse(BaseModel):
    """JSON returned to the frontend: one hint and the level it was given at."""

    hint: str
    level: int


class LearnQuestionRequest(BaseModel):
    """JSON the frontend POSTs to get one learning question about code or a topic.

    Either `code` or `topic` (or both) must be supplied; blank strings are treated
    as "not provided".
    """

    code: str | None = Field(
        default=None,
        max_length=20000,
        description="Code to base the question on (optional if a topic is given).",
    )
    topic: str | None = Field(
        default=None,
        max_length=500,
        description="A concept/topic to quiz on (optional if code is given).",
    )

    @field_validator("code", "topic")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        # Treat empty/whitespace-only input as absent so the check below is honest.
        if value is not None and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _require_code_or_topic(self) -> "LearnQuestionRequest":
        if not self.code and not self.topic:
            raise ValueError("either code or topic must be provided")
        return self


class LearnQuestionResponse(BaseModel):
    """JSON returned to the frontend: one learning question."""

    question: str


class LearnEvaluateRequest(BaseModel):
    """JSON the frontend POSTs to have the learner's answer evaluated.

    `question` and `answer` are required; `code`/`topic` are the same context the
    question was generated from (optional, improves grading accuracy).
    """

    question: str = Field(
        min_length=1, max_length=5000, description="The question the learner answered."
    )
    answer: str = Field(
        min_length=1, max_length=5000, description="The learner's answer."
    )
    code: str | None = Field(default=None, max_length=20000)
    topic: str | None = Field(default=None, max_length=500)

    @field_validator("question", "answer")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty or whitespace only")
        return value


class LearnEvaluateResponse(BaseModel):
    """JSON returned to the frontend: the verdict, feedback, and optional follow-up."""

    verdict: str  # "correct" | "partially_correct" | "incorrect"
    feedback: str
    follow_up: str | None = None
