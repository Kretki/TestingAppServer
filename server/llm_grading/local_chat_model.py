"""gpt-oss model loaded directly into this process with transformers."""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizerBase

from server.contracts.domain_errors import LlmRequestError
from server.llm_grading.reasoning_filter import extract_final_answer

MODULE_LOGGER = logging.getLogger(__name__)
GPU_DEVICE_MAP = {"": 0}
ATTENTION_BACKEND = "flex_attention"


@dataclass(frozen=True)
class GenerationLimits:
    """Bounds and reasoning depth of one generation.

    Usage:
        Built from the server settings at start-up.

    Attributes:
        reasoning_effort: Reasoning depth: low, medium or high.
        max_output_tokens: Limit of reasoning plus final answer, in tokens.
        max_seconds: Time limit of one generation in seconds.
    """

    reasoning_effort: str
    max_output_tokens: int
    max_seconds: float


class LocalChatModel:
    """Chat model running on the GPU inside the server process.

    Usage:
        Create once at start-up and call `start_loading`. Answers run one at a
        time on a dedicated worker thread, because the GPU fits one generation;
        answers that arrive during loading wait for it.
    """

    def __init__(self, model_directory: Path, generation_limits: GenerationLimits) -> None:
        """Store the configuration; nothing is loaded yet.

        Usage:
            Call at start-up.

        Args:
            model_directory: Local folder with the safetensors model.
            generation_limits: Bounds and reasoning depth of generations.
        """
        self._model_directory = model_directory
        self._generation_limits = generation_limits
        self._worker_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-model")
        self._load_lock = threading.Lock()
        self._loaded_model: PreTrainedModel | None = None
        self._tokenizer: PreTrainedTokenizerBase | None = None

    def start_loading(self) -> None:
        """Begin loading the model in the background.

        Usage:
            Call when the application starts, so the first answer does not
            pay for the load. Failures are logged and retried by that answer.
        """
        self._worker_pool.submit(self._load_quietly)

    def stop_worker(self) -> None:
        """Stop the worker thread without waiting for queued work.

        Usage:
            Call when the application stops.
        """
        self._worker_pool.shutdown(wait=False, cancel_futures=True)

    async def complete_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a reply with reasoning on.

        Usage:
            Await to run one LLM call.

        Args:
            system_prompt: Instructions for the model.
            user_prompt: Data the model works on.

        Returns:
            The final answer, without reasoning.

        Raises:
            LlmRequestError: If the model cannot be loaded or gives no answer.
        """
        event_loop = asyncio.get_running_loop()
        return await event_loop.run_in_executor(self._worker_pool, self._generate_answer, system_prompt, user_prompt)

    def _load_quietly(self) -> None:
        """Load the model and log any failure.

        Usage:
            Internal task of `start_loading`.
        """
        try:
            self._ensure_loaded()
        except LlmRequestError:
            MODULE_LOGGER.exception("Could not load the model")

    def _ensure_loaded(self) -> None:
        """Load the tokenizer and weights once.

        Usage:
            Internal step before generating.

        Raises:
            LlmRequestError: If the model files or GPU memory are unusable.
        """
        with self._load_lock:
            if self._loaded_model is not None:
                return
            try:
                # B615 is a false positive: both calls read a local folder and never use the Hub.
                self._tokenizer = AutoTokenizer.from_pretrained(  # nosec B615
                    self._model_directory, local_files_only=True
                )
                self._loaded_model = AutoModelForCausalLM.from_pretrained(  # nosec B615
                    self._model_directory,
                    dtype="auto",
                    device_map=GPU_DEVICE_MAP,
                    attn_implementation=ATTENTION_BACKEND,
                    local_files_only=True,
                )
            except (OSError, ValueError, RuntimeError, ImportError) as load_error:
                raise LlmRequestError(f"Could not load the model: {load_error!r}") from load_error
            MODULE_LOGGER.warning("Model loaded from %s", self._model_directory.name)

    def _generate_answer(self, system_prompt: str, user_prompt: str) -> str:
        """Run one generation on the worker thread.

        Usage:
            Internal step of `complete_chat`.

        Args:
            system_prompt: Instructions for the model.
            user_prompt: Data the model works on.

        Returns:
            The final answer, without reasoning.

        Raises:
            LlmRequestError: If loading or generation fails, or the reply has
                no final answer, for example after hitting a limit.
        """
        self._ensure_loaded()
        chat_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        try:
            with torch.inference_mode():
                return extract_final_answer(self._run_model(chat_messages))
        except (RuntimeError, ValueError) as generation_error:
            torch.cuda.empty_cache()
            raise LlmRequestError(f"Generation failed: {generation_error!r}") from generation_error

    def _run_model(self, chat_messages: list[dict[str, str]]) -> str:
        """Tokenize the chat, generate, and decode the new tokens.

        Usage:
            Internal step of `_generate_answer`.

        Args:
            chat_messages: System and user messages.

        Returns:
            Generated text including special tokens, which mark the channels.
        """
        generation_limits = self._generation_limits
        model_inputs = self._tokenizer.apply_chat_template(
            chat_messages,
            add_generation_prompt=True,
            reasoning_effort=generation_limits.reasoning_effort,
            return_tensors="pt",
            return_dict=True,
        ).to(self._loaded_model.device)
        output_tokens = self._loaded_model.generate(
            **model_inputs,
            max_new_tokens=generation_limits.max_output_tokens,
            max_time=generation_limits.max_seconds,
            do_sample=True,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
        )
        prompt_length = model_inputs["input_ids"].shape[1]
        return self._tokenizer.decode(output_tokens[0][prompt_length:], skip_special_tokens=False)
