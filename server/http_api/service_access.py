"""FastAPI dependencies that hand route handlers their services."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, UploadFile, status

from server.knowledge.knowledge_library import KnowledgeLibrary
from server.llm_grading.grading_service import GradingService
from server.quiz_files.quiz_catalog import QuizCatalog


def read_quiz_catalog(http_request: Request) -> QuizCatalog:
    """Return the shared quiz catalog.

    Usage:
        Used through `CatalogAccess`.

    Args:
        http_request: Current request.

    Returns:
        The catalog stored on the application.
    """
    return http_request.app.state.quiz_catalog


def read_knowledge_library(http_request: Request) -> KnowledgeLibrary:
    """Return the shared knowledge library.

    Usage:
        Used through `LibraryAccess`.

    Args:
        http_request: Current request.

    Returns:
        The library stored on the application.
    """
    return http_request.app.state.knowledge_library


def read_grading_service(http_request: Request) -> GradingService:
    """Return the shared grading service.

    Usage:
        Used through `GradingAccess`.

    Args:
        http_request: Current request.

    Returns:
        The service stored on the application.
    """
    return http_request.app.state.grading_service


def require_upload_name(uploaded_file: UploadFile) -> str:
    """Return the client-side name of an upload.

    Usage:
        Call in upload handlers. The name may be a relative path with folders;
        it is validated by the file store.

    Args:
        uploaded_file: Multipart file.

    Returns:
        The file name.

    Raises:
        HTTPException: 400 if the upload has no file name.
    """
    if not uploaded_file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file has no name")
    return uploaded_file.filename


CatalogAccess = Annotated[QuizCatalog, Depends(read_quiz_catalog)]
LibraryAccess = Annotated[KnowledgeLibrary, Depends(read_knowledge_library)]
GradingAccess = Annotated[GradingService, Depends(read_grading_service)]
