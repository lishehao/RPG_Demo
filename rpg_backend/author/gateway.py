from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rpg_backend.config import Settings, get_settings
from rpg_backend.responses_transport import (
    ResponsesJSONResponse as GatewayJSONResponse,
    ResponsesJSONTransport,
    StructuredResponse,
    build_openai_client,
)


class AuthorGatewayError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class AuthorLLMGateway:
    client: Any
    model: str
    timeout_seconds: float
    max_output_tokens_overview: int | None
    max_output_tokens_beat_plan: int | None
    max_output_tokens_beat_skeleton: int | None
    max_output_tokens_beat_repair: int | None
    max_output_tokens_rulepack: int | None
    use_session_cache: bool = False
    call_trace: list[dict[str, Any]] = field(default_factory=list, repr=False, compare=False)
    _transport: ResponsesJSONTransport = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_transport",
            ResponsesJSONTransport(
                client=self.client,
                model=self.model,
                timeout_seconds=self.timeout_seconds,
                use_session_cache=self.use_session_cache,
                temperature=0.2,
                enable_thinking=False,
                provider_failed_code="llm_provider_failed",
                invalid_response_code="llm_invalid_response",
                invalid_json_code="llm_invalid_json",
                error_factory=self._error_factory,
                call_trace=self.call_trace,
            ),
        )

    @staticmethod
    def _error_factory(code: str, message: str, status_code: int) -> AuthorGatewayError:
        return AuthorGatewayError(
            code=code,
            message=message,
            status_code=status_code,
        )

    def _invoke_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_output_tokens: int | None,
        previous_response_id: str | None = None,
        operation_name: str | None = None,
    ) -> GatewayJSONResponse:
        return self._transport.invoke_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            operation_name=operation_name,
        )


def get_author_llm_gateway(settings: Settings | None = None) -> AuthorLLMGateway:
    resolved = settings or get_settings()
    base_url = (resolved.responses_base_url or "").strip()
    api_key = (resolved.responses_api_key or "").strip()
    model = (resolved.responses_model or "").strip()
    if not base_url or not api_key or not model:
        raise AuthorGatewayError(
            code="llm_config_missing",
            message="APP_RESPONSES_BASE_URL, APP_RESPONSES_API_KEY, and APP_RESPONSES_MODEL are required",
            status_code=500,
        )
    use_session_cache = resolved.responses_use_session_cache
    if use_session_cache is None:
        use_session_cache = "dashscope" in base_url.casefold()
    client = build_openai_client(
        base_url=base_url,
        api_key=api_key,
        use_session_cache=bool(use_session_cache),
        session_cache_header=resolved.responses_session_cache_header,
        session_cache_value=resolved.responses_session_cache_value,
    )
    return AuthorLLMGateway(
        client=client,
        model=model,
        timeout_seconds=float(resolved.responses_timeout_seconds),
        max_output_tokens_overview=resolved.responses_max_output_tokens_author_overview,
        max_output_tokens_beat_plan=resolved.responses_max_output_tokens_author_beat_plan,
        max_output_tokens_beat_skeleton=resolved.responses_max_output_tokens_author_beat_skeleton,
        max_output_tokens_beat_repair=resolved.responses_max_output_tokens_author_beat_repair,
        max_output_tokens_rulepack=resolved.responses_max_output_tokens_author_rulepack,
        use_session_cache=bool(use_session_cache),
    )
