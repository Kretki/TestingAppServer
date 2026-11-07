"""Validation of the JSON object that llm_input.md requires from the LLM."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, ValidationError, model_validator

from server.contracts.domain_errors import LlmRequestError

MAX_HINT_WORDS = 80


class MistakeNote(BaseModel):
    """One entry of `mistakes`; the field names are fixed by llm_input.md.

    Attributes:
        issue: What was wrong or missing.
        explanation: Why it is wrong or why it matters.
        correction: The correct understanding.
    """

    issue: str
    explanation: str
    correction: str


class GradingReply(BaseModel):
    """Reply of the LLM; the field names are fixed by llm_input.md.

    Usage:
        Built by `validate_grading_reply`.

    Attributes:
        verdict: Grade of the answer.
        is_correct: True only for the verdict "correct".
        is_final_feedback: True when the feedback may reveal the solution.
        feedback: Text shown to the user.
        mistakes: Corrections, empty when the feedback is not final.
    """

    verdict: Literal["correct", "partially_correct", "incorrect"]
    is_correct: bool
    is_final_feedback: bool
    feedback: Annotated[str, Field(min_length=1)]
    mistakes: list[MistakeNote]

    @model_validator(mode="after")
    def require_consistent_fields(self) -> Self:
        """Check the field rules of llm_input.md.

        Usage:
            Run by pydantic after field validation. The mistakes rule stops
            corrections reaching a user who still has attempts left.

        Returns:
            The validated reply.

        Raises:
            ValueError: If the fields contradict each other.
        """
        if self.is_correct != (self.verdict == "correct"):
            raise ValueError("is_correct does not match verdict")
        if self.mistakes and not self.is_final_feedback:
            raise ValueError("mistakes must be empty when the feedback is not final")
        return self


def require_allowed_feedback(grading_reply: GradingReply, is_final_attempt: bool) -> None:
    """Enforce the feedback cases of llm_input.md using the real attempt.

    Usage:
        Call on every reply. A user can talk the model into believing an
        attempt is final, so the server, which knows the real numbers, decides
        whether the reply may reveal the solution.

    Args:
        grading_reply: Parsed reply of the model.
        is_final_attempt: Whether this is really the user's last attempt.

    Raises:
        LlmRequestError: If the reply does not match its feedback case.
    """
    may_reveal_solution = is_final_attempt or grading_reply.is_correct
    if grading_reply.is_final_feedback != may_reveal_solution:
        raise LlmRequestError("LLM reply does not match the real attempt state")
    if not may_reveal_solution and len(grading_reply.feedback.split()) > MAX_HINT_WORDS:
        raise LlmRequestError("LLM hint is longer than the allowed limit")


def validate_grading_reply(reply_text: str, is_final_attempt: bool) -> str:
    """Check the model's final answer against the required format.

    Usage:
        Call on the final answer before storing it for the user.

    Args:
        reply_text: Final answer of the model.
        is_final_attempt: Whether this is really the user's last attempt.

    Returns:
        The reply as a compact JSON object.

    Raises:
        LlmRequestError: If the reply is not a valid grading object, or breaks
            the feedback rules for this attempt.
    """
    try:
        grading_reply = GradingReply.model_validate_json(reply_text)
    except ValidationError as format_error:
        raise LlmRequestError(f"LLM reply has an invalid format: {format_error}") from format_error
    require_allowed_feedback(grading_reply, is_final_attempt)
    return grading_reply.model_dump_json()
