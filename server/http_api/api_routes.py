"""REST routes; handlers only translate between HTTP and the services.

File handlers are synchronous so that FastAPI runs their disk access in its
thread pool instead of on the event loop.
"""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Response, UploadFile, status

from server.contracts.quiz_models import QuizSummary
from server.http_api.api_schemas import (
    MAX_NAME_LENGTH,
    LlmAnswerRequest,
    LlmAnswerResult,
    LlmAnswerTicket,
    UploadResult,
)
from server.http_api.service_access import CatalogAccess, GradingAccess, LibraryAccess, require_upload_name
from server.llm_grading.prompt_builder import AnswerAttempt

MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"

FileNameQuery = Annotated[str, Query(min_length=1, max_length=MAX_NAME_LENGTH)]
KnowledgeNameQuery = Annotated[str, Query(alias="name", min_length=1, max_length=MAX_NAME_LENGTH)]

api_router = APIRouter(prefix="/api")


@api_router.get("/test_files")
def list_test_files(quiz_catalog: CatalogAccess) -> list[QuizSummary]:
    """List the quiz files with their descriptions.

    Usage:
        GET /api/test_files

    Args:
        quiz_catalog: Injected catalog.

    Returns:
        One entry per quiz file.
    """
    return quiz_catalog.list_quizzes()


@api_router.get("/test_file")
def read_test_file(file_name: FileNameQuery, quiz_catalog: CatalogAccess) -> Response:
    """Return the content of one quiz file.

    Usage:
        GET /api/test_file?file_name=folder/sample_quiz.json

    Args:
        file_name: Relative path of the quiz file.
        quiz_catalog: Injected catalog.

    Returns:
        The file with its media type, without secret fields.

    Raises:
        QuizServerError: If the name is invalid or the file is missing.
    """
    quiz_file = quiz_catalog.read_quiz(file_name)
    return Response(content=quiz_file.raw_content, media_type=quiz_file.media_type)


@api_router.post("/test_file", status_code=status.HTTP_201_CREATED)
def upload_test_file(uploaded_file: UploadFile, quiz_catalog: CatalogAccess) -> UploadResult:
    """Store a new quiz file.

    Usage:
        POST /api/test_file as multipart form with the field `uploaded_file`.
        Its file name may be a relative path. The file is stored inside the
        folder of its kind (quiz, llm or interview), and missing folders are
        created.

    Args:
        uploaded_file: The .json or .csv file, named _quiz, _llm or _task.
        quiz_catalog: Injected catalog.

    Returns:
        The relative path under which the file was stored.

    Raises:
        QuizServerError: If the name or content is invalid or the file exists.
    """
    file_name = require_upload_name(uploaded_file)
    return UploadResult(file_name=quiz_catalog.add_quiz(file_name, uploaded_file.file.read()))


@api_router.post("/llm_answer", status_code=status.HTTP_202_ACCEPTED)
def submit_llm_answer(
    answer_request: LlmAnswerRequest, background_tasks: BackgroundTasks, grading_service: GradingAccess
) -> LlmAnswerTicket:
    """Accept an answer for checking by the LLM.

    Usage:
        POST /api/llm_answer, then poll GET /api/llm_answer.

    Args:
        answer_request: Quiz file, question id, answer and attempt numbers.
        background_tasks: Injected scheduler.
        grading_service: Injected service.

    Returns:
        The generated request id.

    Raises:
        QuizServerError: If the question is unusable or the queue is full.
    """
    answer_attempt = AnswerAttempt(
        answer_request.user_answer, answer_request.current_attempt, answer_request.max_attempts
    )
    pending_grading = grading_service.submit_answer(
        answer_request.test_file, answer_request.question_id, answer_attempt
    )
    background_tasks.add_task(grading_service.run_grading, pending_grading)
    return LlmAnswerTicket(request_id=pending_grading.request_id)


@api_router.get("/llm_answer")
def read_llm_answer(request_id: UUID, grading_service: GradingAccess) -> LlmAnswerResult:
    """Return the state of an LLM check.

    Usage:
        GET /api/llm_answer?request_id=<id>

    Args:
        request_id: Id from POST /api/llm_answer.
        grading_service: Injected service.

    Returns:
        The state, with the LLM answer once it is ready.

    Raises:
        QuizServerError: If the id is unknown or expired.
    """
    return LlmAnswerResult(**asdict(grading_service.find_result(str(request_id))))


@api_router.get("/knowledge_base_files")
def list_knowledge_files(knowledge_library: LibraryAccess) -> list[str]:
    """List the knowledge base files.

    Usage:
        GET /api/knowledge_base_files

    Args:
        knowledge_library: Injected library.

    Returns:
        Sorted .md file names.
    """
    return knowledge_library.list_documents()


@api_router.get("/knowledge_base_file")
def read_knowledge_file(file_name: KnowledgeNameQuery, knowledge_library: LibraryAccess) -> Response:
    """Return one knowledge base file.

    Usage:
        GET /api/knowledge_base_file?name=folder/sample_topic.md

    Args:
        file_name: Relative path of the .md file.
        knowledge_library: Injected library.

    Returns:
        The file as Markdown.

    Raises:
        QuizServerError: If the name is invalid or the file is missing.
    """
    return Response(content=knowledge_library.read_document(file_name), media_type=MARKDOWN_MEDIA_TYPE)


@api_router.post("/knowledge_base_file", status_code=status.HTTP_201_CREATED)
def upload_knowledge_file(uploaded_file: UploadFile, knowledge_library: LibraryAccess) -> UploadResult:
    """Store a knowledge base file, overwriting a file of the same name.

    Usage:
        POST /api/knowledge_base_file as multipart form with the field
        `uploaded_file`. Its file name may be a relative path; missing folders
        are created.

    Args:
        uploaded_file: The .md file.
        knowledge_library: Injected library.

    Returns:
        The stored file name.

    Raises:
        QuizServerError: If the name or content is invalid.
    """
    file_name = require_upload_name(uploaded_file)
    knowledge_library.save_document(file_name, uploaded_file.file.read())
    return UploadResult(file_name=file_name)
