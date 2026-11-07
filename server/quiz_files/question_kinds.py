"""Question kinds, which are stated by the ending of a quiz file name."""

from enum import StrEnum
from pathlib import PurePosixPath

from server.contracts.domain_errors import InvalidFileContentError, InvalidFileNameError
from server.contracts.quiz_models import QuizDocument


class QuestionKind(StrEnum):
    """How the questions of a quiz file are checked."""

    KIND_TESTING = "testing"
    KIND_LLM = "llm"
    KIND_TASK = "task"


KINDS_BY_NAME_ENDING = {
    "_quiz": QuestionKind.KIND_TESTING,
    "_llm": QuestionKind.KIND_LLM,
    "_task": QuestionKind.KIND_TASK,
}
LLM_CHECKED_KINDS = frozenset({QuestionKind.KIND_LLM, QuestionKind.KIND_TASK})
SECRET_FIELDS = ("llm_system_explanation",)
SECRET_TASK_FIELDS = ("llm_system_explanation", "correct_answer")
TASK_NAME_ENDING = "_task"


def find_question_kind(file_name: str) -> QuestionKind:
    """Read the question kind from a quiz file name.

    Usage:
        Call for every quiz file before using its questions.

    Args:
        file_name: Relative path such as "python/planets_quiz.csv".

    Returns:
        The kind of all questions in the file.

    Raises:
        InvalidFileNameError: If the name does not end in _quiz, _llm or _task.
    """
    file_stem = PurePosixPath(file_name).stem.lower()
    for name_ending, question_kind in KINDS_BY_NAME_ENDING.items():
        if file_stem.endswith(name_ending):
            return question_kind
    raise InvalidFileNameError(f"Quiz file name must end in _quiz, _llm or _task: {file_name!r}")


def find_secret_fields(file_name: str) -> tuple[str, ...]:
    """List the fields that must not leave the server for a file.

    Usage:
        Call before serving a quiz file. It never fails, so that a file with
        an unexpected name still has its secrets removed.

    Args:
        file_name: Relative path of the quiz file.

    Returns:
        Names of the secret fields.
    """
    is_task_file = PurePosixPath(file_name).stem.lower().endswith(TASK_NAME_ENDING)
    return SECRET_TASK_FIELDS if is_task_file else SECRET_FIELDS


def require_choice_fields(quiz_document: QuizDocument) -> None:
    """Check that every testing question can be answered on the client.

    Usage:
        Internal step of `require_kind_fields`.

    Args:
        quiz_document: Parsed quiz.

    Raises:
        InvalidFileContentError: If a question is incomplete.
    """
    for question in quiz_document.questions:
        if question.correct_answer is None or not question.wrong_answers:
            raise InvalidFileContentError(
                f"Question {question.question_id} needs correct_answer and at least one wrong_answer"
            )


def require_task_fields(quiz_document: QuizDocument) -> None:
    """Check that every task tells the LLM how to judge the candidate.

    Usage:
        Internal step of `require_kind_fields`.

    Args:
        quiz_document: Parsed quiz.

    Raises:
        InvalidFileContentError: If a task has no explanation.
    """
    for question in quiz_document.questions:
        if not question.llm_system_explanation:
            raise InvalidFileContentError(f"Task {question.question_id} needs llm_system_explanation")


KIND_REQUIREMENTS = {
    QuestionKind.KIND_TESTING: require_choice_fields,
    QuestionKind.KIND_TASK: require_task_fields,
}


def require_kind_fields(quiz_document: QuizDocument, question_kind: QuestionKind) -> None:
    """Check that the questions have the fields their kind needs.

    Usage:
        Call after parsing.

    Args:
        quiz_document: Parsed quiz.
        question_kind: Kind stated by the file name.

    Raises:
        InvalidFileContentError: If a question is incomplete.
    """
    field_check = KIND_REQUIREMENTS.get(question_kind)
    if field_check is not None:
        field_check(quiz_document)
