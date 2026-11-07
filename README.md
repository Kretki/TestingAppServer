# Quiz server

Local REST server for the quiz application.

    systemctl --user start quiz-server      # also: stop, restart, status
    journalctl --user -u quiz-server -f     # logs

The server runs as a systemd user service, independently of any shell. One-time setup:

    uv sync
    systemctl --user link "$PWD/deployment/quiz-server.service"
    loginctl enable-linger "$USER"

Add `systemctl --user enable quiz-server` to start it automatically. `QUIZ_*` settings go in
`~/.config/quiz-server.env`. Restart the service after a code change or `uv sync`.
To run it in the foreground instead, stop the service and use `uv run quiz-server`.

The server listens on `http://127.0.0.1:8000`; interactive API docs are at `/docs`.
An Android emulator reaches it at `http://10.0.2.2:8000`.

LLM checks run on `models/gpt-oss-20b` (original MXFP4 weights), loaded directly into the server process
with `transformers`; no separate model server is used. Loading starts with the service and takes about
20 seconds, and an answer sent meanwhile waits for it. The model holds most of the GPU memory until the service
stops, and answers are checked one at a time.

Every LLM check runs with reasoning on, and users only see the final answer. A reply cut off by
`QUIZ_LLM_MAX_OUTPUT_TOKENS` or `QUIZ_LLM_TIMEOUT_SECONDS` ends with status `failed`.

`llm_input.md` holds the instructions given to the LLM. It is read for every answer, so edits apply
without a restart. If it is missing or empty, `POST /api/llm_answer` returns `503`.

## Settings (environment variables)

| Variable | Default |
|---|---|
| `QUIZ_HOST` / `QUIZ_PORT` | `127.0.0.1` / `8000` |
| `QUIZ_TEST_DIR` | `test_files/` |
| `QUIZ_KNOWLEDGE_DIR` | `knowledge_base/` |
| `QUIZ_LLM_INPUT_FILE` | `llm_input.md` |
| `QUIZ_MODEL_DIR` | `models/gpt-oss-20b` |
| `QUIZ_LLM_REASONING_EFFORT` | `medium` (`low`, `medium`, `high`) |
| `QUIZ_LLM_TIMEOUT_SECONDS` | `300` |
| `QUIZ_LLM_MAX_OUTPUT_TOKENS` | `4096` |

The server has no authentication: do not bind it to a public interface.

## API

| Call | Input | Output |
|---|---|---|
| `GET /api/test_files` | | `[{"file_name", "description"}]` |
| `GET /api/test_file` | query `file_name` | the file as stored |
| `POST /api/test_file` | multipart field `uploaded_file` (.json/.csv) | `201 {"file_name"}`, `409` if it exists |
| `POST /api/llm_answer` | JSON `{"test_file", "question_id", "user_answer", "current_attempt", "max_attempts"}` | `202 {"request_id"}` |
| `GET /api/llm_answer` | query `request_id` | `{"request_id", "request_status", "llm_answer", "error_detail"}` |
| `GET /api/knowledge_base_files` | | `["name.md"]` |
| `GET /api/knowledge_base_file` | query `name` | the Markdown file |
| `POST /api/knowledge_base_file` | multipart field `uploaded_file` (.md) | `201 {"file_name"}`, overwrites |

The `description` in `GET /api/test_files` is generated, for example `12 testing questions`.

`request_status` is `pending`, `ready` or `failed`. Errors are `{"detail": ...}`.

In `POST /api/llm_answer`, `question_id` is the question's `id`. `current_attempt` starts at 1 and may not
exceed `max_attempts` (at most 100). When they are equal the attempt is final, and the LLM gives the solution.

When ready, `llm_answer` is a string holding the JSON object defined in `llm_input.md`:
`{"verdict", "is_correct", "is_final_feedback", "feedback", "mistakes"}`. A reply that breaks that format, or reveals
more than the real attempt allows, is regenerated up to 3 times and then ends with status `failed`. If you change the format in `llm_input.md`, change `server/llm_grading/grading_reply.py` too.
LLM results are kept in memory and are lost on restart.

## Quiz file formats

The file name states how its questions are checked:

- `*_quiz.csv` / `*_quiz.json`: testing questions, checked by the client. Every question needs
  `correct_answer` and at least one wrong answer.
- `*_llm.csv` / `*_llm.json`: written answers, checked by the LLM. `correct_answer` is optional and is
  given to the LLM as a reference answer.
- `*_task.csv` / `*_task.json`: interview tasks the candidate solves in words, without code, checked by the
  LLM. Every task needs `llm_system_explanation`: the steps to cover, and the hints to give after failed
  attempts 1 and 2. Use `max_attempts: 3` so both hints are reached.

Other names are refused on upload. Existing quizzes are not overwritten.

CSV columns:

    id,question_name,question_text,correct_answer,wrong_answer_1,...,wrong_answer_10,knowledge_file,llm_system_explanation

JSON is an array of objects with the same keys. Empty or missing values are skipped.
`knowledge_file` is optional: it is a path relative to `knowledge_base/`, and the file is given to the LLM as
reference material. See the samples in `test_files/`.

`llm_system_explanation` never leaves the server: `GET /api/test_file` removes it from every file, and also
removes `correct_answer` from `*_task` files. Other files are served unchanged.

## Folders

`test_files/` and `knowledge_base/` may contain folders. Every file name in the API is a path relative to that
directory with `/` separators, such as `python/basics_quiz.json`, in lists, query parameters, upload file names
and `test_file`. Uploads create missing folders. Limits: 8 levels, 512 characters in total, 128 per part; a part
may not start with `.` or contain `..`.

## Tests

    uv run pytest
