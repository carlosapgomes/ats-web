"""LLM client protocol and implementations for the pipeline."""

from __future__ import annotations

from importlib import import_module
from typing import Protocol, cast, runtime_checkable

from django.conf import settings


@runtime_checkable
class LlmClient(Protocol):
    """Protocol for LLM chat completion."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return completion text for the supplied prompts."""
        ...


class StaticLlmClient:
    """Test-friendly client returning a fixed response."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._response_text


class RecordingLlmClient:
    """Test client that records calls and returns configured responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = iter(responses or [])
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return next(self._responses, "")


def get_llm_client() -> LlmClient:
    """Factory: returns configured LLM client from settings."""
    factory_path = getattr(settings, "LLM_CLIENT_FACTORY", None)
    if factory_path is None:
        return StaticLlmClient(response_text='{"error": "no_llm_configured"}')

    module_path, func_name = factory_path.rsplit(".", 1)
    module = import_module(module_path)
    factory = getattr(module, func_name)
    return cast(LlmClient, factory())


def create_openai_client() -> LlmClient:
    """Create OpenAI chat completions client from Django settings."""
    from openai import OpenAI

    api_key = settings.OPENAI_API_KEY
    model = settings.OPENAI_MODEL
    base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    class OpenAiLlmClient:
        def __init__(self, openai_client: OpenAI, model_name: str) -> None:
            self._client = openai_client
            self._model = model_name

        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI returned empty content")
            return content

    return OpenAiLlmClient(client, model)
