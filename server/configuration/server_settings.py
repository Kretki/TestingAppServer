"""Server settings read from environment variables."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 8080
DEFAULT_LLM_REASONING_EFFORT = "medium"
REASONING_EFFORTS = ("low", "medium", "high")
DEFAULT_LLM_TIMEOUT_SECONDS = 300.0
DEFAULT_LLM_MAX_OUTPUT_TOKENS = 4096
DEFAULT_MAX_REQUEST_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_PENDING_REQUESTS = 32
DEFAULT_MAX_STORED_RESULTS = 1000


@dataclass(frozen=True)
class ServerSettings:
    """Immutable runtime configuration of the server.

    Usage:
        Build with `load_settings` in production, or directly in tests.

    Attributes:
        listen_host: Interface the HTTP server binds to.
        listen_port: TCP port of the HTTP server, 1..65535.
        test_directory: Folder holding .json and .csv quiz files.
        knowledge_directory: Folder holding .md knowledge base files.
        instruction_file: Externally managed system prompt of the LLM.
        model_directory: Local folder with the safetensors model.
        llm_timeout_seconds: Time limit of one generation in seconds.
        llm_max_output_tokens: Limit of reasoning plus final answer, in tokens.
        llm_reasoning_effort: Reasoning depth: low, medium or high.
        max_request_bytes: Largest accepted POST body in bytes.
        max_pending_requests: Largest number of LLM checks in progress.
        max_stored_results: Largest number of LLM checks kept in memory.
    """

    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = DEFAULT_LISTEN_PORT
    test_directory: Path = PROJECT_ROOT / "test_files"
    knowledge_directory: Path = PROJECT_ROOT / "knowledge_base"
    instruction_file: Path = PROJECT_ROOT / "llm_input.md"
    model_directory: Path = PROJECT_ROOT / "models" / "gpt-oss-20b"
    llm_timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS
    llm_max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS
    llm_reasoning_effort: str = DEFAULT_LLM_REASONING_EFFORT
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_pending_requests: int = DEFAULT_MAX_PENDING_REQUESTS
    max_stored_results: int = DEFAULT_MAX_STORED_RESULTS


def load_settings(environment: Mapping[str, str]) -> ServerSettings:
    """Build settings from environment variables, falling back to defaults.

    Usage:
        Call once at start-up with `os.environ`.

    Args:
        environment: Variable names mapped to values. Recognised names are
            QUIZ_HOST, QUIZ_PORT, QUIZ_TEST_DIR, QUIZ_KNOWLEDGE_DIR,
            QUIZ_LLM_INPUT_FILE,
            QUIZ_MODEL_DIR, QUIZ_LLM_TIMEOUT_SECONDS, QUIZ_LLM_MAX_OUTPUT_TOKENS and
            QUIZ_LLM_REASONING_EFFORT.

    Returns:
        The resulting ServerSettings.

    Raises:
        ValueError: If a numeric variable is not numeric, or the reasoning
            effort is not low, medium or high.
    """
    defaults = ServerSettings()
    reasoning_effort = environment.get("QUIZ_LLM_REASONING_EFFORT", defaults.llm_reasoning_effort)
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"QUIZ_LLM_REASONING_EFFORT must be one of {REASONING_EFFORTS}")
    return ServerSettings(
        listen_host=environment.get("QUIZ_HOST", defaults.listen_host),
        listen_port=int(environment.get("QUIZ_PORT", defaults.listen_port)),
        test_directory=Path(environment.get("QUIZ_TEST_DIR", defaults.test_directory)),
        knowledge_directory=Path(environment.get("QUIZ_KNOWLEDGE_DIR", defaults.knowledge_directory)),
        instruction_file=Path(environment.get("QUIZ_LLM_INPUT_FILE", defaults.instruction_file)),
        model_directory=Path(environment.get("QUIZ_MODEL_DIR", defaults.model_directory)),
        llm_timeout_seconds=float(environment.get("QUIZ_LLM_TIMEOUT_SECONDS", defaults.llm_timeout_seconds)),
        llm_max_output_tokens=int(environment.get("QUIZ_LLM_MAX_OUTPUT_TOKENS", defaults.llm_max_output_tokens)),
        llm_reasoning_effort=reasoning_effort,
    )
