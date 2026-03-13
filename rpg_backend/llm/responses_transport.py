from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from rpg_backend.llm.base import LLMProviderConfigError
from rpg_backend.llm.response_parsing import ParsedResponseUsage, parse_responses_payload

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover - dependency availability handled at runtime
    AsyncOpenAI = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ResponsesTransportResult:
    response_id: str | None
    output_text: str
    reasoning_summary: str | None
    usage: ParsedResponseUsage
    duration_ms: int
    raw_payload: dict[str, Any]


@dataclass
class ResponsesTransportError(RuntimeError):
    error_code: str
    message: str
    retryable: bool = True

    def __post_init__(self) -> None:
        super().__init__(self.message)


class ResponsesTransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        if AsyncOpenAI is None:
            raise LLMProviderConfigError("missing dependency 'openai'; install project dependencies")

        normalized_base_url = (base_url or "").strip()
        normalized_api_key = (api_key or "").strip()
        normalized_model = (model or "").strip()

        if not normalized_base_url:
            raise LLMProviderConfigError("responses transport misconfigured: APP_RESPONSES_BASE_URL is required")
        if not normalized_api_key:
            raise LLMProviderConfigError("responses transport misconfigured: APP_RESPONSES_API_KEY is required")
        if not normalized_model:
            raise LLMProviderConfigError("responses transport misconfigured: APP_RESPONSES_MODEL is required")

        self.base_url = normalized_base_url
        self.api_key = normalized_api_key
        self.default_model = normalized_model
        self.default_timeout_seconds = float(timeout_seconds)
        self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    async def create(
        self,
        *,
        model: str | None,
        input: list[dict[str, Any]],
        previous_response_id: str | None = None,
        timeout: float | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> ResponsesTransportResult:
        selected_model = (model or "").strip() or self.default_model
        if not selected_model:
            raise ResponsesTransportError(
                error_code="responses_model_missing",
                message="responses call missing model",
                retryable=False,
            )

        started_at = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": selected_model,
            "input": input,
            "timeout": float(timeout or self.default_timeout_seconds),
        }
        if previous_response_id:
            kwargs["previous_response_id"] = str(previous_response_id)
        if extra_body:
            kwargs["extra_body"] = dict(extra_body)

        try:
            response = await self._client.responses.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise ResponsesTransportError(
                error_code="responses_request_failed",
                message=str(exc),
                retryable=True,
            ) from exc

        parsed = parse_responses_payload(response)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        return ResponsesTransportResult(
            response_id=parsed.response_id,
            output_text=parsed.output_text,
            reasoning_summary=parsed.reasoning_summary,
            usage=parsed.usage,
            duration_ms=duration_ms,
            raw_payload=parsed.raw_payload,
        )
