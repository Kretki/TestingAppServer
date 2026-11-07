"""File repository confined to one directory."""

import os
import re
import tempfile
from collections.abc import Collection
from pathlib import Path

from server.contracts.domain_errors import InvalidFileNameError, StoredFileConflictError, StoredFileMissingError

MAX_FILE_NAME_LENGTH = 128
SAFE_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]*")


class DirectoryStore:
    """Store of flat files with validated names.

    Usage:
        Create one per folder. Every name is checked here, so callers can pass
        user-supplied names directly.
    """

    def __init__(self, root_directory: Path, allowed_suffixes: Collection[str]) -> None:
        """Create the store and its folder when missing.

        Usage:
            Call at start-up.

        Args:
            root_directory: Folder that holds the files.
            allowed_suffixes: Lower-case extensions with a leading dot.

        Raises:
            OSError: If the folder cannot be created.
        """
        root_directory.mkdir(parents=True, exist_ok=True)
        self._root_directory = root_directory.resolve()
        self._allowed_suffixes = frozenset(allowed_suffixes)

    def list_names(self) -> list[str]:
        """List the files that have an allowed extension.

        Usage:
            Call to enumerate the folder.

        Returns:
            Sorted file names.
        """
        return sorted(
            folder_entry.name
            for folder_entry in self._root_directory.iterdir()
            if folder_entry.is_file() and folder_entry.suffix.lower() in self._allowed_suffixes
        )

    def read_bytes(self, file_name: str) -> bytes:
        """Read one file.

        Usage:
            Call to fetch file content.

        Args:
            file_name: Name of the file, possibly user-supplied.

        Returns:
            The file content.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
        """
        try:
            return self._resolve_path(file_name).read_bytes()
        except (FileNotFoundError, IsADirectoryError) as missing_error:
            raise StoredFileMissingError(f"File not found: {file_name}") from missing_error

    def write_bytes(self, file_name: str, raw_content: bytes, allow_overwrite: bool) -> None:
        """Store one file.

        Usage:
            Call to add or replace a file.

        Args:
            file_name: Name of the file, possibly user-supplied.
            raw_content: Content to store.
            allow_overwrite: Whether an existing file may be replaced.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileConflictError: If the file exists and may not be replaced.
        """
        target_path = self._resolve_path(file_name)
        if allow_overwrite:
            self._replace_file(target_path, raw_content)
        else:
            self._create_file(target_path, raw_content)

    def _resolve_path(self, file_name: str) -> Path:
        """Turn a file name into a path proven to be inside the folder.

        Usage:
            Call before any file access.

        Args:
            file_name: Name of the file, possibly user-supplied.

        Returns:
            Absolute path of the file.

        Raises:
            InvalidFileNameError: If the name is unsafe, has a disallowed
                extension or resolves outside the folder.
        """
        is_safe_name = (
            len(file_name) <= MAX_FILE_NAME_LENGTH and SAFE_FILE_NAME.fullmatch(file_name) and ".." not in file_name
        )
        if not is_safe_name or Path(file_name).suffix.lower() not in self._allowed_suffixes:
            raise InvalidFileNameError(f"Invalid file name: {file_name!r}")
        target_path = (self._root_directory / file_name).resolve()
        if target_path.parent != self._root_directory:
            raise InvalidFileNameError(f"Invalid file name: {file_name!r}")
        return target_path

    @staticmethod
    def _create_file(target_path: Path, raw_content: bytes) -> None:
        """Write a new file, failing when it exists.

        Usage:
            Internal step of `write_bytes`.

        Args:
            target_path: Validated destination.
            raw_content: Content to store.

        Raises:
            StoredFileConflictError: If the file exists.
        """
        try:
            with target_path.open("xb") as target_file:
                target_file.write(raw_content)
        except FileExistsError as exists_error:
            raise StoredFileConflictError(f"File already exists: {target_path.name}") from exists_error

    @staticmethod
    def _replace_file(target_path: Path, raw_content: bytes) -> None:
        """Write a file atomically, replacing any previous version.

        Usage:
            Internal step of `write_bytes`. Readers see the old or the new
            content, never a partial file.

        Args:
            target_path: Validated destination.
            raw_content: Content to store.
        """
        with tempfile.NamedTemporaryFile(dir=target_path.parent, suffix=".tmp", delete=False) as staging_file:
            staging_file.write(raw_content)
        os.replace(staging_file.name, target_path)
