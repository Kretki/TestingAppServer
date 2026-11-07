"""JSON bodies of the REST API."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.contracts.quiz_models import MAX_IDENTIFIER_LENGTH
from server.llm_grading.grading_jobs import GradingStatus

MAX_ANSWER_LENGTH = 20000
MAX_NAME_LENGTH = 512
MAX_ATTEMPT_NUMBER = 100


class UploadResult(BaseModel):
    """Response of a file upload.

    Attributes:
        file_name: Relative path under which the file was stored.
    """

    file_name: str


class LlmAnswerRequest(BaseModel):
    """Body of POST /api/llm_answer.

    Attributes:
        test_file: Relative path of the _llm or _task file.
        question_id: Value of the question's id field, a string or number.
        user_answer: Answer written by the user.
        current_attempt: Number of this attempt, 1..max_attempts.
        max_attempts: Allowed attempts, 1..100. The LLM reveals the solution
            when current_attempt equals it.
    """

    model_config = ConfigDict(coerce_numbers_to_str=True)

    test_file: Annotated[str, Field(min_length=1, max_length=MAX_NAME_LENGTH)]
    question_id: Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)]
    user_answer: Annotated[str, Field(min_length=1, max_length=MAX_ANSWER_LENGTH)]
    current_attempt: Annotated[int, Field(ge=1, le=MAX_ATTEMPT_NUMBER)]
    max_attempts: Annotated[int, Field(ge=1, le=MAX_ATTEMPT_NUMBER)]

    @model_validator(mode="after")
    def require_valid_attempt(self) -> Self:
        """Check that the attempt is within the allowed attempts.

        Usage:
            Run by pydantic after field validation.

        Returns:
            The validated request.

        Raises:
            ValueError: If current_attempt exceeds max_attempts.
        """
        if self.current_attempt > self.max_attempts:
            raise ValueError("current_attempt must not exceed max_attempts")
        return self


class LlmAnswerTicket(BaseModel):
    """Response of POST /api/llm_answer.

    Attributes:
        request_id: Id to poll with GET /api/llm_answer.
    """

    request_id: str


class LlmAnswerResult(BaseModel):
    """Response of GET /api/llm_answer.

    Attributes:
        request_id: Id of the check.
        request_status: "pending", "ready" or "failed".
        llm_answer: When ready, a JSON object in a string, with the fields
            verdict, is_correct, is_final_feedback, feedback and mistakes.
        error_detail: Reason of the failure when failed.
    """

    request_id: str
    request_status: GradingStatus
    llm_answer: str | None
    error_detail: str | None
