"""Tests of quiz and knowledge base file handling."""

from pathlib import Path

import pytest
from api_helpers import (
    CHOICE_QUIZ,
    CSV_OPEN_QUIZ,
    CSV_QUIZ,
    OPEN_QUIZ,
    TASK_QUIZ,
    dump_quiz,
    prepare_quiz,
    upload_file,
)
from fastapi.testclient import TestClient


def test_quiz_files_are_listed_and_returned(api_client: TestClient) -> None:
    """JSON and CSV quizzes are listed with descriptions and served unchanged."""
    prepare_quiz(api_client)
    assert upload_file(api_client, "/api/test_file", "table_quiz.csv", CSV_QUIZ.encode()).status_code == 201
    assert upload_file(api_client, "/api/test_file", "table_llm.csv", CSV_OPEN_QUIZ.encode()).status_code == 201
    assert api_client.get("/api/test_files").json() == [
        {"file_name": "llm/base_llm.json", "description": "1 llm questions"},
        {"file_name": "llm/table_llm.csv", "description": "1 llm questions"},
        {"file_name": "quiz/base_quiz.json", "description": "1 testing questions"},
        {"file_name": "quiz/table_quiz.csv", "description": "1 testing questions"},
    ]
    csv_response = api_client.get("/api/test_file", params={"file_name": "quiz/table_quiz.csv"})
    assert csv_response.text == CSV_QUIZ
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert api_client.get("/api/test_file", params={"file_name": "llm/base_llm.json"}).json() == OPEN_QUIZ


def test_quiz_upload_is_validated(api_client: TestClient) -> None:
    """Bad quizzes are refused, and existing quizzes are not overwritten."""
    prepare_quiz(api_client)
    route_path = "/api/test_file"
    assert upload_file(api_client, route_path, "base_quiz.json", dump_quiz(CHOICE_QUIZ)).status_code == 409
    assert upload_file(api_client, route_path, "broken_quiz.json", b"{").status_code == 400
    assert upload_file(api_client, route_path, "nested_quiz.json", b"[" * 90_000).status_code == 400
    assert upload_file(api_client, route_path, "binary_quiz.csv", b"\xff\xfe").status_code == 400
    assert upload_file(api_client, route_path, "scalar_llm.json", b"[1, 2]").status_code == 400
    assert upload_file(api_client, route_path, "base_quiz.txt", dump_quiz(CHOICE_QUIZ)).status_code == 400
    repeated = [{"id": 1, "question_text": "One"}, {"id": 1, "question_text": "Two"}]
    assert upload_file(api_client, route_path, "repeat_llm.json", dump_quiz(repeated)).status_code == 400


def test_english_names_receive_descriptions(api_client: TestClient, tmp_path: Path) -> None:
    """English files with the kind at the start of the name are described.

    Args:
        api_client: Test client.
        tmp_path: Folder holding the temporary quiz store.
    """
    quiz_root = tmp_path / "quizzes"
    (quiz_root / "quiz").mkdir(parents=True)
    (quiz_root / "llm").mkdir(parents=True)
    (quiz_root / "interview").mkdir(parents=True)
    (quiz_root / "quiz" / "quiz_sample.json").write_bytes(dump_quiz(CHOICE_QUIZ))
    (quiz_root / "llm" / "llm_sample.json").write_bytes(dump_quiz(OPEN_QUIZ))
    (quiz_root / "interview" / "task_sample.json").write_bytes(dump_quiz(TASK_QUIZ))
    assert api_client.get("/api/test_files").json() == [
        {"file_name": "interview/task_sample.json", "description": "1 task questions"},
        {"file_name": "llm/llm_sample.json", "description": "1 llm questions"},
        {"file_name": "quiz/quiz_sample.json", "description": "1 testing questions"},
    ]


def test_folder_states_description_kind(api_client: TestClient, tmp_path: Path) -> None:
    """A file whose name states no kind is described from its folder.

    Args:
        api_client: Test client.
        tmp_path: Folder holding the temporary quiz store.
    """
    quiz_root = tmp_path / "quizzes"
    (quiz_root / "quiz").mkdir(parents=True)
    (quiz_root / "llm").mkdir(parents=True)
    (quiz_root / "interview").mkdir(parents=True)
    (quiz_root / "other").mkdir(parents=True)
    (quiz_root / "quiz" / "sample_topic.json").write_bytes(dump_quiz(CHOICE_QUIZ))
    (quiz_root / "llm" / "sample_topic.json").write_bytes(dump_quiz(OPEN_QUIZ))
    (quiz_root / "interview" / "sample_topic.json").write_bytes(dump_quiz(TASK_QUIZ))
    (quiz_root / "other" / "sample_topic.json").write_bytes(dump_quiz(CHOICE_QUIZ))
    assert api_client.get("/api/test_files").json() == [
        {"file_name": "interview/sample_topic.json", "description": "1 task questions"},
        {"file_name": "llm/sample_topic.json", "description": "1 llm questions"},
        {"file_name": "other/sample_topic.json", "description": ""},
        {"file_name": "quiz/sample_topic.json", "description": "1 testing questions"},
    ]


def test_file_name_states_question_kind(api_client: TestClient) -> None:
    """Names without a kind are refused, and _quiz files need wrong answers."""
    assert upload_file(api_client, "/api/test_file", "plain.json", dump_quiz(CHOICE_QUIZ)).status_code == 400
    assert upload_file(api_client, "/api/test_file", "open_quiz.json", dump_quiz(OPEN_QUIZ)).status_code == 400
    no_correct = [{"id": 1, "question_text": "Pick", "wrong_answer_1": "second"}]
    assert upload_file(api_client, "/api/test_file", "half_quiz.json", dump_quiz(no_correct)).status_code == 400


@pytest.mark.parametrize(
    "file_name",
    [
        "../secret.json",
        "..\\secret.json",
        "/etc/passwd",
        "a..b.json",
        ".hidden.json",
        "folder/../../secret_quiz.json",
        "folder//x_quiz.json",
        ".git/x_quiz.json",
        "folder/",
        "a/b/c/d/e/f/g/h/i_quiz.json",
    ],
)
def test_path_traversal_is_rejected(api_client: TestClient, file_name: str) -> None:
    """Unsafe names are refused for reading and writing.

    Args:
        api_client: Test client.
        file_name: Unsafe file name.
    """
    assert api_client.get("/api/test_file", params={"file_name": file_name}).status_code == 400
    assert api_client.get("/api/knowledge_base_file", params={"name": file_name}).status_code == 400


def test_upload_size_is_limited(api_client: TestClient) -> None:
    """Bodies over the limit are refused."""
    response = upload_file(api_client, "/api/knowledge_base_file", "large.md", b"x" * 200_000)
    assert response.status_code == 413


def test_knowledge_files_can_be_overwritten(api_client: TestClient) -> None:
    """A second upload replaces the first; only .md files are accepted."""
    for raw_content in (b"old", b"new"):
        assert upload_file(api_client, "/api/knowledge_base_file", "topic.md", raw_content).status_code == 201
    assert api_client.get("/api/knowledge_base_files").json() == ["topic.md"]
    assert api_client.get("/api/knowledge_base_file", params={"name": "topic.md"}).text == "new"
    assert upload_file(api_client, "/api/knowledge_base_file", "topic.json", b"{}").status_code == 400
    assert api_client.get("/api/knowledge_base_file", params={"name": "absent.md"}).status_code == 404
