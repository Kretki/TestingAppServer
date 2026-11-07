"""Use case of checking a written answer with the LLM."""

import logging
from dataclasses import dataclass

from server.contracts.domain_errors import LlmRequestError
from server.contracts.service_contracts import ChatModel, InstructionSource, KnowledgeSource, OpenQuestionSource
from server.llm_grading.grading_jobs import GradingJob, GradingJobStore
from server.llm_grading.grading_reply import validate_grading_reply
from server.llm_grading.prompt_builder import AnswerAttempt, GradingPrompt, build_grading_prompt

MODULE_LOGGER = logging.getLogger(__name__)
LLM_FAILURE_MESSAGE = "The LLM could not check this answer, please submit it again"
MAX_LLM_TRIES = 3


@dataclass(frozen=True)
class PendingGrading:
    """Accepted answer waiting for the LLM.

    Usage:
        Returned by `submit_answer` and passed to `run_grading`.

    Attributes:
        request_id: Id given to the user.
        grading_prompt: Prompts of the LLM call.
        is_final_attempt: Whether this is the user's last attempt.
    """

    request_id: str
    grading_prompt: GradingPrompt
    is_final_attempt: bool


class GradingService:
    """Acceptance, execution and lookup of LLM checks.

    Usage:
        Create once at start-up and share between requests.
    """

    def __init__(
        self,
        question_source: OpenQuestionSource,
        knowledge_source: KnowledgeSource,
        instruction_source: InstructionSource,
        chat_model: ChatModel,
        job_store: GradingJobStore,
    ) -> None:
        """Store the dependencies.

        Usage:
            Call at start-up.

        Args:
            question_source: Lookup of LLM questions.
            knowledge_source: Reference documents.
            instruction_source: Provider of the LLM system prompt.
            chat_model: Model that checks answers.
            job_store: Store of checks.
        """
        self._question_source = question_source
        self._knowledge_source = knowledge_source
        self._instruction_source = instruction_source
        self._chat_model = chat_model
        self._job_store = job_store

    def submit_answer(self, test_file: str, question_id: str, answer_attempt: AnswerAttempt) -> PendingGrading:
        """Validate an answer and register its check.

        Usage:
            Call when the user sends an answer, then schedule `run_grading`.

        Args:
            test_file: Name of the quiz file.
            question_id: Id of the question inside the quiz.
            answer_attempt: The user's answer and attempt numbers.

        Returns:
            The accepted check.

        Raises:
            QuizServerError: If the quiz, question or referenced knowledge
                file or the LLM instructions are unusable, or the queue is full.
        """
        question = self._question_source.find_open_question(test_file, question_id)
        knowledge_text = None
        if question.knowledge_file:
            knowledge_text = self._knowledge_source.read_text(question.knowledge_file)
        grading_prompt = build_grading_prompt(
            self._instruction_source.read_instructions(),
            question.question_text,
            question.correct_answer,
            knowledge_text,
            answer_attempt,
        )
        return PendingGrading(self._job_store.create_job(), grading_prompt, answer_attempt.is_final)

    async def run_grading(self, pending_grading: PendingGrading) -> None:
        """Run the LLM call and store its outcome.

        Usage:
            Schedule as a background task after `submit_answer`. It never
            raises, so a check cannot stay pending forever.

        Args:
            pending_grading: The accepted check.
        """
        try:
            llm_answer = await self._request_valid_reply(pending_grading)
        except LlmRequestError as request_error:
            MODULE_LOGGER.error("LLM check failed: %s", request_error)
            self._job_store.fail_job(pending_grading.request_id, LLM_FAILURE_MESSAGE)
        except Exception:
            MODULE_LOGGER.exception("Unexpected failure of an LLM check")
            self._job_store.fail_job(pending_grading.request_id, LLM_FAILURE_MESSAGE)
        else:
            self._job_store.complete_job(pending_grading.request_id, llm_answer)

    async def _request_valid_reply(self, pending_grading: PendingGrading) -> str:
        """Ask the model until it gives a valid reply.

        Usage:
            Internal step of `run_grading`. The model samples randomly, so a
            new try usually fixes a malformed or rule-breaking reply.

        Args:
            pending_grading: The accepted check.

        Returns:
            The validated reply.

        Raises:
            LlmRequestError: If every try fails; the last error is raised.
        """
        grading_prompt = pending_grading.grading_prompt
        for try_number in range(1, MAX_LLM_TRIES + 1):
            try:
                reply_text = await self._chat_model.complete_chat(
                    grading_prompt.system_prompt, grading_prompt.user_prompt
                )
                return validate_grading_reply(reply_text, pending_grading.is_final_attempt)
            except LlmRequestError as request_error:
                if try_number == MAX_LLM_TRIES:
                    raise
                MODULE_LOGGER.warning("LLM try %d refused: %s", try_number, request_error)
        raise LlmRequestError("No LLM tries were made")

    def find_result(self, request_id: str) -> GradingJob:
        """Read the state of a check.

        Usage:
            Call when the user polls for a result.

        Args:
            request_id: Id of the check.

        Returns:
            The current snapshot.

        Raises:
            GradingRequestMissingError: If the id is unknown or expired.
        """
        return self._job_store.find_job(request_id)
