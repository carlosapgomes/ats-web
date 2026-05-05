"""Tests for LLM JSON parser."""

from __future__ import annotations

import pytest

from apps.pipeline.json_parser import LlmJsonParseError, decode_llm_json_object


class TestDecodeValidJson:
    """JSON puro deve ser parseado corretamente."""

    def test_decode_valid_json_flat(self) -> None:
        result = decode_llm_json_object('{"key": "value", "number": 42}')
        assert result == {"key": "value", "number": 42}

    def test_decode_valid_json_nested(self) -> None:
        data = '{"patient": {"name": "João", "age": 35}, "findings": ["gastritis"]}'
        result = decode_llm_json_object(data)
        assert result["patient"] == {"name": "João", "age": 35}
        assert result["findings"] == ["gastritis"]

    def test_decode_json_with_whitespace(self) -> None:
        result = decode_llm_json_object('  \n  {"a": 1}\n  ')
        assert result == {"a": 1}


class TestDecodeMarkdownBlock:
    """JSON dentro de code blocks markdown deve ser extraído."""

    def test_decode_json_in_markdown_block(self) -> None:
        data = '```json\n{"key": "value"}\n```'
        result = decode_llm_json_object(data)
        assert result == {"key": "value"}

    def test_decode_json_in_markdown_block_no_lang(self) -> None:
        data = '```\n{"key": "value"}\n```'
        result = decode_llm_json_object(data)
        assert result == {"key": "value"}

    def test_decode_json_in_markdown_block_multiline(self) -> None:
        data = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = decode_llm_json_object(data)
        assert result == {"a": 1, "b": 2}


class TestDecodeTrailingCommas:
    """Trailing commas devem ser removidos antes do parse."""

    def test_decode_trailing_comma_in_object(self) -> None:
        data = '{"a": 1, "b": 2,}'
        result = decode_llm_json_object(data)
        assert result == {"a": 1, "b": 2}

    def test_decode_trailing_comma_in_array(self) -> None:
        data = '{"items": [1, 2, 3,]}'
        result = decode_llm_json_object(data)
        assert result == {"items": [1, 2, 3]}

    def test_decode_trailing_comma_in_nested(self) -> None:
        data = '{"patient": {"name": "João", "age": 35,}, "findings": [1, 2,],}'
        result = decode_llm_json_object(data)
        assert result == {"patient": {"name": "João", "age": 35}, "findings": [1, 2]}


class TestDecodeEmbeddedJson:
    """JSON embutido no meio de texto deve ser encontrado via raw_decode scan."""

    def test_decode_json_embedded_in_text(self) -> None:
        data = 'Here is some text\n{"key": "value"}\nand more text'
        result = decode_llm_json_object(data)
        assert result == {"key": "value"}

    def test_decode_json_embedded_with_prefix_and_suffix(self) -> None:
        data = 'The response is: {"decision": "accept", "priority": 1}. End.'
        result = decode_llm_json_object(data)
        assert result == {"decision": "accept", "priority": 1}

    def test_decode_json_embedded_multiple_objects_returns_first(self) -> None:
        data = 'First: {"a": 1}. Second: {"b": 2}.'
        result = decode_llm_json_object(data)
        assert result == {"a": 1}

    def test_decode_json_embedded_in_multiline_text(self) -> None:
        data = (
            "Thank you for your request.\n\n"
            "Here is the structured output:\n"
            '{"patient": {"name": "Maria", "age": 60}}\n\n'
            "Let me know if you need anything else."
        )
        result = decode_llm_json_object(data)
        assert result == {"patient": {"name": "Maria", "age": 60}}


class TestDecodeErrors:
    """Respostas inválidas devem levantar LlmJsonParseError."""

    def test_decode_raises_on_plain_text(self) -> None:
        with pytest.raises(LlmJsonParseError, match="Failed to parse LLM response"):
            decode_llm_json_object("this is not json at all")

    def test_decode_raises_on_unclosed_brace(self) -> None:
        with pytest.raises(LlmJsonParseError):
            decode_llm_json_object('{"key": "value"')

    def test_decode_raises_on_empty_string(self) -> None:
        with pytest.raises(LlmJsonParseError):
            decode_llm_json_object("")

    def test_decode_raises_on_markdown_not_json(self) -> None:
        with pytest.raises(LlmJsonParseError):
            decode_llm_json_object("```\njust some text\nno json here\n```")


class TestLlmJsonParseErrorInheritance:
    """LlmJsonParseError deve herdar ValueError (alinhado com legado)."""

    def test_llm_json_parse_error_is_value_error(self) -> None:
        assert issubclass(LlmJsonParseError, ValueError)

    def test_llm_json_parse_error_caught_as_value_error(self) -> None:
        try:
            decode_llm_json_object("not json")
        except ValueError:
            pass
        else:
            pytest.fail("Expected ValueError to be raised")
