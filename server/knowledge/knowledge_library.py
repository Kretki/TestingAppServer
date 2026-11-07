"""Operations on the Markdown knowledge base."""

from server.contracts.domain_errors import InvalidFileContentError
from server.contracts.service_contracts import FileRepository


class KnowledgeLibrary:
    """Listing, reading and storing of knowledge base documents.

    Usage:
        Create once at start-up and share between requests.
    """

    def __init__(self, repository: FileRepository) -> None:
        """Store the dependency.

        Usage:
            Call at start-up.

        Args:
            repository: Storage of .md files.
        """
        self._repository = repository

    def list_documents(self) -> list[str]:
        """List the knowledge base.

        Usage:
            Call to serve the list of documents.

        Returns:
            Sorted file names.
        """
        return self._repository.list_names()

    def read_document(self, file_name: str) -> bytes:
        """Read a document's bytes.

        Usage:
            Call to serve a document to a client.

        Args:
            file_name: Name of the .md file.

        Returns:
            The file content.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
        """
        return self._repository.read_bytes(file_name)

    def read_text(self, file_name: str) -> str:
        """Read a document as text.

        Usage:
            Call to give the LLM reference material.

        Args:
            file_name: Name of the .md file.

        Returns:
            The document text.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
            InvalidFileContentError: If the stored file is not UTF-8 text.
        """
        try:
            return self._repository.read_bytes(file_name).decode("utf-8")
        except UnicodeDecodeError as decode_error:
            raise InvalidFileContentError(f"File is not UTF-8 text: {file_name}") from decode_error

    def save_document(self, file_name: str, raw_content: bytes) -> None:
        """Store a document, replacing any file with the same name.

        Usage:
            Call for knowledge base uploads.

        Args:
            file_name: Name of the .md file.
            raw_content: UTF-8 encoded Markdown.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            InvalidFileContentError: If the content is not UTF-8 text.
        """
        try:
            raw_content.decode("utf-8")
        except UnicodeDecodeError as decode_error:
            raise InvalidFileContentError("Markdown file must be UTF-8 text") from decode_error
        self._repository.write_bytes(file_name, raw_content, allow_overwrite=True)
