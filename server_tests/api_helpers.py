"""Shared sample data, fake model and request helpers of the API tests."""

import json

import httpx
from fastapi.testclient import TestClient

from server.contracts.domain_errors import LlmRequestError

CHOICE_QUIZ = [
    {
        "id": 1,
        "question_name": "Pick",
        "question_text": "Pick one",
        "correct_answer": "first",
        "wrong_answer_1": "second",
        "wrong_answer_2": "third",
    },
]


OPEN_QUIZ = [
    {
        "id": 2,
        "question_name": "Gravity",
        "question_text": "Explain gravity",
        "correct_answer": "Bodies attract",
        "knowledge_file": "gravity.md",
    },
]


WRONG_COLUMNS = ",".join(f"wrong_answer_{answer_number}" for answer_number in range(1, 11))


CSV_HEADER = f"id,question_name,question_text,correct_answer,{WRONG_COLUMNS},knowledge_file"


VALID_REPLY = json.dumps(
    {"verdict": "correct", "is_correct": True, "is_final_feedback": True, "feedback": "Correct.", "mistakes": []}
)


CSV_QUIZ = f"{CSV_HEADER}\n1,Pick,Pick one,first,second,third,,,,,,,,,,\n"


CSV_OPEN_QUIZ = f"{CSV_HEADER}\n2,Open,Explain,,,,,,,,,,,,,\n"


class FakeChatModel:
    """Chat model that records prompts and returns a fixed reply."""

    def __init__(self) -> None:
        """Create the fake with no recorded prompts and no failure."""
        self.user_prompts: list[str] = []
        self.system_prompts: list[str] = []
        self.must_fail = False
        self.scripted_replies: list[str] = []
        self.lifecycle_events: list[str] = []

    def start_loading(self) -> None:
        """Record the start hook."""
        self.lifecycle_events.append("started")

    def stop_worker(self) -> None:
        """Record the stop hook."""
        self.lifecycle_events.append("stopped")

    async def complete_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Record the prompt and reply.

        Args:
            system_prompt: Recorded instructions.
            user_prompt: Recorded prompt.

        Returns:
            A fixed reply.

        Raises:
            LlmRequestError: If `must_fail` is set.
        """
        self.user_prompts.append(user_prompt)
        self.system_prompts.append(system_prompt)
        if self.must_fail:
            raise LlmRequestError("fake failure")
        return self.scripted_replies.pop(0) if self.scripted_replies else VALID_REPLY


TASK_QUIZ = [
    {
        "id": 1,
        "question_name": "Cache",
        "question_text": "Design a cache",
        "correct_answer": "Secret answer",
        "llm_system_explanation": "Steps: eviction. Hint 1: memory. Hint 2: order.",
    },
]


def upload_file(api_client: TestClient, route_path: str, file_name: str, raw_content: bytes) -> httpx.Response:
    """Send a multipart upload.

    Args:
        api_client: Test client.
        route_path: Upload route.
        file_name: Client-side file name.
        raw_content: File bytes.

    Returns:
        The response.
    """
    return api_client.post(route_path, files={"uploaded_file": (file_name, raw_content)})


def prepare_quiz(api_client: TestClient) -> None:
    """Upload the sample quizzes and the knowledge file.

    Args:
        api_client: Test client.
    """
    assert upload_file(api_client, "/api/knowledge_base_file", "gravity.md", b"Mass attracts mass").status_code == 201
    assert upload_file(api_client, "/api/test_file", "base_quiz.json", dump_quiz(CHOICE_QUIZ)).status_code == 201
    assert upload_file(api_client, "/api/test_file", "base_llm.json", dump_quiz(OPEN_QUIZ)).status_code == 201


def dump_quiz(quiz_rows: list[dict[str, object]]) -> bytes:
    """Encode a quiz as JSON.

    Args:
        quiz_rows: Question objects.

    Returns:
        The encoded file.
    """
    return json.dumps(quiz_rows).encode()


def submit_answer(
    api_client: TestClient, question_id: str | int, test_file: str = "llm/base_llm.json"
) -> httpx.Response:
    """Post an answer.

    Args:
        api_client: Test client.
        question_id: Id of the question.
        test_file: Name of the quiz file.

    Returns:
        The response.
    """
    answer_body = {
        "test_file": test_file,
        "question_id": question_id,
        "user_answer": "Mass bends paths",
        "current_attempt": 1,
        "max_attempts": 3,
    }
    return api_client.post("/api/llm_answer", json=answer_body)


def build_wrong_reply(is_final_feedback: bool, feedback: str = "Not yet, think about the tilt.") -> str:
    """Build a reply with the verdict incorrect.

    Args:
        is_final_feedback: Value of the field of the same name.
        feedback: Text for the user.

    Returns:
        The reply as JSON text.
    """
    reply_fields = {"verdict": "incorrect", "is_correct": False, "is_final_feedback": is_final_feedback}
    return json.dumps(json.loads(VALID_REPLY) | reply_fields | {"feedback": feedback})
