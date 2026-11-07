"""Translation of domain errors to HTTP responses."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from server.contracts import domain_errors

ERROR_STATUS_CODES: dict[type[domain_errors.QuizServerError], int] = {
    domain_errors.InvalidFileNameError: status.HTTP_400_BAD_REQUEST,
    domain_errors.InvalidFileContentError: status.HTTP_400_BAD_REQUEST,
    domain_errors.QuestionTypeError: status.HTTP_400_BAD_REQUEST,
    domain_errors.StoredFileMissingError: status.HTTP_404_NOT_FOUND,
    domain_errors.QuestionMissingError: status.HTTP_404_NOT_FOUND,
    domain_errors.GradingRequestMissingError: status.HTTP_404_NOT_FOUND,
    domain_errors.StoredFileConflictError: status.HTTP_409_CONFLICT,
    domain_errors.GradingQueueFullError: status.HTTP_503_SERVICE_UNAVAILABLE,
    domain_errors.InstructionFileError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


async def render_domain_error(_: Request, domain_error: Exception) -> JSONResponse:
    """Build the JSON response of a domain error.

    Usage:
        Registered by `register_error_handlers`.

    Args:
        _: Current request, unused.
        domain_error: The raised error.

    Returns:
        Response with the mapped status and a `detail` message.
    """
    status_code = ERROR_STATUS_CODES.get(type(domain_error), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(status_code=status_code, content={"detail": str(domain_error)})


def register_error_handlers(application: FastAPI) -> None:
    """Install the domain error handler.

    Usage:
        Call while building the application.

    Args:
        application: Application to configure; it is mutated.
    """
    application.add_exception_handler(domain_errors.QuizServerError, render_domain_error)
