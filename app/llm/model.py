"""
LLM singleton using llama-cpp-python.
Lazy-loads the Qwen2.5-7B-Instruct Q4_K_M GGUF model on first use.
Uses all available CPU cores for faster inference.
"""
import os
from typing import Iterator, Optional

from app.config import settings


class LLMSingleton:
    _instance: Optional["LLMSingleton"] = None
    _model = None

    def __new__(cls) -> "LLMSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._model is not None:
            return

        from llama_cpp import Llama

        model_path = settings.MODEL_PATH
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                "Download it with:\n"
                "  .venv/Scripts/huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF "
                "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf --local-dir models/"
            )

        # Use all CPU cores if MODEL_N_THREADS is 0
        n_threads = settings.MODEL_N_THREADS or os.cpu_count() or 4

        self._model = Llama(
            model_path=model_path,
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=settings.MODEL_N_GPU_LAYERS,
            n_threads=n_threads,
            n_batch=512,
            verbose=False,
        )

    def generate(self, user_message: str, system_prompt: str = "") -> str:
        """Generate a full response (waits for completion)."""
        self._load()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = self._model.create_chat_completion(
            messages=messages,
            max_tokens=settings.MODEL_MAX_TOKENS,
            temperature=settings.MODEL_TEMPERATURE,
        )

        choices = response.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "").strip()

    def generate_stream(self, user_message: str, system_prompt: str = "") -> Iterator[str]:
        """Generate a streaming response — yields tokens one at a time."""
        self._load()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        stream = self._model.create_chat_completion(
            messages=messages,
            max_tokens=settings.MODEL_MAX_TOKENS,
            temperature=settings.MODEL_TEMPERATURE,
            stream=True,
        )

        for chunk in stream:
            token = chunk["choices"][0]["delta"].get("content", "")
            if token:
                yield token

    @property
    def is_loaded(self) -> bool:
        return self._model is not None


# Module-level singleton
llm = LLMSingleton()
