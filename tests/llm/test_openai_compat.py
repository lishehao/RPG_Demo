from __future__ import annotations

import pytest

from rpg_backend.llm.openai_compat import (
    extract_chat_content,
    normalize_chat_completions_url,
    parse_json_object,
)


def test_normalize_chat_completions_url_variants() -> None:
    assert normalize_chat_completions_url("https://example.com") == "https://example.com/v1/chat/completions"
    assert normalize_chat_completions_url("https://example.com/v1") == "https://example.com/v1/chat/completions"
    assert (
        normalize_chat_completions_url("https://example.com/v1/responses")
        == "https://example.com/v1/chat/completions"
    )
    assert (
        normalize_chat_completions_url("https://example.com/v1/chat/completions")
        == "https://example.com/v1/chat/completions"
    )


def test_extract_chat_content_accepts_string_payload() -> None:
    payload = {"choices": [{"message": {"content": "{\"ok\": true}"}}]}
    assert extract_chat_content(payload) == "{\"ok\": true}"


def test_extract_chat_content_accepts_fragment_payload() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "{"},
                        {"type": "text", "text": "\"ok\": true}"},
                    ]
                }
            }
        ]
    }
    assert extract_chat_content(payload) == "{\"ok\": true}"


def test_extract_chat_content_raises_when_message_content_missing() -> None:
    payload = {"choices": [{"message": {"content": []}}]}
    with pytest.raises(ValueError):
        _ = extract_chat_content(payload)


def test_extract_chat_content_raises_when_choices_empty() -> None:
    payload = {"choices": []}
    with pytest.raises(ValueError):
        _ = extract_chat_content(payload)


def test_extract_chat_content_raises_when_message_not_object() -> None:
    payload = {"choices": [{"message": "not-an-object"}]}
    with pytest.raises(ValueError):
        _ = extract_chat_content(payload)


def test_extract_chat_content_raises_when_fragment_list_has_no_text_entries() -> None:
    payload = {"choices": [{"message": {"content": [{"type": "input_text", "value": "ignored"}]}}]}
    with pytest.raises(ValueError):
        _ = extract_chat_content(payload)


def test_parse_json_object_raises_on_non_object() -> None:
    with pytest.raises(ValueError):
        _ = parse_json_object("[1,2,3]")
