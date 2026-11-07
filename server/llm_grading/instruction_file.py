"""Grading instructions kept in an externally managed file."""

from pathlib import Path

from server.contracts.domain_errors import InstructionFileError


class InstructionFile:
    """Text file with the system prompt of the LLM.

    Usage:
        Create once at start-up. The file is read on every call, so edits
        apply to the next answer without a restart.
    """

    def __init__(self, file_path: Path) -> None:
        """Store the location of the file.

        Usage:
            Call at start-up.

        Args:
            file_path: Path of the UTF-8 instructions file.
        """
        self._file_path = file_path

    def read_instructions(self) -> str:
        """Read the current instructions.

        Usage:
            Call for every submitted answer.

        Returns:
            The file text, never empty.

        Raises:
            InstructionFileError: If the file is missing, unreadable or empty.
        """
        try:
            instructions = self._file_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as read_error:
            raise InstructionFileError(f"Cannot read LLM instructions: {self._file_path.name}") from read_error
        if not instructions:
            raise InstructionFileError(f"LLM instructions are empty: {self._file_path.name}")
        return instructions
