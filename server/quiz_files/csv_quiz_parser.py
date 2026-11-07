"""Parser of .csv quiz files."""

import csv
import io

from server.contracts.domain_errors import InvalidFileContentError
from server.contracts.quiz_models import QuizDocument


class CsvQuizParser:
    """Parser of quizzes stored as a table with one question per row.

    Usage:
        Register for the .csv extension.

    Attributes:
        media_type: HTTP media type of the format.
    """

    media_type = "text/csv"

    def parse_quiz(self, raw_content: bytes) -> QuizDocument:
        """Parse and validate a CSV quiz.

        Usage:
            Call for uploaded and stored .csv files.

        Args:
            raw_content: UTF-8 encoded CSV with the columns id, question_name,
                question_text, correct_answer, wrong_answer_1 to wrong_answer_10,
                knowledge_file.

        Returns:
            The validated quiz.

        Raises:
            InvalidFileContentError: If the content is not a valid quiz.
        """
        try:
            table_rows = csv.DictReader(io.StringIO(raw_content.decode("utf-8-sig")))
            return QuizDocument.model_validate({"questions": list(table_rows)})
        except (ValueError, csv.Error) as parse_error:
            raise InvalidFileContentError(f"Invalid CSV quiz: {parse_error}") from parse_error
