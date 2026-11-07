"""Pytest fixtures of the API tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from api_helpers import FakeChatModel
from fastapi.testclient import TestClient

from server.application import create_application
from server.configuration.server_settings import ServerSettings


@pytest.fixture(name="chat_model")
def build_chat_model() -> FakeChatModel:
    """Provide a fresh fake model.

    Returns:
        The fake model.
    """
    return FakeChatModel()


@pytest.fixture(name="api_client")
def build_api_client(tmp_path: Path, chat_model: FakeChatModel) -> Iterator[TestClient]:
    """Provide a client of an application with empty temporary folders.

    Args:
        tmp_path: Temporary folder from pytest.
        chat_model: Fake model.

    Yields:
        The test client.
    """
    (tmp_path / "llm_input.md").write_text("First instructions", encoding="utf-8")
    settings = ServerSettings(
        instruction_file=tmp_path / "llm_input.md",
        test_directory=tmp_path / "quizzes",
        knowledge_directory=tmp_path / "knowledge",
        max_request_bytes=100_000,
        max_pending_requests=4,
    )
    with TestClient(create_application(settings, chat_model, chat_model)) as test_client:
        yield test_client
