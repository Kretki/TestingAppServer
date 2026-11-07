"""Small protocols that decouple the services from concrete implementations."""

from collections.abc import Collection
from typing import Protocol

from server.contracts.quiz_models import QuizDocument, QuizQuestion


class FileRepository(Protocol):
    """Named-file storage."""

    def list_names(self) -> list[str]:
        """List the stored files.

        Usage:
            Call to enumerate the repository.

        Returns:
            Sorted file names.
        """
        ...

    def read_bytes(self, file_name: str) -> bytes:
        """Read one stored file.

        Usage:
            Call to fetch file content.

        Args:
            file_name: Name of the file.

        Returns:
            The file content.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
        """
        ...

    def write_bytes(self, file_name: str, raw_content: bytes, allow_overwrite: bool) -> None:
        """Store one file.

        Usage:
            Call to add or replace a file.

        Args:
            file_name: Name of the file.
            raw_content: Content to store.
            allow_overwrite: Whether an existing file may be replaced.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileConflictError: If the file exists and may not be replaced.
        """
        ...


class FieldRemover(Protocol):
    """Removal of secret fields from a stored file."""

    def remove_fields(self, raw_content: bytes, hidden_fields: Collection[str]) -> bytes:
        """Remove fields from every question of a file.

        Usage:
            Call before a file with secret fields leaves the server.

        Args:
            raw_content: Bytes of the file.
            hidden_fields: Names of the fields to remove.

        Returns:
            The file without the fields, unchanged when it has none of them.

        Raises:
            InvalidFileContentError: If the content cannot be parsed.
        """
        ...


class QuizParser(FieldRemover, Protocol):
    """Parser of one quiz file format.

    Attributes:
        media_type: HTTP media type of the format.
    """

    media_type: str

    def parse_quiz(self, raw_content: bytes) -> QuizDocument:
        """Parse and validate a quiz file.

        Usage:
            Call for uploaded and stored quiz files.

        Args:
            raw_content: Bytes of the file.

        Returns:
            The validated quiz.

        Raises:
            InvalidFileContentError: If the content is not a valid quiz.
        """
        ...


class OpenQuestionSource(Protocol):
    """Lookup of questions that are checked by the LLM."""

    def find_open_question(self, file_name: str, question_id: str) -> QuizQuestion:
        """Find a free-form question.

        Usage:
            Call before starting an LLM check.

        Args:
            file_name: Name of the quiz file.
            question_id: Id of the question inside the quiz.

        Returns:
            The question.

        Raises:
            QuestionMissingError: If the quiz has no such question.
            QuestionTypeError: If the file is checked on the client.
        """
        ...


class KnowledgeSource(Protocol):
    """Read access to reference documents."""

    def read_text(self, file_name: str) -> str:
        """Read a reference document as text.

        Usage:
            Call to give the LLM reference material.

        Args:
            file_name: Name of the document.

        Returns:
            The document text.

        Raises:
            StoredFileMissingError: If the document does not exist.
        """
        ...


class InstructionSource(Protocol):
    """Provider of the LLM system prompt."""

    def read_instructions(self) -> str:
        """Read the current instructions.

        Usage:
            Call for every submitted answer.

        Returns:
            The instructions, never empty.

        Raises:
            InstructionFileError: If the instructions are unavailable.
        """
        ...


class ModelLifecycle(Protocol):
    """Start and stop hooks of a language model."""

    def start_loading(self) -> None:
        """Begin loading the model without blocking.

        Usage:
            Call when the application starts.
        """
        ...

    def stop_worker(self) -> None:
        """Release the model's background worker.

        Usage:
            Call when the application stops.
        """
        ...


class ChatModel(Protocol):
    """Language model that answers one prompt."""

    async def complete_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a reply.

        Usage:
            Await to run one LLM call.

        Args:
            system_prompt: Instructions for the model.
            user_prompt: Data the model works on.

        Returns:
            The reply text.

        Raises:
            LlmRequestError: If the call fails or the reply is unusable.
        """
        ...
