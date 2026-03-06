from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

from rpg_backend.generator.spec_schema import StorySpec
from rpg_backend.llm.retry_policy import is_retriable_llm_error, retry_delay_seconds


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"status {status_code}", request=request, response=response)


def test_is_retriable_llm_error_for_validation_and_json_errors() -> None:
    schema_error: ValidationError | None = None
    try:
        StorySpec.model_validate({})
    except ValidationError as exc:
        schema_error = exc
    else:  # pragma: no cover
        raise AssertionError("expected StorySpec validation to fail")

    assert schema_error is not None
    assert is_retriable_llm_error(ValueError("bad payload")) is True
    assert is_retriable_llm_error(schema_error) is True
    assert is_retriable_llm_error(json.JSONDecodeError("bad json", "{", 1)) is True


def test_is_retriable_llm_error_for_http_status_codes() -> None:
    assert is_retriable_llm_error(_http_status_error(401)) is False
    assert is_retriable_llm_error(_http_status_error(429)) is True
    assert is_retriable_llm_error(_http_status_error(503)) is True


def test_retry_delay_seconds_uses_stable_schedule() -> None:
    assert retry_delay_seconds(1, RuntimeError("network")) == 0.25
    assert retry_delay_seconds(2, RuntimeError("network")) == 0.8
    assert retry_delay_seconds(3, RuntimeError("network")) == 1.5
    assert retry_delay_seconds(4, RuntimeError("network")) == 1.5
    assert retry_delay_seconds(1, ValueError("bad json")) == 0.0
