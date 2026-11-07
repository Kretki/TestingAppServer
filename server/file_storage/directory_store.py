"""File repository confined to one directory."""

import os
import re
import tempfile
from collections.abc import Collection
from pathlib import Path, PurePosixPath

from server.contracts.domain_errors import InvalidFileNameError, StoredFileConflictError, StoredFileMissingError

MAX_PART_LENGTH = 128
MAX_PATH_LENGTH = 512
MAX_PATH_DEPTH = 8
SAFE_PATH_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]*")


def is_safe_part(path_part: str) -> bool:
    """Tell whether one folder or file name is safe.

    Usage:
        Call for every part of a relative path.

    Args:
        path_part: Text between two "/" separators.

    Returns:
        True for a non-hidden name of allowed characters without "..".
    """
    return len(path_part) <= MAX_PART_LENGTH and bool(SAFE_PATH_PART.fullmatch(path_part)) and ".." not in path_part


class DirectoryStore:
    """Store of files in a folder tree, addressed by relative "/" paths.

    Usage:
        Create one per root folder. Every path is checked here, so callers can
        pass user-supplied paths directly.
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
        """List the files of the folder tree that have an allowed extension.

        Usage:
            Call to enumerate the tree. Hidden and unsafe paths are skipped.

        Returns:
            Sorted relative paths with "/" separators.
        """
        relative_names = (
            folder_entry.relative_to(self._root_directory).as_posix()
            for folder_entry in self._root_directory.rglob("*")
            if folder_entry.is_file()
        )
        return sorted(file_name for file_name in relative_names if self._is_allowed_name(file_name))

    def read_bytes(self, file_name: str) -> bytes:
        """Read one file.

        Usage:
            Call to fetch file content.

        Args:
            file_name: Relative path of the file, possibly user-supplied.

        Returns:
            The file content.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileMissingError: If the file does not exist.
        """
        try:
            return self._resolve_path(file_name).read_bytes()
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as missing_error:
            raise StoredFileMissingError(f"File not found: {file_name}") from missing_error

    def write_bytes(self, file_name: str, raw_content: bytes, allow_overwrite: bool) -> None:
        """Store one file.

        Usage:
            Call to add or replace a file.

        Args:
            file_name: Relative path of the file, possibly user-supplied. Missing
                folders are created.
            raw_content: Content to store.
            allow_overwrite: Whether an existing file may be replaced.

        Raises:
            InvalidFileNameError: If the name is not allowed.
            StoredFileConflictError: If the file exists and may not be
                replaced, or a part of the path is already in use.
        """
        target_path = self._resolve_path(file_name)
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if allow_overwrite:
                self._replace_file(target_path, raw_content)
            else:
                self._create_file(target_path, raw_content)
        except (FileExistsError, NotADirectoryError, IsADirectoryError) as conflict_error:
            raise StoredFileConflictError(f"Path is already in use: {file_name}") from conflict_error

    def _is_allowed_name(self, file_name: str) -> bool:
        """Tell whether a relative path is safe and has an allowed extension.

        Usage:
            Internal check for listing and for every file access.

        Args:
            file_name: Relative path with "/" separators, possibly user-supplied.

        Returns:
            True when every folder and file name in the path is safe.
        """
        path_parts = file_name.split("/")
        return (
            len(file_name) <= MAX_PATH_LENGTH
            and len(path_parts) <= MAX_PATH_DEPTH
            and all(is_safe_part(path_part) for path_part in path_parts)
            and PurePosixPath(file_name).suffix.lower() in self._allowed_suffixes
        )

    def _resolve_path(self, file_name: str) -> Path:
        """Turn a relative path into a path proven to be inside the folder.

        Usage:
            Call before any file access.

        Args:
            file_name: Relative path with "/" separators, possibly user-supplied.

        Returns:
            Absolute path of the file.

        Raises:
            InvalidFileNameError: If the path is unsafe, has a disallowed
                extension or resolves outside the folder.
        """
        if not self._is_allowed_name(file_name):
            raise InvalidFileNameError(f"Invalid file name: {file_name!r}")
        target_path = (self._root_directory / file_name).resolve()
        if not target_path.is_relative_to(self._root_directory):
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
            FileExistsError: If the file exists.
        """
        with target_path.open("xb") as target_file:
            target_file.write(raw_content)

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
