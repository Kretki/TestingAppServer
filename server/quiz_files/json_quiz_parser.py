"""Parser of .json quiz files."""

import json

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
