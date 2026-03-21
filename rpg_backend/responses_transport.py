from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from openai import OpenAI

T = TypeVar("T")
ErrorFactory = Callable[[str, str, int], Exception]


@dataclass(frozen=True)
class ResponsesJSONResponse:
    payload: dict[str, Any]
    response_id: str | None
    usage: dict[str, Any]
    input_characters: int


@dataclass(frozen=True)
class StructuredResponse(Generic[T]):
    value: T
    response_id: str | None


def usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        raw = usage.model_dump()
    elif isinstance(usage, dict):
        raw = usage
    else:
        raw = {}
        for key in dir(usage):
            if key.startswith("_"):
                continue
            try:
                raw[key] = getattr(usage, key)
            except Exception:  # noqa: BLE001
                continue
    normalized: dict[str, Any] = {}
    input_details = raw.get("input_tokens_details")
    if isinstance(input_details, dict) and isinstance(input_details.get("cached_tokens"), (int, float)):
        normalized["cached_input_tokens"] = int(input_details["cached_tokens"])
    output_details = raw.get("output_tokens_details")
    if isinstance(output_details, dict) and isinstance(output_details.get("reasoning_tokens"), (int, float)):
        normalized["reasoning_tokens"] = int(output_details["reasoning_tokens"])
    x_details = raw.get("x_details")
    if isinstance(x_details, list) and x_details:
        detail = x_details[0]
        if isinstance(detail, dict):
            if isinstance(detail.get("x_billing_type"), str):
                normalized["billing_type"] = detail["x_billing_type"]
            prompt_details = detail.get("prompt_tokens_details")
            if isinstance(prompt_details, dict):
                if isinstance(prompt_details.get("cached_tokens"), (int, float)):
                    normalized["cached_input_tokens"] = int(prompt_details["cached_tokens"])
                if isinstance(prompt_details.get("cache_creation_input_tokens"), (int, float)):
                    normalized["cache_creation_input_tokens"] = int(prompt_details["cache_creation_input_tokens"])
                cache_creation = prompt_details.get("cache_creation")
                if isinstance(cache_creation, dict):
                    for key, value in cache_creation.items():
                        if isinstance(value, (int, float)):
                            normalized[str(key)] = int(value)
                if isinstance(prompt_details.get("cache_type"), str):
                    normalized["cache_type"] = prompt_details["cache_type"]
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            normalized[str(key)] = int(value)
    return normalized


def build_openai_client(
    *,
    base_url: str,
    api_key: str,
    use_session_cache: bool,
    session_cache_header: str,
    session_cache_value: str,
) -> OpenAI:
    client_kwargs: dict[str, Any] = {
        "base_url": base_url,
        "api_key": api_key,
    }
    if use_session_cache:
        client_kwargs["default_headers"] = {
            session_cache_header: session_cache_value,
        }
    return OpenAI(**client_kwargs)


@dataclass
class ResponsesJSONTransport:
    client: OpenAI
    model: str
    timeout_seconds: float
    use_session_cache: bool
    temperature: float
    enable_thinking: bool
    provider_failed_code: str
    invalid_response_code: str
    invalid_json_code: str
    error_factory: ErrorFactory
    call_trace: list[dict[str, Any]] = field(default_factory=list)

    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int | None,
        previous_response_id: str | None = None,
        operation_name: str | None = None,
        plaintext_fallback_key: str | None = None,
    ) -> ResponsesJSONResponse:
        user_text = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
        input_characters = len(user_text)
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_text,
            "max_output_tokens": max_output_tokens,
            "timeout": self.timeout_seconds,
            "temperature": self.temperature,
            "extra_body": {"enable_thinking": self.enable_thinking},
        }
        if self.use_session_cache and previous_response_id:
            request_kwargs["previous_response_id"] = previous_response_id
        try:
            response = self.client.responses.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self.error_factory(self.provider_failed_code, str(exc), 502) from exc
        try:
            content = response.output_text
        except Exception as exc:  # noqa: BLE001
            raise self.error_factory(
                self.invalid_response_code,
                "provider response did not include message content",
                502,
            ) from exc
        text = str(content or "").strip()
        original_text = text
        if not text:
            raise self.error_factory(
                self.invalid_json_code,
                "provider returned empty content",
                502,
            )
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            payload = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            if plaintext_fallback_key and original_text:
                payload = {plaintext_fallback_key: original_text}
            else:
                raise self.error_factory(self.invalid_json_code, str(exc), 502) from exc
        if not isinstance(payload, dict):
            raise self.error_factory(
                self.invalid_json_code,
                "provider returned a non-object JSON payload",
                502,
            )
        usage = usage_to_dict(getattr(response, "usage", None))
        self.call_trace.append(
            {
                "operation": operation_name or "unknown",
                "response_id": getattr(response, "id", None),
                "used_previous_response_id": bool(previous_response_id),
                "session_cache_enabled": bool(self.use_session_cache),
                "max_output_tokens": max_output_tokens,
                "input_characters": input_characters,
                "usage": usage,
            }
        )
        return ResponsesJSONResponse(
            payload=payload,
            response_id=getattr(response, "id", None),
            usage=usage,
            input_characters=input_characters,
        )
