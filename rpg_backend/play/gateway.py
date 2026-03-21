from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rpg_backend.config import Settings, get_settings
from rpg_backend.responses_transport import (
    ResponsesJSONResponse as PlayGatewayJSONResponse,
    ResponsesJSONTransport,
    build_openai_client,
)


class PlayGatewayError(RuntimeError):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class PlayLLMGateway:
    client: Any
    model: str
    timeout_seconds: float
    max_output_tokens_interpret: int | None
    max_output_tokens_interpret_repair: int | None
    max_output_tokens_ending_judge: int | None
    max_output_tokens_ending_judge_repair: int | None
    max_output_tokens_pyrrhic_critic: int | None
    max_output_tokens_render: int | None
    max_output_tokens_render_repair: int | None
    use_session_cache: bool = False
    enable_thinking: bool = False
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
                temperature=0.4,
                enable_thinking=self.enable_thinking,
                provider_failed_code="play_llm_provider_failed",
                invalid_response_code="play_llm_invalid_response",
                invalid_json_code="play_llm_invalid_json",
                error_factory=self._error_factory,
                call_trace=self.call_trace,
            ),
        )

    @staticmethod
    def _error_factory(code: str, message: str, status_code: int) -> PlayGatewayError:
        return PlayGatewayError(
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
        plaintext_fallback_key: str | None = None,
    ) -> PlayGatewayJSONResponse:
        return self._transport.invoke_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            operation_name=operation_name,
            plaintext_fallback_key=plaintext_fallback_key,
        )


def get_play_llm_gateway(settings: Settings | None = None) -> PlayLLMGateway:
    resolved = settings or get_settings()
    base_url = (resolved.responses_base_url or "").strip()
    api_key = (resolved.responses_api_key or "").strip()
    model = (resolved.responses_model or "").strip()
    if not base_url or not api_key or not model:
        raise PlayGatewayError(
            code="play_llm_config_missing",
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
    return PlayLLMGateway(
        client=client,
        model=model,
        timeout_seconds=float(resolved.responses_timeout_seconds),
        max_output_tokens_interpret=resolved.responses_max_output_tokens_play_interpret,
        max_output_tokens_interpret_repair=resolved.responses_max_output_tokens_play_interpret_repair,
        max_output_tokens_ending_judge=resolved.responses_max_output_tokens_play_ending_judge,
        max_output_tokens_ending_judge_repair=resolved.responses_max_output_tokens_play_ending_judge_repair,
        max_output_tokens_pyrrhic_critic=resolved.responses_max_output_tokens_play_pyrrhic_critic,
        max_output_tokens_render=resolved.responses_max_output_tokens_play_render,
        max_output_tokens_render_repair=resolved.responses_max_output_tokens_play_render_repair,
        use_session_cache=bool(use_session_cache),
        enable_thinking=bool(resolved.responses_enable_thinking_play),
    )
