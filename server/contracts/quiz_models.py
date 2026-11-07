"""Validated domain models of a quiz file."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_QUESTIONS = 1000
MAX_WRONG_ANSWERS = 10
MAX_TEXT_LENGTH = 4000
MAX_IDENTIFIER_LENGTH = 64
MAX_FILE_NAME_LENGTH = 128

QuizText = Annotated[str, Field(min_length=1, max_length=MAX_TEXT_LENGTH)]


class QuizQuestion(BaseModel):
    """One question of a quiz; CSV rows and JSON objects share these keys.

    Usage:
        Built by quiz parsers from a flat mapping with the keys id,
        question_name, question_text, correct_answer, wrong_answer_1 to
        wrong_answer_10 and knowledge_file. The name of the file states how
        its questions are checked.

    Attributes:
        question_id: Identifier unique inside its quiz (key "id").
        question_name: Short name of the question, may be empty.
        question_text: Text shown to the user.
        correct_answer: Correct answer. Required in _quiz files, optional
            reference for the LLM in _llm files.
        wrong_answers: Up to 10 wrong answers.
        knowledge_file: Optional knowledge base .md file, given to the LLM as
            reference material.
    """

    model_config = ConfigDict(coerce_numbers_to_str=True)

    question_id: Annotated[str, Field(alias="id", min_length=1, max_length=MAX_IDENTIFIER_LENGTH)]
    question_name: Annotated[str, Field(max_length=MAX_TEXT_LENGTH)] = ""
    question_text: QuizText
    correct_answer: QuizText | None = None
    wrong_answers: Annotated[list[QuizText], Field(max_length=MAX_WRONG_ANSWERS)] = []
    knowledge_file: Annotated[str, Field(max_length=MAX_FILE_NAME_LENGTH)] | None = None

    @model_validator(mode="before")
    @classmethod
    def collect_wrong_answers(cls, raw_question: object) -> object:
        """Gather numbered wrong answer keys and drop blank values.

        Usage:
            Run by pydantic before field validation.

        Args:
            raw_question: Flat mapping from a parser, or any other JSON value,
                which is left for field validation to refuse.

        Returns:
            Mapping with a `wrong_answers` list and no blank values.
        """
        if not isinstance(raw_question, dict):
            return raw_question
        filled_values = {
            field_name: field_value for field_name, field_value in raw_question.items() if field_value not in (None, "")
        }
        numbered_keys = [f"wrong_answer_{answer_number}" for answer_number in range(1, MAX_WRONG_ANSWERS + 1)]
        wrong_answers = [filled_values[field_name] for field_name in numbered_keys if field_name in filled_values]
        return {**filled_values, "wrong_answers": wrong_answers}


class QuizDocument(BaseModel):
    """Parsed content of one quiz file.

    Usage:
        Returned by quiz parsers.

    Attributes:
        questions: Between 1 and 1000 questions.
    """

    questions: Annotated[list[QuizQuestion], Field(min_length=1, max_length=MAX_QUESTIONS)]

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        """Check that no two questions share an id.

        Usage:
            Run by pydantic after field validation.

        Returns:
            The validated document.

        Raises:
            ValueError: If a question id is repeated.
        """
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("id values must be unique inside a quiz")
        return self


class QuizSummary(BaseModel):
    """One entry of the list of quizzes.

    Usage:
        Returned by `QuizCatalog.list_quizzes`.

    Attributes:
        file_name: Name of the quiz file.
        description: Generated summary, empty for an unusable file.
    """

    file_name: str
    description: str


class QuizFile(BaseModel):
    """Raw quiz file ready to be sent to a client.

    Usage:
        Returned by `QuizCatalog.read_quiz`.

    Attributes:
        raw_content: Exact bytes of the file.
        media_type: HTTP media type of the file.
    """

    raw_content: bytes
    media_type: str
