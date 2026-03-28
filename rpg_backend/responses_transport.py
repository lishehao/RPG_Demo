from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Literal, Protocol, TypeVar

from openai import OpenAI

T = TypeVar("T")
ErrorFactory = Callable[[str, str, int], Exception]
TransportStyle = Literal["responses", "chat_completions"]


@dataclass(frozen=True)
class ResponsesJSONResponse:
    payload: dict[str, Any]
    response_id: str | None
    usage: dict[str, Any]
    input_characters: int
    fallback_source: str | None = None
    raw_text: str | None = None


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
    max_retries: int = 0,
    default_headers: dict[str, str] | None = None,
) -> OpenAI:
    headers = dict(default_headers or {})
    if use_session_cache:
        headers[session_cache_header] = session_cache_value
    normalized_base_url = str(base_url or "").rstrip("/")
    if normalized_base_url.endswith("/responses"):
        normalized_base_url = normalized_base_url[: -len("/responses")]
    client_kwargs: dict[str, Any] = {
        "base_url": normalized_base_url,
        "api_key": api_key,
        "max_retries": max(int(max_retries), 0),
    }
    if headers:
        client_kwargs["default_headers"] = headers
    return OpenAI(**client_kwargs)


def _strip_fenced_json(text: str) -> str:
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
    return text


def strip_model_meta_wrapper_text(text: str) -> str:
    candidate = _strip_fenced_json(str(text or "").strip())
    candidate = candidate.strip("`").strip()
    wrapper_patterns = (
        r"^\s*here(?:'s| is)\s+the\s+json\s+requested\s*:?\s*",
        r"^\s*here(?:'s| is)\s+the\s+requested\s+json\s*:?\s*",
        r"^\s*here(?:'s| is)\s+the\s+requested\s+output\s*:?\s*",
        r"^\s*requested\s+output\s*:?\s*",
        r"^\s*json\s*:?\s*",
        r"^\s*response\s*:?\s*",
        r"^\s*output\s*:?\s*",
        r"^\s*narration\s*:?\s*",
        r"^\s*input_text\s*:?\s*",
    )
    updated = candidate
    for pattern in wrapper_patterns:
        updated = re.sub(pattern, "", updated, flags=re.IGNORECASE)
    return updated.strip().strip("`").strip().strip('"').strip()


def _coerce_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk).strip()
    text = getattr(content, "text", None)
    if isinstance(text, str):
        return text
    return str(content or "").strip()


def _parse_json_payload(
    *,
    text: str,
    invalid_json_code: str,
    error_factory: ErrorFactory,
    plaintext_fallback_key: str | None = None,
    allow_raw_text_passthrough: bool = False,
) -> tuple[dict[str, Any], str | None]:
    original_text = text
    text = str(text or "").strip()
    if not text:
        raise error_factory(
            invalid_json_code,
            "provider returned empty content",
            502,
        )
    text = _strip_fenced_json(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
        fallback_source = None
    except Exception as exc:  # noqa: BLE001
        if plaintext_fallback_key and original_text:
            payload = {plaintext_fallback_key: original_text}
            fallback_source = "plaintext_salvage"
        elif allow_raw_text_passthrough and original_text:
            payload = {}
            fallback_source = "raw_text_passthrough"
        else:
            raise error_factory(invalid_json_code, str(exc), 502) from exc
    if not isinstance(payload, dict):
        if plaintext_fallback_key and original_text:
            return {plaintext_fallback_key: original_text}, "plaintext_salvage"
        if allow_raw_text_passthrough and original_text:
            return {}, "raw_text_passthrough"
        raise error_factory(
            invalid_json_code,
            "provider returned a non-object JSON payload",
            502,
        )
    return payload, fallback_source


class JSONTransport(Protocol):
    def invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int | None,
        previous_response_id: str | None = None,
        operation_name: str | None = None,
        plaintext_fallback_key: str | None = None,
        allow_raw_text_passthrough: bool = False,
    ) -> ResponsesJSONResponse: ...


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
        allow_raw_text_passthrough: bool = False,
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
        payload, fallback_source = _parse_json_payload(
            text=str(content or "").strip(),
            invalid_json_code=self.invalid_json_code,
            error_factory=self.error_factory,
            plaintext_fallback_key=plaintext_fallback_key,
            allow_raw_text_passthrough=allow_raw_text_passthrough,
        )
        usage = usage_to_dict(getattr(response, "usage", None))
        self.call_trace.append(
            {
                "transport": "responses",
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
            fallback_source=fallback_source,
            raw_text=str(content or "").strip(),
        )


@dataclass
class ChatCompletionsJSONTransport:
    client: OpenAI
    model: str
    timeout_seconds: float
    temperature: float
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
        allow_raw_text_passthrough: bool = False,
    ) -> ResponsesJSONResponse:
        user_text = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
        input_characters = len(user_text)
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "max_completion_tokens": max_output_tokens,
            "timeout": self.timeout_seconds,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self.client.chat.completions.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self.error_factory(self.provider_failed_code, str(exc), 502) from exc
        try:
            choice = (getattr(response, "choices", None) or [])[0]
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
        except Exception as exc:  # noqa: BLE001
            raise self.error_factory(
                self.invalid_response_code,
                "provider response did not include chat completion content",
                502,
            ) from exc
        payload, fallback_source = _parse_json_payload(
            text=_coerce_content_text(content),
            invalid_json_code=self.invalid_json_code,
            error_factory=self.error_factory,
            plaintext_fallback_key=plaintext_fallback_key,
            allow_raw_text_passthrough=allow_raw_text_passthrough,
        )
        usage = usage_to_dict(getattr(response, "usage", None))
        self.call_trace.append(
            {
                "transport": "chat_completions",
                "operation": operation_name or "unknown",
                "response_id": getattr(response, "id", None),
                "used_previous_response_id": False,
                "previous_response_id_unsupported": bool(previous_response_id),
                "session_cache_enabled": False,
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
            fallback_source=fallback_source,
            raw_text=_coerce_content_text(content),
        )


def build_json_transport(
    *,
    style: TransportStyle,
    client: OpenAI,
    model: str,
    timeout_seconds: float,
    use_session_cache: bool,
    temperature: float,
    enable_thinking: bool,
    provider_failed_code: str,
    invalid_response_code: str,
    invalid_json_code: str,
    error_factory: ErrorFactory,
    call_trace: list[dict[str, Any]],
) -> JSONTransport:
    if style == "chat_completions":
        del use_session_cache
        del enable_thinking
        return ChatCompletionsJSONTransport(
            client=client,
            model=model,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            provider_failed_code=provider_failed_code,
            invalid_response_code=invalid_response_code,
            invalid_json_code=invalid_json_code,
            error_factory=error_factory,
            call_trace=call_trace,
        )
    return ResponsesJSONTransport(
        client=client,
        model=model,
        timeout_seconds=timeout_seconds,
        use_session_cache=use_session_cache,
        temperature=temperature,
        enable_thinking=enable_thinking,
        provider_failed_code=provider_failed_code,
        invalid_response_code=invalid_response_code,
        invalid_json_code=invalid_json_code,
        error_factory=error_factory,
        call_trace=call_trace,
    )
