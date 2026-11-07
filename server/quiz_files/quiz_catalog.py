"""Operations on the collection of quiz files."""

import logging
from collections.abc import Mapping
from pathlib import PurePath

from server.contracts.domain_errors import (
    InvalidFileContentError,
    InvalidFileNameError,
    QuestionMissingError,
    QuestionTypeError,
)
from server.contracts.quiz_models import QuizDocument, QuizFile, QuizQuestion, QuizSummary
from server.contracts.service_contracts import FileRepository, QuizParser
from server.quiz_files.question_kinds import QuestionKind, find_question_kind, require_kind_fields

MODULE_LOGGER = logging.getLogger(__name__)


class QuizCatalog:
    """Listing, reading, validation and storing of quizzes.

    Usage:
        Create once at start-up and share between requests.
    """

    def __init__(self, repository: FileRepository, quiz_parsers: Mapping[str, QuizParser]) -> None:
        """Store the dependencies.

        Usage:
            Call at start-up.

        Args:
            repository: Storage of quiz files. It must only accept extensions
                present in `quiz_parsers`.
            quiz_parsers: Lower-case file extensions mapped to parsers.
        """
        self._repository = repository
        self._quiz_parsers = quiz_parsers

    def list_quizzes(self) -> list[QuizSummary]:
        """List all quizzes with their descriptions.

        Usage:
            Call to serve the list of quizzes. An unusable file is logged and
            listed with an empty description.

        Returns:
            One summary per stored quiz file.
        """
        return [
            QuizSummary(file_name=file_name, description=self._read_description(file_name))
            for file_name in self._repository.list_names()
        ]

    def read_quiz(self, file_name: str) -> QuizFile:
        """Read a quiz file without changing it.

        Usage:
            Call to serve a quiz to a client.

        Args:
            file_name: Name of the quiz file.

        Returns:
            The file bytes and media type.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
        """
        raw_content = self._repository.read_bytes(file_name)
        return QuizFile(raw_content=raw_content, media_type=self._parser_for(file_name).media_type)

    def add_quiz(self, file_name: str, raw_content: bytes) -> None:
        """Validate and store a new quiz.

        Usage:
            Call for quiz uploads. Existing quizzes are never replaced, because
            clients may hold ids of their questions.

        Args:
            file_name: Name of the new file.
            raw_content: Bytes of the file.

        Raises:
            InvalidFileNameError: If the name is not allowed or does not state
                a question kind.
            InvalidFileContentError: If the content is not a valid quiz.
            StoredFileConflictError: If the file already exists.
        """
        self._parse_validated(file_name, raw_content)
        self._repository.write_bytes(file_name, raw_content, allow_overwrite=False)

    def find_open_question(self, file_name: str, question_id: str) -> QuizQuestion:
        """Find a question that is checked by the LLM.

        Usage:
            Call before starting an LLM check.

        Args:
            file_name: Name of the quiz file.
            question_id: Id of the question inside the quiz.

        Returns:
            The question.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
            InvalidFileContentError: If the stored file is corrupt.
            QuestionMissingError: If the quiz has no such question.
            QuestionTypeError: If the file is not an _llm file.
        """
        if find_question_kind(file_name) is not QuestionKind.KIND_LLM:
            raise QuestionTypeError(f"Questions of {file_name} are checked on the client")
        quiz_document = self._parse_validated(file_name, self._repository.read_bytes(file_name))
        for question in quiz_document.questions:
            if question.question_id == question_id:
                return question
        raise QuestionMissingError(f"Question not found: {question_id}")

    def _parser_for(self, file_name: str) -> QuizParser:
        """Select the parser for a file.

        Usage:
            Internal lookup. Call after, or together with, repository name
            validation; unknown extensions are reported as invalid content.

        Args:
            file_name: Name of the quiz file.

        Returns:
            The parser of the file's format.

        Raises:
            InvalidFileContentError: If no parser handles the extension.
        """
        quiz_parser = self._quiz_parsers.get(PurePath(file_name).suffix.lower())
        if quiz_parser is None:
            raise InvalidFileContentError(f"Unsupported quiz format: {file_name!r}")
        return quiz_parser

    def _parse_validated(self, file_name: str, raw_content: bytes) -> QuizDocument:
        """Parse a quiz and check it against the kind stated by its name.

        Usage:
            Internal step of every operation that uses questions.

        Args:
            file_name: Name of the file, which selects format and kind.
            raw_content: Bytes of the file.

        Returns:
            The validated quiz.

        Raises:
            InvalidFileNameError: If the name does not state a question kind.
            InvalidFileContentError: If the content is not a valid quiz.
        """
        question_kind = find_question_kind(file_name)
        quiz_document = self._parser_for(file_name).parse_quiz(raw_content)
        require_kind_fields(quiz_document, question_kind)
        return quiz_document

    def _read_description(self, file_name: str) -> str:
        """Generate the description of a stored quiz.

        Usage:
            Internal step of `list_quizzes`.

        Args:
            file_name: Name of the quiz file.

        Returns:
            Text such as "12 testing questions", or an empty string for an
            unusable file.
        """
        try:
            quiz_document = self._parse_validated(file_name, self._repository.read_bytes(file_name))
        except (InvalidFileContentError, InvalidFileNameError):
            MODULE_LOGGER.warning("Quiz file %s is unusable", file_name)
            return ""
        return f"{len(quiz_document.questions)} {find_question_kind(file_name).value} questions"
