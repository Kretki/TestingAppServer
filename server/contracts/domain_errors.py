"""Errors raised by the service layer and translated to HTTP by the transport layer."""


class QuizServerError(Exception):
    """Base class of every expected, user-reportable failure.

    Usage:
        Subclass for a new failure and register it in `error_handlers.py`.
    """


class InvalidFileNameError(QuizServerError):
    """Raised when a file name is unsafe or has a disallowed extension."""


class StoredFileMissingError(QuizServerError):
    """Raised when a requested file does not exist."""


class StoredFileConflictError(QuizServerError):
    """Raised when a file exists and must not be overwritten."""


class InvalidFileContentError(QuizServerError):
    """Raised when file content does not match the expected format."""


class QuestionMissingError(QuizServerError):
    """Raised when a quiz has no question with the requested id."""


class QuestionTypeError(QuizServerError):
    """Raised when an LLM check is requested for a non-LLM question."""


class GradingQueueFullError(QuizServerError):
    """Raised when too many LLM checks are already in progress."""


class GradingRequestMissingError(QuizServerError):
    """Raised when an LLM check id is unknown or its result has expired."""


class InstructionFileError(QuizServerError):
    """Raised when the LLM instructions file is missing, unreadable or empty."""


class LlmRequestError(QuizServerError):
    """Raised when the LLM API fails or returns an unusable response."""
