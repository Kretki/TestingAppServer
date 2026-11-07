"""Application wiring and entry point."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from server.configuration.server_settings import ServerSettings, load_settings
from server.contracts.service_contracts import ChatModel, ModelLifecycle, QuizParser
from server.file_storage.directory_store import DirectoryStore
from server.http_api.api_routes import api_router
from server.http_api.error_handlers import register_error_handlers
from server.http_api.request_limits import RequestSizeLimiter
from server.knowledge.knowledge_library import KnowledgeLibrary
from server.llm_grading.grading_jobs import GradingJobStore
from server.llm_grading.grading_service import GradingService
from server.llm_grading.instruction_file import InstructionFile
from server.llm_grading.local_chat_model import GenerationLimits, LocalChatModel
from server.quiz_files.csv_quiz_parser import CsvQuizParser
from server.quiz_files.json_quiz_parser import JsonQuizParser
from server.quiz_files.quiz_catalog import QuizCatalog

QUIZ_PARSERS: dict[str, QuizParser] = {".json": JsonQuizParser(), ".csv": CsvQuizParser()}
KNOWLEDGE_SUFFIXES = (".md",)


def build_chat_model(settings: ServerSettings) -> LocalChatModel:
    """Create the local language model; it is loaded when the server starts.

    Usage:
        Call once from `run_server`.

    Args:
        settings: Server settings.

    Returns:
        The model, not loaded yet.
    """
    generation_limits = GenerationLimits(
        settings.llm_reasoning_effort, settings.llm_max_output_tokens, settings.llm_timeout_seconds
    )
    return LocalChatModel(settings.model_directory, generation_limits)


def attach_services(application: FastAPI, settings: ServerSettings, chat_model: ChatModel) -> None:
    """Build the services and store them on the application.

    Usage:
        Call once while building the application.

    Args:
        application: Application to configure; its state is mutated.
        settings: Server settings.
        chat_model: Model that checks answers.
    """
    quiz_catalog = QuizCatalog(DirectoryStore(settings.test_directory, QUIZ_PARSERS.keys()), QUIZ_PARSERS)
    knowledge_library = KnowledgeLibrary(DirectoryStore(settings.knowledge_directory, KNOWLEDGE_SUFFIXES))
    job_store = GradingJobStore(settings.max_pending_requests, settings.max_stored_results)
    application.state.quiz_catalog = quiz_catalog
    application.state.knowledge_library = knowledge_library
    instruction_source = InstructionFile(settings.instruction_file)
    application.state.grading_service = GradingService(
        quiz_catalog, knowledge_library, instruction_source, chat_model, job_store
    )


def create_application(settings: ServerSettings, chat_model: ChatModel, model_lifecycle: ModelLifecycle) -> FastAPI:
    """Assemble the FastAPI application.

    Usage:
        Call from `run_server`, or from tests with fakes.

    Args:
        settings: Server settings.
        chat_model: Model that checks answers.
        model_lifecycle: Start and stop hooks of the model.

    Returns:
        The configured application.
    """

    @asynccontextmanager
    async def manage_model(_: FastAPI) -> AsyncIterator[None]:
        """Start loading the model at start-up and stop it at shutdown.

        Usage:
            Passed to FastAPI as lifespan handler.

        Args:
            _: The application, unused.

        Yields:
            Control while the application runs.
        """
        model_lifecycle.start_loading()
        yield
        model_lifecycle.stop_worker()

    application = FastAPI(title="Quiz server", lifespan=manage_model)
    attach_services(application, settings, chat_model)
    application.add_middleware(RequestSizeLimiter, max_request_bytes=settings.max_request_bytes)
    register_error_handlers(application)
    application.include_router(api_router)
    return application


def run_server() -> None:
    """Start the HTTP server; blocks until it stops.

    Usage:
        Entry point of `uv run quiz-server`.

    Raises:
        ValueError: If a numeric environment variable is malformed.
    """
    settings = load_settings(os.environ)
    print(settings)
    chat_model = build_chat_model(settings)
    application = create_application(settings, chat_model, chat_model)
    uvicorn.run(application, host=settings.listen_host, port=settings.listen_port)
