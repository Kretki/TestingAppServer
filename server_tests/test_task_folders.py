"""Tests of interview tasks and folder paths."""

from api_helpers import OPEN_QUIZ, TASK_QUIZ, FakeChatModel, dump_quiz, submit_answer, upload_file
from fastapi.testclient import TestClient


def test_task_secrets_never_reach_the_client(api_client: TestClient) -> None:
    """Solution steps and answers are removed from JSON and CSV task files."""
    assert upload_file(api_client, "/api/test_file", "base_task.json", dump_quiz(TASK_QUIZ)).status_code == 201
    csv_task = "id,question_text,correct_answer,llm_system_explanation\n1,Design a cache,Secret answer,Secret steps\n"
    assert upload_file(api_client, "/api/test_file", "table_task.csv", csv_task.encode()).status_code == 201
    assert api_client.get("/api/test_file", params={"file_name": "base_task.json"}).json() == [
        {"id": 1, "question_name": "Cache", "question_text": "Design a cache"}
    ]
    csv_response = api_client.get("/api/test_file", params={"file_name": "table_task.csv"})
    assert csv_response.text == "id,question_text\n1,Design a cache\n"
    assert csv_response.headers["content-type"].startswith("text/csv")


def test_explanation_is_hidden_in_every_file_kind(api_client: TestClient) -> None:
    """The explanation is removed from _llm files too, and they stay usable."""
    quiz_rows = [OPEN_QUIZ[0] | {"knowledge_file": None, "llm_system_explanation": "Secret steps"}]
    assert upload_file(api_client, "/api/test_file", "other_llm.json", dump_quiz(quiz_rows)).status_code == 201
    served_text = api_client.get("/api/test_file", params={"file_name": "other_llm.json"}).text
    assert "Secret steps" not in served_text
    assert "Bodies attract" in served_text


def test_task_needs_explanation(api_client: TestClient) -> None:
    """A task without its guide is refused."""
    bare_task = [{"id": 1, "question_text": "Design a cache"}]
    assert upload_file(api_client, "/api/test_file", "bare_task.json", dump_quiz(bare_task)).status_code == 400


def test_task_answer_reaches_llm_with_guide(api_client: TestClient, chat_model: FakeChatModel) -> None:
    """A task is checked like an LLM question, with the guide in the prompt.

    Args:
        api_client: Test client.
        chat_model: Fake model.
    """
    assert upload_file(api_client, "/api/test_file", "base_task.json", dump_quiz(TASK_QUIZ)).status_code == 201
    assert submit_answer(api_client, 1, "base_task.json").status_code == 202
    assert api_client.get("/api/test_files").json()[0]["description"] == "1 task questions"
    assert chat_model.user_prompts[0] == (
        "<question>Design a cache</question>\n"
        "<knowledge_base>Reference answer: Secret answer</knowledge_base>\n"
        "<task_guide>Steps: eviction. Hint 1: memory. Hint 2: order.</task_guide>\n"
        '<attempt current="1" max="3" />\n'
        '<user_answer>"Mass bends paths"</user_answer>'
    )


def test_folders_work_in_every_call(api_client: TestClient, chat_model: FakeChatModel) -> None:
    """Relative paths work for upload, listing, reading and LLM checks.

    Args:
        api_client: Test client.
        chat_model: Fake model.
    """
    quiz_rows = [OPEN_QUIZ[0] | {"knowledge_file": "physics/deep/gravity.md"}]
    knowledge_response = upload_file(
        api_client, "/api/knowledge_base_file", "physics/deep/gravity.md", b"Mass attracts"
    )
    assert knowledge_response.json() == {"file_name": "physics/deep/gravity.md"}
    quiz_response = upload_file(api_client, "/api/test_file", "physics/orbit_llm.json", dump_quiz(quiz_rows))
    assert quiz_response.json() == {"file_name": "physics/orbit_llm.json"}
    assert api_client.get("/api/knowledge_base_files").json() == ["physics/deep/gravity.md"]
    assert api_client.get("/api/test_files").json()[0]["file_name"] == "physics/orbit_llm.json"
    assert (
        api_client.get("/api/knowledge_base_file", params={"name": "physics/deep/gravity.md"}).text == "Mass attracts"
    )
    assert api_client.get("/api/test_file", params={"file_name": "physics/orbit_llm.json"}).status_code == 200
    assert submit_answer(api_client, 2, "physics/orbit_llm.json").status_code == 202
    assert "Mass attracts" in chat_model.user_prompts[0]


def test_path_conflicts_are_reported(api_client: TestClient) -> None:
    """A file cannot be used as a folder, and overwriting still works in folders."""
    assert upload_file(api_client, "/api/knowledge_base_file", "topic.md", b"text").status_code == 201
    assert upload_file(api_client, "/api/knowledge_base_file", "topic.md/inner.md", b"text").status_code == 409
    assert api_client.get("/api/knowledge_base_file", params={"name": "topic.md/inner.md"}).status_code == 404
    for raw_content in (b"old", b"new"):
        assert upload_file(api_client, "/api/knowledge_base_file", "deep/topic.md", raw_content).status_code == 201
    assert api_client.get("/api/knowledge_base_file", params={"name": "deep/topic.md"}).text == "new"
