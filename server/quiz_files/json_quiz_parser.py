"""Parser of .json quiz files."""

import json
from collections.abc import Collection

from server.contracts.domain_errors import InvalidFileContentError
from server.contracts.quiz_models import QuizDocument


class JsonQuizParser:
    """Parser of quizzes stored as a JSON array of question objects.

    Usage:
        Register for the .json extension.

    Attributes:
        media_type: HTTP media type of the format.
    """

    media_type = "application/json"

    def parse_quiz(self, raw_content: bytes) -> QuizDocument:
        """Parse and validate a JSON quiz.

        Usage:
            Call for uploaded and stored .json files.

        Args:
            raw_content: UTF-8 encoded array of objects with the same keys as
                the CSV columns.

        Returns:
            The validated quiz.

        Raises:
            InvalidFileContentError: If the content is not a valid quiz.
        """
        try:
            return QuizDocument.model_validate({"questions": json.loads(raw_content)})
        except (ValueError, RecursionError) as parse_error:
            raise InvalidFileContentError(f"Invalid JSON quiz: {parse_error}") from parse_error

    def remove_fields(self, raw_content: bytes, hidden_fields: Collection[str]) -> bytes:
        """Remove fields from every question object.

        Usage:
            Call before a file with secret fields leaves the server.

        Args:
            raw_content: Bytes of a valid JSON quiz.
            hidden_fields: Names of the fields to remove.

        Returns:
            The file without the fields, unchanged when it has none of them.

        Raises:
            InvalidFileContentError: If the content is not a question array.
        """
        try:
            questions = json.loads(raw_content)
            public_questions = [
                {
                    field_name: field_value
                    for field_name, field_value in question.items()
                    if field_name not in hidden_fields
                }
                for question in questions
            ]
        except (ValueError, RecursionError, AttributeError, TypeError) as parse_error:
            raise InvalidFileContentError(f"Invalid JSON quiz: {parse_error}") from parse_error
        if public_questions == questions:
            return raw_content
        return json.dumps(public_questions, ensure_ascii=False, indent=2).encode("utf-8")
