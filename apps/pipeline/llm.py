"""LLM client protocol and implementations for the pipeline."""

from __future__ import annotations

import copy
from importlib import import_module
from typing import Any, Protocol, cast, runtime_checkable

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


def create_openai_client(
    *,
    response_schema_name: str | None = None,
    response_schema: dict[str, object] | None = None,
) -> LlmClient:
    """Create OpenAI chat completions client from Django settings.

    Args:
        response_schema_name: Schema name for strict json_schema mode
            (e.g. "llm1_response"). Must be provided together with
            response_schema.
        response_schema: JSON Schema dict for strict json_schema mode.
            When not provided, falls back to json_object mode.

    Returns:
        An LlmClient that uses json_schema strict mode when both
        schema arguments are supplied, or json_object mode otherwise.
    """
    if (response_schema_name is None) != (response_schema is None):
        raise ValueError("response_schema_name and response_schema must be provided together")
    if response_schema_name is not None and not response_schema_name.strip():
        raise ValueError("response_schema_name must be a non-empty string")

    from openai import OpenAI

    api_key = settings.OPENAI_API_KEY
    model = settings.OPENAI_MODEL
    base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Pre-normalize outside the inner class to keep complete() fast
    normalized_schema: dict[str, object] | None = None
    if response_schema_name is not None and response_schema is not None:
        normalized_schema = _normalize_openai_strict_schema(response_schema)

    class OpenAiLlmClient:
        def __init__(
            self,
            openai_client: OpenAI,
            model_name: str,
            schema_name: str | None,
            schema: dict[str, object] | None,
        ) -> None:
            self._client = openai_client
            self._model = model_name
            self._schema_name = schema_name
            self._schema = schema

        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            if self._schema_name is None or self._schema is None:
                response_format: Any = {"type": "json_object"}
            else:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": self._schema_name,
                        "schema": self._schema,
                        "strict": True,
                    },
                }
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_format,
            )
            content: str | None = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI returned empty content")
            return content

    return OpenAiLlmClient(client, model, response_schema_name, normalized_schema)


def create_openai_llm1_client() -> LlmClient:
    """Create OpenAI client for LLM1 with strict Llm1Response schema."""
    from apps.pipeline.schemas.llm1 import Llm1Response

    return create_openai_client(
        response_schema_name="llm1_response",
        response_schema=Llm1Response.model_json_schema(),
    )


def create_openai_llm2_client() -> LlmClient:
    """Create OpenAI client for LLM2 with strict Llm2Response schema."""
    from apps.pipeline.schemas.llm2 import Llm2Response

    return create_openai_client(
        response_schema_name="llm2_response",
        response_schema=Llm2Response.model_json_schema(),
    )


# ── Schema normalization for OpenAI strict mode ─────────────────────────


def _normalize_openai_strict_schema(schema: dict[str, object]) -> dict[str, object]:
    """Normalize JSON Schema so OpenAI strict mode accepts all object nodes.

    Ported from the legacy augmented-triage-system:
      src/triage_automation/infrastructure/llm/openai_client.py

    OpenAI strict mode requires every object node to have:
    - ``additionalProperties: false``
    - ``required`` listing all property names
    """
    normalized = copy.deepcopy(schema)
    _normalize_schema_node(normalized)
    return normalized


def _normalize_schema_node(node: object) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        properties = node.get("properties")
        if node_type == "object" and isinstance(properties, dict):
            property_names = [str(name) for name in properties.keys()]
            node["required"] = property_names
            node.setdefault("additionalProperties", False)

        for value in node.values():
            _normalize_schema_node(value)
        return

    if isinstance(node, list):
        for value in node:
            _normalize_schema_node(value)
