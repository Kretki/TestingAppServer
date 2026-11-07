"""Parser of .csv quiz files."""

import csv
import io
from collections.abc import Collection

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
                knowledge_file, llm_system_explanation.

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

    def remove_fields(self, raw_content: bytes, hidden_fields: Collection[str]) -> bytes:
        """Remove columns from the table.

        Usage:
            Call before a file with secret fields leaves the server.

        Args:
            raw_content: Bytes of a valid CSV quiz.
            hidden_fields: Names of the columns to remove.

        Returns:
            The file without the columns, unchanged when it has none of them.

        Raises:
            InvalidFileContentError: If the content cannot be read.
        """
        try:
            table_reader = csv.DictReader(io.StringIO(raw_content.decode("utf-8-sig")))
            column_names = list(table_reader.fieldnames or [])
            public_columns = [column_name for column_name in column_names if column_name not in hidden_fields]
            if public_columns == column_names:
                return raw_content
            output_buffer = io.StringIO()
            table_writer = csv.DictWriter(output_buffer, public_columns, extrasaction="ignore", lineterminator="\n")
            table_writer.writeheader()
            table_writer.writerows(table_reader)
        except (ValueError, csv.Error) as parse_error:
            raise InvalidFileContentError(f"Invalid CSV quiz: {parse_error}") from parse_error
        return output_buffer.getvalue().encode("utf-8")
