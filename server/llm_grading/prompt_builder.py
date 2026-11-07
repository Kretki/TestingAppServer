"""Request message for the LLM, in the structure defined by llm_input.md."""

import json
from dataclasses import dataclass

MAX_KNOWLEDGE_CHARACTERS = 40000
ANSWER_CLOSING_TAG = "</user_answer"
ESCAPED_CLOSING_TAG = "<\\/user_answer"


@dataclass(frozen=True)
class AnswerAttempt:
    """One attempt of the user to answer a question.

    Usage:
        Built by the transport layer from the POST body.

    Attributes:
        user_answer: Answer written by the user.
        current_attempt: Number of this attempt, starting at 1.
        max_attempts: Allowed attempts; the attempt is final when
            `current_attempt` reaches it.
    """

    user_answer: str
    current_attempt: int
    max_attempts: int

    @property
    def is_final(self) -> bool:
        """Tell whether this is the user's last attempt.

        Usage:
            Read to decide whether the solution may be revealed.

        Returns:
            True when the attempts are used up.
        """
        return self.current_attempt >= self.max_attempts


@dataclass(frozen=True)
class GradingPrompt:
    """Prompts of one LLM call.

    Usage:
        Built by `build_grading_prompt`.

    Attributes:
        system_prompt: Instructions for the model.
        user_prompt: The tagged request message.
    """

    system_prompt: str
    user_prompt: str


def build_knowledge_section(reference_answer: str | None, knowledge_text: str | None) -> str:
    """Compose the content of the knowledge_base element.

    Usage:
        Internal step of `build_grading_prompt`.

    Args:
        reference_answer: The quiz file's correct answer, or None.
        knowledge_text: Knowledge base document, or None. Text beyond 40000
            characters is dropped to fit the GPU memory.

    Returns:
        The references, empty when the question has none.
    """
    knowledge_sections = []
    if reference_answer:
        knowledge_sections.append(f"Reference answer: {reference_answer}")
    if knowledge_text:
        knowledge_sections.append(knowledge_text[:MAX_KNOWLEDGE_CHARACTERS])
    return "\n\n".join(knowledge_sections)


def encode_user_answer(user_answer: str) -> str:
    """Encode the untrusted answer as a JSON string that cannot close its tag.

    Usage:
        Internal step of `build_grading_prompt`. Escaping the slash keeps the
        JSON value identical, but a user cannot end the element and add a fake
        attempt element after it.

    Args:
        user_answer: Answer written by the user.

    Returns:
        The JSON string.
    """
    return json.dumps(user_answer, ensure_ascii=False).replace(ANSWER_CLOSING_TAG, ESCAPED_CLOSING_TAG)


def build_grading_prompt(
    instructions: str,
    question_text: str,
    reference_answer: str | None,
    knowledge_text: str | None,
    answer_attempt: AnswerAttempt,
) -> GradingPrompt:
    """Compose the prompts for checking one answer.

    Usage:
        Call when an answer is submitted.

    Args:
        instructions: System prompt, from the instructions file.
        question_text: Text of the quiz question.
        reference_answer: The quiz file's correct answer, or None.
        knowledge_text: Knowledge base document, or None.
        answer_attempt: The user's answer and attempt numbers.

    Returns:
        The prompts for the LLM.
    """
    request_lines = [
        f"<question>{question_text}</question>",
        f"<knowledge_base>{build_knowledge_section(reference_answer, knowledge_text)}</knowledge_base>",
        f'<attempt current="{answer_attempt.current_attempt}" max="{answer_attempt.max_attempts}" />',
        f"<user_answer>{encode_user_answer(answer_attempt.user_answer)}</user_answer>",
    ]
    return GradingPrompt(system_prompt=instructions, user_prompt="\n".join(request_lines))
