"""Question kinds, which are stated by the ending of a quiz file name."""

from enum import StrEnum
from pathlib import PurePath

from server.contracts.domain_errors import InvalidFileContentError, InvalidFileNameError
from server.contracts.quiz_models import QuizDocument


class QuestionKind(StrEnum):
    """How the questions of a quiz file are checked."""

    KIND_TESTING = "testing"
    KIND_LLM = "llm"


KINDS_BY_NAME_ENDING = {"_quiz": QuestionKind.KIND_TESTING, "_llm": QuestionKind.KIND_LLM}


def find_question_kind(file_name: str) -> QuestionKind:
    """Read the question kind from a quiz file name.

    Usage:
        Call for every quiz file before using its questions.

    Args:
        file_name: Name such as "planets_quiz.csv" or "planets_llm.json".

    Returns:
        The kind of all questions in the file.

    Raises:
        InvalidFileNameError: If the name does not end in _quiz or _llm.
    """
    file_stem = PurePath(file_name).stem
    for name_ending, question_kind in KINDS_BY_NAME_ENDING.items():
        if file_stem.endswith(name_ending):
            return question_kind
    raise InvalidFileNameError(f"Quiz file name must end in _quiz or _llm: {file_name!r}")


def require_kind_fields(quiz_document: QuizDocument, question_kind: QuestionKind) -> None:
    """Check that the questions have the fields their kind needs.

    Usage:
        Call after parsing. Testing questions need a correct answer and at
        least one wrong answer; LLM questions need nothing extra.

    Args:
        quiz_document: Parsed quiz.
        question_kind: Kind stated by the file name.

    Raises:
        InvalidFileContentError: If a testing question is incomplete.
    """
    if question_kind is not QuestionKind.KIND_TESTING:
        return
    for question in quiz_document.questions:
        if question.correct_answer is None or not question.wrong_answers:
            raise InvalidFileContentError(
                f"Question {question.question_id} needs correct_answer and at least one wrong_answer"
            )
