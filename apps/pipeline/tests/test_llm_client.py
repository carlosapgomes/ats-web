"""Tests for LLM client protocol and implementations."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestStaticLlmClient:
    """Tests for StaticLlmClient."""

    def test_returns_fixed_response(self) -> None:
        from apps.pipeline.llm import StaticLlmClient

        client = StaticLlmClient(response_text="hello")
        result = client.complete(system_prompt="sys", user_prompt="usr")
        assert result == "hello"

    def test_ignores_prompt_arguments(self) -> None:
        from apps.pipeline.llm import StaticLlmClient

        client = StaticLlmClient(response_text="fixed")
        result1 = client.complete(system_prompt="a", user_prompt="b")
        result2 = client.complete(system_prompt="x", user_prompt="y")
        assert result1 == "fixed"
        assert result2 == "fixed"


class TestRecordingLlmClient:
    """Tests for RecordingLlmClient."""

    def test_captures_calls(self) -> None:
        from apps.pipeline.llm import RecordingLlmClient

        client = RecordingLlmClient(responses=["r1", "r2"])
        client.complete(system_prompt="sys1", user_prompt="usr1")
        client.complete(system_prompt="sys2", user_prompt="usr2")

        assert len(client.calls) == 2
        assert client.calls[0] == {"system_prompt": "sys1", "user_prompt": "usr1"}
        assert client.calls[1] == {"system_prompt": "sys2", "user_prompt": "usr2"}

    def test_returns_sequential_responses(self) -> None:
        from apps.pipeline.llm import RecordingLlmClient

        client = RecordingLlmClient(responses=["first", "second", "third"])
        assert client.complete(system_prompt="s", user_prompt="u") == "first"
        assert client.complete(system_prompt="s", user_prompt="u") == "second"
        assert client.complete(system_prompt="s", user_prompt="u") == "third"

    def test_returns_empty_string_when_no_responses_left(self) -> None:
        from apps.pipeline.llm import RecordingLlmClient

        client = RecordingLlmClient(responses=["only"])
        client.complete(system_prompt="s", user_prompt="u")
        result = client.complete(system_prompt="s", user_prompt="u")
        assert result == ""

    def test_default_responses_is_empty(self) -> None:
        from apps.pipeline.llm import RecordingLlmClient

        client = RecordingLlmClient()
        result = client.complete(system_prompt="s", user_prompt="u")
        assert result == ""


class TestGetLlmClient:
    """Tests for get_llm_client factory."""

    def test_returns_static_client_when_no_factory_configured(self) -> None:
        from apps.pipeline.llm import LlmClient, get_llm_client

        client = get_llm_client()
        assert isinstance(client, LlmClient)
        result = client.complete(system_prompt="sys", user_prompt="usr")
        assert "no_llm_configured" in result

    def test_calls_factory_when_configured(self, settings: Any) -> None:
        from apps.pipeline.llm import StaticLlmClient, get_llm_client

        # Configure a factory that returns a known client
        settings.LLM_CLIENT_FACTORY = None  # default, no factory

        # Test with factory path set to None - should return StaticLlmClient
        client = get_llm_client()
        assert isinstance(client, StaticLlmClient)

    def test_uses_custom_factory_path(self, settings: Any) -> None:
        from apps.pipeline.llm import get_llm_client

        # Use a simple callable via import path
        settings.LLM_CLIENT_FACTORY = "apps.pipeline.tests.test_llm_client._dummy_factory"
        client = get_llm_client()
        result = client.complete(system_prompt="s", user_prompt="u")
        assert result == "dummy-response"


def _dummy_factory() -> Any:
    """Dummy factory for testing get_llm_client with a custom path."""
    from apps.pipeline.llm import StaticLlmClient

    return StaticLlmClient(response_text="dummy-response")


class TestCreateOpenAiClient:
    """Tests for create_openai_client."""

    def test_creates_client_with_settings(self, settings: Any) -> None:
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            # Configure a mock completion response
            mock_completion = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = '{"key": "value"}'
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion

            from apps.pipeline.llm import create_openai_client

            client = create_openai_client()
            result = client.complete(system_prompt="sys", user_prompt="usr")

            assert result == '{"key": "value"}'
            mock_openai_cls.assert_called_once_with(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
            mock_client.chat.completions.create.assert_called_once_with(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "usr"},
                ],
                response_format={"type": "json_object"},
            )

    def test_raises_on_empty_content(self, settings: Any) -> None:
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            mock_completion = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = None
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion

            from apps.pipeline.llm import create_openai_client

            client = create_openai_client()
            with pytest.raises(RuntimeError, match="OpenAI returned empty content"):
                client.complete(system_prompt="sys", user_prompt="usr")
